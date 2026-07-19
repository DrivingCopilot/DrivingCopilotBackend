"""
app/services/text2sql.py

자연어 질문을 SQL로 변환·실행하는 Text2SQL 파이프라인.
DrivingCopilotAgent(feature/neo4j_GraphDB)의 text2sql.py를 Backend MCP 서버로 포팅한 것.

파이프라인:
  1. Schema Linking   : 질문과 관련된 테이블 스키마만 필터링
  2. Few-shot (선택)  : Qdrant에서 유사 질문-SQL 예시 검색 (없으면 graceful skip)
  3. Self-Consistency : N개 SQL 생성 후 다수결 투표
  4. 검증·실행        : 금지 구문 차단 + 읽기 전용 실행

무거운 의존성(langchain-openai, langchain-qdrant, 임베딩 모델)은 함수 내부에서
lazy import 하여, 의존성/엔드포인트가 없어도 MCP 서버 자체는 기동되도록 한다.
"""

import asyncio
import json
import logging
import sqlite3
from collections import Counter
from typing import Any, Dict

from app.database import DB_PATH
from app import config

logger = logging.getLogger(__name__)

# 금지 구문 (읽기 전용 보장 — DB는 mode=ro로도 한 번 더 차단)
_FORBIDDEN = ("DROP", "DELETE", "ALTER", "INSERT", "UPDATE", "CREATE", "REPLACE", "TRUNCATE")

# Backend vehicle_data.db 실제 스키마 기준 테이블 설명 (Schema Linking용)
_SCHEMAS = {
    "vehicle_telemetry": "table: vehicle_telemetry, columns: id, ts, speed, rpm, fuel, battery, tire (실시간 차량 센서 데이터, tire는 JSON 문자열 {\"FL\",\"FR\",\"RL\",\"RR\"})",
    "maintenance_log": "table: maintenance_log, columns: id, date, mileage, type, parts, cost (차량 정비 이력)",
    "dtc_codes": "table: dtc_codes, columns: code, description, severity, resolved (OBD-II 오류 및 진단 코드)",
    "trip_history": "table: trip_history, columns: id, start_time, end_time, distance, avg_speed, fuel (차량 운행 기록)",
}

_KEYWORDS = {
    "vehicle_telemetry": ["현재", "실시간", "속도", "rpm", "연료", "배터리", "타이어", "센서"],
    "maintenance_log": ["정비", "오일", "교환", "교체", "비용", "마지막", "이력", "수리"],
    "dtc_codes": ["경고", "코드", "오류", "해결", "미해결", "obd", "dtc", "진단"],
    "trip_history": ["주행", "거리", "운행", "이번 달", "출발", "도착", "평균 속도"],
}


def schema_linking(query: str) -> Dict[str, str]:
    """질문과 관련된 테이블 스키마만 키워드 룰로 필터링. 매칭 없으면 전체 반환."""
    query_lower = query.lower()
    selected = {
        table: _SCHEMAS[table]
        for table, words in _KEYWORDS.items()
        if any(word in query_lower for word in words)
    }
    return selected or _SCHEMAS


def _few_shot_sql(query: str) -> str:
    """
    Qdrant에서 유사 질문-SQL few-shot 예시를 검색해 프롬프트 조각을 만든다.
    Qdrant/임베딩 모델이 없으면 빈 문자열로 graceful degrade.
    """
    try:
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
        search_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="metadata.source",
                    match=models.MatchValue(value="few_shots_examples"),
                )
            ]
        )
        results = vectorstore.similarity_search(
            query=query, k=config.FEW_SHOT_K, filter=search_filter
        )
        if not results:
            return ""

        prompt_text = "## 참고용 유사 SQL 작성 예시\n"
        for i, doc in enumerate(results, 1):
            q = doc.metadata.get("question", "")
            s = doc.metadata.get("sql", "")
            prompt_text += f"예시 {i}, 질문: {q}\n      SQL: {s}\n"
        return prompt_text
    except Exception as e:
        logger.warning("few-shot 예시 검색 생략 (Qdrant/임베딩 불가): %s", e)
        return ""


def _generate_sql(query: str, table_info: str, few_shot_examples: str) -> str:
    """LLM으로 단일 SQL 생성. langchain-openai/엔드포인트 없으면 예외 발생."""
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import PromptTemplate
    from langchain_openai import ChatOpenAI

    prompt = PromptTemplate.from_template(
        """You are an expert SQLite Data Analyst for an On-Device Multimodal Driving Copilot system.
Your task is to convert the user's natural language question into a strictly valid and optimized SQLite query.

### Database Schema (Table Information)
{table_info}

{few_shot_examples}

### Rules and Constraints:
1. Return ONLY the raw SQL query. Do NOT include markdown formatting (e.g., ```sql), explanations, or any other text.
2. Use ONLY the tables and columns provided in the schema above. Do not invent columns.
3. If the query asks for "today", "this month", or related timeframes, use SQLite date/time functions (e.g., DATE('now'), strftime('%Y-%m', 'now')).
4. Focus on vehicle telemetry, maintenance, DTC codes, and trip history specific structures as described.
5. Provide the most efficient and robust query possible.

### User Question
{question}

### SQL Query
"""
    )
    llm_kwargs: Dict[str, Any] = {
        "model": config.LLM_MODEL,
        "temperature": config.LLM_TEMPERATURE,
        "api_key": config.LLM_API_KEY,
    }
    if config.LLM_BASE_URL:
        llm_kwargs["base_url"] = config.LLM_BASE_URL

    chain = prompt | ChatOpenAI(**llm_kwargs) | StrOutputParser()
    return chain.invoke(
        {
            "table_info": table_info,
            "few_shot_examples": few_shot_examples,
            "question": query,
        }
    )


def _self_consistency(query: str, table_info: str, few_shot_examples: str) -> str:
    """N개 SQL을 생성하고 다수결 투표로 최종 SQL을 선택한다."""
    sqls = []
    for _ in range(config.SC_NUM_SAMPLES):
        try:
            sql = _generate_sql(query, table_info, few_shot_examples)
            if sql:
                # 소형 모델은 SQL 뒤에 코드펜스/설명을 덧붙이곤 한다.
                # 1) 선행 ```sql/``` 펜스 제거 2) 첫 닫는 펜스 이후 잘라냄
                # 3) 첫 세미콜론까지만 취해 단일 문장 보장 4) 공백 정규화
                cleaned = sql.strip().removeprefix("```sql").removeprefix("```")
                cleaned = cleaned.split("```", 1)[0]
                cleaned = cleaned.split(";", 1)[0]
                cleaned = " ".join(cleaned.strip().split())
                if cleaned:
                    sqls.append(cleaned)
        except Exception as e:
            logger.error("SQL 생성 오류: %s", e)

    if not sqls:
        return ""

    best_sql, votes = Counter(sqls).most_common(1)[0]
    logger.info("선택된 SQL (%d/%d표): %s", votes, len(sqls), best_sql)
    return best_sql


def _validate_and_execute(generated_sql: str) -> Dict[str, Any]:
    """금지 구문 차단 후 읽기 전용으로 SQL을 실행한다."""
    upper_sql = generated_sql.upper()
    if any(stmt in upper_sql for stmt in _FORBIDDEN):
        return {"success": False, "error": "금지된 구문이 포함되어 있습니다 (읽기 전용만 허용)."}

    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cursor = con.cursor()
    try:
        cursor.execute(f"EXPLAIN QUERY PLAN {generated_sql}")  # 구문 사전 검증
        cursor.execute(generated_sql)
        rows = cursor.fetchall() if cursor.description else []
        return {"success": True, "data": [dict(row) for row in rows]}
    except sqlite3.Error as e:
        return {"success": False, "error": f"DB exception: {e}"}
    finally:
        con.close()


def _run_text_to_sql(query: str) -> str:
    """동기 파이프라인 본체. (블로킹 작업이므로 to_thread로 호출됨)"""
    try:
        table_info = "\n".join(schema_linking(query).values())
        few_shot = _few_shot_sql(query)
        sql = _self_consistency(query, table_info, few_shot)
        if not sql:
            return "오류: SQL 생성에 실패했습니다. (LLM 엔드포인트/langchain-openai 설치 확인 필요)"

        result = _validate_and_execute(sql)
        if not result["success"]:
            return f"SQL 실행 오류: {result['error']} (생성된 SQL: {sql})"

        return json.dumps(
            {"sql": sql, "rows": result["data"]}, ensure_ascii=False, default=str
        )
    except Exception as e:
        logger.exception("text2sql 처리 실패")
        return f"text2sql 처리 중 오류: {e}"


async def text_to_sql(query: str) -> str:
    """MCP 툴 진입점. 블로킹 파이프라인을 스레드로 오프로딩한다."""
    return await asyncio.to_thread(_run_text_to_sql, query)
