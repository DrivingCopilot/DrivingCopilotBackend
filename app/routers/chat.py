# app/routers/chat.py
#
# Frontend(3000) ↔ Backend(8000) ↔ Supervisor Agent(8001) 사이의 WebSocket relay.
# - 사용자 발화를 Query Router로 1차 분류한 뒤 supervisor 의 /ws 로 전달
# - supervisor 가 송출하는 토큰 스트림(text/tool_start/tool_result/done)을 그대로 Frontend 로 forward
# - 보조 타입(status)은 Backend 에서 필터하여 Frontend 로 전달하지 않음
# - turn-level 30 초 타임아웃으로 supervisor hang 안전망

import asyncio
import json
import logging
import os

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.query_router import classify_query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws")

SUPERVISOR_WS_URL = os.getenv("SUPERVISOR_WS_URL", "ws://localhost:8001/ws")
TURN_TIMEOUT_SECONDS = 30.0


async def _send_done(ws: WebSocket, reason: str) -> None:
    try:
        await ws.send_text(json.dumps({"type": "done", "reason": reason}))
    except Exception:
        logger.debug("failed to send done frame to client", exc_info=True)


@router.websocket("/chat")
async def chat_ws(websocket: WebSocket) -> None:
    await websocket.accept()

    try:
        upstream = await websockets.connect(SUPERVISOR_WS_URL)
    except Exception:
        logger.exception("failed to connect upstream supervisor")
        try:
            await websocket.send_text(
                json.dumps({"type": "text", "data": "supervisor 서버에 연결할 수 없습니다."})
            )
            await _send_done(websocket, reason="upstream_unavailable")
        finally:
            await websocket.close()
        return

    try:
        while True:
            try:
                message = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            # Query Router: 발화를 분류하고 route_type을 supervisor hint로 전달
            # has_image는 향후 프론트엔드가 {"text": ..., "has_image": true} JSON을
            # 보내도록 확장되면 파싱 로직 추가 예정. 현재는 텍스트 전용.
            try:
                route_result = classify_query(message, has_image=False)
                route_type = route_result["route_type"]
                logger.debug(
                    "route_result: query=%r → %s (confidence=%.2f, method=%s)",
                    message,
                    route_type,
                    route_result["confidence"],
                    route_result["method"],
                )
            except Exception:
                logger.exception("query router failed; falling back to empty route_type")
                route_type = ""

            try:
                await upstream.send(
                    json.dumps({"query": message, "route_type": route_type})
                )
            except Exception:
                logger.exception("upstream send failed")
                await _send_done(websocket, reason="upstream_send_error")
                break

            try:
                while True:
                    frame_raw = await asyncio.wait_for(
                        upstream.recv(), timeout=TURN_TIMEOUT_SECONDS
                    )
                    try:
                        frame = json.loads(frame_raw)
                    except json.JSONDecodeError:
                        await websocket.send_text(frame_raw)
                        continue

                    if frame.get("type") == "status":
                        continue  # filter, Frontend 로 forward 하지 않음

                    await websocket.send_text(json.dumps(frame, ensure_ascii=False))

                    if frame.get("type") == "done":
                        break
            except asyncio.TimeoutError:
                logger.warning("turn timeout waiting for supervisor done")
                await _send_done(websocket, reason="timeout")
            except websockets.ConnectionClosed:
                logger.warning("upstream closed during turn")
                await _send_done(websocket, reason="upstream_closed")
                break
    finally:
        try:
            await upstream.close()
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass
