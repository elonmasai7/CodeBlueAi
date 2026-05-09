from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import structlog

logger = structlog.get_logger()


class EscalationLevel(str, Enum):
    NURSE_NOTIFICATION = "NURSE_NOTIFICATION"
    ICU_NOTIFICATION = "ICU_NOTIFICATION"
    PHYSICIAN_NOTIFICATION = "PHYSICIAN_NOTIFICATION"
    RAPID_RESPONSE = "RAPID_RESPONSE"
    CODE_BLUE = "CODE_BLUE"
    TRANSFER_TO_ICU = "TRANSFER_TO_ICU"
    TRANSFER_TO_OR = "TRANSFER_TO_OR"


class EscalationAction(str, Enum):
    PAGE = "PAGE"
    CALL = "CALL"
    TEXT = "TEXT"
    ALERT = "ALERT"
    BROADCAST = "BROADCAST"


@dataclass
class Notification:
    recipient_role: str
    recipient_name: str
    action: EscalationAction
    message: str
    priority: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Task:
    id: str
    description: str
    assigned_to: str
    due: datetime
    status: str = "PENDING"
    completed_at: Optional[datetime] = None


@dataclass
class Escalation:
    id: str
    patient_id: str
    mrn: str
    level: EscalationLevel
    reason: str
    recommendations: List[str]
    notifications: List[Notification]
    tasks: List[Task]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


class CoordinatorAgent:
    def __init__(self):
        self._escalation_matrix = {
            "CRITICAL": EscalationLevel.CODE_BLUE,
            "HIGH": EscalationLevel.RAPID_RESPONSE,
            "MODERATE": EscalationLevel.PHYSICIAN_NOTIFICATION,
            "LOW": EscalationLevel.NURSE_NOTIFICATION,
        }
        self._response_times = {
            "CODE_BLUE": "Immediate",
            "RAPID_RESPONSE": "< 5 minutes",
            "PHYSICIAN_NOTIFICATION": "< 15 minutes",
            "NURSE_NOTIFICATION": "< 30 minutes",
        }

    def coordinate_escalation(
        self,
        patient_id: str,
        mrn: str,
        risk_level: str,
        diagnosis: str,
        protocol: Optional[str],
        scores: Dict[str, float],
        vitals: Dict[str, float],
    ) -> Escalation:
        level = self._escalation_matrix.get(risk_level, EscalationLevel.NURSE_NOTIFICATION)
        
        notifications = self._generate_notifications(patient_id, mrn, level, diagnosis, protocol)
        tasks = self._generate_task_list(patient_id, mrn, protocol, vitals)
        recommendations = self._generate_recommendations(level, diagnosis, scores)
        
        return Escalation(
            id=f"esc_{patient_id}_{datetime.utcnow().timestamp()}",
            patient_id=patient_id,
            mrn=mrn,
            level=level,
            reason=self._generate_reason(level, risk_level, diagnosis, scores),
            recommendations=recommendations,
            notifications=notifications,
            tasks=tasks,
        )

    def _generate_notifications(
        self,
        patient_id: str,
        mrn: str,
        level: EscalationLevel,
        diagnosis: str,
        protocol: Optional[str],
    ) -> List[Notification]:
        notifications = []
        
        if level in [EscalationLevel.CODE_BLUE, EscalationLevel.RAPID_RESPONSE]:
            notifications.extend([
                Notification(
                    recipient_role="ICU Team",
                    recipient_name="ICU Rapid Response Team",
                    action=EscalationAction.BROADCAST,
                    message=f"CODE BLUE - Patient {mrn} - Immediate response required - {diagnosis}",
                    priority="CRITICAL",
                ),
                Notification(
                    recipient_role="Attending Physician",
                    recipient_name="Primary MD",
                    action=EscalationAction.PAGE,
                    message=f"URGENT: Your patient {mrn} requires immediate evaluation - {diagnosis}",
                    priority="CRITICAL",
                ),
                Notification(
                    recipient_role="Nursing Supervisor",
                    recipient_name="Charge Nurse",
                    action=EscalationAction.ALERT,
                    message=f"Rapid Response triggered for {mrn}",
                    priority="HIGH",
                ),
            ])
        elif level == EscalationLevel.PHYSICIAN_NOTIFICATION:
            notifications.append(Notification(
                recipient_role="Attending Physician",
                recipient_name="Primary MD",
                action=EscalationAction.PAGE,
                message=f"Patient {mrn} deteriorating - Please evaluate within 15 minutes - {diagnosis}",
                priority="HIGH",
            ))
            notifications.append(Notification(
                recipient_role="Charge Nurse",
                recipient_name="Unit Charge",
                action=EscalationAction.ALERT,
                message=f"Physician notification sent for {mrn}",
                priority="MODERATE",
            ))
        else:
            notifications.append(Notification(
                recipient_role="Bedside Nurse",
                recipient_name="Primary RN",
                action=EscalationAction.ALERT,
                message=f"Patient {mrn} showing concerning trends - Intensify monitoring",
                priority="MODERATE",
            ))
        
        if protocol:
            notifications.append(Notification(
                recipient_role="Pharmacist",
                recipient_name="Clinical Pharmacy",
                action=EscalationAction.TEXT,
                message=f"Protocol {protocol} initiated for {mrn} - Antibiotics approval needed",
                priority="MODERATE",
            ))
        
        return notifications

    def _generate_task_list(
        self,
        patient_id: str,
        mrn: str,
        protocol: Optional[str],
        vitals: Dict[str, float],
    ) -> List[Task]:
        tasks = []
        now = datetime.utcnow()
        
        tasks.append(Task(
            id=f"task_{mrn}_vitals",
            description=f"Repeat vitals anddocument in chart for {mrn}",
            assigned_to="Bedside RN",
            due=now,
        ))
        
        if vitals.get("systolic_bp", 120) < 90:
            tasks.append(Task(
                id=f"task_{mrn}_iv",
                description=f"Establish large bore IV access for {mrn}",
                assigned_to="Bedside RN",
                due=now,
            ))
            tasks.append(Task(
                id=f"task_{mrn}_fluid",
                description="Initiate fluid resuscitation per protocol",
                assigned_to="Bedside RN",
                due=now,
            ))
        
        tasks.append(Task(
            id=f"task_{mrn}_labs",
            description=f"Lactate, blood cultures, CBC, BMP for {mrn}",
            assigned_to="Phlebotomist/Lab",
            due=now,
        ))
        
        if protocol and "SEPSIS" in protocol:
            tasks.append(Task(
                id=f"task_{mrn}_abx",
                description=f"Administer broad spectrum antibiotics per {protocol}",
                assigned_to="RN/Pharmacist",
                due=now,
            ))
        
        tasks.append(Task(
            id=f"task_{mrn}_foley",
            description=f"Insert Foley catheter for UO monitoring - {mrn}",
            assigned_to="RN",
            due=now,
        ))
        
        tasks.append(Task(
            id=f"task_{mrn}_icu",
            description=f"Prepare for ICU transfer - {mrn}",
            assigned_to="Bedside RN",
            due=now,
        ))
        
        return tasks

    def _generate_recommendations(self, level: EscalationLevel, diagnosis: str, scores: Dict[str, float]) -> List[str]:
        recommendations = []
        
        if level == EscalationLevel.CODE_BLUE:
            recommendations.extend([
                "Immediate bedside presence required",
                "Activate Code Blue response team",
                "Prepare crash cart and defibrillator",
                "Document all interventions with exact timing",
            ])
        elif level == EscalationLevel.RAPID_RESPONSE:
            recommendations.extend([
                "ICU team to bedside within 5 minutes",
                "Bedside nurse to call charge for additional help",
                "Prepare for potential intubation",
                "Ensure airway equipment at bedside",
            ])
        else:
            recommendations.extend([
                f"Physician assessment within {self._response_times.get(level.value, '30 minutes')}",
                "Intensify monitoring - vitals every 15-30 minutes",
                "Review medication orders for optimization",
                "Consider advance care planning discussion",
            ])
        
        return recommendations

    def _generate_reason(self, level: EscalationLevel, risk_level: str, diagnosis: str, scores: Dict[str, float]) -> str:
        news2 = scores.get("NEWS2", 0)
        sofa = scores.get("SOFA", 0)
        
        return f"{level.value} - {diagnosis} - NEWS2: {news2}, SOFA: {sofa} - Risk: {risk_level}"
