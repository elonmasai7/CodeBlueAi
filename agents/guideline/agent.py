from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger()


@dataclass
class Intervention:
    action: str
    timing: str
    dose: str = ""
    route: str = ""
    frequency: str = ""
    priority: str = "STANDARD"
    contraindications: List[str] = field(default_factory=list)


@dataclass
class Protocol:
    name: str
    code: str
    description: str
    interventions: List[Intervention]
    required_monitoring: List[str] = field(default_factory=list)
    follow_up_actions: List[str] = field(default_factory=list)
    estimated_duration: str = ""


@dataclass
class GuidelineResponse:
    patient_id: str
    mrn: str
    triggered_protocol: str
    protocol_details: Protocol
    urgency: str
    reasoning: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


class GuidelineAgent:
    def __init__(self):
        self._protocols = {
            "SEPTIC_SHOCK": self._sepsis_bundle_protocol(),
            "SEVERE_SEPSIS": self._severe_sepsis_protocol(),
            "STEMI": self._stemi_protocol(),
            "NSTEMI": self._nstemi_protocol(),
            "ISCHEMIC_STROKE": self._stroke_protocol(),
            "CARDIAC_ARREST": self._acls_protocol(),
            "PE": self._pe_protocol(),
            "DKA": self._dka_protocol(),
        }

    def get_protocol(self, diagnosis_code: str, diagnosis_name: str = "") -> Optional[Protocol]:
        name_lower = diagnosis_name.lower()
        
        if "septic shock" in name_lower or "shock" in name_lower:
            return self._protocols.get("SEPTIC_SHOCK")
        if "sepsis" in name_lower:
            return self._protocols.get("SEVERE_SEPSIS")
        if "stemi" in name_lower or "stem" in name_lower:
            return self._protocols.get("STEMI")
        if "nstemi" in name_lower or "angina" in name_lower:
            return self._protocols.get("NSTEMI")
        if "stroke" in name_lower:
            return self._protocols.get("ISCHEMIC_STROKE")
        if "pulmonary embolism" in name_lower or "pe" in name_lower:
            return self._protocols.get("PE")
        if "diabetic ketoacidosis" in name_lower or "dka" in name_lower:
            return self._protocols.get("DKA")
        
        return self._protocols.get(diagnosis_code)

    def generate_response(self, patient_id: str, mrn: str, diagnosis_code: str, diagnosis_name: str, patient_data: Dict[str, Any]) -> GuidelineResponse:
        protocol = self.get_protocol(diagnosis_code, diagnosis_name)
        
        if not protocol:
            return GuidelineResponse(
                patient_id=patient_id,
                mrn=mrn,
                triggered_protocol="GENERAL_SUPPORTIVE",
                protocol_details=self._general_supportive_protocol(),
                urgency="STANDARD",
                reasoning="No specific protocol matched - initiating general supportive care",
            )
        
        urgency = self._determine_urgency(protocol)
        
        return GuidelineResponse(
            patient_id=patient_id,
            mrn=mrn,
            triggered_protocol=protocol.name,
            protocol_details=protocol,
            urgency=urgency,
            reasoning=self._generate_reasoning(protocol, patient_data),
        )

    def _sepsis_bundle_protocol(self) -> Protocol:
        return Protocol(
            name="1-Hour Sepsis Bundle",
            code="SEP-1HR",
            description="Surviving Sepsis Campaign 1-hour bundle for septic shock",
            interventions=[
                Intervention(action="Measure lactate", timing="Within 1 hour", priority="IMMEDIATE"),
                Intervention(action="Blood cultures before antibiotics", timing="Within 1 hour", priority="IMMEDIATE"),
                Intervention(action="Broad spectrum antibiotics", timing="Within 1 hour", dose="Vancomycin 1g IV + Piperacillin-Tazobactam 4.5g IV", route="IV", priority="IMMEDIATE"),
                Intervention(action=" Crystalloids 30mL/kg for hypotension", timing="Within 1 hour", dose="NS 0.9% 1000mL bolus", route="IV", priority="IMMEDIATE"),
                Intervention(action="Vasopressors if still hypotensive", timing="After fluid challenge", dose="Norepinephrine 0.1-0.5 mcg/kg/min", route="IV", priority="HIGH"),
            ],
            required_monitoring=["Repeat lactate in 2-4 hours", "Continuous cardiac monitoring", "Foley for UO monitoring", "Serial vitals q15min"],
            follow_up_actions=["Repeat blood cultures if initial negative", "Source control within 6-12 hours", "ICU consultation"],
            estimated_duration="1 hour for initial bundle, ongoing monitoring",
        )

    def _severe_sepsis_protocol(self) -> Protocol:
        return Protocol(
            name="Severe Sepsis Bundle",
            code="SEP-SEVERE",
            description="3-hour and 6-hour bundles for severe sepsis",
            interventions=[
                Intervention(action="Lactate measurement", timing="Within 3 hours", priority="HIGH"),
                Intervention(action="Blood cultures", timing="Within 3 hours", priority="HIGH"),
                Intervention(action="Antibiotics", timing="Within 3 hours", dose="Broad spectrum within 1 hour of recognition", priority="HIGH"),
                Intervention(action="Crystalloids 30mL/kg", timing="Within 3 hours if hypotensive", priority="MODERATE"),
            ],
            required_monitoring=["Repeat lactate in 6 hours", "Urinary output > 0.5mL/kg/hr", "Mental status assessment"],
            follow_up_actions=["Source control", "ICU evaluation", "Consider hydrocortisone if refractory shock"],
            estimated_duration="6 hours",
        )

    def _stemi_protocol(self) -> Protocol:
        return Protocol(
            name="STEMI Reperfusion Protocol",
            code="STEMI-PCI",
            description="Emergency PCI pathway for STEMI",
            interventions=[
                Intervention(action="Aspirin 325mg + P2Y12 inhibitor", timing="Immediate", dose="Ticagrelor 180mg or Clopidogrel 600mg", priority="IMMEDIATE"),
                Intervention(action="Heparin IV", timing="Immediate", dose="UFH 70 units/kg", priority="IMMEDIATE"),
                Intervention(action="Activate Cath Lab", timing="Immediate", priority="IMMEDIATE"),
                Intervention(action="Morphine PRN", timing="For chest pain", dose="2-4mg IV", priority="MODERATE"),
            ],
            required_monitoring=["12-lead ECG q15min until PCI", "Troponin q3h x3", "Cardiac telemetry"],
            follow_up_actions=["PCI within 90 minutes", "ICU monitoring post-PCI", "Statin and beta-blocker optimization"],
            estimated_duration="90 minutes to PCI",
        )

    def _nstemi_protocol(self) -> Protocol:
        return Protocol(
            name="NSTEMI/UA Protocol",
            code="NSTEMI-MGMT",
            description="Risk stratification and management for NSTEMI",
            interventions=[
                Intervention(action="Aspirin", timing="Immediate", priority="HIGH"),
                Intervention(action="Heparin LMWH or UFH", timing="Immediate", priority="HIGH"),
                Intervention(action="Cardiologist consultation", timing="Within 30 minutes", priority="HIGH"),
                Intervention(action="Risk stratification (TIMI/GRACE)", timing="Within 2 hours", priority="HIGH"),
            ],
            required_monitoring=["Continuous telemetry", "Serial troponins", "Repeat ECG for chest pain"],
            follow_up_actions=["Invasive strategy if high risk", "Early discharge if low risk", "Stress testing if intermediate risk"],
            estimated_duration="24-48 hours",
        )

    def _stroke_protocol(self) -> Protocol:
        return Protocol(
            name="Acute Stroke Protocol",
            code="STROKE-ACUTE",
            description="Acute stroke evaluation and treatment",
            interventions=[
                Intervention(action="STAT Stroke Team Activation", timing="Immediate", priority="IMMEDIATE"),
                Intervention(action="Non-contrast CT Head", timing="Within 25 minutes", priority="IMMEDIATE"),
                Intervention(action="Labs: CBC, BMP, PT/INR, Troponin, Glucose", timing="Immediate", priority="HIGH"),
                Intervention(action="Blood pressure management", timing="If SBP > 185", dose="Labetalol 10-20mg IV", priority="HIGH"),
                Intervention(action="tPA if eligible", timing="Within 4.5 hours", dose="0.9mg/kg (max 90mg)", priority="IMMEDIATE"),
            ],
            required_monitoring=["NIHSS q1h x24h", "BP q15min x2h", "Neuro checks q1h"],
            follow_up_actions=["MRI/MRA if candidate", "Endovascular consideration", "Rehab consultation", "Speech/swallow evaluation"],
            estimated_duration="Critical first 24 hours",
        )

    def _acls_protocol(self) -> Protocol:
        return Protocol(
            name="ACLS Cardiac Arrest Algorithm",
            code="ACLS",
            description="Advanced Cardiac Life Support",
            interventions=[
                Intervention(action="High Quality CPR", timing="Continuous", priority="IMMEDIATE"),
                Intervention(action="Epinephrine 1mg IV/IO", timing="Every 3-5 minutes", dose="1mg q3-5min", priority="IMMEDIATE"),
                Intervention(action="Shockable rhythm? Apply defibrillator", timing="Immediate", priority="IMMEDIATE"),
                Intervention(action="Amiodarone 300mg IV", timing="After 2nd shock", dose="300mg first, 150mg second", priority="HIGH"),
                Intervention(action="Identify and treat reversible causes", timing="Ongoing", priority="HIGH"),
            ],
            required_monitoring=["End-tidal CO2 monitoring", "Quality CPR feedback", "Return of spontaneous circulation monitoring"],
            follow_up_actions=["Post-cardiac arrest care", "Therapeutic hypothermia consideration", "PCI if STEMI on post-arrest ECG"],
            estimated_duration="Until ROSC or termination",
        )

    def _pe_protocol(self) -> Protocol:
        return Protocol(
            name="Pulmonary Embolism Workup",
            code="PE-WORKUP",
            description="Evaluation and management of suspected PE",
            interventions=[
                Intervention(action="Wells Score / Geneva Score", timing="Immediate", priority="HIGH"),
                Intervention(action="D-dimer if low probability", timing="Immediate", priority="MODERATE"),
                Intervention(action="CT Pulmonary Angiography", timing="If moderate-high probability", priority="HIGH"),
                Intervention(action="Heparin Anticoagulation", timing="If PE confirmed", dose="LMWH enoxaparin 1mg/kg or UFH", priority="HIGH"),
                Intervention(action="Massive PE: Thrombolysis consideration", timing="If hypotensive", dose="tPA 100mg IV over 2 hours", priority="IMMEDIATE"),
            ],
            required_monitoring=["SpO2 > 92%", "Hemodynamic stability", "Serial echocardiography if massive PE"],
            follow_up_actions=["V/Q scan if contrast contraindicated", "IVC filter if anticoagulation contraindicated", "Hypercoagulability workup"],
            estimated_duration="24 hours for diagnosis",
        )

    def _dka_protocol(self) -> Protocol:
        return Protocol(
            name="DKA Protocol",
            code="DKA-MGMT",
            description="Diabetic Ketoacidosis management",
            interventions=[
                Intervention(action="Fluid resuscitation", timing="Immediate", dose="NS 0.9% 1-1.5L in first hour", route="IV", priority="IMMEDIATE"),
                Intervention(action="Potassium replacement", timing="When K+ < 5.3", dose="20-30mEq KCl per liter", route="IV", priority="HIGH"),
                Intervention(action="Insulin infusion", timing="After initial fluids", dose="0.1 units/kg/hr regular insulin", route="IV", priority="HIGH"),
                Intervention(action="Transition to SC insulin", timing="When glucose < 200", priority="MODERATE"),
            ],
            required_monitoring=["Fingerstick glucose q1h", "BMP q2-4h", "Anion gap closure assessment", "pH and bicarbonate trending"],
            follow_up_actions=["Insulin drip to SC transition protocol", "Dietary education", "Endocrine consultation"],
            estimated_duration="12-24 hours until resolution",
        )

    def _general_supportive_protocol(self) -> Protocol:
        return Protocol(
            name="General Supportive Care",
            code="GENERAL",
            description="Standard monitoring and supportive measures",
            interventions=[
                Intervention(action="Continuous vital sign monitoring", timing="Ongoing", priority="STANDARD"),
                Intervention(action="IV access established", timing="Immediate", priority="HIGH"),
                Intervention(action="Supplemental oxygen to maintain SpO2 > 94%", timing="As needed", priority="HIGH"),
            ],
            required_monitoring=["Routine neuro checks", "I/O monitoring", "Pain assessment"],
            follow_up_actions=["Specialist consultation as indicated", "Repeat evaluation in 4-6 hours"],
            estimated_duration="Variable",
        )

    def _determine_urgency(self, protocol: Protocol) -> str:
        if "1-Hour" in protocol.name or "ACLS" in protocol.code:
            return "IMMEDIATE"
        if protocol.code in ["STEMI-PCI", "STROKE-ACUTE"]:
            return "IMMEDIATE"
        if protocol.code in ["SEP-1HR", "SEP-SEVERE"]:
            return "URGENT"
        return "STANDARD"

    def _generate_reasoning(self, protocol: Protocol, patient_data: Dict[str, Any]) -> str:
        vitals = patient_data.get("vitals", {})
        sbp = vitals.get("systolic_bp", 120)
        
        if sbp < 90:
            return f"Patient hypotensive (SBP {sbp}), indicating shock state. {protocol.name} initiated for hemodynamic support and source identification."
        if protocol.code in ["STEMI-PCI", "STROKE-ACUTE"]:
            return f"Time-critical diagnosis requiring immediate intervention per {protocol.name} protocol."
        return f"Clinical presentation consistent with protocol criteria. Initiating {protocol.name} for standardized evidence-based care."
