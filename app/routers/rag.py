# app/routers/rag.py
#
# RAG 관련 엔드포인트.
#   POST /rag/route   — Query Router (키워드 규칙 1차 + TF-IDF 2차)
#   POST /rag/search  — 벡터 검색 stub (2주차 Qdrant 연동 예정)
#   POST /rag/graph   — Graph RAG stub (4~5주차 Neo4j 연동 예정)
#   POST /rag/sql     — Text2SQL stub (6~7주차 SQLite 연동 예정)
#   POST /rag/evaluate — 평가 파이프라인 stub (9~10주차 예정)

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.query_router import classify_query

router = APIRouter()


# ── 요청 / 응답 스키마 ─────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str


class RouteRequest(BaseModel):
    query: str
    has_image: bool = False


class RouteResponse(BaseModel):
    query: str
    route_type: str
    confidence: float
    method: str


class GraphRequest(BaseModel):
    query: str
    entities: list[str] = []


class SqlRequest(BaseModel):
    query: str


# ── 엔드포인트 ──────────────────────────────────────────────────────────────

@router.post("/route", response_model=RouteResponse)
def rag_route(req: RouteRequest) -> RouteResponse:
    """
    Query Router — 발화를 5가지 타입으로 분류한다.

    분류 결과:
        rag     : 매뉴얼·도메인 지식 검색
        tool    : 차량 제어 명령 (MCP Tool 12종)
        sql     : 주행 이력 데이터 조회
        vision  : 이미지·카메라 분석
        chat    : 일반 대화 (폴백)

    반환:
        route_type : 분류 결과
        confidence : 신뢰도 (0.0 ~ 1.0)
        method     : 분류 방법 (rule | keyword | tfidf | tfidf_fallback)
    """
    result = classify_query(req.query, req.has_image)
    return RouteResponse(query=req.query, **result)


@router.post("/search")
def rag_search(req: SearchRequest):
    """벡터 검색 stub — 2주차에 Qdrant 연동 예정."""
    return {
        "query": req.query,
        "chunks": [],
        "scores": [],
        "message": "RAG search stub - Qdrant 연동 예정",
    }


@router.post("/graph")
def rag_graph(req: GraphRequest):
    """Graph RAG stub — 4~5주차에 Neo4j 연동 예정."""
    return {
        "query": req.query,
        "nodes": [],
        "edges": [],
        "context": "",
        "message": "Graph RAG stub - Neo4j 연동 예정",
    }


@router.post("/sql")
def rag_sql(req: SqlRequest):
    """Text2SQL stub — 6~7주차에 SQLite 연동 예정."""
    return {
        "query": req.query,
        "sql": "",
        "result": [],
        "answer": "",
        "message": "Text2SQL stub - SQLite 연동 예정",
    }


@router.post("/evaluate")
def rag_evaluate(test_set_id: str):
    """평가 파이프라인 stub — 9~10주차에 Gold Set 연동 예정."""
    return {
        "metrics": {},
        "details": [],
        "message": "Evaluate stub - Gold Set 구축 예정",
    }
