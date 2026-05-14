from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import vehicle, rag, tools, chat

app = FastAPI(
    title="Driving Copilot API",
    description="On-Device Multimodal Driving Copilot Backend",
    version="0.1.0"
)

# CORS 설정 (React 프론트엔드 연결용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React 기본 포트
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록 (Spring의 @RequestMapping 등록이랑 동일)
app.include_router(vehicle.router, tags=["Vehicle"])
app.include_router(rag.router, prefix="/rag", tags=["RAG"])
app.include_router(tools.router, tags=["Tools"])
app.include_router(chat.router, tags=["Chat"])


@app.get("/")
def root():
    return {"status": "Driving Copilot Backend Running"}
