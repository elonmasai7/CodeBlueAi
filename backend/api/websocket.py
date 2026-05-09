from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
import json
import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/ws")

connections: List[WebSocket] = []


@router.websocket("/clinical")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connections.append(websocket)
    logger.info("websocket_connected")
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            logger.info("websocket_message_received", message_type=message.get("type"))
            await websocket.send_json({"status": "received", "type": message.get("type")})
    except WebSocketDisconnect:
        connections.remove(websocket)
        logger.info("websocket_disconnected")
    except Exception as e:
        logger.error("websocket_error", error=str(e))
        connections.remove(websocket)


async def broadcast_message(message: dict):
    for conn in connections:
        try:
            await conn.send_json(message)
        except Exception:
            pass
