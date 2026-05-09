from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import structlog

logger = structlog.get_logger()


class AlertLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    INFO = "INFO"


class AlertType(str, Enum):
    VITAL_ABNORMALITY = "VITAL_ABNORMALITY"
    SEPSIS_SUSPECTED = "SEPSIS_SUSPECTED"
    SEPTIC_SHOCK = "SEPTIC_SHOCK"
    AKI_DETECTED = "AKI_DETECTED"
    STROKE_SCREEN = "STROKE_SCREEN"
    ACS_SCREEN = "ACS_SCREEN"
    LAB_CRITICAL = "LAB_CRITICAL"
    MEDICATION_ALERT = "MEDICATION_ALERT"
    DETERIORATION = "DETERIORATION"


@dataclass
class Alert:
    id: str
    alert_type: AlertType
    severity: AlertLevel
    patient_id: str
    mrn: str
    title: str
    description: str
    evidence: List[str] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None


class MonitorAgent:
    def __init__(self, scoring_service):
        self.scoring_service = scoring_service
        self._thresholds = {
            "heart_rate": {"low": 50, "high": 130},
            "systolic_bp": {"low": 85, "high": 180},
            "diastolic_bp": {"low": 50, "high": 120},
            "respiratory_rate": {"low": 10, "high": 28},
            "temperature": {"low": 35.5, "high": 39.0},
            "spo2": {"low": 88, "high": 100},
            "lactate": {"low": 0.5, "high": 4.0},
        }

    def monitor_vitals(self, patient_id: str, mrn: str, vitals: Dict[str, float]) -> List[Alert]:
        alerts = []
        
        for key, threshold in self._thresholds.items():
            value = vitals.get(key)
            if value is None:
                continue
            
            if value < threshold["low"] or value > threshold["high"]:
                severity = self._determine_severity(key, value, threshold)
                alerts.append(self._create_vital_alert(patient_id, mrn, key, value, threshold, severity))
        
        return alerts

    def analyze_clinical_picture(self, patient_id: str, mrn: str, vitals: Dict[str, float]) -> Dict[str, Any]:
        from agents.monitor.clinical_scoring import VitalReading
        
        reading = VitalReading(
            heart_rate=vitals.get("heart_rate", 70),
            systolic_bp=vitals.get("systolic_bp", 120),
            diastolic_bp=vitals.get("diastolic_bp", 80),
            respiratory_rate=vitals.get("respiratory_rate", 16),
            temperature=vitals.get("temperature", 37.0),
            spo2=vitals.get("spo2", 97),
            map=vitals.get("map", 90),
            lactate=vitals.get("lactate", 1.0),
            gcs=vitals.get("gcs", 15.0),
        )
        
        news2 = self.scoring_service.calculate_news2(reading)
        sofa = self.scoring_service.calculate_sofa(reading)
        qsofa = self.scoring_service.calculate_qsofa(reading)
        sepsis = self.scoring_service.detect_sepsis(reading, qsofa)
        
        result = {
            "patient_id": patient_id,
            "mrn": mrn,
            "scores": {
                "NEWS2": {
                    "value": news2.value,
                    "interpretation": news2.interpretation,
                    "risk_level": news2.risk_level,
                    "components": news2.components,
                },
                "SOFA": {
                    "value": sofa.value,
                    "interpretation": sofa.interpretation,
                    "risk_level": sofa.risk_level,
                    "components": sofa.components,
                },
                "qSOFA": {
                    "value": qsofa.value,
                    "interpretation": qsofa.interpretation,
                    "risk_level": qsofa.risk_level,
                    "components": qsofa.components,
                },
            },
            "sepsis_screening": sepsis,
            "alerts": [],
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        if news2.risk_level in ["CRITICAL", "HIGH"]:
            result["alerts"].append({
                "type": AlertType.DETERIORATION,
                "severity": news2.risk_level,
                "title": f"Patient Deterioration - NEWS2 {news2.value}",
                "description": news2.interpretation,
            })
        
        if sepsis["suspected"]:
            result["alerts"].append({
                "type": AlertType.SEPSIS_SUSPECTED if sepsis["stage"] != "SEPTIC_SHOCK" else AlertType.SEPTIC_SHOCK,
                "severity": AlertLevel.CRITICAL,
                "title": f"Sepsis {sepsis['stage']} - Probability {sepsis['probability']:.0%}",
                "description": f"Suspected {sepsis['stage']} with {sepsis['confidence']} confidence",
                "evidence": sepsis["evidence"],
            })
        
        return result

    def _determine_severity(self, key: str, value: float, threshold: Dict) -> AlertLevel:
        if key == "heart_rate":
            if value > 150 or value < 40: return AlertLevel.CRITICAL
            if value > 130 or value < 50: return AlertLevel.HIGH
            return AlertLevel.MODERATE
        elif key == "systolic_bp":
            if value < 70 or value > 200: return AlertLevel.CRITICAL
            if value < 85 or value > 180: return AlertLevel.HIGH
            return AlertLevel.MODERATE
        elif key == "spo2":
            if value < 85: return AlertLevel.CRITICAL
            if value < 88: return AlertLevel.HIGH
            return AlertLevel.MODERATE
        elif key == "temperature":
            if value > 40 or value < 35: return AlertLevel.CRITICAL
            if value > 39 or value < 35.5: return AlertLevel.HIGH
            return AlertLevel.MODERATE
        elif key == "lactate":
            if value > 6: return AlertLevel.CRITICAL
            if value > 4: return AlertLevel.HIGH
            return AlertLevel.MODERATE
        else:
            return AlertLevel.MODERATE

    def _create_vital_alert(self, patient_id: str, mrn: str, vital_key: str, value: float, threshold: Dict, severity: AlertLevel) -> Alert:
        return Alert(
            id=f"alert_{patient_id}_{vital_key}_{datetime.utcnow().timestamp()}",
            alert_type=AlertType.VITAL_ABNORMALITY,
            severity=severity,
            patient_id=patient_id,
            mrn=mrn,
            title=f"Abnormal {vital_key.replace('_', ' ').title()}",
            description=f"{vital_key.replace('_', ' ').title()}: {value} (Range: {threshold['low']}-{threshold['high']})",
            evidence=[f"Current value: {value}", f"Threshold range: {threshold['low']}-{threshold['high']}"],
        )
