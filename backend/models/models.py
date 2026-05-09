from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, Integer, Float, Boolean, Text, JSON, ForeignKey, Enum as SAEnum
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(AsyncAttrs, DeclarativeBase):
    pass


class SexEnum(str, Enum):
    M = "M"
    F = "F"
    OTHER = "OTHER"


class UnitType(str, Enum):
    ICU = "ICU"
    ER = "ER"
    TELEMETRY = "TELEMETRY"
    MED_SURG = "MED_SURG"


class RiskLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    NORMAL = "NORMAL"


class EventStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class AlertSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class Patient(Base):
    __tablename__ = "patients"

    id = Column(String, primary_key=True)
    mrn = Column(String(20), unique=True, nullable=False, index=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    date_of_birth = Column(DateTime)
    sex = Column(SAEnum(SexEnum), default=SexEnum.OTHER)
    unit_type = Column(SAEnum(UnitType), default=UnitType.MED_SURG)
    bed_number = Column(String(20))
    admission_date = Column(DateTime, default=datetime.utcnow)
    discharge_date = Column(DateTime, nullable=True)
    primary_diagnosis = Column(Text)
    allergies = Column(JSON, default=list)
    comorbidities = Column(JSON, default=list)
    risk_level = Column(SAEnum(RiskLevel), default=RiskLevel.NORMAL)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    vitals = relationship("VitalSign", back_populates="patient", cascade="all, delete-orphan")
    labs = relationship("LabResult", back_populates="patient", cascade="all, delete-orphan")
    medications = relationship("Medication", back_populates="patient", cascade="all, delete-orphan")
    events = relationship("ClinicalEvent", back_populates="patient", cascade="all, delete-orphan")


class VitalSign(Base):
    __tablename__ = "vital_signs"

    id = Column(String, primary_key=True)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    heart_rate = Column(Float)
    systolic_bp = Column(Float)
    diastolic_bp = Column(Float)
    mean_arterial_pressure = Column(Float)
    respiratory_rate = Column(Float)
    temperature = Column(Float)
    oxygen_saturation = Column(Float)
    spo2 = Column(Float)
    lactate = Column(Float)
    blood_glucose = Column(Float)
    gcs = Column(Float)

    news2_score = Column(Float)
    sofa_score = Column(Float)
    qsofa_score = Column(Float)

    patient = relationship("Patient", back_populates="vitals")


class LabResult(Base):
    __tablename__ = "lab_results"

    id = Column(String, primary_key=True)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    test_name = Column(String(100))
    value = Column(Float)
    unit = Column(String(50))
    reference_low = Column(Float)
    reference_high = Column(Float)
    is_critical = Column(Boolean, default=False)

    patient = relationship("Patient", back_populates="labs")


class Medication(Base):
    __tablename__ = "medications"

    id = Column(String, primary_key=True)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    name = Column(String(200))
    dosage = Column(String(100))
    route = Column(String(50))
    frequency = Column(String(50))
    start_date = Column(DateTime)
    end_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    patient = relationship("Patient", back_populates="medications")


class ClinicalEvent(Base):
    __tablename__ = "clinical_events"

    id = Column(String, primary_key=True)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    event_type = Column(String(100))
    severity = Column(SAEnum(AlertSeverity))
    status = Column(SAEnum(EventStatus), default=EventStatus.PENDING)
    title = Column(String(200))
    description = Column(Text)
    triggered_by = Column(String(100))
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    patient = relationship("Patient", back_populates="events")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user_id = Column(String(100))
    action = Column(String(100))
    resource_type = Column(String(100))
    resource_id = Column(String(100))
    details = Column(JSON, default=dict)
    ip_address = Column(String(50))
    user_agent = Column(Text)


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id = Column(String, primary_key=True)
    agent_id = Column(String(100))
    agent_type = Column(String(50))
    message_type = Column(String(50))
    content = Column(Text)
    patient_id = Column(String(100), nullable=True)
    session_id = Column(String(100))
    metadata = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    hashed_password = Column(String(255))
    role = Column(String(50), default="clinician")
    is_active = Column(Boolean, default=True)
    full_name = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)


class User(BaseModel):
    id: str
    username: str
    email: str
    role: str = "clinician"
    is_active: bool = True
    full_name: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 28800


class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[str] = None
    role: Optional[str] = None
