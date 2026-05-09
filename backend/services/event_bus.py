from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import asyncio
import json
import random

import redis.asyncio as redis
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.models.models import Patient, VitalSign, LabResult, Medication, ClinicalEvent, EventStatus
from agents.monitor.clinical_scoring import calculate_news2, calculate_sofa, calculate_qsofa

logger = structlog.get_logger()

PUBSUB_CHANNEL = "codeblue:events"


class EventBus:
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._redis: Optional[redis.Redis] = None
        self._pubsub = None

    async def connect(self):
        self._redis = redis.from_url(self.redis_url, decode_responses=True)
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(PUBSUB_CHANNEL)
        logger.info("eventbus_connected", channel=PUBSUB_CHANNEL)

    async def disconnect(self):
        if self._pubsub:
            await self._pubsub.unsubscribe(PUBSUB_CHANNEL)
        if self._redis:
            await self._redis.close()

    async def publish(self, event: Dict[str, Any]):
        if self._redis:
            await self._redis.publish(PUBSUB_CHANNEL, json.dumps(event))

    async def subscribe(self):
        if self._pubsub:
            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    yield json.loads(message["data"])


class ClinicalEventGenerator:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._running = False

    async def start(self, interval: int = 30):
        self._running = True
        logger.info("clinical_event_generator_started", interval=interval)
        
        while self._running:
            try:
                await self.generate_deterioration_event()
            except Exception as e:
                logger.error("event_generation_failed", error=str(e))
            await asyncio.sleep(interval)

    def stop(self):
        self._running = False
        logger.info("clinical_event_generator_stopped")

    async def generate_deterioration_event(self):
        async with get_db_session() as session:
            result = await session.execute(
                select(Patient).where(Patient.is_active == True).order_by(Patient.risk_level.desc()).limit(1)
            )
            patient = result.scalar_one_or_none()
            
            if not patient:
                return

            event_data = {
                "type": "VITAL_ALERT",
                "patient_id": patient.id,
                "mrn": patient.mrn,
                "timestamp": datetime.utcnow().isoformat(),
                "severity": "HIGH",
                "title": "Patient Deterioration Detected",
                "description": f"Patient {patient.first_name} {patient.last_name} showing signs of clinical deterioration",
                "data": {
                    "heart_rate": random.uniform(100, 140),
                    "systolic_bp": random.uniform(80, 95),
                    "spo2": random.uniform(85, 92),
                    "respiratory_rate": random.uniform(22, 30),
                    "temperature": random.uniform(38.5, 39.5),
                    "lactate": random.uniform(3.0, 5.5),
                },
            }
            
            await self.event_bus.publish(event_data)
            logger.info("deterioration_event_published", patient_id=patient.id, mrn=patient.mrn)


event_bus = EventBus(redis_url="redis://localhost:6379")
clinical_event_generator = ClinicalEventGenerator(event_bus)
