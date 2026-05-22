import sqlite3
import json
from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from app.services import vehicle as vehicle_service
from app.database import init_db

mcp = FastMCP(name="vehicle-tools")


# ---- 1) 에어컨 / 히터 ----
@mcp.tool()
async def control_climate(
    temperature: Annotated[int, Field(description="설정 온도(℃, 16~32)", ge=16, le=32)],
    on: Annotated[bool, Field(description="에어컨 ON(True)/OFF(False)")] = True,
) -> str:
    """차량 에어컨/히터를 켜거나 끄고 온도를 설정한다."""
    vehicle_service.update_vehicle_state("ac_on", on)
    vehicle_service.update_vehicle_state("ac_temperature", float(temperature))
    return f"에어컨을 {'켜고' if on else '끄고'} 온도를 {temperature}℃로 설정했어요."


# ---- 2) 네비게이션 ----
@mcp.tool()
async def set_navigation(
    destination: Annotated[str, Field(description="목적지(지번/도로명/장소명)", min_length=1)],
) -> str:
    """네비게이션 목적지를 설정하고 경로 안내를 시작한다."""
    return f"'{destination}'(으)로 길 안내를 시작합니다."


# ---- 3) 미디어 ----
@mcp.tool()
async def control_media(
    action: Annotated[
        Literal["play", "pause", "next", "prev"],
        Field(description="미디어 동작: play(재생) / pause(일시정지) / next(다음곡) / prev(이전곡)"),
    ],
) -> str:
    """미디어 재생을 제어한다."""
    messages = {
        "play": "음악을 재생합니다.",
        "pause": "음악을 일시 정지했어요.",
        "next": "다음 곡으로 넘겼어요.",
        "prev": "이전 곡으로 돌아갔어요.",
    }
    return messages[action]


# ---- 4) 차량 상태 조회 ----
@mcp.tool()
async def get_vehicle_status() -> str:
    """현재 차량 상태(속도/연료/타이어/에어컨/창문/와이퍼/주행모드/경고등)를 조회한다."""
    s = vehicle_service.get_vehicle_state()
    tp = s.tire_pressure
    warnings = ", ".join(s.warning_lights) if s.warning_lights else "없음"
    return (
        f"속도 {s.speed:.0f}km/h, RPM {s.rpm}, "
        f"연료 {s.fuel:.0f}%, 배터리 {s.battery:.0f}%, "
        f"에어컨 {'ON' if s.ac_on else 'OFF'}({s.ac_temperature:.0f}℃), "
        f"창문 {'열림' if s.window_open else '닫힘'}, "
        f"와이퍼 {'ON' if s.wiper_on else 'OFF'}, "
        f"주행 모드 {s.driving_mode}, "
        f"타이어 압력(psi, 좌앞/우앞/좌뒤/우뒤) "
        f"{tp.front_left}/{tp.front_right}/{tp.rear_left}/{tp.rear_right}, "
        f"경고등 {warnings}."
    )


# ---- 5) 창문 ----
@mcp.tool()
async def control_window(
    is_open: Annotated[bool, Field(description="창문 열기(True)/닫기(False)")],
) -> str:
    """창문을 열거나 닫는다."""
    vehicle_service.update_vehicle_state("window_open", is_open)
    return "창문을 열었습니다." if is_open else "창문을 닫았습니다."


# ---- 6) 조명 ----
@mcp.tool()
async def control_lighting(
    on: Annotated[bool, Field(description="실내등 ON(True)/OFF(False)")],
) -> str:
    """실내 조명을 켜거나 끈다."""
    return "실내등을 켰습니다." if on else "실내등을 껐습니다."


# ---- 7) 시트 ----
@mcp.tool()
async def control_seat(
    direction: Annotated[
        Literal["forward", "backward", "up", "down"],
        Field(description="시트 이동 방향: forward/backward/up/down"),
    ],
    recline_angle: Annotated[
        int | None,
        Field(description="등받이 각도(선택, 90~120도)", ge=90, le=120),
    ] = None,
) -> str:
    """운전석 시트 위치/등받이를 조절한다."""
    extra = f", 등받이 각도 {recline_angle}도" if recline_angle is not None else ""
    return f"시트를 {direction} 방향으로 조절했어요{extra}."


# ---- 8) 자동 주차 ----
@mcp.tool()
async def control_parking(
    enable: Annotated[bool, Field(description="자동 주차 모드 ON(True)/OFF(False)")],
) -> str:
    """자동 주차 모드를 활성화/해제한다."""
    return "자동 주차 모드를 활성화했습니다." if enable else "자동 주차 모드를 해제했습니다."


# ---- 9) 긴급 ----
@mcp.tool()
async def trigger_emergency(
    kind: Annotated[
        Literal["call", "alert"],
        Field(description="긴급 동작: call(긴급 전화 연결) / alert(비상등 점등)"),
    ],
) -> str:
    """긴급 호출(전화) 또는 비상등을 작동시킨다."""
    return "긴급 전화를 연결합니다." if kind == "call" else "비상등을 켰습니다."


# ---- 10) 주행 모드 ----
@mcp.tool()
async def set_driving_mode(
    mode: Annotated[
        Literal["normal", "eco", "sport"],
        Field(description="주행 모드: normal(일반) / eco(연비) / sport(스포츠)"),
    ],
) -> str:
    """주행 모드를 변경한다."""
    vehicle_service.update_vehicle_state("driving_mode", mode)
    return f"주행 모드를 {mode}로 변경했습니다."


# ---- 11) 와이퍼 ----
@mcp.tool()
async def control_wiper(
    on: Annotated[bool, Field(description="와이퍼 ON(True)/OFF(False)")],
) -> str:
    """와이퍼를 켜거나 끈다."""
    vehicle_service.update_vehicle_state("wiper_on", on)
    return "와이퍼를 켰습니다." if on else "와이퍼를 껐습니다."


# ---- 12) 대시보드 항목 조회 ----
@mcp.tool()
async def query_dashboard(
    metric: Annotated[
        Literal["speed", "rpm", "fuel", "battery", "tire_pressure", "warning_lights"],
        Field(description="조회할 항목"),
    ],
) -> str:
    """대시보드의 특정 지표를 조회한다."""
    s = vehicle_service.get_vehicle_state()
    if metric == "speed":
        return f"현재 속도는 {s.speed:.0f}km/h 입니다."
    if metric == "rpm":
        return f"현재 RPM은 {s.rpm}입니다."
    if metric == "fuel":
        return f"연료 잔량은 {s.fuel:.0f}% 입니다."
    if metric == "battery":
        return f"배터리는 {s.battery:.0f}% 입니다."
    if metric == "tire_pressure":
        tp = s.tire_pressure
        return (
            f"타이어 압력(psi) - 좌앞 {tp.front_left}, 우앞 {tp.front_right}, "
            f"좌뒤 {tp.rear_left}, 우뒤 {tp.rear_right}"
        )
    if not s.warning_lights:
        return "켜진 경고등이 없습니다."
    return f"켜진 경고등: {', '.join(s.warning_lights)}"

@mcp.tool()
async def execute_db(
        query: Annotated[str,Field(description="실행할 SQL 쿼리")],
) -> str:
    """LLM의 쿼리를 실행하여 결과를 반환한다."""
    con = sqlite3.connect("vehicle_data.db")
    cursor = con.cursor()
    try:
        cursor.execute(query)
        if query.strip().upper().startswith("SELECT"):
            rows = cursor.fetchall()
            return json.dumps(rows, default=str)
        else:
            con.commit()
            return "성공적으로 쿼리가 실행되었습니다."
    except Exception as e:
        return f"오류가 발생했습니다: {str(e)}"
    finally:
        con.close()

if __name__ == "__main__":
    mcp.run()
