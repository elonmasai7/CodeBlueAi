from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.db.session import get_db_session, init_db, close_db
from backend.models.models import Patient, VitalSign, LabResult, Medication, ClinicalEvent, AgentMessage, AuditLog
from agents.monitor.agent import MonitorAgent
from agents.monitor.clinical_scoring import ClinicalScoringService, VitalReading
from agents.diagnostic.agent import DiagnosticAgent
from agents.guideline.agent import GuidelineAgent
from agents.coordinator.agent import CoordinatorAgent
from agents.documentation.agent import DocumentationAgent
from mcp_server.server import mcp_server
from a2a_bus.message_bus import message_bus, A2AMessage
from backend.services.event_bus import event_bus

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()

scoring_service = ClinicalScoringService()
monitor_agent = MonitorAgent(scoring_service)
diagnostic_agent = DiagnosticAgent()
guideline_agent = GuidelineAgent()
coordinator_agent = CoordinatorAgent()
documentation_agent = DocumentationAgent()


class PatientCreate(BaseModel):
    mrn: str
    first_name: str
    last_name: str
    date_of_birth: datetime
    sex: str
    unit_type: str = "MED_SURG"
    bed_number: str
    primary_diagnosis: Optional[str] = None


class VitalCreate(BaseModel):
    patient_id: str
    heart_rate: Optional[float] = None
    systolic_bp: Optional[float] = None
    diastolic_bp: Optional[float] = None
    respiratory_rate: Optional[float] = None
    temperature: Optional[float] = None
    spo2: Optional[float] = None
    lactate: Optional[float] = None


class ClinicalAnalysisRequest(BaseModel):
    patient_id: str


class WebSocketMessage(BaseModel):
    type: str
    payload: Dict[str, Any] = Field(default_factory=dict)


connections: List[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    try:
        await event_bus.connect()
    except Exception:
        pass
    logger.info("code_blue_ai_startup")
    yield
    await event_bus.disconnect()
    await close_db()
    logger.info("code_blue_ai_shutdown")


app = FastAPI(
    title="Code Blue AI",
    description="Autonomous Clinical Emergency Agent Network",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws/clinical")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"status": "connected", "message": "Clinical WebSocket active"})
    except WebSocketDisconnect:
        connections.remove(websocket)


async def broadcast_event(event: Dict[str, Any]):
    for conn in connections:
        try:
            await conn.send_json(event)
        except Exception:
            pass


@app.get("/")
async def root():
    return {"service": "Code Blue AI", "status": "operational", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/v1/patients")
async def list_patients(
    unit_type: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50),
):
    async with get_db_session() as session:
        query = select(Patient).where(Patient.is_active == True)
        
        if unit_type:
            query = query.where(Patient.unit_type == unit_type)
        if risk_level:
            query = query.where(Patient.risk_level == risk_level)
        if search:
            search_term = f"%{search}%"
            query = query.where(Patient.mrn.ilike(search_term) | Patient.last_name.ilike(search_term))
        
        query = query.order_by(Patient.risk_level.desc()).limit(limit)
        result = await session.execute(query)
        patients = result.scalars().all()
        
        return [p.__dict__ for p in patients]


@app.get("/api/v1/patients/{patient_id}")
async def get_patient(patient_id: str):
    async with get_db_session() as session:
        result = await session.execute(
            select(Patient)
            .options(selectinload(Patient.vitals), selectinload(Patient.labs), selectinload(Patient.medications))
            .where(Patient.id == patient_id)
        )
        patient = result.scalar_one_or_none()
        
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        return {
            "id": patient.id,
            "mrn": patient.mrn,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
            "sex": patient.sex,
            "unit_type": patient.unit_type,
            "bed_number": patient.bed_number,
            "primary_diagnosis": patient.primary_diagnosis,
            "allergies": patient.allergies or [],
            "comorbidities": patient.comorbidities or [],
            "risk_level": patient.risk_level,
            "vitals": [v.__dict__ for v in patient.vitals[-10:]],
            "labs": [l.__dict__ for l in patient.labs[-10:]],
            "medications": [m.__dict__ for m in patient.medications],
        }


@app.post("/api/v1/vitals")
async def create_vital(vital: VitalCreate):
    async with get_db_session() as session:
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
        
        patient_result = await session.execute(select(Patient).where(Patient.id == vital.patient_id))
        patient = patient_result.scalar_one_or_none()
        
        if patient:
            vitals_dict = vital.model_dump(exclude={"patient_id"})
            vitals_dict["map"] = new_vital.mean_arterial_pressure
            analysis = monitor_agent.analyze_clinical_picture(patient.id, patient.mrn, vitals_dict)
            
            if analysis["alerts"]:
                await broadcast_event({
                    "type": "ALERT",
                    "patient_id": patient.id,
                    "mrn": patient.mrn,
                    "alerts": analysis["alerts"],
                    "scores": analysis["scores"],
                    "timestamp": datetime.utcnow().isoformat(),
                })
            
            return {"vital_id": new_vital.id, "analysis": analysis}
        
        return {"vital_id": new_vital.id}


@app.post("/api/v1/analyze/{patient_id}")
async def analyze_patient(patient_id: str):
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


@app.post("/api/v1/demo/trigger")
async def trigger_demo():
    async with get_db_session() as session:
        result = await session.execute(select(Patient).order_by(Patient.risk_level.desc()).limit(1))
        patient = result.scalar_one_or_none()
        
        if not patient:
            return {"status": "no_active_patients"}
        
        await broadcast_event({
            "type": "DEMO_START",
            "patient_id": patient.id,
            "mrn": patient.mrn,
            "patient_name": f"{patient.first_name} {patient.last_name}",
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
        
        analysis = monitor_agent.analyze_clinical_picture(patient.id, patient.mrn, vitals)
        
        await broadcast_event({
            "type": "AGENT_MESSAGE",
            "agent": "MonitorAgent",
            "message": f"Detecting deterioration in patient {patient.mrn}",
            "severity": "CRITICAL",
            "data": analysis,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        return {
            "status": "demo_triggered",
            "patient_id": patient.id,
            "mrn": patient.mrn,
            "initial_vitals": vitals,
            "analysis": analysis,
        }


@app.get("/api/v1/agent-feed")
async def get_agent_feed(limit: int = Query(20)):
    async with get_db_session() as session:
        result = await session.execute(
            select(AgentMessage).order_by(AgentMessage.timestamp.desc()).limit(limit)
        )
        messages = result.scalars().all()
        
        return [
            {
                "id": m.id,
                "agent_id": m.agent_id,
                "agent_type": m.agent_type,
                "message_type": m.message_type,
                "content": m.content,
                "patient_id": m.patient_id,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in messages
        ]


@app.post("/api/v1/mcp/execute")
async def execute_mcp_tool(request: Dict[str, Any]):
    from mcp_server.server import MCPToolRequest
    mcp_request = MCPToolRequest(
        tool=request.get("tool", ""),
        arguments=request.get("arguments", {}),
    )
    result = await mcp_server.execute_tool(mcp_request)
    return result.model_dump()


@app.get("/api/v1/mcp/tools")
async def list_mcp_tools():
    return {"tools": mcp_server.list_tools()}


@app.get("/api/v1/a2a/status")
async def a2a_status():
    return message_bus.get_stats()
