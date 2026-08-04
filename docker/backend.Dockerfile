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
USER appuser

# 기본값은 REST API. MCP 서버는 docker-compose의 command:로 override한다.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
