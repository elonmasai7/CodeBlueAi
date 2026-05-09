import pytest
from datetime import datetime
from agents.diagnostic.agent import DiagnosticAgent


@pytest.fixture
def diagnostic_agent():
    return DiagnosticAgent()


class TestDiagnosticAgent:
    @pytest.mark.asyncio
    async def test_sepsis_diagnosis(self, diagnostic_agent):
        result = await diagnostic_agent.analyze(
            patient_id="test_patient",
            mrn="MRN001",
            vitals={
                "heart_rate": 130,
                "systolic_bp": 82,
                "diastolic_bp": 52,
                "respiratory_rate": 28,
                "temperature": 39.2,
                "spo2": 87,
                "map": 62,
                "lactate": 4.8,
            },
            labs=[
                {"test_name": "Lactate", "value": 4.8},
                {"test_name": "WBC", "value": 18.5},
                {"test_name": "CRP", "value": 250},
                {"test_name": "Procalcitonin", "value": 25.0},
            ],
            medications=[{"name": "Vancomycin"}, {"name": "Piperacillin"}],
            allergies=["Penicillin"],
            comorbidities=["Diabetes", "Hypertension"],
            primary_diagnosis="Community Acquired Pneumonia",
        )
        
        assert result.primary_diagnosis is not None
        assert result.primary_diagnosis.probability > 0.5
        assert "sepsis" in result.primary_diagnosis.name.lower() or "pneumonia" in result.primary_diagnosis.name.lower()

    @pytest.mark.asyncio
    async def test_stemi_diagnosis(self, diagnostic_agent):
        result = await diagnostic_agent.analyze(
            patient_id="test_patient",
            mrn="MRN001",
            vitals={
                "heart_rate": 110,
                "systolic_bp": 80,
                "diastolic_bp": 50,
                "respiratory_rate": 22,
                "temperature": 37.0,
                "spo2": 95,
                "map": 60,
                "lactate": 1.5,
            },
            labs=[
                {"test_name": "Troponin I", "value": 5.2},
            ],
            medications=[],
            allergies=[],
            comorbidities=["Hyperlipidemia"],
            primary_diagnosis="Chest Pain",
        )
        
        assert result.primary_diagnosis is not None
        assert "stemi" in result.primary_diagnosis.name.lower()

    @pytest.mark.asyncio
    async def test_risk_prediction(self, diagnostic_agent):
        result = await diagnostic_agent.analyze(
            patient_id="test_patient",
            mrn="MRN001",
            vitals={"heart_rate": 140, "systolic_bp": 75, "spo2": 85, "lactate": 5.5},
            labs=[{"test_name": "Lactate", "value": 5.5}],
            medications=[],
            allergies=[],
            comorbidities=[],
            primary_diagnosis="Sepsis",
        )
        
        assert result.risk_prediction["icu_admission_probability"] > 0.5
        assert len(result.risk_prediction["risk_factors"]) > 0
