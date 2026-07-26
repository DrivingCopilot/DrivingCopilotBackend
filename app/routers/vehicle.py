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
    _ws_clients.difference_update(dead)


_HEARTBEAT_TICKS = 4  # 0.5s * 4 = 2s — 변경이 없어도 이 주기로 재전송해 클라이언트가 연결 생존을 확인하게 한다.


async def poll_vehicle_state() -> None:
    """vehicle_state.json 변경을 0.5초마다 감지해 WebSocket으로 브로드캐스트한다.

    상태 변경이 없어도 _HEARTBEAT_TICKS마다 현재 상태를 재전송한다 — uvicorn --reload
    재시작이나 네트워크 순단처럼 onclose가 뜨지 않고 조용히 죽는 연결을, 프론트가
    "일정 시간 메시지 없음"으로 감지해 재연결할 수 있게 하기 위함이다.
    """
    last: dict | None = None
    ticks_since_broadcast = 0
    while True:
        await asyncio.sleep(0.5)
        ticks_since_broadcast += 1
        try:
            current = vehicle_service.get_vehicle_state()
            current_dict = current.model_dump()
            changed = current_dict != last
            if changed or ticks_since_broadcast >= _HEARTBEAT_TICKS:
                last = current_dict
                ticks_since_broadcast = 0
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
