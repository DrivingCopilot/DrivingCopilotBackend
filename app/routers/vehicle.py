from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from app.models.vehicle import VehicleState
from app.services import vehicle as vehicle_service

router = APIRouter()


# Spring의 @GetMapping("/vehicle/state") 랑 동일
@router.get("/vehicle/state", response_model=VehicleState)
def get_vehicle_state():
    """현재 차량 상태 반환"""
    return vehicle_service.get_vehicle_state()


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
