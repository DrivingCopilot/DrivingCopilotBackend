from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class SearchRequest(BaseModel):
    query: str


class RouteRequest(BaseModel):
    query: str
    has_image: bool = False


class GraphRequest(BaseModel):
    query: str
    entities: list[str] = []


class SqlRequest(BaseModel):
    query: str

# 1주차: stub 응답 (2~3주차에 실제 구현)
@router.post("/search")
def rag_search(req: SearchRequest):
    """벡터 검색 - 2주차에 Qdrant 연동"""
    return {
        "chunks": [],
        "scores": [],
        "message": "RAG search stub - Qdrant 연동 예정"
    }


@router.post("/route")
def rag_route(req: RouteRequest):
    """쿼리 라우터 - 3주차에 분류기 구현"""
    # 임시: 키워드 기반 단순 분류
    query = req.query.lower()

    if req.has_image:
        route = "vision"
    elif any(k in query for k in ["켜", "꺼", "설정", "조절", "열어", "닫아"]):
        route = "tool"
    elif any(k in query for k in ["얼마나", "몇", "총", "평균", "기록"]):
        route = "sql"
    elif any(k in query for k in ["뭐야", "무엇", "어떻게", "왜", "경고등", "매뉴얼"]):
        route = "rag"
    else:
        route = "chat"

    return {"route_type": route, "query": req.query}


@router.post("/graph")
def rag_graph(req: GraphRequest):
    """Graph RAG - 4~5주차에 Neo4j 연동"""
    return {
        "nodes": [],
        "edges": [],
        "context": "",
        "message": "Graph RAG stub - Neo4j 연동 예정"
    }


@router.post("/sql")
def rag_sql(req: SqlRequest):
    """Text2SQL - 6~7주차에 구현"""
    return {
        "sql": "",
        "result": [],
        "answer": "",
        "message": "Text2SQL stub - SQLite 연동 예정"
    }


@router.post("/evaluate")
def rag_evaluate(test_set_id: str):
    """평가 파이프라인 - 9~10주차에 구현"""
    return {
        "metrics": {},
        "details": [],
        "message": "Evaluate stub - Gold Set 구축 예정"
    }
