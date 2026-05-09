from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.db.session import get_db_session
from backend.models.models import Patient

router = APIRouter(prefix="/patients")


@router.get("")
async def list_patients(
    unit_type: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
) -> List[Dict[str, Any]]:
    async with get_db_session() as session:
        query = select(Patient).where(Patient.is_active == True)
        
        if unit_type:
            query = query.where(Patient.unit_type == unit_type)
        if risk_level:
            query = query.where(Patient.risk_level == risk_level)
        if search:
            search_term = f"%{search}%"
            query = query.where(
                Patient.mrn.ilike(search_term) | Patient.last_name.ilike(search_term)
            )
        
        query = query.order_by(Patient.risk_level.desc()).limit(limit)
        result = await session.execute(query)
        patients = result.scalars().all()
        
        return [_serialize_patient(p) for p in patients]


@router.get("/{patient_id}")
async def get_patient(patient_id: str) -> Dict[str, Any]:
    async with get_db_session() as session:
        result = await session.execute(
            select(Patient)
            .options(
                selectinload(Patient.vitals),
                selectinload(Patient.labs),
                selectinload(Patient.medications),
            )
            .where(Patient.id == patient_id)
        )
        patient = result.scalar_one_or_none()
        
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        return _serialize_patient_full(patient)


def _serialize_patient(p: Patient) -> Dict[str, Any]:
    return {
        "id": p.id,
        "mrn": p.mrn,
        "first_name": p.first_name,
        "last_name": p.last_name,
        "date_of_birth": p.date_of_birth.isoformat() if p.date_of_birth else None,
        "sex": p.sex,
        "unit_type": p.unit_type,
        "bed_number": p.bed_number,
        "primary_diagnosis": p.primary_diagnosis,
        "allergies": p.allergies or [],
        "comorbidities": p.comorbidities or [],
        "risk_level": p.risk_level,
        "admission_date": p.admission_date.isoformat() if p.admission_date else None,
    }


def _serialize_patient_full(p: Patient) -> Dict[str, Any]:
    result = _serialize_patient(p)
    result["vitals"] = [
        {
            "id": v.id,
            "timestamp": v.timestamp.isoformat(),
            "heart_rate": v.heart_rate,
            "systolic_bp": v.systolic_bp,
            "diastolic_bp": v.diastolic_bp,
            "mean_arterial_pressure": v.mean_arterial_pressure,
            "respiratory_rate": v.respiratory_rate,
            "temperature": v.temperature,
            "oxygen_saturation": v.oxygen_saturation,
            "spo2": v.spo2,
            "lactate": v.lactate,
            "gcs": v.gcs,
        }
        for v in p.vitals[-20:]
    ]
    result["labs"] = [
        {
            "id": l.id,
            "timestamp": l.timestamp.isoformat(),
            "test_name": l.test_name,
            "value": l.value,
            "unit": l.unit,
            "reference_low": l.reference_low,
            "reference_high": l.reference_high,
            "is_critical": l.is_critical,
        }
        for l in p.labs[-20:]
    ]
    result["medications"] = [
        {
            "id": m.id,
            "name": m.name,
            "dosage": m.dosage,
            "route": m.route,
            "frequency": m.frequency,
            "is_active": m.is_active,
        }
        for m in p.medications
    ]
    return result
