# docker/backend.Dockerfile
#
# REST API(main.py, :8000) + MCP 서버(mcp_server.py, :9000) 공용 이미지.
# 두 프로세스 모두 CPU 전용이다 — Vector RAG(bge-m3/bge-reranker via sentence-transformers)는
# CPU로 충분한 크기고, 무거운 VLM/LLM 추론은 DrivingCopilotAgent 레포의 로컬 모델 서버가
# 전담한다(Backend는 OPENAI_BASE_URL로 그 서버를 HTTP 호출만 함). 실행 프로세스는
# docker-compose의 command:로 갈라진다.
#
# 빌드 (repo 루트에서):
#   docker build -f docker/backend.Dockerfile -t driving-copilot-backend:latest .

FROM python:3.10-slim

WORKDIR /app

# sentence-transformers가 의존성으로 torch를 끌고 오는데 기본 인덱스는 CUDA 번들 wheel을
# 줄 수 있다 — 이 이미지는 CPU 전용이므로 먼저 CPU wheel을 명시적으로 깐다
# (DrivingCopilotAgent의 docker/agent.Dockerfile과 동일한 이유).
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY main.py mcp_server.py ./

# REST API(8000) + MCP 서버(9000). 실제 여는 포트는 command:로 실행되는 프로세스에 따라 다르다.
EXPOSE 8000 9000

RUN useradd --create-home --uid 1000 appuser

# /app 자체가 root 소유(WORKDIR/COPY가 USER 전환 전에 실행됨)라 appuser가 SQLite
# journal/wal 파일을 옆에 만들지 못해 init_db()가 "attempt to write a readonly
# database"로 실패한다 — 디렉터리 소유권을 appuser로 넘겨야 한다.
RUN chown appuser:appuser /app

# vehicle_data.db/vehicle_state.json은 .gitignore 대상이라 fresh clone엔 없다. 이미지 안에
# appuser 소유의 빈 파일로 미리 만들어둔다 — docker-compose로 실행할 때는 이 값이 바인드
# 마운트로 덮이므로 호스트 쪽 파일도 반드시 먼저 존재해야 한다(없으면 Docker가 파일이
# 아니라 디렉터리를 마운트해 IsADirectoryError/sqlite3.OperationalError가 난다). 자세한
# 절차는 docker-compose.yml/README 참고.
RUN touch vehicle_data.db vehicle_state.json && mkdir -p data/camera_stub \
    && chown appuser:appuser vehicle_data.db vehicle_state.json data/camera_stub

USER appuser

# 기본값은 REST API. MCP 서버는 docker-compose의 command:로 override한다.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
