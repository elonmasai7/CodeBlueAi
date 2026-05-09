from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.db.session import get_db_session
from backend.models.models import Patient
from agents.monitor.agent import MonitorAgent
from agents.monitor.clinical_scoring import ClinicalScoringService
from agents.diagnostic.agent import DiagnosticAgent
from agents.guideline.agent import GuidelineAgent
from agents.coordinator.agent import CoordinatorAgent
from agents.documentation.agent import DocumentationAgent

router = APIRouter(prefix="/analyze")
scoring_service = ClinicalScoringService()
monitor_agent = MonitorAgent(scoring_service)
diagnostic_agent = DiagnosticAgent()
guideline_agent = GuidelineAgent()
coordinator_agent = CoordinatorAgent()
documentation_agent = DocumentationAgent()


@router.post("/{patient_id}")
async def analyze_patient(patient_id: str) -> Dict[str, Any]:
    async with get_db_session() as session:
        result = await session.execute(
            select(Patient)
            .options(selectinload(Patient.vitals), selectinload(Patient.labs), selectinload(Patient.medications))
            .where(Patient.id == patient_id)
        )
        patient = result.scalar_one_or_none()
        
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        latest_vitals = patient.vitals[-1].__dict__ if patient.vitals else {}
        vitals_dict = {
            "heart_rate": latest_vitals.get("heart_rate", 70),
            "systolic_bp": latest_vitals.get("systolic_bp", 120),
            "diastolic_bp": latest_vitals.get("diastolic_bp", 80),
            "respiratory_rate": latest_vitals.get("respiratory_rate", 16),
            "temperature": latest_vitals.get("temperature", 37.0),
            "spo2": latest_vitals.get("spo2", 97),
            "map": latest_vitals.get("mean_arterial_pressure", 90),
            "lactate": latest_vitals.get("lactate", 1.0),
        }
        
        monitor_result = monitor_agent.analyze_clinical_picture(patient.id, patient.mrn, vitals_dict)
        
        diagnostic_result = await diagnostic_agent.analyze(
            patient.id,
            patient.mrn,
            vitals_dict,
            [l.__dict__ for l in patient.labs],
            [m.__dict__ for m in patient.medications],
            patient.allergies or [],
            patient.comorbidities or [],
            patient.primary_diagnosis or "Unknown",
        )
        
        guideline_response = guideline_agent.generate_response(
            patient.id,
            patient.mrn,
            diagnostic_result.primary_diagnosis.code if diagnostic_result.primary_diagnosis else "UNKNOWN",
            diagnostic_result.primary_diagnosis.name if diagnostic_result.primary_diagnosis else "Unknown",
            {"vitals": vitals_dict},
        )
        
        coordinator_response = coordinator_agent.coordinate_escalation(
            patient.id,
            patient.mrn,
            monitor_result["scores"]["NEWS2"]["risk_level"],
            diagnostic_result.primary_diagnosis.name if diagnostic_result.primary_diagnosis else "Unknown",
            guideline_response.triggered_protocol,
            monitor_result["scores"],
            vitals_dict,
        )
        
        soap = documentation_agent.generate_soap_note(
            patient.id,
            patient.mrn,
            f"{patient.first_name} {patient.last_name}",
            vitals_dict,
            [l.__dict__ for l in patient.labs],
            [m.__dict__ for m in patient.medications],
            diagnostic_result.primary_diagnosis.name if diagnostic_result.primary_diagnosis else "Unknown",
            guideline_response.triggered_protocol,
            monitor_result["scores"],
            {"level": coordinator_response.level.value, "reason": coordinator_response.reason},
        )
        
        return {
            "patient_id": patient.id,
            "mrn": patient.mrn,
            "monitor": monitor_result,
            "diagnostic": {
                "differential": [
                    {"code": d.code, "name": d.name, "probability": d.probability, "evidence": d.evidence}
                    for d in diagnostic_result.differential
                ],
                "primary_diagnosis": diagnostic_result.primary_diagnosis.name if diagnostic_result.primary_diagnosis else None,
                "risk_prediction": diagnostic_result.risk_prediction,
            },
            "guideline": {
                "protocol": guideline_response.triggered_protocol,
                "urgency": guideline_response.urgency,
                "interventions": [
                    {"action": i.action, "timing": i.timing, "dose": i.dose, "priority": i.priority}
                    for i in guideline_response.protocol_details.interventions
                ],
            },
            "coordinator": {
                "level": coordinator_response.level.value,
                "reason": coordinator_response.reason,
                "notifications": [
                    {"recipient": n.recipient_name, "action": n.action.value, "priority": n.priority}
                    for n in coordinator_response.notifications
                ],
                "tasks": [
                    {"description": t.description, "assigned_to": t.assigned_to, "due": t.due.isoformat()}
                    for t in coordinator_response.tasks
                ],
            },
            "documentation": {
                "subjective": soap.subjective,
                "objective": soap.objective,
                "assessment": soap.assessment,
                "plan": soap.plan,
                "clinical_rationale": soap.clinical_rationale,
            },
        }
