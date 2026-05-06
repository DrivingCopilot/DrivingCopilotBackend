from fastapi import APIRouter
from app.models.vehicle import VehicleState
from app.services import vehicle as vehicle_service

router = APIRouter()


# Spring의 @GetMapping("/vehicle/state") 랑 동일
@router.get("/vehicle/state", response_model=VehicleState)
def get_vehicle_state():
    """현재 차량 상태 반환"""
    return vehicle_service.get_vehicle_state()
