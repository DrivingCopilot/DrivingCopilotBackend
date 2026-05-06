# Driving Copilot Backend

On-Device Multimodal Driving Copilot - FastAPI Backend

## 실행 방법

```bash
# 1. 가상환경 활성화
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows

# 2. 패키지 설치
pip install -r requirements.txt

# 3. 서버 실행
uvicorn main:app --reload
```

## API 문서
서버 실행 후 http://localhost:8000/docs 접속

## 프로젝트 구조
```
DrivingCopilotBackend/
├── main.py                  # 진입점
├── requirements.txt         # 패키지 목록
├── .env                     # 환경변수
└── app/
    ├── routers/             # API 엔드포인트
    │   ├── vehicle.py       # /vehicle/state
    │   ├── rag.py           # /rag/*
    │   └── tools.py         # /tools/execute
    ├── models/              # Pydantic 모델 (DTO)
    │   └── vehicle.py
    └── services/            # 비즈니스 로직
        └── vehicle.py
```

## API 목록
| Method | Endpoint | 설명 | 상태 |
|--------|----------|------|------|
| GET | /vehicle/state | 차량 상태 조회 | ✅ Mock |
| POST | /tools/execute | Tool 실행 | ✅ Mock |
| POST | /rag/route | 쿼리 라우터 | ✅ 키워드 기반 |
| POST | /rag/search | 벡터 검색 | 🔜 2주차 |
| POST | /rag/graph | Graph RAG | 🔜 5주차 |
| POST | /rag/sql | Text2SQL | 🔜 6주차 |
| WS | /ws/chat | 채팅 스트리밍 | 🔜 3주차 |

## 주차별 개발 계획
- **1주차**: FastAPI 기반 구조 + Mock API
- **2주차**: Qdrant 벡터 검색 + MCP Tool 연동
- **3주차**: Query Router + WebSocket 스트리밍
- **4~5주차**: Neo4j Graph RAG
- **6~7주차**: Text2SQL
