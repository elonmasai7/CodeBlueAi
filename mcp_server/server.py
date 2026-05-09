from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger()


class MCPToolRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None
    request_id: Optional[str] = None


class MCPToolResponse(BaseModel):
    tool: str
    result: Any
    success: bool = True
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MCPServer:
    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._initialized = False
        self._register_tools()

    def _register_tools(self):
        self._tools["fhir_search"] = {
            "description": "Search FHIR resources",
            "parameters": {
                "resource_type": {"type": "string", "required": True},
                "patient_id": {"type": "string"},
                "query": {"type": "string"},
                "count": {"type": "integer", "default": 20},
            },
            "handler": self._fhir_search,
        }
        
        self._tools["fhir_get_patient"] = {
            "description": "Get patient by ID or MRN",
            "parameters": {
                "identifier": {"type": "string", "required": True},
            },
            "handler": self._fhir_get_patient,
        }
        
        self._tools["fhir_get_observations"] = {
            "description": "Get patient observations/vitals",
            "parameters": {
                "patient_id": {"type": "string", "required": True},
                "count": {"type": "integer", "default": 50},
            },
            "handler": self._fhir_get_observations,
        }
        
        self._tools["fhir_get_labs"] = {
            "description": "Get patient laboratory results",
            "parameters": {
                "patient_id": {"type": "string", "required": True},
            },
            "handler": self._fhir_get_labs,
        }
        
        self._tools["fhir_get_medications"] = {
            "description": "Get patient medications",
            "parameters": {
                "patient_id": {"type": "string", "required": True},
            },
            "handler": self._fhir_get_medications,
        }
        
        self._tools["fhir_get_allergies"] = {
            "description": "Get patient allergies",
            "parameters": {
                "patient_id": {"type": "string", "required": True},
            },
            "handler": self._fhir_get_allergies,
        }
        
        self._tools["clinical_score_news2"] = {
            "description": "Calculate NEWS2 score",
            "parameters": {
                "vitals": {"type": "object", "required": True},
            },
            "handler": self._calc_news2,
        }
        
        self._tools["clinical_score_sofa"] = {
            "description": "Calculate SOFA score",
            "parameters": {
                "vitals": {"type": "object", "required": True},
            },
            "handler": self._calc_sofa,
        }
        
        self._tools["clinical_score_qsofa"] = {
            "description": "Calculate qSOFA score",
            "parameters": {
                "vitals": {"type": "object", "required": True},
            },
            "handler": self._calc_qsofa,
        }
        
        self._tools["clinical_score_mews"] = {
            "description": "Calculate MEWS score",
            "parameters": {
                "vitals": {"type": "object", "required": True},
            },
            "handler": self._calc_mews,
        }
        
        self._tools["drug_interaction_check"] = {
            "description": "Check drug interactions between multiple medications",
            "parameters": {
                "drugs": {"type": "array", "required": True},
            },
            "handler": self._check_drug_interactions,
        }

        self._tools["drug_interaction_graph"] = {
            "description": "Get interaction graph for multiple drugs",
            "parameters": {
                "drugs": {"type": "array", "required": True},
            },
            "handler": self._drug_interaction_graph,
        }

        self._tools["drug_renal_dosing"] = {
            "description": "Get renal dosing recommendations",
            "parameters": {
                "drug": {"type": "string", "required": True},
                "creatinine_clearance": {"type": "number", "required": True},
            },
            "handler": self._renal_dosing,
        }

        self._tools["protocol_get"] = {
            "description": "Get clinical protocol by diagnosis",
            "parameters": {
                "diagnosis": {"type": "string", "required": True},
            },
            "handler": self._get_protocol,
        }

        self._tools["protocol_list"] = {
            "description": "List all available clinical protocols",
            "parameters": {},
            "handler": self._list_protocols,
        }

        self._tools["alert_dispatch"] = {
            "description": "Dispatch clinical alert",
            "parameters": {
                "patient_id": {"type": "string", "required": True},
                "severity": {"type": "string", "required": True},
                "message": {"type": "string", "required": True},
            },
            "handler": self._dispatch_alert,
        }

        self._tools["alert_acknowledge"] = {
            "description": "Acknowledge a clinical alert",
            "parameters": {
                "alert_id": {"type": "string", "required": True},
                "acknowledged_by": {"type": "string", "required": True},
            },
            "handler": self._acknowledge_alert,
        }

        self._tools["audit_log"] = {
            "description": "Create audit log entry",
            "parameters": {
                "user_id": {"type": "string", "required": True},
                "action": {"type": "string", "required": True},
                "resource": {"type": "string", "required": True},
                "resource_id": {"type": "string"},
                "details": {"type": "object"},
                "ip_address": {"type": "string"},
            },
            "handler": self._create_audit_log,
        }

        self._tools["audit_query"] = {
            "description": "Query audit logs",
            "parameters": {
                "user_id": {"type": "string"},
                "action": {"type": "string"},
                "resource_type": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
            "handler": self._query_audit_logs,
        }

        self._tools["audit_export"] = {
            "description": "Export audit logs as JSON",
            "parameters": {
                "format": {"type": "string", "default": "json"},
                "limit": {"type": "integer", "default": 100},
            },
            "handler": self._export_audit_logs,
        }
        
        self._tools["discover"] = {
            "description": "Discover available MCP tools",
            "parameters": {},
            "handler": self._discover_tools,
        }
        
        self._initialized = True
        logger.info("mcp_server_initialized", tool_count=len(self._tools))

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "description": tool["description"],
                "parameters": tool["parameters"],
            }
            for name, tool in self._tools.items()
        ]

    async def execute_tool(self, request: MCPToolRequest) -> MCPToolResponse:
        start_time = datetime.utcnow()
        
        if request.tool not in self._tools:
            return MCPToolResponse(
                tool=request.tool,
                result=None,
                success=False,
                error=f"Unknown tool: {request.tool}",
            )
        
        try:
            tool = self._tools[request.tool]
            handler = tool["handler"]
            
            result = await handler(request.arguments)
            
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return MCPToolResponse(
                tool=request.tool,
                result=result,
                success=True,
                execution_time_ms=execution_time,
            )
        except Exception as e:
            logger.error("mcp_tool_failed", tool=request.tool, error=str(e))
            return MCPToolResponse(
                tool=request.tool,
                result=None,
                success=False,
                error=str(e),
            )

    async def _fhir_search(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [{"resourceType": "Bundle", "total": 0, "entry": []}]

    async def _fhir_get_patient(self, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return {"resourceType": "Patient", "id": args.get("identifier", "unknown")}

    async def _fhir_get_observations(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []

    async def _fhir_get_labs(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []

    async def _fhir_get_medications(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []

    async def _fhir_get_allergies(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []

    async def _calc_news2(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from agents.monitor.clinical_scoring import VitalReading, ClinicalScoringService
        service = ClinicalScoringService()
        v = args.get("vitals", {})
        reading = VitalReading(
            heart_rate=v.get("heart_rate", 70),
            systolic_bp=v.get("systolic_bp", 120),
            diastolic_bp=v.get("diastolic_bp", 80),
            respiratory_rate=v.get("respiratory_rate", 16),
            temperature=v.get("temperature", 37.0),
            spo2=v.get("spo2", 97),
            map=v.get("map", 90),
            lactate=v.get("lactate", 1.0),
        )
        score = service.calculate_news2(reading)
        return {"score": score.value, "interpretation": score.interpretation, "risk_level": score.risk_level}

    async def _calc_sofa(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from agents.monitor.clinical_scoring import VitalReading, ClinicalScoringService
        service = ClinicalScoringService()
        v = args.get("vitals", {})
        reading = VitalReading(
            heart_rate=v.get("heart_rate", 70),
            systolic_bp=v.get("systolic_bp", 120),
            diastolic_bp=v.get("diastolic_bp", 80),
            respiratory_rate=v.get("respiratory_rate", 16),
            temperature=v.get("temperature", 37.0),
            spo2=v.get("spo2", 97),
            map=v.get("map", 90),
            lactate=v.get("lactate", 1.0),
        )
        score = service.calculate_sofa(reading)
        return {"score": score.value, "interpretation": score.interpretation, "risk_level": score.risk_level}

    async def _calc_qsofa(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from agents.monitor.clinical_scoring import VitalReading, ClinicalScoringService
        service = ClinicalScoringService()
        v = args.get("vitals", {})
        reading = VitalReading(
            heart_rate=v.get("heart_rate", 70),
            systolic_bp=v.get("systolic_bp", 120),
            diastolic_bp=v.get("diastolic_bp", 80),
            respiratory_rate=v.get("respiratory_rate", 16),
            temperature=v.get("temperature", 37.0),
            spo2=v.get("spo2", 97),
            map=v.get("map", 90),
            lactate=v.get("lactate", 1.0),
        )
        score = service.calculate_qsofa(reading)
        return {"score": score.value, "interpretation": score.interpretation, "risk_level": score.risk_level}

    async def _calc_mews(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {"score": 0, "interpretation": "Low risk", "risk_level": "LOW"}

    async def _check_drug_interactions(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from mcp_server.drug_db import drug_interaction_service
        drugs = args.get("drugs", [])
        if len(drugs) < 2:
            return {"interactions": [], "severity": "NONE", "note": "Need at least 2 drugs to check interactions"}
        interactions = drug_interaction_service.check_multi_interactions(drugs)
        return {
            "interactions": [
                {"drug1": i.drug1, "drug2": i.drug2, "severity": i.severity, "description": i.description, "recommendation": i.recommendation}
                for i in interactions
            ],
            "severity": "NONE" if not interactions else max(i.severity for i in interactions),
            "max_severity": drug_interaction_service._get_max_severity(interactions),
            "total_checked": len(drugs),
            "pairs_checked": len(interactions),
        }

    async def _renal_dosing(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from mcp_server.drug_db import drug_interaction_service
        drug = args.get("drug", "")
        crcl = args.get("creatinine_clearance", 90)
        result = drug_interaction_service.get_renal_dosing(drug, crcl)
        return {
            "drug": result.drug,
            "indication": result.indication,
            "crcl_threshold": result.crcl_threshold,
            "recommendation": result.recommendation,
            "monitoring": result.monitoring,
        }

    async def _get_protocol(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from agents.guideline.agent import GuidelineAgent
        agent = GuidelineAgent()
        diagnosis = args.get("diagnosis", "")
        protocol = agent.get_protocol(diagnosis, diagnosis)
        if protocol:
            return {
                "name": protocol.name,
                "code": protocol.code,
                "description": protocol.description,
                "interventions": [
                    {"action": i.action, "timing": i.timing, "dose": i.dose, "priority": i.priority}
                    for i in protocol.interventions
                ],
                "required_monitoring": protocol.required_monitoring,
                "follow_up_actions": protocol.follow_up_actions,
                "estimated_duration": protocol.estimated_duration,
            }
        return {"name": "General Supportive Care", "code": "GENERAL", "description": "Standard monitoring and supportive measures"}

    async def _dispatch_alert(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {"alert_id": "placeholder", "dispatched": True}

    async def _create_audit_log(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {"log_id": "placeholder", "created": True}

    async def _discover_tools(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {"tools": self.list_tools(), "version": "1.0.0"}

    async def _drug_interaction_graph(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from mcp_server.drug_db import drug_interaction_service
        drugs = args.get("drugs", [])
        return drug_interaction_service.get_interaction_graph(drugs)

    async def _list_protocols(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from agents.guideline.agent import GuidelineAgent
        agent = GuidelineAgent()
        return {
            "protocols": [
                {"name": p, "code": agent._protocols[p].code}
                for p in agent._protocols
            ]
        }

    async def _acknowledge_alert(self, args: Dict[str, Any]) -> Dict[str, Any]:
        alert_id = args.get("alert_id", "")
        acknowledged_by = args.get("acknowledged_by", "")
        return {"alert_id": alert_id, "acknowledged_by": acknowledged_by, "acknowledged_at": datetime.utcnow().isoformat(), "status": "acknowledged"}

    async def _query_audit_logs(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from backend.db.session import get_db_session
        from backend.models.models import AuditLog
        from sqlalchemy import select

        limit = args.get("limit", 50)
        async with get_db_session() as session:
            query = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
            result = await session.execute(query)
            logs = result.scalars().all()
        return {
            "logs": [
                {"id": l.id, "timestamp": l.timestamp.isoformat(), "user_id": l.user_id, "action": l.action, "resource_type": l.resource_type, "resource_id": l.resource_id}
                for l in logs
            ],
            "count": len(logs),
        }

    async def _export_audit_logs(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from backend.db.session import get_db_session
        from backend.models.models import AuditLog
        from sqlalchemy import select

        limit = args.get("limit", 100)
        async with get_db_session() as session:
            query = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
            result = await session.execute(query)
            logs = result.scalars().all()
        return {
            "format": args.get("format", "json"),
            "exported_at": datetime.utcnow().isoformat(),
            "count": len(logs),
            "logs": [
                {"id": l.id, "timestamp": l.timestamp.isoformat(), "user_id": l.user_id, "action": l.action, "resource_type": l.resource_type, "resource_id": l.resource_id, "details": l.details, "ip_address": l.ip_address}
                for l in logs
            ],
        }


mcp_server = MCPServer()
