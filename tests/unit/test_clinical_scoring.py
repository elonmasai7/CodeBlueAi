import pytest
from datetime import datetime
from agents.monitor.clinical_scoring import ClinicalScoringService, VitalReading


@pytest.fixture
def scoring_service():
    return ClinicalScoringService()


class TestClinicalScoring:
    def test_news2_normal(self, scoring_service):
        vitals = VitalReading(
            heart_rate=70,
            systolic_bp=120,
            diastolic_bp=80,
            respiratory_rate=16,
            temperature=37.0,
            spo2=98,
            map=93,
            lactate=1.0,
        )
        score = scoring_service.calculate_news2(vitals)
        assert score.value == 0
        assert score.risk_level == "LOW"

    def test_news2_high_risk(self, scoring_service):
        vitals = VitalReading(
            heart_rate=140,
            systolic_bp=85,
            diastolic_bp=50,
            respiratory_rate=28,
            temperature=39.5,
            spo2=85,
            map=62,
            lactate=5.0,
        )
        score = scoring_service.calculate_news2(vitals)
        assert score.value >= 15
        assert score.risk_level == "CRITICAL"

    def test_qsofa_sepsis(self, scoring_service):
        vitals = VitalReading(
            heart_rate=110,
            systolic_bp=90,
            respiratory_rate=26,
            spo2=92,
            map=85,
            gcs=14,
        )
        score = scoring_service.calculate_qsofa(vitals)
        assert score.value >= 2
        assert score.risk_level == "CRITICAL"

    def test_sepsis_detection_shock(self, scoring_service):
        vitals = VitalReading(
            heart_rate=130,
            systolic_bp=78,
            diastolic_bp=50,
            respiratory_rate=30,
            temperature=39.2,
            spo2=86,
            map=60,
            lactate=4.8,
        )
        qsofa = scoring_service.calculate_qsofa(vitals)
        result = scoring_service.detect_sepsis(vitals, qsofa)
        assert result["suspected"] == True
        assert result["stage"] == "SEPTIC_SHOCK"
        assert result["probability"] >= 0.8

    def test_sofa_moderate(self, scoring_service):
        vitals = VitalReading(
            heart_rate=100,
            systolic_bp=100,
            diastolic_bp=60,
            respiratory_rate=22,
            temperature=38.5,
            spo2=140,
            map=75,
            lactate=3.0,
        )
        score = scoring_service.calculate_sofa(vitals)
        assert score.value >= 2
        assert score.risk_level in ["MODERATE", "HIGH", "CRITICAL"]


class TestMonitorAgent:
    def test_vital_alert_detection(self):
        from agents.monitor.agent import MonitorAgent
        service = ClinicalScoringService()
        agent = MonitorAgent(service)
        
        alerts = agent.monitor_vitals(
            "patient_123",
            "MRN001",
            {"heart_rate": 150, "systolic_bp": 80, "spo2": 84}
        )
        
        assert len(alerts) >= 3
        assert any(a.severity == "CRITICAL" for a in alerts)

    def test_clinical_analysis(self):
        from agents.monitor.agent import MonitorAgent
        service = ClinicalScoringService()
        agent = MonitorAgent(service)
        
        result = agent.analyze_clinical_picture(
            "patient_123",
            "MRN001",
            {
                "heart_rate": 130,
                "systolic_bp": 82,
                "diastolic_bp": 52,
                "respiratory_rate": 28,
                "temperature": 39.2,
                "spo2": 87,
                "map": 62,
                "lactate": 4.8,
                "gcs": 15,
            }
        )
        
        assert result["scores"]["NEWS2"]["value"] >= 10
        assert result["sepsis_screening"]["suspected"] == True
        assert len(result["alerts"]) > 0
