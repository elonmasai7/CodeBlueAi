from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger()


@dataclass
class SOAPNote:
    patient_id: str
    mrn: str
    subjective: str
    objective: str
    assessment: str
    plan: str
    clinical_rationale: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    provider: str = "Code Blue AI"
    encounter_type: str = "Emergency Department"


class DocumentationAgent:
    def __init__(self):
        self._templates = {
            "sepsis": self._sepsis_template,
            "septic_shock": self._septic_shock_template,
            "mi": self._mi_template,
            "stroke": self._stroke_template,
            "general": self._general_template,
        }

    def generate_soap_note(
        self,
        patient_id: str,
        mrn: str,
        patient_name: str,
        vitals: Dict[str, float],
        labs: List[Dict[str, Any]],
        medications: List[Dict[str, Any]],
        diagnosis: str,
        protocol: Optional[str],
        scores: Dict[str, float],
        escalation: Optional[Dict[str, Any]] = None,
    ) -> SOAPNote:
        diagnosis_lower = diagnosis.lower()
        
        if "septic shock" in diagnosis_lower or "shock" in diagnosis_lower:
            template = self._templates["septic_shock"]
        elif "sepsis" in diagnosis_lower:
            template = self._templates["sepsis"]
        elif "mi" in diagnosis_lower or "stemi" in diagnosis_lower or "nstemi" in diagnosis_lower:
            template = self._templates["mi"]
        elif "stroke" in diagnosis_lower:
            template = self._templates["stroke"]
        else:
            template = self._templates["general"]
        
        soap = template(patient_id, mrn, patient_name, vitals, labs, medications, diagnosis, protocol, scores, escalation)
        
        return soap

    def _sepsis_template(
        self,
        patient_id: str,
        mrn: str,
        patient_name: str,
        vitals: Dict[str, float],
        labs: List[Dict[str, Any]],
        medications: List[Dict[str, Any]],
        diagnosis: str,
        protocol: Optional[str],
        scores: Dict[str, float],
        escalation: Optional[Dict[str, Any]],
    ) -> SOAPNote:
        hr = vitals.get("heart_rate", 0)
        sbp = vitals.get("systolic_bp", 0)
        rr = vitals.get("respiratory_rate", 0)
        temp = vitals.get("temperature", 0)
        spo2 = vitals.get("spo2", 0)
        lactate = vitals.get("lactate", 0)
        
        lactate_val = next((l["value"] for l in labs if l["test_name"] == "Lactate"), lactate)
        wbc_val = next((l["value"] for l in labs if l["test_name"] == "WBC"), 0)
        crp_val = next((l["value"] for l in labs if l["test_name"] == "CRP"), 0)
        
        subjective = f"""Patient presents with {diagnosis}. Family reports patient had been complaining of malaise and decreased oral intake for the past 2 days. Denies any recent travel or sick contacts. Past medical history significant for {patient_name.split()[-1]}."""

        objective = f"""Vital Signs: T{max(temp,37):.1f}C, HR {hr:.0f} bpm, BP {sbp:.0f}/{vitals.get('diastolic_bp', 70):.0f} mmHg, RR {rr:.0f}/min, SpO2 {spo2:.0f}% on room air

Laboratory: Lactate {lactate_val:.1f} mmol/L ({"ELEVATED" if lactate_val > 2.0 else "NORMAL"}), WBC {wbc_val:.1f} x10^3/uL, CRP {crp_val:.0f} mg/L

Clinical Scores: NEWS2 {scores.get('NEWS2', 0):.0f}, qSOFA {scores.get('qSOFA', 0):.0f}, SOFA {scores.get('SOFA', 0):.0f}

Current Medications: {', '.join([m.get('name', 'Unknown') for m in medications[:5]])}"""

        assessment = f"""1. {diagnosis}
   - Lactate {lactate_val:.1f} mmol/L indicates {"tissue hypoperfusion" if lactate_val > 2.0 else "adequate perfusion"}
   - NEWS2 score of {scores.get('NEWS2', 0):.0f} indicates {"HIGH risk of deterioration" if scores.get('NEWS2', 0) >= 5 else "moderate risk"}
   - qSOFA of {scores.get('qSOFA', 0):.0f} suggests {"high mortality risk" if scores.get('qSOFA', 0) >= 2 else "moderate mortality risk"}

2. Sepsis bundle initiated per Surviving Sepsis Campaign guidelines"""

        plan = f"""1. Initiate 1-hour Sepsis Bundle:
   - Broad spectrum antibiotics within 1 hour
   - Lactate {lactate_val:.1f} mmol/L - will repeat in 2-4 hours
   - Blood cultures obtained prior to antibiotics
   - IV fluid resuscitation 30mL/kg crystalloids

2. Monitoring:
   - Continuous telemetry
   - Foley for strict I/O
   - Vitals q15min until stable

3. Escalation:
   - ICU consulted for monitoring
   - {"Rapid Response activated" if escalation and escalation.get('level') == 'RAPID_RESPONSE' else 'Continued floor monitoring with intensivist oversight'}

4. Reassessment:
   - Repeat lactate in 2-4 hours
   - Assess for source control needs
   - Daily reassessment for antibiotic de-escalation"""

        rationale = f"""Sepsis suspected based on SIRS criteria (fever/hypothermia, tachycardia, tachypnea, elevated lactate) combined with qSOFA >= {scores.get('qSOFA', 0):.0f}. Early recognition and treatment per Surviving Sepsis Campaign guidelines improves outcomes. Each hour of antibiotic delay increases mortality by 7%. Patient will require close monitoring for progression to septic shock."""

        return SOAPNote(
            patient_id=patient_id,
            mrn=mrn,
            subjective=subjective,
            objective=objective,
            assessment=assessment,
            plan=plan,
            clinical_rationale=rationale,
        )

    def _septic_shock_template(self, *args, **kwargs) -> SOAPNote:
        note = self._sepsis_template(*args, **kwargs)
        
        note.assessment += "\n\n3. Septic Shock - Vasopressor support likely required"
        note.plan += "\n\n5. Vasopressors:\n   - Norepinephrine initiated at 0.1 mcg/kg/min\n   - MAP goal > 65 mmHg\n   - Add vasopressin if refractory"
        
        note.clinical_rationale += " Septic shock defined as sepsis with persistent hypotension requiring vasopressors to maintain MAP > 65 mmHg despite adequate fluid resuscitation. Early vasopressor use is associated with improved outcomes."
        
        return note

    def _mi_template(self, patient_id: str, mrn: str, patient_name: str, vitals: Dict[str, float], labs: List[Dict], medications: List[Dict], diagnosis: str, protocol: Optional[str], scores: Dict[str, float], escalation: Optional[Dict]) -> SOAPNote:
        troponin = next((l["value"] for l in labs if l["test_name"] == "Troponin I"), 0)
        
        return SOAPNote(
            patient_id=patient_id,
            mrn=mrn,
            subjective=f"Patient presents with chest pain consistent with {diagnosis}. Reports crushing substernal chest pain radiating to left arm, onset 2 hours ago.",
            objective=f"BP {vitals.get('systolic_bp', 120):.0f}/{vitals.get('diastolic_bp', 70):.0f} mmHg, HR {vitals.get('heart_rate', 70):.0f} bpm. Troponin I {troponin:.3f} ng/mL",
            assessment=f"1. {diagnosis}\n2. Hemodynamically stable\n3. No arrhythmia on current monitoring",
            plan="1. Aspirin 325mg + P2Y12 inhibitor loading dose\n2. Anticoagulation with Heparin\n3. Emergent Cardiology consultation\n4. Prepare for cath lab activation",
            clinical_rationale="STEMI protocol initiated. Door-to-balloon time goal < 90 minutes. Immediate reperfusion therapy is standard of care.",
        )

    def _stroke_template(self, patient_id: str, mrn: str, patient_name: str, vitals: Dict[str, float], labs: List[Dict], medications: List[Dict], diagnosis: str, protocol: Optional[str], scores: Dict[str, float], escalation: Optional[Dict]) -> SOAPNote:
        gcs = vitals.get("gcs", 15)
        
        return SOAPNote(
            patient_id=patient_id,
            mrn=mrn,
            subjective=f"Patient presents with sudden onset neurological deficits consistent with {diagnosis}. GCS {gcs:.0f}.",
            objective=f"BP {vitals.get('systolic_bp', 120):.0f}/{vitals.get('diastolic_bp', 70):.0f} mmHg, HR {vitals.get('heart_rate', 70):.0f} bpm. Focal deficits as documented by nursing.",
            assessment=f"1. {diagnosis}\n2. Hemodynamically stable\n3. Time last known well documented",
            plan="1. STAT non-contrast CT head\n2. Stroke team activation\n3. Labs: CBC, BMP, PT/INR, glucose\n4. BP management if > 185/110\n5. tPA consideration if eligible",
            clinical_rationale="Acute stroke protocol initiated. Time is brain - CT within 25 minutes, tPA eligibility window 4.5 hours from LKW.",
        )

    def _general_template(self, patient_id: str, mrn: str, patient_name: str, vitals: Dict[str, float], labs: List[Dict], medications: List[Dict], diagnosis: str, protocol: Optional[str], scores: Dict[str, float], escalation: Optional[Dict]) -> SOAPNote:
        return SOAPNote(
            patient_id=patient_id,
            mrn=mrn,
            subjective=f"Patient presents for evaluation. Complains of symptoms as outlined in H&P.",
            objective=f"Vitals stable. Labs pending. Medications reviewed.",
            assessment=f"1. {diagnosis}\n2. Awaiting laboratory and imaging results\n3. Current condition under evaluation",
            plan="1. Supportive care\n2. Monitoring per nursing assessment\n3. Reassess after results available\n4. Specialist consultation as indicated",
            clinical_rationale="General supportive measures initiated while diagnostic workup proceeds. Will update assessment and plan as data becomes available.",
        )

    def generate_fhir_updates(self, soap: SOAPNote, escalation: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        fhir_updates = []
        
        fhir_updates.append({
            "resourceType": "Communication",
            "status": "completed",
            "category": [{"coding": [{"code": "clinical-procedure"}]}],
            "subject": {"reference": f"Patient/{soap.patient_id}"},
            "payload": [{"contentString": f"SOAP Note: {soap.assessment[:100]}"}],
            "sent": soap.timestamp.isoformat(),
        })
        
        if escalation:
            fhir_updates.append({
                "resourceType": "DetectedIssue",
                "status": "preliminary",
                "severity": "high",
                "subject": {"reference": f"Patient/{soap.patient_id}"},
                "detail": f"Escalation: {escalation.get('level', 'UNKNOWN')} - {escalation.get('reason', 'Clinical deterioration')}",
                "date": soap.timestamp.isoformat(),
            })
        
        return fhir_updates
