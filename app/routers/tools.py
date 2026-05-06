from fastapi import APIRouter

from app.models.tools import ToolExecuteResponse, ToolExecuteRequest
from app.services import vehicle as vehicle_service

router = APIRouter()

# 12종 Tool 목록
AVAILABLE_TOOLS = [
    "climate",        # 에어컨/히터
    "navigation",     # 네비게이션
    "media",          # 미디어
    "vehicle_status", # 차량 상태 조회
    "window",         # 창문
    "lighting",       # 조명
    "seat",           # 시트
    "parking",        # 주차
    "emergency",      # 긴급
    "driving_mode",   # 주행 모드
    "wiper",          # 와이퍼
    "dashboard_query" # 대시보드 조회
]

@router.post("/tools/execute", response_model=ToolExecuteResponse)
def execute_tool(req: ToolExecuteRequest):
    """차량 Tool 실행 - 2주차에 MCP 연동"""

    if req.tool_name not in AVAILABLE_TOOLS:
        return ToolExecuteResponse(
            success=False,
            message=f"알 수 없는 Tool: {req.tool_name}. 사용 가능: {AVAILABLE_TOOLS}"
        )

    # 1주차: Mock 실행 (실제 MCP 연동은 2주차)
    result = _mock_tool_execute(req.tool_name, req.params)
    return ToolExecuteResponse(success=True, result=result, message="Tool 실행 완료")


def _mock_tool_execute(tool_name: str, params: dict) -> dict:
    """Mock Tool 실행 - 나중에 MCP로 교체"""
    if tool_name == "climate":
        temp = params.get("temperature", 22)
        vehicle_service.update_vehicle_state("ac_on", True)
        vehicle_service.update_vehicle_state("ac_temperature", temp)
        return {"action": "에어컨 설정", "temperature": temp}

    elif tool_name == "window":
        open_state = params.get("open", False)
        vehicle_service.update_vehicle_state("window_open", open_state)
        return {"action": "창문 제어", "open": open_state}

    elif tool_name == "wiper":
        on_state = params.get("on", True)
        vehicle_service.update_vehicle_state("wiper_on", on_state)
        return {"action": "와이퍼 제어", "on": on_state}

    elif tool_name == "driving_mode":
        mode = params.get("mode", "normal")
        vehicle_service.update_vehicle_state("driving_mode", mode)
        return {"action": "주행모드 변경", "mode": mode}

    elif tool_name == "vehicle_status":
        state = vehicle_service.get_vehicle_state()
        return {"vehicle_state": state.model_dump()}

    else:
        return {"action": f"{tool_name} 실행됨", "params": params}
