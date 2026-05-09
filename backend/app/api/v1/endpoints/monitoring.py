from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.models.patient import Patient
from app.models.fhir import Observation, Encounter, Condition
from app.schemas.patient import PatientInDB
from datetime import datetime, timedelta
import random

router = APIRouter()

# Mock data for demonstration - in real implementation, this would come from FHIR server
def generate_mock_vitals():
    return {
        "heart_rate": random.randint(60, 120),
        "respiratory_rate": random.randint(12, 25),
        "temperature": round(random.uniform(36.0, 39.0), 1),
        "map": random.randint(65, 110),
        "o2_sat": random.randint(90, 100),
        "lactate": round(random.uniform(0.5, 4.0), 1),
        "wbc": round(random.uniform(4.0, 15.0), 1)
    }

def calculate_news2(vitals):
    score = 0
    # Respiratory rate
    rr = vitals["respiratory_rate"]
    if rr <= 8:
        score += 3
    elif rr <= 11:
        score += 1
    elif rr <= 20:
        score += 0
    elif rr <= 24:
        score += 2
    else:
        score += 3
    
    # Oxygen saturation
    spo2 = vitals["o2_sat"]
    if spo2 <= 91:
        score += 3
    elif spo2 <= 93:
        score += 2
    elif spo2 <= 95:
        score += 1
    else:
        score += 0
    
    # Systolic BP (using MAP as approximation)
    map_val = vitals["map"]
    if map_val <= 70:
        score += 3
    elif map_val <= 80:
        score += 2
    elif map_val <= 100:
        score += 0
    elif map_val <= 110:
        score += 1
    else:
        score += 3
    
    # Heart rate
    hr = vitals["heart_rate"]
    if hr <= 40:
        score += 3
    elif hr <= 50:
        score += 1
    elif hr <= 90:
        score += 0
    elif hr <= 110:
        score += 1
    elif hr <= 130:
        score += 2
    else:
        score += 3
    
    # Temperature
    temp = vitals["temperature"]
    if temp <= 35.0:
        score += 3
    elif temp <= 36.0:
        score += 1
    elif temp <= 38.0:
        score += 0
    elif temp <= 39.0:
        score += 1
    else:
        score += 2
    
    # AVPU (simplified as normal for mock)
    # In real implementation, this would come from neurological assessment
    
    return score

def calculate_sofa(vitals, labs=None):
    # Simplified SOFA score calculation
    score = 0
    
    # Respiratory (PaO2/FiO2 ratio - approximated from SpO2)
    spo2 = vitals["o2_sat"]
    if spo2 < 90:
        score += 4
    elif spo2 < 95:
        score += 3
    elif spo2 < 97:
        score += 2
    elif spo2 < 98:
        score += 1
    else:
        score += 0
    
    # Cardiovascular (MAP)
    map_val = vitals["map"]
    if map_val < 70:
        score += 3
    elif map_val < 100:
        score += 2
    elif map_val < 110:
        score += 1
    else:
        score += 0
    
    # Hepatic (bilirubin - not available in mock, assume normal)
    # Coagulation (platelets - not available in mock, assume normal)
    # Neurological (GCS - not available in mock, assume normal)
    # Renal (creatinine - not available in mock, assume normal)
    
    return score

def calculate_qsofa(vitals):
    score = 0
    # Respiratory rate >= 22
    if vitals["respiratory_rate"] >= 22:
        score += 1
    # Systolic BP <= 100 mmHg (approximated from MAP)
    if vitals["map"] <= 70:
        score += 1
    # Altered mental status (simplified)
    # In real implementation, this would come from neurological assessment
    return score

@router.get("/patients", response_model=List[dict])
async def get_patients_with_vitals(db: Session = Depends(get_db)):
    """
    Get all patients with their current vitals and scores.
    """
    patients = db.query(Patient).limit(50).all()
    result = []
    
    for patient in patients:
        vitals = generate_mock_vitals()
        news2 = calculate_news2(vitals)
        sofa = calculate_sofa(vitals)
        qsofa = calculate_qsofa(vitals)
        
        # Determine risk level
        if news2 >= 7 or sofa >= 3 or qsofa >= 2:
            risk = "critical"
        elif news2 >= 5 or sofa >= 2 or qsofa >= 1:
            risk = "high"
        elif news2 >= 3 or sofa >= 1:
            risk = "medium"
        else:
            risk = "low"
        
        result.append({
            "id": patient.id,
            "mrn": patient.mrn,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "age": (datetime.now() - patient.birth_date).days // 365,
            "gender": patient.gender.value if hasattr(patient.gender, 'value') else str(patient.gender),
            "bed_number": f"B{random.randint(1, 50):02d}",
            "diagnosis": random.choice(["Pneumonia", "CHF", "COPD Exacerbation", "Sepsis", "Post-Op", "None"]),
            "risk": risk,
            "vitals": vitals,
            "scores": {
                "news2": news2,
                "sofa": sofa,
                "qsofa": qsofa
            },
            "last_updated": datetime.now().isoformat()
        })
    
    return result

@router.get("/patients/{patient_id}", response_model=dict)
async def get_patient_detail(patient_id: int, db: Session = Depends(get_db)):
    """
    Get detailed information for a specific patient including trends.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Generate mock trend data
    trends = {}
    for vital in ["heart_rate", "respiratory_rate", "temperature", "map", "o2_sat", "lactate", "wbc"]:
        base_value = generate_mock_vitals()[vital]
        # Generate 24 hours of data with some variation
        trends[vital] = [
            {
                "time": (datetime.now() - timedelta(hours=x)).isoformat(),
                "value": base_value + random.uniform(-5, 5)
            }
            for x in range(24, 0, -1)
        ]
    
    return {
        "id": patient.id,
        "mrn": patient.mrn,
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "birth_date": patient.birth_date.isoformat(),
        "gender": patient.gender.value if hasattr(patient.gender, 'value') else str(patient.gender),
        "vitals": generate_mock_vitals(),
        "scores": {
            "news2": calculate_news2(generate_mock_vitals()),
            "sofa": calculate_sofa(generate_mock_vitals()),
            "qsofa": calculate_qsofa(generate_mock_vitals())
        },
        "trends": trends,
        "recent_observations": [],  # Would come from FHIR in real implementation
        "active_conditions": [],    # Would come from FHIR in real implementation
        "medications": [],          # Would come from FHIR in real implementation
        "allergies": []             # Would come from FHIR in real implementation
    }

@router.post("/patients/{patient_id}/alert")
async def create_patient_alert(patient_id: int, alert_data: dict, db: Session = Depends(get_db)):
    """
    Create an alert for a patient (simulating agent detection).
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # In real implementation, this would store the alert in database
    # and trigger notifications via the A2A bus
    return {
        "status": "alert_created",
        "patient_id": patient_id,
        "alert": alert_data,
        "timestamp": datetime.now().isoformat()
    }
