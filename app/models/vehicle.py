from pydantic import BaseModel

# Spring의 DTO 클래스랑 동일한 개념
class TirePressure(BaseModel):
    front_left: float = 33.0
    front_right: float = 33.0
    rear_left: float = 33.0
    rear_right: float = 33.0


class VehicleState(BaseModel):
    speed: float = 0.0          # 현재 속도 (km/h)
    rpm: int = 0                # 엔진 RPM
    fuel: float = 75.0          # 연료 잔량 (%)
    battery: float = 90.0       # 배터리 (%)
    tire_pressure: TirePressure = TirePressure()
    ac_on: bool = False         # 에어컨 상태
    ac_temperature: float = 22.0  # 에어컨 온도
    wiper_on: bool = False      # 와이퍼 상태
    window_open: bool = False   # 창문 상태
    driving_mode: str = "normal"  # normal / eco / sport
    warning_lights: list[str] = []  # 켜진 경고등 목록
