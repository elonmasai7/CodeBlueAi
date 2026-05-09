import pytest
from agents.coordinator.agent import CoordinatorAgent, EscalationLevel


@pytest.fixture
def coordinator_agent():
    return CoordinatorAgent()


class TestCoordinatorAgent:
    def test_critical_escalation(self, coordinator_agent):
        escalation = coordinator_agent.coordinate_escalation(
            patient_id="test_patient",
            mrn="MRN001",
            risk_level="CRITICAL",
            diagnosis="Septic Shock",
            protocol="1-Hour Sepsis Bundle",
            scores={"NEWS2": 12, "SOFA": 11, "qSOFA": 3},
            vitals={"systolic_bp": 78, "heart_rate": 130},
        )
        
        assert escalation.level == EscalationLevel.CODE_BLUE
        assert len(escalation.notifications) >= 2
        assert any(n.priority == "CRITICAL" for n in escalation.notifications)

    def test_high_risk_escalation(self, coordinator_agent):
        escalation = coordinator_agent.coordinate_escalation(
            patient_id="test_patient",
            mrn="MRN001",
            risk_level="HIGH",
            diagnosis="Sepsis",
            protocol="Severe Sepsis Bundle",
            scores={"NEWS2": 8, "SOFA": 6},
            vitals={"systolic_bp": 95, "heart_rate": 110},
        )
        
        assert escalation.level == EscalationLevel.RAPID_RESPONSE
        assert len(escalation.tasks) >= 3

    def test_task_generation(self, coordinator_agent):
        escalation = coordinator_agent.coordinate_escalation(
            patient_id="test_patient",
            mrn="MRN001",
            risk_level="CRITICAL",
            diagnosis="Septic Shock",
            protocol="Sepsis Bundle",
            scores={"NEWS2": 10},
            vitals={"systolic_bp": 75},
        )
        
        assert len(escalation.tasks) > 0
        assert any("vitals" in t.description.lower() for t in escalation.tasks)
        assert any("labs" in t.description.lower() for t in escalation.tasks)

    def test_notification_types(self, coordinator_agent):
        escalation = coordinator_agent.coordinate_escalation(
            patient_id="test_patient",
            mrn="MRN001",
            risk_level="HIGH",
            diagnosis="Sepsis",
            protocol=None,
            scores={},
            vitals={},
        )
        
        assert len(escalation.notifications) >= 1
        assert all(hasattr(n, 'recipient_role') for n in escalation.notifications)
        assert all(hasattr(n, 'action') for n in escalation.notifications)
