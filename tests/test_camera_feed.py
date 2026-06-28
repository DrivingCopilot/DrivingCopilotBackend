import base64

import pytest

import mcp_server as ms


@pytest.mark.asyncio
async def test_get_camera_frame_returns_base64_jpeg():
    result = await ms.get_camera_frame()

    decoded = base64.b64decode(result)
    assert decoded.startswith(b"\xff\xd8\xff")  # JPEG magic bytes


@pytest.mark.asyncio
async def test_get_camera_frame_missing_stub(monkeypatch, tmp_path):
    monkeypatch.setattr(ms, "_CAMERA_STUB_FRAME", tmp_path / "missing.jpg")

    result = await ms.get_camera_frame()

    assert result.startswith("오류")
