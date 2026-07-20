"""
app/services/qdrant.py

Qdrant 클라이언트 / 임베딩 모델 싱글톤 헬퍼.

로컬 파일 모드(QdrantClient(path=...))는 저장 디렉터리에 파일 락을 걸기 때문에,
같은 프로세스에서 인스턴스를 여러 번 생성하면 "already accessed by another instance"
락 충돌이 발생한다. 여러 MCP 툴이 asyncio.to_thread 로 동시에 첫 호출을 하더라도
인스턴스가 단 하나만 생성되도록, 생성 구간을 Lock 으로 직렬화한다(double-checked locking).
bge-m3 임베딩 모델도 호출마다 재로드하지 않도록 동일하게 캐싱한다.

접속 모드:
- QDRANT_URL(서버 모드) — 운영 권장. docker-compose 의 qdrant 서비스(6333)에 접속하며,
  서버가 동시 접근을 처리하므로 여러 워커/스레드의 동시 검색에 안전하다.
- QDRANT_PATH(로컬 파일 모드) — 별도 서버 없이 로컬 개발용. 파일 락 특성상 단일 프로세스
  전용이며, 아래 싱글톤으로 인스턴스 생성 경합은 막지만 임베디드 엔진 자체는 동시 검색에
  안전하지 않으므로 단일 워커 로컬 개발 환경에서만 사용한다.
QDRANT_PATH 가 설정돼 있으면 파일 모드, 비어 있으면 서버 모드로 접속한다.
"""

from __future__ import annotations

import threading

from app import config

_embeddings = None
_embeddings_lock = threading.Lock()

_qdrant_client = None
_qdrant_lock = threading.Lock()


def get_embeddings():
    """bge-m3 임베딩 모델 싱글톤."""
    global _embeddings
    if _embeddings is None:
        with _embeddings_lock:
            if _embeddings is None:  # 락 획득 전에 다른 스레드가 이미 생성했는지 재확인
                from langchain_huggingface import HuggingFaceEmbeddings

                _embeddings = HuggingFaceEmbeddings(model_name=config.EMBED_MODEL_NAME)
    return _embeddings


def get_qdrant_client():
    """프로세스 내 싱글톤 QdrantClient. QDRANT_PATH 설정 시 로컬 파일 모드."""
    global _qdrant_client
    if _qdrant_client is None:
        with _qdrant_lock:
            if _qdrant_client is None:  # double-checked locking: 이중 생성(=락 충돌) 방지
                from qdrant_client import QdrantClient

                if config.QDRANT_PATH:
                    _qdrant_client = QdrantClient(path=config.QDRANT_PATH)
                else:
                    _qdrant_client = QdrantClient(url=config.QDRANT_URL)
    return _qdrant_client
