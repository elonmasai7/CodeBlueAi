from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import structlog
import uuid

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
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None


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
        self._processed_messages: List[A2AMessage] = []
        self._max_retries = 3
        self._max_processed_history = 500
        self._observers: List[Callable] = []
        self._trace_enabled = True

        self._register_default_contracts()
        self._setup_tracing_observer()

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

        self.register_contract(A2AContract(
            message_type="AGENT_RESPONSE",
            schema={
                "type": "object",
                "required": ["message_id", "result"],
                "properties": {
                    "message_id": {"type": "string"},
                    "result": {"type": "object"},
                    "error": {"type": "string"},
                }
            },
            required_agents=[],
        ))

    def _setup_tracing_observer(self):
        try:
            from a2a_bus.tracing import agent_tracer

            async def trace_observer(message: A2AMessage):
                if not self._trace_enabled:
                    return

                try:
                    if message.span_id:
                        agent_tracer.add_event(
                            message.span_id,
                            f"a2a.message.received",
                            {"message_type": message.message_type, "from_agent": message.from_agent}
                        )
                except Exception:
                    pass

            self.register_observer(trace_observer)
        except ImportError:
            logger.warning("tracing_not_available")

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
        if not message.id:
            message.id = str(uuid.uuid4())

        trace_id = message.trace_id or str(uuid.uuid4()).replace("-", "")[:16]
        span_id = str(uuid.uuid4()).replace("-", "")[:8]

        message.trace_id = trace_id
        message.span_id = span_id

        try:
            if message.message_type in self._contracts:
                contract = self._contracts[message.message_type]
                if not self._validate_message(message.payload, contract.schema):
                    logger.warning("a2a_validation_failed", message_id=message.id, message_type=message.message_type)
                    self._dead_letter_queue.append(message)
                    self._record_failure(message, "schema_validation_failed")
                    return False

            self._message_queue.append(message)
            await self._process_queue()

            await self._notify_observers(message)

            self._processed_messages.append(message)
            if len(self._processed_messages) > self._max_processed_history:
                self._processed_messages = self._processed_messages[-self._max_processed_history:]

            return True

        except Exception as e:
            logger.error("a2a_send_failed", message_id=message.id, error=str(e), message_type=message.message_type)
            if message.retry_count < self._max_retries:
                message.retry_count += 1
                self._message_queue.append(message)
            else:
                self._dead_letter_queue.append(message)
                self._record_failure(message, str(e))
            return False

    async def _deliver_to_handler(self, message: A2AMessage):
        handlers = self._handlers.get(message.message_type, [])

        if not handlers:
            logger.debug("a2a_no_handlers", message_type=message.message_type, message_id=message.id)
            return

        for handler in handlers:
            try:
                result = await handler(message)
                logger.info(
                    "a2a_handler_success",
                    message_id=message.id,
                    handler=handler.__name__,
                    message_type=message.message_type,
                    trace_id=message.trace_id,
                )
            except Exception as e:
                logger.error(
                    "a2a_handler_failed",
                    message_id=message.id,
                    handler=handler.__name__,
                    error=str(e),
                    trace_id=message.trace_id,
                )
                self._record_failure(message, f"handler_error: {str(e)}")

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

        for field_name in required:
            if field_name not in payload:
                return False

        return True

    def _record_failure(self, message: A2AMessage, error: str):
        try:
            from a2a_bus.tracing import agent_tracer

            if message.span_id:
                agent_tracer.end_span(
                    message.span_id,
                    status="ERROR",
                    error_message=error,
                    attributes={
                        "message.id": message.id,
                        "message.type": message.message_type,
                        "error": error,
                    }
                )
        except ImportError:
            pass

    def get_dead_letter_messages(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": m.id,
                "message_type": m.message_type,
                "from_agent": m.from_agent,
                "to_agent": m.to_agent,
                "retry_count": m.retry_count,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in self._dead_letter_queue
        ]

    def retry_dead_letter(self, message_id: str) -> bool:
        for i, msg in enumerate(self._dead_letter_queue):
            if msg.id == message_id:
                msg.retry_count = 0
                message = self._dead_letter_queue.pop(i)
                self._message_queue.append(message)
                logger.info("a2a_dlq_retry", message_id=message_id)
                return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        total_processed = len(self._processed_messages)
        failed_count = sum(1 for m in self._processed_messages if m.retry_count >= self._max_retries)

        by_type: Dict[str, int] = {}
        for m in self._processed_messages:
            by_type[m.message_type] = by_type.get(m.message_type, 0) + 1

        try:
            from a2a_bus.tracing import agent_tracer
            tracing_stats = agent_tracer.get_stats()
        except ImportError:
            tracing_stats = {}

        return {
            "queue_length": len(self._message_queue),
            "dead_letter_length": len(self._dead_letter_queue),
            "total_processed": total_processed,
            "failed_count": failed_count,
            "failure_rate": failed_count / total_processed if total_processed > 0 else 0,
            "registered_contracts": len(self._contracts),
            "registered_handlers": sum(len(h) for h in self._handlers.values()),
            "messages_by_type": by_type,
            "tracing": tracing_stats,
        }

    def enable_tracing(self, enabled: bool = True):
        self._trace_enabled = enabled


message_bus = A2AMessageBus()
