# Driving Copilot Backend

On-Device Multimodal Driving Copilot - FastAPI Backend

## 실행 방법

이 레포는 **REST API(8000)**와 **MCP 서버(9000)** 두 프로세스로 구성됩니다. 둘 다
따로 띄워야 하고(터미널 2개 필요), `DrivingCopilotAgent`의 knowledge/execution/perception이
MCP 서버(9000)를 호출해 차량 제어·카메라 프레임 조회를 합니다.

### 1. 가상환경 + 패키지 설치

**Mac / Linux**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell)**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Qdrant 벡터 DB 실행 (서버 모드)

벡터 RAG(차량 매뉴얼 검색)와 Text2SQL few-shot은 Qdrant 서버(6333)에 접속합니다.
Docker로 서버를 띄웁니다.

```bash
docker compose up -d        # qdrant 컨테이너 기동 (6333/6334)
docker compose ps           # 상태 확인
```

접속 모드는 `.env`로 제어합니다. 기본값은 **서버 모드**입니다.

```dotenv
QDRANT_PATH=                     # 비워두면 서버 모드
QDRANT_URL=http://localhost:6333
```

> 파일 모드로 쓰려면 `QDRANT_PATH`에 로컬 저장소 경로를 넣으면 됩니다(서버 불필요).
> 두 모드는 저장 포맷이 달라 데이터가 자동 공유되지 않습니다.

### 3. 서버 2개 실행 (Mac/Windows 공통 명령어, 터미널만 따로)

```bash
# 터미널 1 — REST API (8000, vehicle-state / camera-frame 등)
uvicorn main:app --reload

# 터미널 2 — MCP 서버 (9000, 차량 제어 12종 Tool)
python mcp_server.py
```

`mcp_server.py`는 `streamable-http` transport로 `http://127.0.0.1:9000/mcp`에 뜹니다.
`DrivingCopilotAgent`의 `.env`/`config.py`에 있는 `MCP_SERVER_URL` 기본값과 일치해야 하니
포트를 바꿨다면 Agent 쪽 설정도 같이 맞춰주세요.

### 확인

```bash
# Mac/Linux
lsof -iTCP -sTCP:LISTEN -P | grep -E ":8000|:9000"
```
```powershell
# Windows
netstat -ano | findstr "8000 9000"
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