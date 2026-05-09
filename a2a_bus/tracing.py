from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.trace import set_span_in_context
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import structlog
import json

logger = structlog.get_logger()

tracer_provider = TracerProvider(
    resource=Resource.create({"service.name": "codeblue-ai", "service.version": "1.0.0"})
)
tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer("codeblue-a2a-bus")

propagator = TraceContextTextMapPropagator()


@dataclass
class TraceContext:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    baggage: Dict[str, str] = field(default_factory=dict)


@dataclass
class AgentSpan:
    agent_name: str
    operation: str
    trace_id: str
    span_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "OK"
    error_message: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: list[Dict[str, Any]] = field(default_factory=list)


class AgentTracer:
    def __init__(self, service_name: str = "codeblue-a2a"):
        self.service_name = service_name
        self._spans: list[AgentSpan] = []
        self._active_spans: Dict[str, Any] = {}
        self._tracer = trace.get_tracer(service_name)

    def start_span(
        self,
        agent_name: str,
        operation: str,
        parent_context: Optional[TraceContext] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> TraceContext:
        trace_id = parent_context.trace_id if parent_context else format(uuid.uuid4().hex[:16], 'x')
        span_id = format(uuid.uuid4().hex[:8], 'x')

        span = self._tracer.start_span(
            f"{agent_name}.{operation}",
            attributes={
                "agent.name": agent_name,
                "agent.operation": operation,
                "trace.id": trace_id,
                "span.id": span_id,
                **(attributes or {}),
            },
        )

        context = TraceContext(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_context.span_id if parent_context else None,
        )

        self._active_spans[span_id] = {
            "span": span,
            "agent_name": agent_name,
            "operation": operation,
            "start_time": datetime.utcnow(),
        }

        return context

    def add_event(self, span_id: str, name: str, attributes: Optional[Dict[str, Any]] = None):
        if span_id in self._active_spans:
            span_data = self._active_spans[span_id]
            span_data["span"].add_event(name, attributes=attributes or {})
            span_data["events"].append({
                "name": name,
                "timestamp": datetime.utcnow().isoformat(),
                "attributes": attributes,
            })

    def end_span(
        self,
        span_id: str,
        status: str = "OK",
        error_message: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        if span_id not in self._active_spans:
            logger.warning("end_span_not_found", span_id=span_id)
            return

        span_data = self._active_spans.pop(span_id)
        span = span_data["span"]
        end_time = datetime.utcnow()

        if status != "OK":
            span.set_status(Status(StatusCode.ERROR, error_message))
        else:
            span.set_status(Status(StatusCode.OK))

        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)

        span.end()

        agent_span = AgentSpan(
            agent_name=span_data["agent_name"],
            operation=span_data["operation"],
            trace_id=self._active_spans.get(span_id, {}).get("span", span).attributes.get("trace.id", "unknown"),
            span_id=span_id,
            start_time=span_data["start_time"],
            end_time=end_time,
            status=status,
            error_message=error_message,
            attributes=attributes or {},
            events=span_data.get("events", []),
        )
        self._spans.append(agent_span)

    def inject_context(self, carrier: Dict[str, str]) -> Dict[str, str]:
        span = trace.get_current_span()
        carrier = {}
        propagator.inject(carrier, set_span_in_context(span))
        return carrier

    def extract_context(self, carrier: Dict[str, str]) -> Optional[TraceContext]:
        context = propagator.extract(carrier)
        span = trace.get_current_span(context)
        if span:
            span_ctx = span.get_span_context()
            return TraceContext(
                trace_id=format(span_ctx.trace_id, '032x'),
                span_id=format(span_ctx.span_id, '016x'),
            )
        return None

    def get_trace(self, trace_id: str) -> list[AgentSpan]:
        return [s for s in self._spans if s.trace_id == trace_id]

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._spans)
        errors = sum(1 for s in self._spans if s.status != "OK")
        durations = [
            (s.end_time - s.start_time).total_seconds()
            for s in self._spans
            if s.end_time
        ]
        avg_duration = sum(durations) / len(durations) if durations else 0

        by_agent: Dict[str, int] = {}
        for s in self._spans:
            by_agent[s.agent_name] = by_agent.get(s.agent_name, 0) + 1

        return {
            "total_spans": total,
            "error_count": errors,
            "error_rate": errors / total if total > 0 else 0,
            "avg_duration_ms": avg_duration * 1000,
            "spans_by_agent": by_agent,
        }

    def clear_old_spans(self, max_age_hours: int = 24):
        cutoff = datetime.utcnow().timestamp() - (max_age_hours * 3600)
        self._spans = [
            s for s in self._spans
            if s.start_time.timestamp() > cutoff
        ]


agent_tracer = AgentTracer()
