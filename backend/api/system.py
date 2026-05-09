from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from backend.services.auth import get_current_user, TokenPayload, require_permission
from backend.services.security import Permission, check_permission, rbac_service
from backend.services.circuit_breaker import circuit_registry
from backend.db.session import get_db_session
from backend.models.models import AuditLog
from a2a_bus.tracing import agent_tracer
from datetime import datetime
import uuid

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


@router.get("/circuit-breakers")
async def list_circuit_breakers(user: TokenPayload = Depends(get_current_user)):
    if not check_permission(user.role, Permission.VIEW_AUDIT):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    return {"circuit_breakers": circuit_registry.get_all_states()}


@router.get("/tracing/stats")
async def get_tracing_stats(user: TokenPayload = Depends(get_current_user)):
    if not check_permission(user.role, Permission.VIEW_AUDIT):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    return agent_tracer.get_stats()


@router.get("/audit-log")
async def get_audit_log(
    limit: int = 100,
    user: TokenPayload = Depends(get_current_user),
):
    if not check_permission(user.role, Permission.VIEW_AUDIT):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    async with get_db_session() as session:
        result = await session.execute(
            select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
        )
        logs = result.scalars().all()

        return {
            "logs": [
                {
                    "id": log.id,
                    "timestamp": log.timestamp.isoformat(),
                    "user_id": log.user_id,
                    "action": log.action,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "details": log.details,
                    "ip_address": log.ip_address,
                }
                for log in logs
            ]
        }


@router.post("/audit-log")
async def create_audit_log(
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict = {},
    user: TokenPayload = Depends(get_current_user),
):
    async with get_db_session() as session:
        audit_entry = AuditLog(
            id=str(uuid.uuid4()),
            user_id=user.sub,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            timestamp=datetime.utcnow(),
        )
        session.add(audit_entry)

        return {"status": "created", "id": audit_entry.id}
