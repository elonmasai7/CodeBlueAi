import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any

FIRST_NAMES = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda", "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen", "Daniel", "Nancy", "Matthew", "Lisa", "Anthony", "Betty", "Mark", "Margaret", "Donald", "Sandra", "Steven", "Ashley", "Paul", "Kimberly", "Andrew", "Emily", "Joshua", "Donna", "Kenneth", "Michelle", "Kevin", "Dorothy", "Brian", "Carol", "George", "Amanda", "Timothy", "Melissa", "Ronald", "Deborah"]

LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts"]

SEED_DIAGNOSES = [
    "Community Acquired Pneumonia", "Acute Exacerbation of COPD", "Sepsis - Urinary Source",
    "Acute Myocardial Infarction", "Ischemic Stroke", "Hemorrhagic Stroke",
    "Diabetic Ketoacidosis", "Upper GI Bleed", "Acute Pancreatitis",
    "Pulmonary Embolism", "Acute Kidney Injury", "Cellulitis",
    "CHF Exacerbation", "Atrial Fibrillation with RVR", "Deep Vein Thrombosis",
    "Spontaneous Pneumothorax", "Acute Appendicitis", "Cholecystitis",
    "Meningitis", "Traumatic Brain Injury", "Hip Fracture",
    "Sepsis - Pulmonary Source", "Sepsis - Abdominal Source", "Septic Shock",
    "Respiratory Failure", "Metabolic Acidosis", "Hypertensive Emergency",
]

SEED_MEDICATIONS = [
    {"name": "Vancomycin", "dosage": "1g", "route": "IV", "frequency": "q12h"},
    {"name": "Piperacillin-Tazobactam", "dosage": "4.5g", "route": "IV", "frequency": "q6h"},
    {"name": "Ceftriaxone", "dosage": "1g", "route": "IV", "frequency": "q24h"},
    {"name": "Metronidazole", "dosage": "500mg", "route": "IV", "frequency": "q8h"},
    {"name": "Heparin", "dosage": "5000 units", "route": "SC", "frequency": "q12h"},
    {"name": "Enoxaparin", "dosage": "40mg", "route": "SC", "frequency": "q24h"},
    {"name": "Lisinopril", "dosage": "10mg", "route": "PO", "frequency": "q24h"},
    {"name": "Metoprolol", "dosage": "25mg", "route": "PO", "frequency": "q12h"},
    {"name": "Aspirin", "dosage": "81mg", "route": "PO", "frequency": "q24h"},
    {"name": "Atorvastatin", "dosage": "80mg", "route": "PO", "frequency": "q24h"},
    {"name": "Furosemide", "dosage": "40mg", "route": "IV", "frequency": "q12h"},
    {"name": "Insulin Glargine", "dosage": "20 units", "route": "SC", "frequency": "q24h"},
    {"name": "Insulin Aspart", "dosage": "4 units", "route": "SC", "frequency": "AC"},
    {"name": "Morphine", "dosage": "2mg", "route": "IV", "frequency": "PRN"},
    {"name": "Ondansetron", "dosage": "4mg", "route": "IV", "frequency": "q8h"},
    {"name": "Pantoprazole", "dosage": "40mg", "route": "IV", "frequency": "q24h"},
    {"name": "Dexamethasone", "dosage": "4mg", "route": "IV", "frequency": "q6h"},
    {"name": "Acetaminophen", "dosage": "650mg", "route": "PO", "frequency": "q6h"},
    {"name": "Oxygen", "dosage": "2-4L/min", "route": "NC", "frequency": "Continuous"},
    {"name": "NS 0.9%", "dosage": "1000mL", "route": "IV", "frequency": "q8h"},
]

SEED_ALLERGIES = [
    "Penicillin", "Sulfa drugs", "Iodine contrast", "Latex", "Codeine",
    "Morphine", "Aspirin", "NSAIDs", "Cephalosporins", "Vancomycin",
]

LAB_TESTS = [
    {"name": "WBC", "unit": "10^3/uL", "low": 4.5, "high": 11.0},
    {"name": "Hemoglobin", "unit": "g/dL", "low": 12.0, "high": 17.5},
    {"name": "Platelets", "unit": "10^3/uL", "low": 150, "high": 400},
    {"name": "Sodium", "unit": "mEq/L", "low": 136, "high": 145},
    {"name": "Potassium", "unit": "mEq/L", "low": 3.5, "high": 5.0},
    {"name": "Creatinine", "unit": "mg/dL", "low": 0.7, "high": 1.3},
    {"name": "BUN", "unit": "mg/dL", "low": 7, "high": 20},
    {"name": "Glucose", "unit": "mg/dL", "low": 70, "high": 100},
    {"name": "Lactate", "unit": "mmol/L", "low": 0.5, "high": 2.2},
    {"name": "Troponin I", "unit": "ng/mL", "low": 0, "high": 0.04},
    {"name": "CRP", "unit": "mg/L", "low": 0, "high": 10},
    {"name": "Procalcitonin", "unit": "ng/mL", "low": 0, "high": 0.25},
    {"name": "pH", "unit": "", "low": 7.35, "high": 7.45},
    {"name": "pCO2", "unit": "mmHg", "low": 35, "high": 45},
    {"name": "pO2", "unit": "mmHg", "low": 80, "high": 100},
]


def generate_mrn() -> str:
    return f"MRN{random.randint(10000000, 99999999)}"


def generate_patients_data(count: int) -> List[Dict[str, Any]]:
    patients = []
    now = datetime.utcnow()
    
    for i in range(count):
        age = random.randint(18, 95)
        dob = now - timedelta(days=age * 365 + random.randint(0, 364))
        admission_days_ago = random.randint(0, 14)
        admission = now - timedelta(hours=admission_days_ago * 24)
        unit = random.choice(["ICU", "ER", "TELEMETRY", "MED_SURG"])
        
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        
        diagnosis = random.choice(SEED_DIAGNOSES)
        risk = determine_risk_level(diagnosis, unit)
        
        vitals = generate_vitals_series(admission, unit, risk)
        labs = generate_labs(now, diagnosis, risk)
        meds = random.sample(SEED_MEDICATIONS, random.randint(3, 8))
        allergies = random.sample(SEED_ALLERGIES, random.randint(0, 3))
        
        comorbidities = generate_comorbidities(diagnosis)
        
        bed = f"{random.choice(['A','B','C','D'])}{random.randint(1, 20)}"
        
        patient = {
            "mrn": generate_mrn(),
            "first_name": first,
            "last_name": last,
            "date_of_birth": dob,
            "sex": random.choice(["M", "F"]),
            "unit_type": unit,
            "bed_number": bed,
            "admission_date": admission,
            "primary_diagnosis": diagnosis,
            "allergies": allergies,
            "comorbidities": comorbidities,
            "risk_level": risk,
            "vitals": vitals,
            "labs": labs,
            "medications": meds,
        }
        patients.append(patient)
    
    return patients


def determine_risk_level(diagnosis: str, unit: str) -> str:
    if unit == "ER":
        return random.choice(["HIGH", "MODERATE", "LOW"])
    if diagnosis in ["Septic Shock", "Acute MI", "Ischemic Stroke", "Hemorrhagic Stroke"]:
        return "CRITICAL"
    if diagnosis in ["Sepsis - Urinary Source", "Sepsis - Pulmonary Source", "Sepsis - Abdominal Source", "Pulmonary Embolism", "Diabetic Ketoacidosis"]:
        return "HIGH"
    if unit == "ICU":
        return random.choice(["HIGH", "MODERATE"])
    if diagnosis in ["CHF Exacerbation", "Acute Kidney Injury", "Cellulitis"]:
        return "MODERATE"
    return random.choice(["LOW", "NORMAL"])


def generate_vitals_series(admission: datetime, unit: str, risk: str) -> List[Dict[str, Any]]:
    vitals = []
    now = datetime.utcnow()
    hours_ago = int((now - admission).total_seconds() / 3600)
    readings = min(hours_ago, 48)
    
    base_hr = 75 if risk not in ["CRITICAL", "HIGH"] else 95
    base_sbp = 125 if risk not in ["CRITICAL", "HIGH"] else 95
    base_spo2 = 97 if risk not in ["CRITICAL", "HIGH"] else 91
    base_rr = 16 if risk not in ["CRITICAL", "HIGH"] else 24
    base_temp = 37.0 if risk not in ["CRITICAL", "HIGH"] else 38.5
    base_lactate = 1.2 if risk not in ["CRITICAL", "HIGH"] else 3.5
    
    for i in range(readings):
        ts = admission + timedelta(hours=i)
        jitter_hr = random.uniform(-5, 5)
        jitter_sbp = random.uniform(-8, 8)
        jitter_spo2 = random.uniform(-1, 1)
        jitter_rr = random.uniform(-2, 2)
        jitter_temp = random.uniform(-0.3, 0.3)
        jitter_lactate = random.uniform(-0.2, 0.2)
        
        if risk in ["CRITICAL", "HIGH"]:
            jitter_hr += random.uniform(5, 20)
            jitter_sbp -= random.uniform(5, 30)
            jitter_spo2 -= random.uniform(2, 6)
            jitter_rr += random.uniform(3, 8)
            jitter_temp += random.uniform(0.5, 1.5)
            jitter_lactate += random.uniform(0.5, 2.5)
        
        hr = max(40, min(180, base_hr + jitter_hr))
        sbp = max(60, min(200, base_sbp + jitter_sbp))
        spo2 = max(70, min(100, base_spo2 + jitter_spo2))
        rr = max(8, min(40, base_rr + jitter_rr))
        temp = max(35.0, min(41.0, base_temp + jitter_temp))
        lactate = max(0.5, min(8.0, base_lactate + jitter_lactate))
        
        vdata = {
            "timestamp": ts,
            "heart_rate": round(hr, 1),
            "systolic_bp": round(sbp, 1),
            "diastolic_bp": round(sbp - random.uniform(30, 50), 1),
            "map": round((sbp + (sbp - 40)) / 3, 1),
            "respiratory_rate": round(rr, 1),
            "temperature": round(temp, 1),
            "spo2": round(spo2, 1),
            "lactate": round(lactate, 2),
        }
        vitals.append(vdata)
    
    return vitals


def generate_labs(now: datetime, diagnosis: str, risk: str) -> List[Dict[str, Any]]:
    labs = []
    
    for test in LAB_TESTS:
        is_critical = False
        value = random.uniform(test["low"], test["high"])
        
        if risk in ["CRITICAL", "HIGH"]:
            if test["name"] == "Lactate":
                value = random.uniform(2.5, 6.0)
                is_critical = value > 4.0
            elif test["name"] == "WBC":
                value = random.uniform(12.0, 25.0)
                is_critical = value > 20.0
            elif test["name"] == "Troponin I":
                value = random.uniform(0.05, 5.0) if diagnosis == "Acute Myocardial Infarction" else random.uniform(0, 0.03)
                is_critical = value > 0.4
            elif test["name"] == "Creatinine":
                value = random.uniform(1.5, 4.0) if "Kidney" in diagnosis else value
                is_critical = value > 3.0
            elif test["name"] == "Glucose":
                value = random.uniform(250, 500) if "Diabetic" in diagnosis else value
        
        labs.append({
            "timestamp": now - timedelta(hours=random.randint(0, 12)),
            "test_name": test["name"],
            "value": round(value, 2),
            "unit": test["unit"],
            "reference_low": test["low"],
            "reference_high": test["high"],
            "is_critical": is_critical,
        })
    
    return labs


def generate_comorbidities(diagnosis: str) -> List[str]:
    base_comorbidities = ["Hypertension", "Hyperlipidemia", "Type 2 Diabetes"]
    specific = []
    
    if "Pneumonia" in diagnosis or "COPD" in diagnosis:
        specific.append("Asthma")
    if "CHF" in diagnosis or "MI" in diagnosis:
        specific.append("Heart Failure")
        specific.append("Coronary Artery Disease")
    if "Kidney" in diagnosis:
        specific.append("CKD Stage 3")
    if "Stroke" in diagnosis:
        specific.append("Atrial Fibrillation")
    if "Diabetes" in diagnosis:
        specific.append("Obesity")
    
    return list(set(base_comorbidities + specific))
