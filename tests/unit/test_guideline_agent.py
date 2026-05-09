import pytest
from agents.guideline.agent import GuidelineAgent


@pytest.fixture
def guideline_agent():
    return GuidelineAgent()


class TestGuidelineAgent:
    def test_septic_shock_protocol(self, guideline_agent):
        protocol = guideline_agent.get_protocol("SEPTIC_SHOCK", "Septic Shock")
        
        assert protocol is not None
        assert protocol.name == "1-Hour Sepsis Bundle"
        assert len(protocol.interventions) >= 4
        assert any("lactate" in i.action.lower() for i in protocol.interventions)
        assert any("antibiotics" in i.action.lower() for i in protocol.interventions)

    def test_stemi_protocol(self, guideline_agent):
        protocol = guideline_agent.get_protocol("STEMI", "STEMI")
        
        assert protocol is not None
        assert "STEMI" in protocol.name
        assert any("Aspirin" in i.action for i in protocol.interventions)
        assert any("Cath Lab" in i.action for i in protocol.interventions)

    def test_stroke_protocol(self, guideline_agent):
        protocol = guideline_agent.get_protocol("ISCHEMIC_STROKE", "Ischemic Stroke")
        
        assert protocol is not None
        assert "Stroke" in protocol.name
        assert any("CT" in i.action for i in protocol.interventions)

    def test_protocol_response_generation(self, guideline_agent):
        response = guideline_agent.generate_response(
            patient_id="test_patient",
            mrn="MRN001",
            diagnosis_code="SEPTIC_SHOCK",
            diagnosis_name="Septic Shock",
            patient_data={
                "vitals": {"systolic_bp": 78, "heart_rate": 130}
            }
        )
        
        assert response.triggered_protocol == "1-Hour Sepsis Bundle"
        assert response.urgency in ["IMMEDIATE", "URGENT"]
        assert len(response.protocol_details.interventions) > 0

    def test_unknown_diagnosis(self, guideline_agent):
        protocol = guideline_agent.get_protocol("UNKNOWN", "Unknown condition")
        response = guideline_agent.generate_response(
            "test", "MRN001", "UNKNOWN", "Unknown", {}
        )
        
        assert response.triggered_protocol == "GENERAL_SUPPORTIVE"
        assert response.urgency == "STANDARD"
