import asyncio
import json
import logging
from typing import Set

from fastapi import APIRouter, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from app.models.vehicle import VehicleState
from app.services import vehicle as vehicle_service

logger = logging.getLogger(__name__)

router = APIRouter()

_ws_clients: Set[WebSocket] = set()


async def _broadcast(state: VehicleState) -> None:
    if not _ws_clients:
        return
    payload = json.dumps(state.model_dump(), ensure_ascii=False)
    dead: Set[WebSocket] = set()
    for ws in list(_ws_clients):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    _ws_clients -= dead


async def poll_vehicle_state() -> None:
    """vehicle_state.json 변경을 0.5초마다 감지해 WebSocket으로 브로드캐스트한다."""
    last: dict | None = None
    while True:
        await asyncio.sleep(0.5)
        try:
            current = vehicle_service.get_vehicle_state()
            current_dict = current.model_dump()
            if current_dict != last:
                last = current_dict
                await _broadcast(current)
        except Exception:
            logger.debug("vehicle state poll error", exc_info=True)


# Spring의 @GetMapping("/vehicle/state") 랑 동일
@router.get("/vehicle/state", response_model=VehicleState)
def get_vehicle_state():
    """현재 차량 상태 반환"""
    return vehicle_service.get_vehicle_state()


@router.websocket("/ws/vehicle")
async def vehicle_ws(websocket: WebSocket) -> None:
    """차량 상태 실시간 스트림 — MCP 툴이 상태를 변경하면 0.5초 내에 push된다."""
    await websocket.accept()
    _ws_clients.add(websocket)
    try:
        # 연결 즉시 현재 상태 전송
        state = vehicle_service.get_vehicle_state()
        await websocket.send_text(json.dumps(state.model_dump(), ensure_ascii=False))
        while True:
            await websocket.receive_text()  # disconnect 감지용
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(websocket)


@router.get("/vehicle/camera-frame")
def get_camera_frame():
    """get_camera_frame MCP tool이 읽는 것과 동일한 카메라 stub 프레임 이미지를 반환한다 (프론트엔드 미리보기용)."""
    if not vehicle_service.CAMERA_STUB_FRAME.exists():
        return JSONResponse(status_code=404, content={"error": "camera frame not found"})
    return FileResponse(vehicle_service.CAMERA_STUB_FRAME, media_type="image/jpeg")


@router.post("/vehicle/camera-frame")
async def upload_camera_frame(file: UploadFile = File(...)):
    """업로드된 이미지로 카메라 stub 프레임을 교체한다. get_camera_frame MCP tool이 다음 호출부터 이 이미지를 읽는다."""
    data = await file.read()
    vehicle_service.save_camera_frame(data)
    return {"status": "ok"}
