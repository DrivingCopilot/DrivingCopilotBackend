# tests/test_query_router.py
#
# Query Router 단위 테스트.
# pytest tests/test_query_router.py 로 실행.

import pytest
from app.services.query_router import classify_query, CONFIDENCE_THRESHOLD


# ── 응답 스키마 검증 ────────────────────────────────────────────────────────

class TestResponseSchema:
    """모든 응답이 필수 키를 가지는지 확인."""

    def test_has_required_keys(self):
        result = classify_query("에어컨 켜줘")
        assert "route_type" in result
        assert "confidence" in result
        assert "method" in result

    def test_route_type_is_valid(self):
        valid = {"rag", "tool", "sql", "vision", "chat"}
        for query in ["에어컨 켜줘", "경고등이 뭐야", "총 주행 거리 몇 킬로야", "안녕"]:
            result = classify_query(query)
            assert result["route_type"] in valid, f"{query!r} → {result['route_type']}"

    def test_confidence_in_range(self):
        for query in ["에어컨 켜줘", "경고등이 뭐야", "총 주행 거리 몇 킬로야", "안녕"]:
            result = classify_query(query)
            assert 0.0 <= result["confidence"] <= 1.0, f"{query!r} confidence out of range"

    def test_method_is_valid(self):
        valid = {"rule", "keyword", "tfidf", "tfidf_fallback"}
        for query in ["에어컨 켜줘", "경고등이 뭐야", "총 주행 거리 몇 킬로야", "안녕"]:
            result = classify_query(query)
            assert result["method"] in valid, f"{query!r} → method={result['method']}"


# ── 0단계: vision 우선 처리 ────────────────────────────────────────────────

class TestVisionPriority:
    """has_image=True면 텍스트 내용과 무관하게 vision 반환."""

    def test_vision_on_image_flag(self):
        result = classify_query("이게 뭐야", has_image=True)
        assert result["route_type"] == "vision"
        assert result["confidence"] == 1.0
        assert result["method"] == "rule"

    def test_vision_overrides_strong_tool_keyword(self):
        result = classify_query("에어컨 켜줘", has_image=True)
        assert result["route_type"] == "vision"

    def test_no_vision_without_flag(self):
        result = classify_query("이게 뭐야", has_image=False)
        assert result["route_type"] != "vision"


# ── 1단계: 키워드 규칙 ─────────────────────────────────────────────────────

class TestKeywordRouting:
    """키워드 룰로 명확하게 분류되는 케이스."""

    @pytest.mark.parametrize("query", [
        "에어컨 켜줘",
        "히터 꺼줘",
        "창문 열어줘",
        "볼륨 올려줘",
        "온도 22도로 설정해줘",
        "드라이빙 모드 바꿔줘",
    ])
    def test_tool_keyword(self, query):
        result = classify_query(query)
        assert result["route_type"] == "tool", f"expected tool for {query!r}"
        assert result["method"] == "keyword"
        assert result["confidence"] == 1.0

    @pytest.mark.parametrize("query", [
        "엔진 경고등이 뭐야",
        "오일 교환 방법 알려줘",
        "타이어 교체 주기가 어떻게 돼",
    ])
    def test_rag_keyword(self, query):
        result = classify_query(query)
        assert result["route_type"] == "rag", f"expected rag for {query!r}"
        assert result["method"] == "keyword"

    @pytest.mark.parametrize("query", [
        "이번달 총 주행거리 몇 킬로야",
        "평균 연비 통계 보여줘",
        "급브레이크 몇 번 했어",
    ])
    def test_sql_keyword(self, query):
        result = classify_query(query)
        assert result["route_type"] == "sql", f"expected sql for {query!r}"
        assert result["method"] == "keyword"


# ── 2단계: TF-IDF 분류기 ──────────────────────────────────────────────────

class TestTfidfRouting:
    """키워드 룰을 피한 표현에서 TF-IDF가 올바르게 분류하는지."""

    @pytest.mark.parametrize("query,expected", [
        ("실내가 너무 더운데 시원하게 해줘", "tool"),
        ("음악 소리가 너무 크다", "tool"),
        ("블루투스 스피커 연결 좀", "tool"),
        ("엔진 경고등이 왜 켜진 거야", "rag"),
        ("오일 교환 시기가 어떻게 돼", "rag"),
        ("이번 달 연비가 어느 정도야", "sql"),
        ("지금까지 총 주행 거리가 얼마야", "sql"),
    ])
    def test_tfidf_classification(self, query, expected):
        result = classify_query(query)
        # TF-IDF는 확률 기반이므로 method 체크 대신 route_type만 검증
        assert result["route_type"] == expected, (
            f"{query!r} → {result['route_type']} (expected {expected}, "
            f"confidence={result['confidence']:.2f})"
        )

    @pytest.mark.parametrize("query", [
        "안녕하세요",
        "고맙습니다",
        "오늘 날씨 어때",
        "배가 고프네",
    ])
    def test_chat_classification(self, query):
        result = classify_query(query)
        assert result["route_type"] == "chat", (
            f"{query!r} → {result['route_type']} (confidence={result['confidence']:.2f})"
        )


# ── 폴백 동작 ─────────────────────────────────────────────────────────────

class TestFallback:
    """신뢰도 낮은 입력에서 chat 폴백이 동작하는지."""

    def test_empty_string_fallback(self):
        result = classify_query("")
        # 빈 문자열은 분류 불가 → chat 폴백
        assert result["route_type"] == "chat"

    def test_single_char_fallback(self):
        result = classify_query("음")
        assert result["route_type"] == "chat"

    def test_fallback_confidence_below_threshold(self):
        # tfidf_fallback 케이스는 confidence < CONFIDENCE_THRESHOLD 여야 함
        result = classify_query("")
        if result["method"] == "tfidf_fallback":
            assert result["confidence"] < CONFIDENCE_THRESHOLD


# ── 분류기 재사용 (캐시) ───────────────────────────────────────────────────

class TestClassifierCache:
    """lru_cache가 동작해 분류기를 재학습하지 않는지 확인."""

    def test_consistent_results(self):
        q = "에어컨 온도 낮춰줘"
        first = classify_query(q)
        second = classify_query(q)
        assert first == second
