"""
app/config.py

Knowledge Tool(text2sql 등)에서 공유하는 설정 상수.
환경변수로 덮어쓸 수 있으며, 미설정 시 로컬 개발 기본값을 사용한다.
"""

import os

# ---------------------------------------------------------------------------
# LLM (OpenAI 호환 엔드포인트 — 로컬 vLLM/Qwen2-VL 등)
# ---------------------------------------------------------------------------
# 로컬 vLLM 사용 시: OPENAI_BASE_URL=http://localhost:8000/v1, OPENAI_API_KEY=dummy
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2-vl-1.5b-instruct-int4")
LLM_BASE_URL = os.getenv("OPENAI_BASE_URL")           # None이면 실제 OpenAI API 사용
LLM_API_KEY = os.getenv("OPENAI_API_KEY", "not-needed")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))

# Self-Consistency: 생성할 SQL 후보 개수 (다수결 투표)
SC_NUM_SAMPLES = int(os.getenv("SC_NUM_SAMPLES", "5"))

# ---------------------------------------------------------------------------
# Qdrant (Text2SQL few-shot 예시 검색용)
# ---------------------------------------------------------------------------
# 접속 모드는 app/services/qdrant.py 의 싱글톤 헬퍼가 결정한다.
# QDRANT_PATH가 설정되면 로컬 파일 모드(별도 서버 불필요, 단일 워커 로컬 개발용),
# 비어 있으면 QDRANT_URL(서버 모드, 동시 접근 안전 — 운영 권장)로 접속한다.
QDRANT_PATH = os.getenv("QDRANT_PATH", "")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "vehicle_manuals")
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "BAAI/bge-m3")
FEW_SHOT_K = int(os.getenv("FEW_SHOT_K", "3"))
VECTOR_SEARCH_K = int(os.getenv("VECTOR_SEARCH_K", "5"))  # 최종 반환 개수 (reranker 이후)
VECTOR_SEARCH_CANDIDATE_K = int(os.getenv("VECTOR_SEARCH_CANDIDATE_K", "20"))  # reranker 투입 전 1차 후보 개수
RERANKER_MODEL_NAME = os.getenv("RERANKER_MODEL_NAME", "BAAI/bge-reranker-v2-m3")

# ---------------------------------------------------------------------------
# Neo4j (Graph RAG)
# ---------------------------------------------------------------------------
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
GRAPH_MAX_RESULTS = int(os.getenv("GRAPH_MAX_RESULTS", "50"))  # graph_rag_search 결과 상한
