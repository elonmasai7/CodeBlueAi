from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uuid
from sqlalchemy import select

from backend.db.session import get_db_session
from backend.models.models import Patient, VitalSign
from agents.monitor.agent import MonitorAgent
from agents.monitor.clinical_scoring import ClinicalScoringService

router = APIRouter(prefix="/vitals")
scoring_service = ClinicalScoringService()
monitor_agent = MonitorAgent(scoring_service)


class VitalCreate(BaseModel):
    patient_id: str
    heart_rate: Optional[float] = None
    systolic_bp: Optional[float] = None
    diastolic_bp: Optional[float] = None
    respiratory_rate: Optional[float] = None
    temperature: Optional[float] = None
    spo2: Optional[float] = None
    lactate: Optional[float] = None


@router.post("")
async def create_vital(vital: VitalCreate) -> Dict[str, Any]:
    async with get_db_session() as session:
        patient_result = await session.execute(
            select(Patient).where(Patient.id == vital.patient_id)
        )
        patient = patient_result.scalar_one_or_none()
        
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        new_vital = VitalSign(
            id=str(uuid.uuid4()),
            patient_id=vital.patient_id,
            heart_rate=vital.heart_rate,
            systolic_bp=vital.systolic_bp,
            diastolic_bp=vital.diastolic_bp,
            respiratory_rate=vital.respiratory_rate,
            temperature=vital.temperature,
            oxygen_saturation=vital.spo2,
            spo2=vital.spo2,
            lactate=vital.lactate,
            gcs=15.0,
        )
        
        if vital.systolic_bp and vital.diastolic_bp:
            new_vital.mean_arterial_pressure = (vital.systolic_bp + vital.diastolic_bp * 2) / 3
        
        session.add(new_vital)
        
        vitals_dict = vital.model_dump(exclude={"patient_id"})
        vitals_dict["map"] = new_vital.mean_arterial_pressure
        analysis = monitor_agent.analyze_clinical_picture(patient.id, patient.mrn, vitals_dict)
        
        return {"vital_id": new_vital.id, "analysis": analysis}
