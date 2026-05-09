import pytest
from agents.documentation.agent import DocumentationAgent


@pytest.fixture
def documentation_agent():
    return DocumentationAgent()


class TestDocumentationAgent:
    def test_sepsis_soap_note(self, documentation_agent):
        soap = documentation_agent.generate_soap_note(
            patient_id="test_patient",
            mrn="MRN001",
            patient_name="John Doe",
            vitals={
                "heart_rate": 130,
                "systolic_bp": 82,
                "diastolic_bp": 52,
                "respiratory_rate": 28,
                "temperature": 39.2,
                "spo2": 87,
                "lactate": 4.8,
            },
            labs=[
                {"test_name": "Lactate", "value": 4.8},
                {"test_name": "WBC", "value": 18.5},
            ],
            medications=[{"name": "Vancomycin"}, {"name": "Piperacillin"}],
            diagnosis="Sepsis - Pulmonary Source",
            protocol="1-Hour Sepsis Bundle",
            scores={"NEWS2": 12, "qSOFA": 3, "SOFA": 10},
            escalation={"level": "RAPID_RESPONSE", "reason": "Sepsis suspected"},
        )
        
        assert soap.subjective
        assert soap.objective
        assert soap.assessment
        assert soap.plan
        assert soap.clinical_rationale
        assert "sepsis" in soap.assessment.lower()
        assert "bundle" in soap.plan.lower()

    def test_stemi_soap_note(self, documentation_agent):
        soap = documentation_agent.generate_soap_note(
            patient_id="test_patient",
            mrn="MRN001",
            patient_name="Jane Smith",
            vitals={
                "heart_rate": 110,
                "systolic_bp": 80,
                "diastolic_bp": 50,
            },
            labs=[{"test_name": "Troponin I", "value": 5.2}],
            medications=[],
            diagnosis="STEMI - Anterior Wall",
            protocol="STEMI Protocol",
            scores={"NEWS2": 8},
        )
        
        assert "stemi" in soap.assessment.lower() or "mi" in soap.assessment.lower()
        assert "aspirin" in soap.plan.lower()

    def test_fhir_updates_generation(self, documentation_agent):
        soap = documentation_agent.generate_soap_note(
            patient_id="test_patient",
            mrn="MRN001",
            patient_name="John Doe",
            vitals={},
            labs=[],
            medications=[],
            diagnosis="Sepsis",
            protocol="Sepsis Bundle",
            scores={},
        )
        
        updates = documentation_agent.generate_fhir_updates(
            soap,
            {"level": "RAPID_RESPONSE", "reason": "Clinical deterioration"}
        )
        
        assert len(updates) >= 1
        assert updates[0]["resourceType"] == "Communication"
