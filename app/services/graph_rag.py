"""
app/services/graph_rag.py

Graph RAG: Neo4j 차량 지식 그래프에서 엔티티(부품/경고등/증상/DTC 등) 주변
1-hop 관계를 탐색해 관계형 컨텍스트를 반환한다.

그래프 스키마(노드: Component/WarningLight/Symptom/Maintenance/DTC Code/System/
Action/Schedule, 관계: INDICATES/CAUSED_BY/MAINTAINED_BY 등)는 DrivingCopilotGraph의
graph/schema.py 정의를 따른다.

무거운 의존성(neo4j 드라이버)은 함수 내부 lazy import + graceful degradation.
"""

import asyncio
import logging
from typing import List

from app import config

logger = logging.getLogger(__name__)

# 엔티티/질의어로 노드를 매칭하고 주변 관계를 1-hop 탐색하는 Cypher.
# 노드 종류별로 식별 속성(name/description/code/type)이 달라 coalesce로 폭넓게 매칭.
_CYPHER = """
MATCH (n)-[r]-(m)
WHERE any(term IN $terms WHERE
        toLower(coalesce(n.name, ''))        CONTAINS term
     OR toLower(coalesce(n.description, '')) CONTAINS term
     OR toLower(coalesce(n.code, ''))        CONTAINS term
     OR toLower(coalesce(n.type, ''))        CONTAINS term)
RETURN labels(n) AS src_labels,
       coalesce(n.name, n.code, n.type, n.description) AS src,
       type(r) AS rel,
       labels(m) AS dst_labels,
       coalesce(m.name, m.code, m.type, m.description) AS dst
LIMIT $limit
"""


def _extract_terms(query: str, entities: List[str]) -> List[str]:
    """엔티티가 주어지면 그것을, 없으면 질의어를 소문자 검색어로 사용."""
    if entities:
        return [e.strip().lower() for e in entities if e.strip()]
    return [w.lower() for w in query.split() if len(w) > 1]


def _run_graph_search(query: str, entities: List[str]) -> str:
    terms = _extract_terms(query, entities)
    if not terms:
        return "검색할 엔티티가 없습니다."

    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
        )
        try:
            with driver.session(database=config.NEO4J_DATABASE) as session:
                records = session.run(
                    _CYPHER, terms=terms, limit=config.GRAPH_MAX_RESULTS
                )
                lines = [
                    f"({rec['src']})-[:{rec['rel']}]-({rec['dst']})"
                    for rec in records
                    if rec["src"] is not None and rec["dst"] is not None
                ]
        finally:
            driver.close()

        if not lines:
            return f"'{', '.join(terms)}' 관련 그래프 관계를 찾지 못했습니다."

        # 중복 제거 후 반환
        unique = list(dict.fromkeys(lines))
        return "## 그래프 관계\n" + "\n".join(unique)
    except Exception as e:
        logger.exception("graph_rag_search 실패")
        return f"graph_rag_search 처리 중 오류: {e}"


async def graph_search(query: str, entities: List[str] | None = None) -> str:
    """MCP 툴 진입점. 블로킹 탐색을 스레드로 오프로딩한다."""
    return await asyncio.to_thread(_run_graph_search, query, entities or [])
