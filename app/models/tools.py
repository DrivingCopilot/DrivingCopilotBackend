from typing import Optional
from pydantic import BaseModel

class ToolExecuteRequest(BaseModel):
    tool_name: str
    params: dict = {}


class ToolExecuteResponse(BaseModel):
    success: bool
    result: Optional[dict] = None
    message: str = ""
