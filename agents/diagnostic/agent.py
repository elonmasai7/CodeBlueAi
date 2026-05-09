from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger()


@dataclass
class Diagnosis:
    code: str
    name: str
    probability: float
    evidence: List[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class DiagnosticReport:
    patient_id: str
    mrn: str
    differential: List[Diagnosis]
    primary_diagnosis: Optional[Diagnosis] = None
    risk_prediction: Dict[str, Any] = field(default_factory=dict)
    confidence: str = "MODERATE"
    timestamp: datetime = field(default_factory=datetime.utcnow)


class DiagnosticAgent:
    def __init__(self):
        self._sepsis_ddx = [
            "Community Acquired Pneumonia",
            "Urinary Tract Infection leading to Sepsis",
            "Abdominal Sepsis - Bowel Perforation",
            "Soft Tissue Infection - Necrotizing Fasciitis",
            "Ventilator Associated Pneumonia",
            "Clostridioides difficile Colitis",
            "Acute Cholecystitis",
            "Acute Pancreatitis",
            "Spontaneous Bacterial Peritonitis",
        ]
        self._cardiac_ddx = [
            "STEMI - Anterior Wall",
            "STEMI - Inferior Wall",
            "Non-STEMI (NSTEMI)",
            "Unstable Angina",
            "Takotsubo Cardiomyopathy",
            "Aortic Dissection",
            "Pulmonary Embolism",
            "Pericarditis",
        ]
        self._neuro_ddx = [
            "Ischemic Stroke - MCA Territory",
            "Ischemic Stroke - PCA Territory",
            "Hemorrhagic Stroke - Basal Ganglia",
            "Subarachnoid Hemorrhage",
            "Seizure - Generalized",
            "Status Epilepticus",
            "Menigitis/Encephalitis",
            "Hypertensive Encephalopathy",
        ]

    async def analyze(
        self,
        patient_id: str,
        mrn: str,
        vitals: Dict[str, float],
        labs: List[Dict[str, Any]],
        medications: List[Dict[str, Any]],
        allergies: List[str],
        comorbidities: List[str],
        primary_diagnosis: str,
    ) -> DiagnosticReport:
        differential = []
        
        if self._is_sepsis_suspected(vitals, labs):
            differential.extend(self._analyze_sepsis(vitals, labs, medications, allergies))
        
        if self._is_cardiac_suspected(vitals, labs):
            differential.extend(self._analyze_cardiac(vitals, labs))
        
        if self._is_neuro_suspected(vitals):
            differential.extend(self._analyze_neuro(vitals, labs))
        
        if not differential:
            differential.append(Diagnosis(
                code="Z00", name="General Examination", probability=0.85, evidence=["No acute findings"]
            ))
        
        differential.sort(key=lambda x: x.probability, reverse=True)
        
        primary = differential[0] if differential else None
        
        risk_prediction = self._predict_risk(vitals, labs, primary)
        
        return DiagnosticReport(
            patient_id=patient_id,
            mrn=mrn,
            differential=differential,
            primary_diagnosis=primary,
            risk_prediction=risk_prediction,
            confidence=self._assess_confidence(labs, vitals),
        )

    def _is_sepsis_suspected(self, vitals: Dict[str, float], labs: List[Dict[str, Any]]) -> bool:
        lactate = next((l["value"] for l in labs if l["test_name"] == "Lactate"), 1.0)
        wbc = next((l["value"] for l in labs if l["test_name"] == "WBC"), 8.0)
        temp = vitals.get("temperature", 37.0)
        hr = vitals.get("heart_rate", 70)
        rr = vitals.get("respiratory_rate", 16)
        
        criteria_met = 0
        if temp > 38 or temp < 36: criteria_met += 1
        if hr > 90: criteria_met += 1
        if rr > 20: criteria_met += 1
        if wbc > 12 or wbc < 4: criteria_met += 1
        if lactate > 2.0: criteria_met += 1
        
        return criteria_met >= 2

    def _is_cardiac_suspected(self, vitals: Dict[str, float], labs: List[Dict[str, Any]]) -> bool:
        troponin = next((l["value"] for l in labs if l["test_name"] == "Troponin I"), 0.0)
        sbp = vitals.get("systolic_bp", 120)
        hr = vitals.get("heart_rate", 70)
        
        return troponin > 0.04 or (sbp < 90 and hr > 100)

    def _is_neuro_suspected(self, vitals: Dict[str, float]) -> bool:
        gcs = vitals.get("gcs", 15)
        sbp = vitals.get("systolic_bp", 120)
        
        return gcs < 14 or sbp > 180

    def _analyze_sepsis(self, vitals: Dict[str, float], labs: List[Dict[str, Any]], medications: List[Dict], allergies: List[str]) -> List[Diagnosis]:
        diagnoses = []
        lactate = next((l["value"] for l in labs if l["test_name"] == "Lactate"), 1.0)
        wbc = next((l["value"] for l in labs if l["test_name"] == "WBC"), 8.0)
        crp = next((l["value"] for l in labs if l["test_name"] == "CRP"), 5.0)
        procalcitonin = next((l["value"] for l in labs if l["test_name"] == "Procalcitonin"), 0.1)
        
        evidence = [f"Lactate: {lactate} mmol/L", f"WBC: {wbc} 10^3/uL", f"CRP: {crp} mg/L"]
        
        if lactate > 4.0:
            prob = 0.82
            reasoning = "High lactate indicates tissue hypoperfusion, likely septic shock"
        elif lactate > 2.0:
            prob = 0.65
            reasoning = "Elevated lactate suggests developing sepsis"
        else:
            prob = 0.40
            reasoning = "Lactate normal but other markers suggest infection"
        
        if procalcitonin > 10:
            prob = min(0.95, prob + 0.1)
            evidence.append(f"Procalcitonin: {procalcitonin} ng/mL - High bacterial infection likely")
        
        if any("pneumonia" in m.lower() or "copd" in m.lower() for m in [l.get("name", "") for l in medications]):
            diagnoses.append(Diagnosis(
                code="J18.9", name="Pneumonia leading to Sepsis", probability=prob + 0.05,
                evidence=evidence + ["Respiratory history consistent"],
                reasoning=reasoning
            ))
        
        diagnoses.append(Diagnosis(
            code="A41.9", name="Gram Negative Sepsis", probability=prob,
            evidence=evidence, reasoning=reasoning
        ))
        
        return diagnoses

    def _analyze_cardiac(self, vitals: Dict[str, float], labs: List[Dict[str, Any]]) -> List[Diagnosis]:
        diagnoses = []
        troponin = next((l["value"] for l in labs if l["test_name"] == "Troponin I"), 0.0)
        
        if troponin > 0.4:
            diagnoses.append(Diagnosis(
                code="I21.9", name="STEMI", probability=0.88,
                evidence=[f"Troponin I: {troponin} ng/mL - Elevated"],
                reasoning="Troponin elevation indicates acute myocardial injury"
            ))
        elif troponin > 0.04:
            diagnoses.append(Diagnosis(
                code="I21.4", name="NSTEMI", probability=0.72,
                evidence=[f"Troponin I: {troponin} ng/mL - Mildly elevated"],
                reasoning="Mild troponin elevation consistent with NSTEMI"
            ))
        
        return diagnoses

    def _analyze_neuro(self, vitals: Dict[str, float], labs: List[Dict[str, Any]]) -> List[Diagnosis]:
        gcs = vitals.get("gcs", 15)
        sbp = vitals.get("systolic_bp", 120)
        
        if gcs < 9:
            return [Diagnosis(
                code="S06.9", name="Traumatic Brain Injury with Altered Consciousness", probability=0.78,
                evidence=[f"GCS: {gcs}"], reasoning="Severely depressed consciousness"
            )]
        
        if sbp > 180:
            return [Diagnosis(
                code="I64.9", name="Stroke - Hemorrhagic likely", probability=0.65,
                evidence=[f"SBP: {sbp} mmHg - Hypertensive"], reasoning="Hypertension with neurological symptoms"
            )]
        
        return []

    def _predict_risk(self, vitals: Dict[str, float], labs: List[Dict[str, Any]], primary: Optional[Diagnosis]) -> Dict[str, Any]:
        risk_factors = []
        score = 0.0
        
        sbp = vitals.get("systolic_bp", 120)
        if sbp < 90:
            risk_factors.append("Hypotension")
            score += 2.0
        
        lactate = next((l["value"] for l in labs if l["test_name"] == "Lactate"), 1.0)
        if lactate > 4.0:
            risk_factors.append("Severely Elevated Lactate")
            score += 3.0
        elif lactate > 2.0:
            risk_factors.append("Elevated Lactate")
            score += 1.5
        
        if primary and "sepsis" in primary.name.lower():
            if score > 4: mortality = "HIGH (>40%)"
            elif score > 2: mortality = "MODERATE (15-40%)"
            else: mortality = "LOW (<15%)"
        else:
            mortality = "LOW (<10%)"
        
        return {
            "icu_admission_probability": min(0.99, score / 5 * 0.8),
            "mortality_risk": mortality,
            "30_day_readmission": min(0.5, score / 10),
            "risk_factors": risk_factors,
            "composite_score": score,
        }

    def _assess_confidence(self, labs: List[Dict], vitals: Dict[str, float]) -> str:
        if len(labs) >= 10 and all(vitals.get(k) for k in ["heart_rate", "systolic_bp", "spo2"]):
            return "HIGH"
        elif len(labs) >= 5:
            return "MODERATE"
        return "LOW"
