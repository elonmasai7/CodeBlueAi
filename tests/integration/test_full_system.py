import pytest
import asyncio
from datetime import datetime
from a2a_bus.message_bus import A2AMessageBus, A2AMessage, AgentType


@pytest.fixture
def bus():
    return A2AMessageBus()


class TestA2AMessageBus:
    def test_contract_registration(self, bus):
        stats = bus.get_stats()
        assert stats["registered_contracts"] >= 5
        assert stats["registered_handlers"] == 0

    @pytest.mark.asyncio
    async def test_message_validation(self, bus):
        valid_msg = A2AMessage(
            id="test-001",
            from_agent=AgentType.MONITOR,
            to_agent=AgentType.DIAGNOSTIC,
            message_type="VITAL_ALERT",
            payload={
                "patient_id": "patient-123",
                "mrn": "MRN001",
                "vitals": {"heart_rate": 130, "systolic_bp": 85},
            },
        )
        result = await bus.send_message(valid_msg)
        assert result == True

    @pytest.mark.asyncio
    async def test_invalid_message_goes_to_dlq(self, bus):
        invalid_msg = A2AMessage(
            id="test-002",
            from_agent=AgentType.MONITOR,
            to_agent=AgentType.DIAGNOSTIC,
            message_type="VITAL_ALERT",
            payload={"patient_id": "patient-123"},
        )
        result = await bus.send_message(invalid_msg)
        assert result == False
        assert len(bus.get_dead_letter_messages()) >= 1

    @pytest.mark.asyncio
    async def test_handler_execution(self, bus):
        received = []

        async def handler(message: A2AMessage):
            received.append(message)
            return True

        bus.register_handler("DIAGNOSTIC_REQUEST", handler)

        msg = A2AMessage(
            id="test-003",
            from_agent=AgentType.MONITOR,
            to_agent=AgentType.DIAGNOSTIC,
            message_type="DIAGNOSTIC_REQUEST",
            payload={
                "patient_id": "patient-123",
                "mrn": "MRN001",
                "clinical_data": {"vitals": {}},
            },
            reply_to="test-003",
        )
        await bus.send_message(msg)

        assert len(received) == 1
        assert received[0].id == "test-003"

    def test_stats(self, bus):
        stats = bus.get_stats()
        assert "queue_length" in stats
        assert "dead_letter_length" in stats
        assert "registered_contracts" in stats
        assert "messages_by_type" in stats

    def test_dlq_retry(self, bus):
        result = bus.retry_dead_letter("nonexistent-id")
        assert result == False


class TestA2AContracts:
    def test_vital_alert_contract(self, bus):
        contract = bus._contracts.get("VITAL_ALERT")
        assert contract is not None
        assert "patient_id" in contract.schema["required"]
        assert "mrn" in contract.schema["required"]
        assert "vitals" in contract.schema["required"]

    def test_escalation_contract(self, bus):
        contract = bus._contracts.get("ESCALATION_REQUEST")
        assert contract is not None
        assert "risk_level" in contract.schema["required"]
        assert contract.required_agents == [AgentType.COORDINATOR]


class TestCircuitBreakerIntegration:
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self):
        from backend.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        cb = CircuitBreaker("test-service", CircuitBreakerConfig(failure_threshold=3, recovery_timeout=1))

        failures = 0
        for i in range(5):
            try:
                async def failing_func():
                    raise Exception("Service down")

                await cb.call(failing_func)
            except Exception:
                failures += 1

        assert cb.state.value == "OPEN"
        assert cb.failure_count >= 3

    @pytest.mark.asyncio
    async def test_circuit_breaker_allows_half_open(self):
        from backend.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        cb = CircuitBreaker("test-service-2", CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0))

        for i in range(3):
            try:
                async def failing():
                    raise Exception("down")
                await cb.call(failing)
            except Exception:
                pass

        assert cb.state.value == "OPEN"

        await asyncio.sleep(0.1)
        assert cb._should_attempt_reset()
        assert cb.state.value == "HALF_OPEN"


class TestRBACService:
    def test_admin_has_all_permissions(self):
        from backend.services.security import rbac_service, UserRole, Permission

        perms = rbac_service.get_permissions(UserRole.ADMIN)
        all_perms = [p for p in Permission]
        assert set(perms) == set(all_perms)

    def test_readonly_minimal_permissions(self):
        from backend.services.security import rbac_service, UserRole, Permission

        perms = rbac_service.get_permissions(UserRole.READONLY)
        assert Permission.READ_PATIENT in perms
        assert Permission.MANAGE_USERS not in perms
        assert Permission.WRITE_PATIENT not in perms

    def test_nurse_can_dispatch_alerts(self):
        from backend.services.security import rbac_service, UserRole, Permission

        assert rbac_service.has_permission(UserRole.NURSE, Permission.DISPATCH_ALERT)
        assert not rbac_service.has_permission(UserRole.NURSE, Permission.RUN_ANALYSIS)

    def test_filter_by_permission(self):
        from backend.services.security import rbac_service, UserRole, Permission

        resources = [{"id": 1, "type": "patient"}, {"id": 2, "type": "patient"}]
        result = rbac_service.filter_by_permission(UserRole.PHARMACIST, resources, Permission.READ_PATIENT)
        assert len(result) == 2

        result = rbac_service.filter_by_permission(UserRole.READONLY, resources, Permission.WRITE_PATIENT)
        assert len(result) == 0


class TestSMARTonFHIR:
    @pytest.mark.asyncio
    async def test_launch_url_generation(self):
        from backend.services.smart_on_fhir import smart_service

        url = smart_service.build_launch_url()
        assert "authorization_uri" in url or "client_id" in url

    @pytest.mark.asyncio
    async def test_token_exchange_invalid_code(self):
        from backend.services.smart_on_fhir import SMARTBundleRequest

        request = SMARTBundleRequest(
            grant_type="authorization_code",
            code="invalid_code",
            redirect_uri="http://localhost/callback",
            client_id="test-client",
        )

        with pytest.raises(ValueError, match="Invalid authorization code"):
            await smart_service.token_exchange(request)

    @pytest.mark.asyncio
    async def test_token_introspection(self):
        from backend.services.smart_on_fhir import SMARTBundleRequest, smart_service

        auth_request = SMARTBundleRequest(
            grant_type="authorization_code",
            code="valid_code_placeholder",
            redirect_uri="http://localhost/callback",
            client_id="codeblue-smart-client",
        )

        with pytest.raises(ValueError):
            await smart_service.token_exchange(auth_request)


class TestFHIRClient:
    @pytest.mark.asyncio
    async def test_fhir_client_context_manager(self):
        from fhir.client import FHIRClient

        client = FHIRClient("http://localhost:8080/fhir")
        async with client as c:
            assert c.base_url == "http://localhost:8080/fhir"

    @pytest.mark.asyncio
    async def test_fhir_search_endpoint(self):
        from fhir.client import FHIRClient

        client = FHIRClient("http://nonexistent:9999")
        async with client:
            with pytest.raises(Exception):
                await client.get_capability_statement()


class TestMonitoringFlow:
    @pytest.mark.asyncio
    async def test_full_agent_chain_simulation(self):
        from agents.monitor.agent import MonitorAgent
        from agents.monitor.clinical_scoring import ClinicalScoringService
        from agents.diagnostic.agent import DiagnosticAgent
        from agents.guideline.agent import GuidelineAgent
        from agents.coordinator.agent import CoordinatorAgent

        scoring = ClinicalScoringService()
        monitor = MonitorAgent(scoring)
        diagnostic = DiagnosticAgent()
        guideline = GuidelineAgent()
        coordinator = CoordinatorAgent()

        vitals = {
            "heart_rate": 128,
            "systolic_bp": 82,
            "diastolic_bp": 52,
            "respiratory_rate": 30,
            "temperature": 39.2,
            "spo2": 87,
            "map": 62,
            "lactate": 4.8,
            "gcs": 15,
        }

        monitor_result = monitor.analyze_clinical_picture("patient-001", "MRN001", vitals)
        assert monitor_result["scores"]["NEWS2"]["value"] >= 10
        assert monitor_result["sepsis_screening"]["suspected"] == True
        assert monitor_result["sepsis_screening"]["stage"] == "SEPTIC_SHOCK"

        diagnostic_result = await diagnostic.analyze(
            "patient-001", "MRN001", vitals,
            [{"test_name": "Lactate", "value": 4.8}, {"test_name": "WBC", "value": 18.5}],
            [], [], ["Penicillin"],
            ["Diabetes", "Hypertension"],
            "Community Acquired Pneumonia",
        )
        assert diagnostic_result.primary_diagnosis is not None
        assert diagnostic_result.primary_diagnosis.probability > 0.5

        guideline_result = guideline.generate_response(
            "patient-001", "MRN001",
            diagnostic_result.primary_diagnosis.code,
            diagnostic_result.primary_diagnosis.name,
            {"vitals": vitals},
        )
        assert "Sepsis" in guideline_result.triggered_protocol or "SEPTIC" in guideline_result.triggered_protocol
        assert guideline_result.urgency in ["IMMEDIATE", "URGENT"]
        assert len(guideline_result.protocol_details.interventions) > 0

        coordinator_result = coordinator.coordinate_escalation(
            "patient-001", "MRN001",
            monitor_result["scores"]["NEWS2"]["risk_level"],
            diagnostic_result.primary_diagnosis.name,
            guideline_result.triggered_protocol,
            monitor_result["scores"],
            vitals,
        )
        assert coordinator_result.level.value in ["CODE_BLUE", "RAPID_RESPONSE"]
        assert len(coordinator_result.tasks) > 0
        assert len(coordinator_result.notifications) > 0
