# app/services/query_router.py
#
# Query Router 2단계 분류 파이프라인
#   1단계: 키워드 규칙 — 명확한 발화는 바로 확정 (confidence=1.0)
#   2단계: TF-IDF 분류기 — 키워드 미매칭 시 통계적 분류
#   폴백  : 신뢰도 임계값 미달이면 "chat" 반환
#
# 외부 호출:
#   from app.services.query_router import classify_query
#   result = classify_query("에어컨 켜줘")
#   # → {"route_type": "tool", "confidence": 1.0, "method": "keyword"}

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

logger = logging.getLogger(__name__)

RouteType = Literal["rag", "tool", "sql", "vision", "chat"]

# 신뢰도 임계값: 이 값 미만이면 chat 폴백
# 4분류 random baseline = 0.25; mini dataset(~80건) 학습 시 0.40이 적정.
# Gold Set 200건 이상 확보 후 0.60~0.70으로 상향 예정.
CONFIDENCE_THRESHOLD: float = 0.40


# ── 1단계: 키워드 규칙 ─────────────────────────────────────────────────────

_KEYWORD_RULES: dict[str, list[str]] = {
    # 명령형 어미를 포함한 패턴으로 한정 — "켜진", "꺼진" 같은 상태 표현과 혼동 방지
    "tool": [
        "켜줘", "켜줄", "꺼줘", "꺼줄",
        "열어줘", "열어줄", "닫아줘", "닫아줄",
        "올려줘", "올려줄", "내려줘", "내려줄",
        "설정해줘", "설정해줄", "조절해줘", "조절해줄",
        "맞춰줘", "맞춰줄", "바꿔줘", "바꿔줄",
        "틀어줘", "틀어줄", "연결해줘", "연결해줄",
        "작동시켜", "해제해줘", "해제해줄", "넘겨줘",
    ],
    "sql": [
        "얼마나", "몇 킬로", "몇 번", "몇 시간", "몇 리터",
        "총 주행", "총 거리", "평균 연비", "평균 속도", "평균 주행",
        "기록 보여", "통계", "이번달", "지난달", "이번 주",
    ],
    "rag": [
        "뭐야", "무엇", "어떻게", "왜", "경고등", "매뉴얼",
        "설명해줘", "알려줘", "의미", "뜻", "방법", "주기", "주의사항",
    ],
}


def _keyword_route(query: str) -> RouteType | None:
    """1단계: 키워드 규칙 매칭. 해당 없으면 None 반환."""
    q = query.lower()
    for route, keywords in _KEYWORD_RULES.items():
        if any(k in q for k in keywords):
            return route  # type: ignore[return-value]
    return None


# ── 학습 데이터 (mini Gold Set — 4분류 × ~20건) ────────────────────────────

_TRAIN_DATA: list[tuple[str, str]] = [
    # tool
    ("에어컨 온도 좀 낮춰줄 수 있어", "tool"),
    ("실내가 너무 더운데 시원하게 해줘", "tool"),
    ("음악 소리가 너무 크다", "tool"),
    ("뒷유리 김 서려 있어", "tool"),
    ("내비 목적지 집으로 해줘", "tool"),
    ("블루투스 스피커 연결 좀", "tool"),
    ("사이드미러 접어줘", "tool"),
    ("차 좀 시동 걸어줘", "tool"),
    ("어시스트 모드 활성화해줘", "tool"),
    ("스포츠 모드로 전환해줘", "tool"),
    ("실내등 좀 켜줄래", "tool"),
    ("앞 유리 성에 제거해줘", "tool"),
    ("주차 브레이크 잠가줘", "tool"),
    ("통풍 시트 활성화해줘", "tool"),
    ("트렁크 좀 열어줄 수 있어", "tool"),
    ("음악 볼륨 좀 높여줘", "tool"),
    ("다음 곡 재생해줘", "tool"),
    ("와이퍼 속도 올려줘", "tool"),
    ("실내 온도 23도로 해줘", "tool"),
    ("에코 모드로 바꿔줘", "tool"),
    # rag
    ("엔진 경고등이 왜 켜진 거야", "rag"),
    ("브레이크 패드 얼마나 됐을 때 교체해야 해", "rag"),
    ("타이어 공기압 적정 수치가 얼마야", "rag"),
    ("오일 교환 시기가 어떻게 돼", "rag"),
    ("ABS가 정확히 어떤 기능이야", "rag"),
    ("ESC 경고등 켜지면 어떻게 해야 해", "rag"),
    ("배터리 방전됐을 때 대처법 알려줘", "rag"),
    ("냉각수 어디서 보충해", "rag"),
    ("트랙션 컨트롤이 뭐야", "rag"),
    ("겨울에 눈길 주행할 때 주의할 점 있어", "rag"),
    ("와이퍼 블레이드 교체 방법 알려줘", "rag"),
    ("타이어 마모 한계가 얼마야", "rag"),
    ("연료 경고등 켜지면 얼마나 더 달릴 수 있어", "rag"),
    ("에어백 작동 조건이 어떻게 돼", "rag"),
    ("선루프 끼임 방지 기능이 있어", "rag"),
    ("핸들 떨리는 이유가 뭐야", "rag"),
    ("자동 주차 기능 어떻게 쓰는 거야", "rag"),
    ("블라인드 스팟 경고가 어떤 원리야", "rag"),
    ("TPMS 경고등 의미가 뭐야", "rag"),
    ("디퍼런셜 잠금이 뭐야", "rag"),
    # sql
    ("이번 달 연비가 어느 정도야", "sql"),
    ("지금까지 총 주행 거리가 얼마야", "sql"),
    ("지난 주 평균 속도 알 수 있어", "sql"),
    ("급브레이크 사용 횟수 확인하고 싶어", "sql"),
    ("오늘 연료 소모량이 얼마야", "sql"),
    ("이번 주 총 운전 시간이 얼마야", "sql"),
    ("최고 속도 기록이 어떻게 돼", "sql"),
    ("최근 한 달 평균 연비 보여줘", "sql"),
    ("지난달 주행 거리 데이터 줘", "sql"),
    ("급가속한 횟수 알고 싶어", "sql"),
    ("오늘 운행한 거리가 얼마야", "sql"),
    ("이번 달 주유 횟수 알 수 있어", "sql"),
    ("최근 경고등 발생 이력 보여줘", "sql"),
    ("올해 총 주행 거리 통계 줘", "sql"),
    ("평균 주차 시간이 얼마야", "sql"),
    ("요즘 연비가 좀 떨어진 것 같은데 데이터 보여줘", "sql"),
    ("지난 주에 속도위반 경고 몇 번 났어", "sql"),
    ("이번 달 운행 패턴 분석해줘", "sql"),
    ("배터리 잔량 변화 추이 보여줘", "sql"),
    ("최근 30일 주행 요약 데이터 줘", "sql"),
    # chat
    ("안녕하세요", "chat"),
    ("고맙습니다", "chat"),
    ("잘 부탁드려요", "chat"),
    ("오늘 날씨 어때", "chat"),
    ("운전할 때 좋은 팁 있어", "chat"),
    ("심심한데 얘기 좀 해줘", "chat"),
    ("음악 좀 추천해줄래", "chat"),
    ("배가 고프네", "chat"),
    ("요즘 피곤해", "chat"),
    ("졸리다", "chat"),
    ("농담 한 개 해줘", "chat"),
    ("드라이브하기 좋은 날씨야", "chat"),
    ("오늘 기분이 별로야", "chat"),
    ("목이 말라", "chat"),
    ("여행 코스 추천해줄래", "chat"),
    ("우리 얼마나 더 가야 해", "chat"),
    ("오늘 약속 있는데 늦겠다", "chat"),
    ("커피 한 잔 마시고 싶다", "chat"),
    ("주변에 맛집 있어", "chat"),
    ("잠깐 쉬어가도 될 것 같아", "chat"),
]


# ── 2단계: TF-IDF 분류기 ──────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _build_classifier() -> Pipeline:
    """
    TF-IDF + LogisticRegression 파이프라인을 학습하고 캐시.
    앱 시작 후 첫 호출 시 1회 학습, 이후 캐시된 모델 재사용.
    """
    texts, labels = zip(*_TRAIN_DATA)
    pipeline = Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                analyzer="char",        # 한국어: 형태소 분석 없이 char n-gram
                ngram_range=(2, 4),     # 2~4글자 단위 패턴 학습
                min_df=1,
                sublinear_tf=True,
            ),
        ),
        (
            "clf",
            # multi_class는 scikit-learn 1.6에서 제거됨 — lbfgs는 기본적으로 multinomial
            LogisticRegression(
                max_iter=1000,
                C=1.0,
                solver="lbfgs",
            ),
        ),
    ])
    pipeline.fit(list(texts), list(labels))
    logger.info("TF-IDF 분류기 학습 완료: %d개 샘플", len(texts))
    return pipeline


# ── Reranker Stub ──────────────────────────────────────────────────────────

def _reranker_stub(
    query: str,
    route_type: str,
    score: float,
) -> tuple[str, float]:
    """
    bge-reranker-v2-m3 자리 예약.
    통합 단계에서 실제 모델로 교체 예정.
    현재는 입력값 그대로 반환 (no-op).

    TODO:
        from app.services.reranker import bge_reranker
        return bge_reranker(query, route_type, score)
    """
    return route_type, score


# ── 메인 공개 함수 ─────────────────────────────────────────────────────────

def classify_query(query: str, has_image: bool = False) -> dict:
    """
    2단계 Query Router.

    Args:
        query     : 사용자 발화 텍스트
        has_image : 이미지 첨부 여부 (True면 "vision" 확정)

    Returns:
        {
            "route_type" : "rag" | "tool" | "sql" | "vision" | "chat",
            "confidence" : float (0.0 ~ 1.0),
            "method"     : "rule" | "keyword" | "tfidf" | "tfidf_fallback",
        }
    """
    # 0. vision 우선 처리 — 이미지 있으면 텍스트 분류 건너뜀
    if has_image:
        return {"route_type": "vision", "confidence": 1.0, "method": "rule"}

    # 1단계: 키워드 규칙
    keyword_result = _keyword_route(query)
    if keyword_result is not None:
        return {"route_type": keyword_result, "confidence": 1.0, "method": "keyword"}

    # 2단계: TF-IDF 분류기
    clf = _build_classifier()
    proba: np.ndarray = clf.predict_proba([query])[0]
    classes: np.ndarray = clf.classes_

    best_idx = int(np.argmax(proba))
    best_route: str = classes[best_idx]
    best_score: float = float(proba[best_idx])

    # Reranker (현재 no-op stub)
    best_route, best_score = _reranker_stub(query, best_route, best_score)

    # 신뢰도 임계값 미달 → chat 폴백
    if best_score < CONFIDENCE_THRESHOLD:
        return {
            "route_type": "chat",
            "confidence": best_score,
            "method": "tfidf_fallback",
        }

    return {"route_type": best_route, "confidence": best_score, "method": "tfidf"}


def warmup() -> None:
    """앱 시작 시 TF-IDF 모델을 미리 학습해 첫 요청 지연을 방지."""
    _build_classifier()
    logger.info("Query Router warmup 완료")
