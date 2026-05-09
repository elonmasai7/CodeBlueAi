#!/usr/bin/env python3
"""
Demo Scenario Runner for Code Blue AI

Simulates a patient deterioration scenario from stable to septic shock.
Drives the full agent chain: Monitor -> Diagnostic -> Guideline -> Coordinator -> Documentation.
Outputs structured events that the frontend renders in real-time.
"""

import asyncio
import json
import sys
import uuid
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional

PATIENT = {
    "id": "demo-patient-001",
    "mrn": "MRN00000001",
    "first_name": "John",
    "last_name": "Doe",
    "age": 62,
    "sex": "M",
    "bed": "ICU-A3",
    "unit": "ICU",
    "diagnosis": "Community Acquired Pneumonia",
    "allergies": ["Penicillin"],
    "comorbidities": ["Type 2 Diabetes", "Hypertension"],
}


PHASES = [
    {
        "step": 0,
        "phase": "STABLE BASELINE",
        "description": "Patient admitted for pneumonia. Vitals stable on floor.",
        "vitals": {
            "heart_rate": 88,
            "systolic_bp": 125,
            "diastolic_bp": 78,
            "respiratory_rate": 18,
            "temperature": 37.5,
            "spo2": 95,
            "map": 94,
            "lactate": 1.2,
        },
        "expected_agent": "Monitor",
        "expected_action": "Normal monitoring, no alerts",
        "delay": 3,
    },
    {
        "step": 1,
        "phase": "EARLY DETERIORATION",
        "description": "Six hours later. Tachycardia developing, mild hypotension. Temperature rising.",
        "vitals": {
            "heart_rate": 102,
            "systolic_bp": 108,
            "diastolic_bp": 65,
            "respiratory_rate": 24,
            "temperature": 38.4,
            "spo2": 91,
            "map": 79,
            "lactate": 2.1,
        },
        "expected_agent": "Monitor",
        "expected_action": "NEWS2 5, qSOFA 1 - Low-medium risk",
        "delay": 5,
    },
    {
        "step": 2,
        "phase": "SEPSIS SUSPECTED",
        "description": "Two hours later. Clear deterioration. Lactate climbing. SpO2 dropping.",
        "vitals": {
            "heart_rate": 118,
            "systolic_bp": 92,
            "diastolic_bp": 58,
            "respiratory_rate": 28,
            "temperature": 39.0,
            "spo2": 88,
            "map": 69,
            "lactate": 3.5,
        },
        "expected_agent": "Monitor + Diagnostic",
        "expected_action": "NEWS2 9, qSOFA 2 - SEPSIS SUSPECTED",
        "delay": 5,
    },
    {
        "step": 3,
        "phase": "SEPTIC SHOCK",
        "description": "Patient in shock. Hypotension refractory. Lactate critically elevated.",
        "vitals": {
            "heart_rate": 128,
            "systolic_bp": 82,
            "diastolic_bp": 52,
            "respiratory_rate": 30,
            "temperature": 39.2,
            "spo2": 87,
            "map": 62,
            "lactate": 4.8,
        },
        "expected_agent": "ALL AGENTS",
        "expected_action": "CODE BLUE - Rapid Response - ICU Transfer",
        "delay": 4,
    },
    {
        "step": 4,
        "phase": "TREATMENT INITIATED",
        "description": "Antibiotics given, fluids running, ICU team at bedside. Vitals stabilizing.",
        "vitals": {
            "heart_rate": 115,
            "systolic_bp": 92,
            "diastolic_bp": 60,
            "respiratory_rate": 26,
            "temperature": 38.8,
            "spo2": 91,
            "map": 71,
            "lactate": 4.2,
        },
        "expected_agent": "Monitor",
        "expected_action": "NEWS2 8 - Still high risk, improving",
        "delay": 3,
    },
    {
        "step": 5,
        "phase": "STABILIZED",
        "description": "Four hours post-bundle. MAP > 65, lactate dropping.ICU admission confirmed.",
        "vitals": {
            "heart_rate": 98,
            "systolic_bp": 102,
            "diastolic_bp": 65,
            "respiratory_rate": 22,
            "temperature": 38.0,
            "spo2": 94,
            "map": 77,
            "lactate": 2.8,
        },
        "expected_agent": "Monitor",
        "expected_action": "NEWS2 6 - Improving, continue monitoring",
        "delay": 3,
    },
]


@dataclass
class AgentEvent:
    timestamp: str
    agent: str
    message_type: str
    title: str
    content: str
    data: Dict[str, Any] = field(default_factory=dict)
    severity: str = "INFO"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DemoScenarioRunner:
    def __init__(self, output_callback=None):
        self.output_callback = output_callback or print
        self.events: List[AgentEvent] = []
        self.patient = PATIENT.copy()

    def emit(self, event: AgentEvent):
        self.events.append(event)
        self.output_callback(json.dumps(event.to_dict(), indent=None))

    def run_monitor_phase(self, phase: Dict) -> Dict[str, Any]:
        vitals = phase["vitals"]
        hr = vitals["heart_rate"]
        sbp = vitals["systolic_bp"]
        rr = vitals["respiratory_rate"]
        temp = vitals["temperature"]
        spo2 = vitals["spo2"]
        lactate = vitals["lactate"]

        news2 = self._calc_news2(hr, sbp, rr, temp, spo2)
        sofa = self._calc_sofa(hr, spo2, lactate)
        qsofa = self._calc_qsofa(rr, sbp)

        sepsis = self._detect_sepsis(qsofa, lactate, sbp)

        self.emit(AgentEvent(
            timestamp=datetime.utcnow().isoformat(),
            agent="MonitorAgent",
            message_type="VITAL_ALERT",
            title=f"Vitals Updated - {phase['phase']}",
            content=f"NEWS2: {news2:.0f} | SOFA: {sofa:.0f} | qSOFA: {qsofa:.0f}",
            data={"vitals": vitals, "news2": news2, "sofa": sofa, "qsofa": qsofa, "sepsis": sepsis},
            severity="HIGH" if news2 >= 7 else "MODERATE" if news2 >= 5 else "LOW",
        ))

        if sepsis["suspected"]:
            self.emit(AgentEvent(
                timestamp=datetime.utcnow().isoformat(),
                agent="MonitorAgent",
                message_type="DETERIORATION_DETECTED",
                title=f"{sepsis['stage']} - Probability {sepsis['probability']:.0%}",
                content=f"{sepsis['evidence'][0] if sepsis['evidence'] else 'Clinical deterioration detected'}",
                data=sepsis,
                severity="CRITICAL" if "SHOCK" in sepsis["stage"] else "HIGH",
            ))

        return {"news2": news2, "sofa": sofa, "qsofa": qsofa, "sepsis": sepsis}

    def run_diagnostic_phase(self, scores: Dict) -> Dict[str, Any]:
        sepsis = scores["sepsis"]
        if not sepsis["suspected"]:
            self.emit(AgentEvent(
                timestamp=datetime.utcnow().isoformat(),
                agent="DiagnosticAgent",
                message_type="DIAGNOSTIC_RESULT",
                title="No acute diagnosis",
                content="Clinical picture not consistent with sepsis or critical diagnosis. Continue monitoring.",
                data={},
                severity="INFO",
            ))
            return {}

        differential = [
            {"code": "J12.9", "name": "Community Acquired Pneumonia leading to Sepsis", "probability": 0.78, "evidence": ["Pneumonia dx", "Elevated lactate", "Tachycardia"]},
            {"code": "A41.9", "name": "Gram Negative Sepsis", "probability": 0.65, "evidence": ["High lactate", "Hypotension", "Fever"]},
            {"code": "N39.0", "name": "Urinary Tract Infection with Sepsis", "probability": 0.35, "evidence": ["UTI suspected", "Elevated WBC"]},
        ]

        self.emit(AgentEvent(
            timestamp=datetime.utcnow().isoformat(),
            agent="DiagnosticAgent",
            message_type="DIAGNOSTIC_RESULT",
            title=f"Primary Diagnosis: {differential[0]['name']}",
            content=f"Confidence: {differential[0]['probability']:.0%} | ICU admission probability: {min(0.95, sepsis['probability'] + 0.05):.0%}",
            data={"differential": differential, "primary": differential[0]},
            severity="CRITICAL",
        ))

        return {"differential": differential, "primary": differential[0]}

    def run_guideline_phase(self, diagnosis: Dict) -> Dict[str, Any]:
        protocol = {
            "name": "1-Hour Sepsis Bundle",
            "code": "SEP-1HR",
            "interventions": [
                {"action": "Measure lactate", "timing": "Within 1 hour", "dose": "", "priority": "IMMEDIATE"},
                {"action": "Blood cultures before antibiotics", "timing": "Within 1 hour", "dose": "", "priority": "IMMEDIATE"},
                {"action": "Broad spectrum antibiotics", "timing": "Within 1 hour", "dose": "Vancomycin 1g IV + Pip-Tazo 4.5g IV", "priority": "IMMEDIATE"},
                {"action": "Crystalloids 30mL/kg", "timing": "Within 1 hour", "dose": "NS 0.9% 1000mL bolus", "priority": "IMMEDIATE"},
                {"action": "Vasopressors if still hypotensive", "timing": "After fluid challenge", "dose": "Norepinephrine 0.1-0.5 mcg/kg/min", "priority": "HIGH"},
            ],
            "required_monitoring": ["Repeat lactate in 2-4 hours", "Continuous telemetry", "Foley for UO"],
            "urgency": "IMMEDIATE",
        }

        self.emit(AgentEvent(
            timestamp=datetime.utcnow().isoformat(),
            agent="GuidelineAgent",
            message_type="GUIDELINE_RESPONSE",
            title=f"Protocol Retrieved: {protocol['name']}",
            content=f"Urgency: {protocol['urgency']} | {len(protocol['interventions'])} interventions",
            data=protocol,
            severity="CRITICAL",
        ))

        return protocol

    def run_coordinator_phase(self, protocol: Dict) -> Dict[str, Any]:
        tasks = [
            {"id": str(uuid.uuid4())[:8], "description": "Repeat vitals and document", "assigned_to": "Bedside RN", "due": "Now", "status": "PENDING"},
            {"id": str(uuid.uuid4())[:8], "description": "Establish large bore IV access", "assigned_to": "RN", "due": "Now", "status": "PENDING"},
            {"id": str(uuid.uuid4())[:8], "description": "Lactate, blood cultures, CBC, BMP", "assigned_to": "Lab/Phlebotomy", "due": "Now", "status": "PENDING"},
            {"id": str(uuid.uuid4())[:8], "description": "Administer Vancomycin 1g IV + Pip-Tazo 4.5g IV", "assigned_to": "RN/Pharmacy", "due": "Now", "status": "PENDING"},
            {"id": str(uuid.uuid4())[:8], "description": "Insert Foley catheter", "assigned_to": "RN", "due": "Now", "status": "PENDING"},
        ]

        self.emit(AgentEvent(
            timestamp=datetime.utcnow().isoformat(),
            agent="CoordinatorAgent",
            message_type="ESCALATION_NOTIFICATION",
            title="RAPID RESPONSE ACTIVATED",
            content=f"ICU team en route | Attending MD paged | {len(tasks)} tasks created",
            data={"level": "RAPID_RESPONSE", "tasks": tasks, "notifications": [
                {"recipient": "ICU Rapid Response Team", "action": "BROADCAST", "priority": "CRITICAL"},
                {"recipient": "Dr. James Smith (Attending)", "action": "PAGE", "priority": "CRITICAL"},
                {"recipient": "Charge Nurse", "action": "ALERT", "priority": "HIGH"},
            ]},
            severity="CRITICAL",
        ))

        return {"tasks": tasks}

    def run_documentation_phase(self) -> Dict[str, Any]:
        soap = {
            "subjective": "Patient with Community Acquired Pneumonia, now with evidence of clinical deterioration. Family reports increased confusion and decreased oral intake since this morning. Denies recent travel or sick contacts.",
            "objective": f"VS: T 39.2C, HR 128, BP 82/52, RR 30, SpO2 87% on RA. Lactate 4.8 mmol/L. WBC 18.5. GCS 14. CXR shows multilobar pneumonia.",
            "assessment": "1. Septic Shock secondary to Community Acquired Pneumonia. 2. Hypotension requiring vasopressors. 3. Acute Hypoxemic Respiratory Failure.",
            "plan": "1. Initiate 1-hour Sepsis Bundle: cultures, antibiotics, 30mL/kg fluids, vasopressors. 2. ICU transfer for close monitoring. 3. Repeat lactate in 2-4 hours. 4. Source control with respiratory isolation. 5. Daily reassessment for antibiotic de-escalation.",
            "rationale": "Septic shock defined as sepsis with persistent hypotension requiring vasopressors despite adequate fluid resuscitation. Each hour of antibiotic delay increases mortality by 7%. Early goal-directed therapy improves outcomes.",
        }

        self.emit(AgentEvent(
            timestamp=datetime.utcnow().isoformat(),
            agent="DocumentationAgent",
            message_type="SOAP_NOTE_GENERATED",
            title="Clinical Note Complete",
            content=f"Assessment: Septic Shock | Plan: 1-hour Sepsis Bundle initiated",
            data=soap,
            severity="INFO",
        ))

        return soap

    def run_full_scenario(self):
        print("=" * 60)
        print("CODE BLUE AI - DEMO SCENARIO: SEPTIC SHOCK PROGRESSION")
        print("=" * 60)
        print(f"\nPatient: {self.patient['first_name']} {self.patient['last_name']}, {self.patient['age']}M")
        print(f"Admission: {self.patient['diagnosis']} | Bed {self.patient['bed']}")
        print(f"Allergies: {', '.join(self.patient['allergies'])}")
        print(f"Comorbidities: {', '.join(self.patient['comorbidities'])}")
        print("\n" + "-" * 60)

        for phase in PHASES:
            print(f"\n{'='*60}")
            print(f"STEP {phase['step']}: {phase['phase']}")
            print(f"{'='*60}")
            print(f"  {phase['description']}")
            print(f"  Vitals: HR {phase['vitals']['heart_rate']} | BP {phase['vitals']['systolic_bp']}/{phase['vitals']['diastolic_bp']} | SpO2 {phase['vitals']['spo2']}% | RR {phase['vitals']['respiratory_rate']} | T {phase['vitals']['temperature']}C | Lac {phase['vitals']['lactate']}")
            print()

            scores = self.run_monitor_phase(phase)

            if phase["step"] >= 2:
                diagnosis = self.run_diagnostic_phase(scores)

                if diagnosis:
                    protocol = self.run_guideline_phase(diagnosis)
                    tasks = self.run_coordinator_phase(protocol)
                    if phase["step"] == 3:
                        self.run_documentation_phase()

            print(f"  [Expected] {phase['expected_action']}")
            print()

            if phase["delay"] > 0:
                asyncio.run(asyncio.sleep(phase["delay"]))

        print("\n" + "=" * 60)
        print("DEMO COMPLETE")
        print("=" * 60)
        print(f"\nTotal events generated: {len(self.events)}")
        print("\nAgent Activity Summary:")
        agent_counts: Dict[str, int] = {}
        for event in self.events:
            agent_counts[event.agent] = agent_counts.get(event.agent, 0) + 1
        for agent, count in agent_counts.items():
            print(f"  {agent}: {count} events")

    def _calc_news2(self, hr, sbp, rr, temp, spo2) -> float:
        score = 0
        score += 3 if rr <= 11 or rr >= 25 else 1 if rr <= 24 else 0
        score += 3 if hr <= 40 or hr >= 131 else 2 if hr >= 111 else 1 if hr >= 91 else 0
        score += 3 if sbp <= 90 else 2 if sbp <= 100 else 1 if sbp <= 110 else 0
        score += 3 if spo2 <= 91 else 2 if spo2 <= 93 else 1 if spo2 <= 95 else 0
        score += 3 if temp <= 35.0 else 1 if temp <= 36.0 else 0 if temp <= 38.0 else 1 if temp <= 39.0 else 2
        if sbp <= 100:
            score += 2
        return float(score)

    def _calc_sofa(self, hr, spo2, lactate) -> float:
        score = 0.0
        score += 4 if spo2 < 80 else 3 if spo2 < 100 else 2 if spo2 < 150 else 1 if spo2 < 250 else 0
        score += 4 if lactate > 4.0 else 3 if lactate > 2.5 else 2 if lactate > 2.0 else 0
        score += 4 if hr > 150 else 3 if hr > 110 else 1 if hr > 70 else 0
        return float(score)

    def _calc_qsofa(self, rr, sbp) -> float:
        score = 0.0
        if rr >= 22: score += 1
        if sbp <= 100: score += 1
        return score

    def _detect_sepsis(self, qsofa, lactate, sbp) -> Dict[str, Any]:
        if sbp < 90 and lactate > 4.0:
            return {"suspected": True, "stage": "SEPTIC_SHOCK", "probability": 0.92, "evidence": ["Hypotension", "Lactate > 4", "qSOFA >= 2"]}
        if qsofa >= 2 and lactate > 2.0:
            return {"suspected": True, "stage": "SEVERE_SEPSIS", "probability": 0.85, "evidence": ["qSOFA >= 2", "Lactate elevated"]}
        if qsofa >= 2:
            return {"suspected": True, "stage": "SEPSIS", "probability": 0.72, "evidence": ["qSOFA >= 2"]}
        if lactate > 2.0:
            return {"suspected": True, "stage": "SEPSIS_SUSPECTED", "probability": 0.60, "evidence": ["Lactate elevated"]}
        return {"suspected": False, "stage": "NONE", "probability": 0.05, "evidence": []}


def main():
    print("\nStarting Code Blue AI Demo Scenario...\n")
    runner = DemoScenarioRunner()
    runner.run_full_scenario()


if __name__ == "__main__":
    main()
