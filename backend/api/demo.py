from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
from datetime import datetime
import uuid

from backend.db.session import get_db_session
from backend.models.models import Patient, ClinicalEvent
from backend.services.event_bus import event_bus

router = APIRouter(prefix="/demo")


class DemoTrigger(BaseModel):
    patient_id: str | None = None


@router.post("/trigger")
async def trigger_demo(patient_id: str | None = None) -> Dict[str, Any]:
    async with get_db_session() as session:
        if patient_id:
            result = await session.execute(
                Patient.__table__.select().where(Patient.id == patient_id)
            )
            patient_row = result.first()
            if not patient_row:
                raise HTTPException(status_code=404, detail="Patient not found")
        else:
            result = await session.execute(
                Patient.__table__.select()
                .where(Patient.is_active == True)
                .order_by(Patient.risk_level.desc())
                .limit(1)
            )
            patient_row = result.first()
            if not patient_row:
                return {"status": "no_active_patients"}
        
        patient = dict(patient_row)
        
        await event_bus.publish({
            "type": "DEMO_START",
            "patient_id": patient["id"],
            "mrn": patient["mrn"],
            "patient_name": f"{patient['first_name']} {patient['last_name']}",
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        vitals = {
            "heart_rate": 128,
            "systolic_bp": 82,
            "diastolic_bp": 52,
            "respiratory_rate": 28,
            "temperature": 39.2,
            "spo2": 87,
            "map": 62,
            "lactate": 4.8,
        }
        
        from agents.monitor.agent import MonitorAgent
        from agents.monitor.clinical_scoring import ClinicalScoringService
        scoring_service = ClinicalScoringService()
        monitor_agent = MonitorAgent(scoring_service)
        analysis = monitor_agent.analyze_clinical_picture(patient["id"], patient["mrn"], vitals)
        
        return {
            "status": "demo_triggered",
            "patient_id": patient["id"],
            "mrn": patient["mrn"],
            "initial_vitals": vitals,
            "analysis": analysis,
        }
