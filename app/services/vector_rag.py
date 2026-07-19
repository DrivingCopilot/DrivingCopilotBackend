"""
app/services/vector_rag.py

Vector RAG: Qdrant `vehicle_manuals` 컬렉션에서 차량 매뉴얼 청크를 의미 검색한다.
(DrivingCopilotGraph의 인덱싱 파이프라인이 적재한 컬렉션을 읽기 측에서 사용)

무거운 의존성(임베딩 모델, qdrant, 리랭커)은 함수 내부 lazy import + graceful degradation.
Qdrant/임베딩/리랭커가 없으면 명확한 오류 문자열을 반환하거나 해당 단계를 건너뛰고,
서버는 계속 동작한다.
"""

import asyncio
import logging

from app import config

logger = logging.getLogger(__name__)

_reranker = None  # 모듈 레벨 싱글톤 (CrossEncoder 로드 비용 절감). False = 로드 시도 후 실패.


def _run_vector_search(query: str) -> list:
    """1차 Vector 검색. 리랭커 투입 전 후보 chunk(Document) 리스트를 반환한다."""
    from langchain_qdrant import QdrantVectorStore
    from qdrant_client.http import models

    from app.services.qdrant import get_embeddings, get_qdrant_client

    embeddings = get_embeddings()
    client = get_qdrant_client()
    vectorstore = QdrantVectorStore(
        client=client,
        collection_name=config.COLLECTION_NAME,
        embedding=embeddings,
    )

    # few-shot 예시는 제외하고 실제 매뉴얼 청크만 검색
    search_filter = models.Filter(
        must_not=[
            models.FieldCondition(
                key="metadata.source",
                match=models.MatchValue(value="few_shots_examples"),
            )
        ]
    )
    return vectorstore.similarity_search(
        query=query, k=config.VECTOR_SEARCH_CANDIDATE_K, filter=search_filter
    )


def _get_reranker():
    """bge-reranker-v2-m3 CrossEncoder 싱글톤. 로드 실패 시 None 반환(graceful degradation)."""
    global _reranker
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder
            _reranker = CrossEncoder(config.RERANKER_MODEL_NAME)
        except Exception:
            logger.exception("리랭커 모델 로드 실패 — 1차 검색 결과를 그대로 사용합니다.")
            _reranker = False
    return _reranker or None


def _rerank(query: str, docs: list) -> list:
    """1차 검색 후보를 질문-청크 쌍 재채점으로 재정렬한다. 리랭커 로드 실패 시 원본 순서 그대로 반환."""
    if not docs:
        return docs

    reranker = _get_reranker()
    if reranker is None:
        return docs

    pairs = [(query, doc.page_content) for doc in docs]
    scores = reranker.predict(pairs)
    ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
    return [doc for doc, _ in ranked]


def _format_docs(docs: list) -> str:
    """chunk(Document) 리스트를 MCP 툴 반환용 문자열로 포맷팅한다. (최종 단계)"""
    if not docs:
        return "관련 매뉴얼 내용을 찾지 못했습니다."
    return "\n\n".join(
        f"[{i}] {doc.page_content}" for i, doc in enumerate(docs, 1)
    )


async def vector_search(query: str) -> str:
    """MCP 툴 진입점. 블로킹 검색+리랭킹을 스레드로 오프로딩한다."""
    try:
        docs = await asyncio.to_thread(_run_vector_search, query)
        docs = await asyncio.to_thread(_rerank, query, docs)
        docs = docs[: config.VECTOR_SEARCH_K]
        return _format_docs(docs)
    except Exception as e:
        logger.exception("vector_rag_search 실패")
        return f"vector_rag_search 처리 중 오류: {e}"