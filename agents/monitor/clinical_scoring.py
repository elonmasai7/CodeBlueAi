from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import uuid
import structlog

logger = structlog.get_logger()


@dataclass
class VitalReading:
    heart_rate: float
    systolic_bp: float
    diastolic_bp: float
    respiratory_rate: float
    temperature: float
    spo2: float
    map: float
    lactate: float = 1.0
    gcs: float = 15.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ClinicalScore:
    name: str
    value: float
    interpretation: str
    components: Dict[str, float] = field(default_factory=dict)
    risk_level: str = "LOW"


class ClinicalScoringService:
    def calculate_news2(self, vitals: VitalReading) -> ClinicalScore:
        score = 0.0
        components = {}

        rr = vitals.respiratory_rate
        if rr <= 11: 
            score += 3
            components["resp_rate"] = 3
        elif rr <= 20: 
            score += 1
            components["resp_rate"] = 1
        elif rr <= 24: 
            score += 2
            components["resp_rate"] = 2
        else: 
            score += 3
            components["resp_rate"] = 3

        hr = vitals.heart_rate
        if hr <= 40: 
            score += 3
            components["heart_rate"] = 3
        elif hr <= 50: 
            score += 1
            components["heart_rate"] = 1
        elif hr <= 90: 
            score += 0
            components["heart_rate"] = 0
        elif hr <= 110: 
            score += 1
            components["heart_rate"] = 1
        elif hr <= 130: 
            score += 2
            components["heart_rate"] = 2
        else: 
            score += 3
            components["heart_rate"] = 3

        sbp = vitals.systolic_bp
        if sbp <= 90: 
            score += 3
            components["systolic_bp"] = 3
        elif sbp <= 100: 
            score += 2
            components["systolic_bp"] = 2
        elif sbp <= 110: 
            score += 1
            components["systolic_bp"] = 1
        elif sbp <= 219: 
            score += 0
            components["systolic_bp"] = 0
        else: 
            score += 3
            components["systolic_bp"] = 3

        spo2 = vitals.spo2
        if spo2 <= 91: 
            score += 3
            components["spo2"] = 3
        elif spo2 <= 93: 
            score += 2
            components["spo2"] = 2
        elif spo2 <= 95: 
            score += 1
            components["spo2"] = 1
        else: 
            score += 0
            components["spo2"] = 0

        temp = vitals.temperature
        if temp <= 35.0: 
            score += 3
            components["temperature"] = 3
        elif temp <= 36.0: 
            score += 1
            components["temperature"] = 1
        elif temp <= 38.0: 
            score += 0
            components["temperature"] = 0
        elif temp <= 39.0: 
            score += 1
            components["temperature"] = 1
        else: 
            score += 2
            components["temperature"] = 2

        if sbp <= 100: 
            score += 2
            components["supplimental_o2"] = 2

        interpretation = self._interpret_news2(score)
        
        return ClinicalScore(
            name="NEWS2",
            value=score,
            interpretation=interpretation,
            components=components,
            risk_level=self._news2_risk_level(score),
        )

    def calculate_sofa(self, vitals: VitalReading, lactate: float = 1.0) -> ClinicalScore:
        score = 0.0
        components = {}

        spo2 = vitals.spo2
        if spo2 < 80: 
            score += 4
            components["pao2_fio2"] = 4
        elif spo2 < 100: 
            score += 3
            components["pao2_fio2"] = 3
        elif spo2 < 150: 
            score += 2
            components["pao2_fio2"] = 2
        elif spo2 < 250: 
            score += 1
            components["pao2_fio2"] = 1
        else: 
            components["pao2_fio2"] = 0

        map_val = vitals.map
        if map_val < 70: 
            score += 4
            components["cardiovascular"] = 4
        elif map_val < 92: 
            score += 3
            components["cardiovascular"] = 3
        elif map_val < 125: 
            score += 2
            components["cardiovascular"] = 2
        else: 
            score += 0
            components["cardiovascular"] = 0

        hr = vitals.heart_rate
        if hr > 150: 
            score += 4
            components["cns"] = 4
        elif hr > 110: 
            score += 3
            components["cns"] = 3
        elif hr > 70: 
            score += 1
            components["cns"] = 1
        else:
            components["cns"] = 0

        if lactate > 4.0: 
            score += 4
            components["liver"] = 4
        elif lactate > 2.5: 
            score += 3
            components["liver"] = 3
        elif lactate > 2.0: 
            score += 2
            components["liver"] = 2
        else:
            components["liver"] = 0

        interpretation = self._interpret_sofa(score)
        
        return ClinicalScore(
            name="SOFA",
            value=score,
            interpretation=interpretation,
            components=components,
            risk_level=self._sofa_risk_level(score),
        )

    def calculate_qsofa(self, vitals: VitalReading) -> ClinicalScore:
        score = 0.0
        components = {}

        rr = vitals.respiratory_rate
        if rr >= 22: 
            score += 1
            components["resp_rate"] = 1
        else:
            components["resp_rate"] = 0

        sbp = vitals.systolic_bp
        if sbp <= 100: 
            score += 1
            components["systolic_bp"] = 1
        else:
            components["systolic_bp"] = 0

        altered = vitals.gcs < 15
        if altered: 
            score += 1
            components["gcs"] = 1
        else:
            components["gcs"] = 0

        interpretation = self._interpret_qsofa(score)
        
        return ClinicalScore(
            name="qSOFA",
            value=score,
            interpretation=interpretation,
            components=components,
            risk_level=self._qsofa_risk_level(score),
        )

    def detect_sepsis(self, vitals: VitalReading, qsofa: ClinicalScore) -> Dict[str, Any]:
        has_qsofa = qsofa.value >= 2
        has_sirs = self._has_sirs(vitals)
        has_hypotension = vitals.systolic_bp < 90
        has_lactate_elevated = vitals.lactate > 2.0
        
        if has_qsofa and has_hypotension:
            return {
                "suspected": True,
                "stage": "SEPTIC_SHOCK",
                "probability": 0.92,
                "evidence": ["qSOFA >= 2", "Hypotension (SBP < 90)", f"Lactate elevated ({vitals.lactate} mmol/L)"],
                "confidence": "HIGH",
            }
        elif has_qsofa and has_lactate_elevated:
            return {
                "suspected": True,
                "stage": "SEVERE_SEPSIS",
                "probability": 0.85,
                "evidence": ["qSOFA >= 2", f"Lactate elevated ({vitals.lactate} mmol/L)"],
                "confidence": "HIGH",
            }
        elif has_qsofa and has_sirs:
            return {
                "suspected": True,
                "stage": "SEPSIS",
                "probability": 0.72,
                "evidence": ["qSOFA >= 2", "SIRS criteria met"],
                "confidence": "MODERATE",
            }
        elif has_sirs and has_lactate_elevated:
            return {
                "suspected": True,
                "stage": "SEPSIS_SUSPECTED",
                "probability": 0.65,
                "evidence": ["SIRS criteria met", f"Lactate elevated ({vitals.lactate} mmol/L)"],
                "confidence": "MODERATE",
            }
        else:
            return {
                "suspected": False,
                "stage": "NONE",
                "probability": 0.05,
                "evidence": [],
                "confidence": "HIGH",
            }

    def detect_aki(self, creatinine_trend: List[float]) -> Dict[str, Any]:
        if len(creatinine_trend) < 2:
            return {"detected": False}
        
        baseline = creatinine_trend[0]
        current = creatinine_trend[-1]
        
        if current >= baseline * 3:
            return {
                "detected": True,
                "stage": "AKI_STAGE_3",
                "evidence": f"Creatinine increased 3x baseline ({baseline} -> {current})",
            }
        elif current >= baseline * 2:
            return {
                "detected": True,
                "stage": "AKI_STAGE_2",
                "evidence": f"Creatinine increased 2x baseline ({baseline} -> {current})",
            }
        elif current >= baseline * 1.5:
            return {
                "detected": True,
                "stage": "AKI_STAGE_1",
                "evidence": f"Creatinine increased 1.5x baseline ({baseline} -> {current})",
            }
        
        return {"detected": False}

    def _has_sirs(self, vitals: VitalReading) -> bool:
        count = 0
        if vitals.temperature > 38 or vitals.temperature < 36: count += 1
        if vitals.heart_rate > 90: count += 1
        if vitals.respiratory_rate > 20: count += 1
        if vitals.lactate > 2.0: count += 1
        return count >= 2

    def _interpret_news2(self, score: float) -> str:
        if score >= 7: return "High risk - Urgent clinical review recommended"
        if score >= 5: return "Medium risk - Senior nurse review within 1 hour"
        if score >= 1: return "Low-medium risk - Continue routine monitoring"
        return "Low risk - Standard monitoring"

    def _interpret_sofa(self, score: float) -> str:
        if score >= 12: return "Severe organ dysfunction (>50% mortality)"
        if score >= 10: return "Severe organ dysfunction (40-50% mortality)"
        if score >= 6: return "Moderate organ dysfunction (25-35% mortality)"
        if score >= 2: return "Mild organ dysfunction (<10% mortality)"
        return "Normal organ function"

    def _interpret_qsofa(self, score: float) -> str:
        if score == 3: return "High risk of poor outcome - ICU admission likely"
        if score == 2: return "Moderate risk - Consider ICU evaluation"
        if score == 1: return "Low risk - Standard care"
        return "Minimal risk - Routine care"

    def _news2_risk_level(self, score: float) -> str:
        if score >= 7: return "CRITICAL"
        if score >= 5: return "HIGH"
        if score >= 1: return "MODERATE"
        return "LOW"

    def _sofa_risk_level(self, score: float) -> str:
        if score >= 12: return "CRITICAL"
        if score >= 6: return "HIGH"
        if score >= 2: return "MODERATE"
        return "LOW"

    def _qsofa_risk_level(self, score: float) -> str:
        if score >= 2: return "CRITICAL"
        if score == 1: return "MODERATE"
        return "LOW"
