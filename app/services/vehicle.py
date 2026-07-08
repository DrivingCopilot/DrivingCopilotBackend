"""
app/services/vehicle.py

차량 상태를 JSON 파일로 영속 관리한다.
FastAPI 프로세스와 MCP subprocess(Agent 측에서 spawn) 가
동일한 파일을 읽고 써서 상태를 공유한다.

파일 위치: DrivingCopilotBackend/ 루트의 vehicle_state.json
"""

import json
import os
from pathlib import Path

from app.models.vehicle import VehicleState, TirePressure

# 상태 파일: 이 파일(vehicle.py)이 있는 services/ 에서 두 단계 위가 Backend 루트
_STATE_FILE = Path(__file__).parent.parent.parent / "vehicle_state.json"

# 카메라 stub 프레임: FastAPI 프로세스(업로드 수신)와 MCP subprocess(get_camera_frame 읽기)가
# 동일한 파일을 공유한다. 실 카메라 연동 전까지 이 파일을 갈아치우는 방식으로 Vision 입력을 대체한다.
CAMERA_STUB_FRAME = Path(__file__).parent.parent.parent / "data" / "camera_stub" / "sample_frame.jpg"

# 기본 초기값
_DEFAULTS: dict = {
    "speed": 60.0,
    "rpm": 2000,
    "fuel": 75.0,
    "battery": 90.0,
    "tire_pressure": {
        "front_left": 33.0,
        "front_right": 33.0,
        "rear_left": 32.0,
        "rear_right": 33.0,
    },
    "ac_on": False,
    "ac_temperature": 22.0,
    "wiper_on": False,
    "window_open": True,
    "driving_mode": "normal",
    "warning_lights": [],
}


def _load() -> dict:
    """JSON 파일에서 차량 상태를 읽는다. 파일이 없으면 기본값 반환."""
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(_DEFAULTS)


def _save(data: dict) -> None:
    """차량 상태를 JSON 파일에 저장한다."""
    _STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_vehicle_state() -> VehicleState:
    """현재 차량 상태를 반환한다."""
    return VehicleState(**_load())


def update_vehicle_state(field: str, value) -> VehicleState:
    """
    특정 필드를 업데이트하고 저장한 뒤 새 상태를 반환한다.
    MCP tool 과 FastAPI 엔드포인트 양쪽에서 호출된다.
    """
    data = _load()
    data[field] = value
    _save(data)
    return VehicleState(**data)


def save_camera_frame(data: bytes) -> None:
    """업로드된 이미지로 카메라 stub 프레임을 교체한다. MCP의 get_camera_frame이 다음 호출부터 이 파일을 읽는다."""
    CAMERA_STUB_FRAME.parent.mkdir(parents=True, exist_ok=True)
    CAMERA_STUB_FRAME.write_bytes(data)
