import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import vehicle, rag, tools, chat
from app.routers.vehicle import poll_vehicle_state
from app.services.query_router import warmup as router_warmup


@asynccontextmanager
async def lifespan(app: FastAPI):
    router_warmup()
    poll_task = asyncio.create_task(poll_vehicle_state())
    yield
    poll_task.cancel()
    try:
        await poll_task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title="Driving Copilot API",
    description="On-Device Multimodal Driving Copilot Backend",
    version="0.1.0",
    lifespan=lifespan,
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
