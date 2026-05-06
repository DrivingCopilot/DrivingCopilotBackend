from app.models.vehicle import VehicleState, TirePressure

# 1주차: Mock 데이터로 동작
# 추후 실제 차량 센서 DB 연동으로 교체
_mock_vehicle_state = VehicleState(
    speed=60.0,
    rpm=2000,
    fuel=75.0,
    battery=90.0,
    tire_pressure=TirePressure(
        front_left=33.0,
        front_right=33.0,
        rear_left=32.0,
        rear_right=33.0
    ),
    ac_on=False,
    ac_temperature=22.0,
    wiper_on=False,
    window_open=True,
    driving_mode="normal",
    warning_lights=[]
)


def get_vehicle_state() -> VehicleState:
    return _mock_vehicle_state


def update_vehicle_state(field: str, value) -> VehicleState:
    """Tool 실행 후 차량 상태 업데이트"""
    global _mock_vehicle_state
    updated = _mock_vehicle_state.model_copy(update={field: value})
    _mock_vehicle_state = updated
    return _mock_vehicle_state
