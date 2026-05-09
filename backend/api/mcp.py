from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any, List

from mcp_server.server import mcp_server, MCPToolRequest

router = APIRouter(prefix="/mcp")


@router.get("/tools")
async def list_tools() -> Dict[str, Any]:
    return {"tools": mcp_server.list_tools()}


class MCPExecuteRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any] = {}
    session_id: str | None = None


@router.post("/execute")
async def execute_tool(request: MCPExecuteRequest) -> Dict[str, Any]:
    mcp_request = MCPToolRequest(
        tool=request.tool,
        arguments=request.arguments,
        session_id=request.session_id,
    )
    result = await mcp_server.execute_tool(mcp_request)
    return {
        "tool": result.tool,
        "result": result.result,
        "success": result.success,
        "error": result.error,
        "execution_time_ms": result.execution_time_ms,
        "timestamp": result.timestamp.isoformat(),
    }
