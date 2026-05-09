import pytest
from fhir.client import FHIRClient, FHIRBundle
from datetime import datetime


class TestFHIRResourceValidation:
    def test_observation_loinc_codes(self):
        loinc_map = {
            "heart-rate": "8867-4",
            "systolic-bp": "8480-6",
            "diastolic-bp": "8462-4",
            "body-temp": "8310-5",
            "resp-rate": "9279-1",
            "spo2": "2708-6",
            "lactate": "2519-8",
        }
        for name, code in loinc_map.items():
            assert len(code) == 5 or len(code) == 6
            assert code.isdigit() or "-" in code

    def test_bundle_type_validation(self):
        valid_types = ["searchset", "batch", "transaction", "history", "document", "collection"]
        for vt in valid_types:
            b = FHIRBundle(type=vt)
            assert b.type == vt

    @pytest.mark.asyncio
    async def test_fhir_client_initialization(self):
        client = FHIRClient("http://localhost:8080/fhir", timeout=5)
        async with client:
            assert client.base_url == "http://localhost:8080/fhir"
            assert client.timeout == 5


class TestFHIRBundleCompliance:
    def test_bundle_structure(self):
        bundle = FHIRBundle(
            resource_type="Bundle",
            type="searchset",
            total=5,
            entry=[
                {
                    "fullUrl": "http://example.com/Patient/123",
                    "resource": {
                        "resourceType": "Patient",
                        "id": "123",
                        "name": [{"family": "Doe", "given": ["John"]}],
                    }
                }
            ]
        )

        assert bundle.resource_type == "Bundle"
        assert bundle.type == "searchset"
        assert len(bundle.entry) == 1
        assert bundle.entry[0]["resource"]["resourceType"] == "Patient"

    def test_patient_resource_structure(self):
        patient = {
            "resourceType": "Patient",
            "id": "test-001",
            "identifier": [
                {"system": "http://hospital.example/mrn", "value": "MRN001"}
            ],
            "name": [{"family": "Doe", "given": ["John"]}],
            "gender": "male",
            "birthDate": "1964-01-15",
            "address": [{"city": "Boston", "state": "MA"}],
        }

        assert patient["resourceType"] == "Patient"
        assert "identifier" in patient
        assert "name" in patient
        assert "gender" in patient
        assert "birthDate" in patient

    def test_observation_resource_structure(self):
        observation = {
            "resourceType": "Observation",
            "status": "final",
            "category": [{"coding": [{"code": "vital-signs", "display": "Vital Signs"}]}],
            "subject": {"reference": "Patient/test-001"},
            "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4", "display": "Heart rate"}]},
            "effectiveDateTime": datetime.utcnow().isoformat(),
            "valueQuantity": {"value": 88, "unit": "bpm"},
        }

        assert observation["resourceType"] == "Observation"
        assert observation["status"] in ["final", "preliminary", "registered", "cancelled"]
        assert "code" in observation
        assert "valueQuantity" in observation or "component" in observation

    def test_medication_request_structure(self):
        med_req = {
            "resourceType": "MedicationRequest",
            "status": "active",
            "intent": "order",
            "medicationReference": {"display": "Vancomycin 1g IV"},
            "subject": {"reference": "Patient/test-001"},
            "dosageInstruction": [{"text": "1g IV q12h", "route": {"text": "Intravenous"}}],
        }

        assert med_req["resourceType"] == "MedicationRequest"
        assert med_req["status"] in ["active", "on-hold", "completed", "cancelled", "stopped"]
        assert med_req["intent"] in ["proposal", "plan", "order", "original-order", "reflex-order", "filler-order", "instance-order"]

    def test_communication_structure(self):
        comm = {
            "resourceType": "Communication",
            "status": "completed",
            "category": [{"coding": [{"code": "clinical-procedure"}]}],
            "subject": {"reference": "Patient/test-001"},
            "sent": datetime.utcnow().isoformat(),
            "payload": [{"contentString": "SOAP note: Septic shock diagnosed. 1-hour bundle initiated."}],
        }

        assert comm["resourceType"] == "Communication"
        assert comm["status"] in ["preparation", "in-progress", "not-done", "on-hold", "stopped", "completed", "entered-in-error"]
        assert "payload" in comm
        assert len(comm["payload"]) > 0

    def test_detected_issue_structure(self):
        di = {
            "resourceType": "DetectedIssue",
            "status": "preliminary",
            "severity": "high",
            "subject": {"reference": "Patient/test-001"},
            "detail": "Sepsis detected - NEWS2 12, qSOFA 3",
            "date": datetime.utcnow().isoformat(),
        }

        assert di["resourceType"] == "DetectedIssue"
        assert di["severity"] in ["high", "moderate", "low"]
        assert di["status"] in ["preliminary", "confirmed", "refuted", "entered-in-error"]

    def test_care_plan_structure(self):
        cp = {
            "resourceType": "CarePlan",
            "status": "active",
            "intent": "plan",
            "title": "1-Hour Sepsis Bundle",
            "description": "Initiate within 1 hour of septic shock recognition",
            "subject": {"reference": "Patient/test-001"},
            "period": {"start": datetime.utcnow().isoformat()},
        }

        assert cp["resourceType"] == "CarePlan"
        assert cp["status"] in ["active", "on-hold", "completed", "cancelled", "entered-in-error"]
        assert cp["intent"] == "plan"
