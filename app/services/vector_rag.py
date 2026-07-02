"""
app/services/vector_rag.py

Vector RAG: Qdrant `vehicle_manuals` 컬렉션에서 차량 매뉴얼 청크를 의미 검색한다.
(DrivingCopilotGraph의 인덱싱 파이프라인이 적재한 컬렉션을 읽기 측에서 사용)

무거운 의존성(임베딩 모델, qdrant)은 함수 내부 lazy import + graceful degradation.
Qdrant/임베딩이 없으면 명확한 오류 문자열을 반환하고 서버는 계속 동작한다.
"""

import asyncio
import logging

from app import config

logger = logging.getLogger(__name__)


def _run_vector_search(query: str) -> str:
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
        from langchain_qdrant import QdrantVectorStore
        from qdrant_client import QdrantClient
        from qdrant_client.http import models

        embeddings = HuggingFaceEmbeddings(model_name=config.EMBED_MODEL_NAME)
        client = QdrantClient(url=config.QDRANT_URL)
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
        docs = vectorstore.similarity_search(
            query=query, k=config.VECTOR_SEARCH_K, filter=search_filter
        )
        if not docs:
            return "관련 매뉴얼 내용을 찾지 못했습니다."

        return "\n\n".join(
            f"[{i}] {doc.page_content}" for i, doc in enumerate(docs, 1)
        )
    except Exception as e:
        logger.exception("vector_rag_search 실패")
        return f"vector_rag_search 처리 중 오류: {e}"


async def vector_search(query: str) -> str:
    """MCP 툴 진입점. 블로킹 검색을 스레드로 오프로딩한다."""
    return await asyncio.to_thread(_run_vector_search, query)
