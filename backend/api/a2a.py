from fastapi import APIRouter
from typing import Dict, Any

from a2a_bus.message_bus import message_bus

router = APIRouter(prefix="/a2a")


@router.get("/status")
async def a2a_status() -> Dict[str, Any]:
    return message_bus.get_stats()


@router.get("/contracts")
async def list_contracts() -> Dict[str, Any]:
    return {
        "contracts": [
            {"message_type": k, "required_agents": v.required_agents}
            for k, v in message_bus._contracts.items()
        ]
    }
