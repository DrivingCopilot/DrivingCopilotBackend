"""
app/services/qdrant.py

Qdrant 클라이언트 / 임베딩 모델 싱글톤 헬퍼.

로컬 파일 모드(QdrantClient(path=...))는 저장 디렉터리에 파일 락을 걸기 때문에,
같은 프로세스에서 인스턴스를 여러 번 생성하면 "already accessed by another instance"
락 충돌이 발생한다. lru_cache로 프로세스 내 단일 인스턴스만 유지한다.
bge-m3 임베딩 모델도 호출마다 재로드하지 않도록 캐싱한다.

QDRANT_PATH가 설정돼 있으면 파일 모드, 아니면 QDRANT_URL(서버 모드)로 접속한다.
"""

from __future__ import annotations

from functools import lru_cache

from app import config


@lru_cache(maxsize=1)
def get_embeddings():
    """bge-m3 임베딩 모델 싱글톤."""
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(model_name=config.EMBED_MODEL_NAME)


@lru_cache(maxsize=1)
def get_qdrant_client():
    """프로세스 내 싱글톤 QdrantClient. QDRANT_PATH 설정 시 로컬 파일 모드."""
    from qdrant_client import QdrantClient

    if config.QDRANT_PATH:
        return QdrantClient(path=config.QDRANT_PATH)
    return QdrantClient(url=config.QDRANT_URL)
