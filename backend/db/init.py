import asyncio
import re
from datetime import datetime, timedelta
from typing import Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.models.models import Patient, VitalSign, LabResult, Medication, ClinicalEvent, SexEnum, UnitType, RiskLevel, AlertSeverity, EventStatus
from fhir.synthetic_data import generate_patients_data, SEED_DIAGNOSES, SEED_MEDICATIONS

logger = structlog.get_logger()

UNITS = [UnitType.ICU, UnitType.ER, UnitType.TELEMETRY, UnitType.MED_SURG]
SEXES = [SexEnum.M, SexEnum.F]


async def seed_patients(session: AsyncSession, count: int = 1000):
    logger.info("seeding_patients", count=count)
    
    patients_data = generate_patients_data(count)
    
    for pdata in patients_data:
        patient = Patient(
            id=str(uuid.uuid4()),
            mrn=pdata["mrn"],
            first_name=pdata["first_name"],
            last_name=pdata["last_name"],
            date_of_birth=pdata["date_of_birth"],
            sex=pdata["sex"],
            unit_type=pdata["unit_type"],
            bed_number=pdata["bed_number"],
            admission_date=pdata["admission_date"],
            primary_diagnosis=pdata["primary_diagnosis"],
            allergies=pdata["allergies"],
            comorbidities=pdata["comorbidities"],
            risk_level=pdata["risk_level"],
        )
        session.add(patient)
        
        for vdata in pdata["vitals"]:
            vitals = VitalSign(
                id=str(uuid.uuid4()),
                patient_id=patient.id,
                timestamp=vdata["timestamp"],
                heart_rate=vdata["heart_rate"],
                systolic_bp=vdata["systolic_bp"],
                diastolic_bp=vdata["diastolic_bp"],
                mean_arterial_pressure=vdata["map"],
                respiratory_rate=vdata["respiratory_rate"],
                temperature=vdata["temperature"],
                oxygen_saturation=vdata["spo2"],
                spo2=vdata["spo2"],
                lactate=vdata["lactate"],
                gcs=15.0,
                news2_score=calculate_news2(vdata),
                sofa_score=calculate_sofa(vdata),
                qsofa_score=calculate_qsofa(vdata),
            )
            session.add(vitals)
        
        for ldata in pdata["labs"]:
            lab = LabResult(
                id=str(uuid.uuid4()),
                patient_id=patient.id,
                timestamp=ldata["timestamp"],
                test_name=ldata["test_name"],
                value=ldata["value"],
                unit=ldata["unit"],
                reference_low=ldata["reference_low"],
                reference_high=ldata["reference_high"],
                is_critical=ldata["is_critical"],
            )
            session.add(lab)
        
        for mdata in pdata["medications"]:
            med = Medication(
                id=str(uuid.uuid4()),
                patient_id=patient.id,
                name=mdata["name"],
                dosage=mdata["dosage"],
                route=mdata["route"],
                frequency=mdata["frequency"],
                start_date=mdata["start_date"],
                is_active=True,
            )
            session.add(med)
    
    await session.commit()
    logger.info("seeding_complete", count=count)


def calculate_news2(vitals: dict) -> float:
    score = 0
    rr = vitals.get("respiratory_rate", 18)
    hr = vitals.get("heart_rate", 70)
    sbp = vitals.get("systolic_bp", 120)
    spo2 = vitals.get("spo2", 96)
    temp = vitals.get("temperature", 37.0)
    
    if rr <= 11: score += 3
    elif rr <= 20: score += 1
    elif rr <= 24: score += 2
    else: score += 3
    
    if hr <= 40: score += 3
    elif hr <= 50: score += 1
    elif hr <= 90: score += 0
    elif hr <= 110: score += 1
    elif hr <= 130: score += 2
    else: score += 3
    
    if sbp <= 90: score += 3
    elif sbp <= 100: score += 2
    elif sbp <= 110: score += 1
    elif sbp <= 219: score += 0
    else: score += 3
    
    if spo2 <= 91: score += 3
    elif spo2 <= 93: score += 2
    elif spo2 <= 95: score += 1
    else: score += 0
    
    if temp <= 35.0: score += 3
    elif temp <= 36.0: score += 1
    elif temp <= 38.0: score += 0
    elif temp <= 39.0: score += 1
    else: score += 2
    
    return float(score)


def calculate_sofa(vitals: dict) -> float:
    score = 0.0
    spo2 = vitals.get("spo2", 98)
    map_val = vitals.get("map", 90)
    hr = vitals.get("heart_rate", 70)
    
    if spo2 < 80: score += 4
    elif spo2 < 100: score += 3
    elif spo2 < 150: score += 2
    elif spo2 < 250: score += 1
    
    if map_val < 70: score += 4
    elif map_val < 92: score += 3
    elif map_val < 125: score += 2
    else: score += 0
    
    if hr > 150: score += 4
    elif hr > 110: score += 3
    elif hr > 70: score += 1
    
    return float(score)


def calculate_qsofa(vitals: dict) -> float:
    score = 0.0
    rr = vitals.get("respiratory_rate", 18)
    sbp = vitals.get("systolic_bp", 120)
    altered = vitals.get("gcs", 15) < 15
    
    if rr >= 22: score += 1
    if sbp <= 100: score += 1
    if altered: score += 1
    
    return score


async def seed_demo_event(session: AsyncSession, patient_id: str):
    event = ClinicalEvent(
        id=str(uuid.uuid4()),
        patient_id=patient_id,
        event_type="SEPTIC_SHOCK_DETECTED",
        severity=AlertSeverity.CRITICAL,
        status=EventStatus.ACTIVE,
        title="Septic Shock Likely",
        description="Patient showing signs of septic shock - hypotension, tachycardia, hypoxia, rising lactate",
        triggered_by="MonitorAgent",
        metadata={
            "systolic_bp": 82,
            "heart_rate": 128,
            "spo2": 87,
            "lactate": 4.8,
            "temperature": 39.2,
            "news2": 12,
            "sofa": 11,
            "qsofa": 3,
        },
    )
    session.add(event)
    await session.commit()
    return event
