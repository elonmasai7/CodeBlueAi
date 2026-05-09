from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import structlog

logger = structlog.get_logger()


class AgentType(str, Enum):
    MONITOR = "MonitorAgent"
    DIAGNOSTIC = "DiagnosticAgent"
    GUIDELINE = "GuidelineAgent"
    COORDINATOR = "CoordinatorAgent"
    DOCUMENTATION = "DocumentationAgent"


@dataclass
class A2AMessage:
    id: str
    from_agent: str
    to_agent: str
    message_type: str
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    session_id: Optional[str] = None
    reply_to: Optional[str] = None
    retry_count: int = 0


@dataclass
class A2AContract:
    message_type: str
    schema: Dict[str, Any]
    required_agents: List[str] = field(default_factory=list)


class A2AMessageBus:
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
        self._contracts: Dict[str, A2AContract] = {}
        self._message_queue: List[A2AMessage] = []
        self._dead_letter_queue: List[A2AMessage] = []
        self._max_retries = 3
        self._observers: List[Callable] = []
        
        self._register_default_contracts()

    def _register_default_contracts(self):
        self.register_contract(A2AContract(
            message_type="VITAL_ALERT",
            schema={
                "type": "object",
                "required": ["patient_id", "mrn", "vitals"],
                "properties": {
                    "patient_id": {"type": "string"},
                    "mrn": {"type": "string"},
                    "vitals": {"type": "object"},
                }
            },
            required_agents=[AgentType.MONITOR],
        ))
        
        self.register_contract(A2AContract(
            message_type="DIAGNOSTIC_REQUEST",
            schema={
                "type": "object",
                "required": ["patient_id", "mrn", "clinical_data"],
                "properties": {
                    "patient_id": {"type": "string"},
                    "mrn": {"type": "string"},
                    "clinical_data": {"type": "object"},
                }
            },
            required_agents=[AgentType.DIAGNOSTIC],
        ))
        
        self.register_contract(A2AContract(
            message_type="GUIDELINE_REQUEST",
            schema={
                "type": "object",
                "required": ["patient_id", "mrn", "diagnosis"],
                "properties": {
                    "patient_id": {"type": "string"},
                    "mrn": {"type": "string"},
                    "diagnosis": {"type": "string"},
                }
            },
            required_agents=[AgentType.GUIDELINE],
        ))
        
        self.register_contract(A2AContract(
            message_type="ESCALATION_REQUEST",
            schema={
                "type": "object",
                "required": ["patient_id", "mrn", "risk_level", "diagnosis"],
                "properties": {
                    "patient_id": {"type": "string"},
                    "mrn": {"type": "string"},
                    "risk_level": {"type": "string"},
                    "diagnosis": {"type": "string"},
                }
            },
            required_agents=[AgentType.COORDINATOR],
        ))
        
        self.register_contract(A2AContract(
            message_type="DOCUMENTATION_REQUEST",
            schema={
                "type": "object",
                "required": ["patient_id", "mrn", "clinical_summary"],
                "properties": {
                    "patient_id": {"type": "string"},
                    "mrn": {"type": "string"},
                    "clinical_summary": {"type": "object"},
                }
            },
            required_agents=[AgentType.DOCUMENTATION],
        ))

    def register_contract(self, contract: A2AContract):
        self._contracts[contract.message_type] = contract
        logger.info("a2a_contract_registered", message_type=contract.message_type)

    def register_handler(self, message_type: str, handler: Callable):
        if message_type not in self._handlers:
            self._handlers[message_type] = []
        self._handlers[message_type].append(handler)
        logger.info("a2a_handler_registered", message_type=message_type)

    def register_observer(self, observer: Callable):
        self._observers.append(observer)

    async def send_message(self, message: A2AMessage) -> bool:
        try:
            if message.message_type in self._contracts:
                contract = self._contracts[message.message_type]
                if not self._validate_message(message.payload, contract.schema):
                    logger.warning("a2a_validation_failed", message_id=message.id)
                    self._dead_letter_queue.append(message)
                    return False
            
            if message.reply_to:
                await self._deliver_to_handler(message)
            else:
                self._message_queue.append(message)
                await self._process_queue()
            
            await self._notify_observers(message)
            
            return True
        except Exception as e:
            logger.error("a2a_send_failed", message_id=message.id, error=str(e))
            if message.retry_count < self._max_retries:
                message.retry_count += 1
                self._message_queue.append(message)
            else:
                self._dead_letter_queue.append(message)
            return False

    async def _deliver_to_handler(self, message: A2AMessage):
        handlers = self._handlers.get(message.message_type, [])
        for handler in handlers:
            try:
                result = await handler(message)
                if result:
                    logger.info("a2a_handler_success", message_id=message.id, handler=handler.__name__)
                    return
            except Exception as e:
                logger.error("a2a_handler_failed", message_id=message.id, handler=handler.__name__, error=str(e))

    async def _process_queue(self):
        while self._message_queue:
            message = self._message_queue.pop(0)
            await self._deliver_to_handler(message)

    async def _notify_observers(self, message: A2AMessage):
        for observer in self._observers:
            try:
                await observer(message)
            except Exception as e:
                logger.error("a2a_observer_failed", error=str(e))

    def _validate_message(self, payload: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        
        for field in required:
            if field not in payload:
                return False
        
        return True

    def get_dead_letter_messages(self) -> List[A2AMessage]:
        return self._dead_letter_queue.copy()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "queue_length": len(self._message_queue),
            "dead_letter_length": len(self._dead_letter_queue),
            "registered_contracts": len(self._contracts),
            "registered_handlers": sum(len(h) for h in self._handlers.values()),
        }


message_bus = A2AMessageBus()
