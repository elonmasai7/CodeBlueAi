from typing import Dict, List, Optional, Any, Literal
from dataclasses import dataclass, field
from datetime import datetime
import structlog
import httpx

logger = structlog.get_logger()


@dataclass
class FHIRResource:
    resource_type: str
    id: Optional[str] = None
    meta: Optional[Dict] = None
    implicit_rules: Optional[str] = None
    language: Optional[str] = "en"


@dataclass
class FHIRBundle:
    resource_type: str = "Bundle"
    type: str = "searchset"
    total: int = 0
    entry: List[Dict[str, Any]] = field(default_factory=list)


class FHIRClient:
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._auth_token: Optional[str] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            headers={"Accept": "application/fhir+json", "Content-Type": "application/fhir+json"},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    def set_auth_token(self, token: str):
        self._auth_token = token
        if self._client:
            self._client.headers["Authorization"] = f"Bearer {token}"

    async def _get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        if not self._client:
            raise RuntimeError("FHIRClient must be used as async context manager")
        try:
            response = await self._client.get(path, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error("fhir_get_failed", path=path, status=e.response.status_code, detail=e.response.text[:200])
            raise
        except httpx.RequestError as e:
            logger.error("fhir_request_failed", path=path, error=str(e))
            raise

    async def _post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self._client:
            raise RuntimeError("FHIRClient must be used as async context manager")
        try:
            response = await self._client.post(path, json=data)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error("fhir_post_failed", path=path, status=e.response.status_code)
            raise

    async def _put(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self._client:
            raise RuntimeError("FHIRClient must be used as async context manager")
        try:
            response = await self._client.put(path, json=data)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error("fhir_put_failed", path=path, status=e.response.status_code)
            raise

    async def _delete(self, path: str) -> Dict[str, Any]:
        if not self._client:
            raise RuntimeError("FHIRClient must be used as async context manager")
        try:
            response = await self._client.delete(path)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error("fhir_delete_failed", path=path, status=e.response.status_code)
            raise

    async def get_capability_statement(self) -> Dict[str, Any]:
        return await self._get("/metadata")

    async def get_patient(self, patient_id: str) -> Dict[str, Any]:
        return await self._get(f"/Patient/{patient_id}")

    async def search_patients(
        self,
        name: Optional[str] = None,
        identifier: Optional[str] = None,
        birthdate: Optional[str] = None,
        gender: Optional[str] = None,
        _count: int = 50,
    ) -> FHIRBundle:
        params = {"_count": _count}
        if name:
            params["name"] = name
        if identifier:
            params["identifier"] = identifier
        if birthdate:
            params["birthdate"] = birthdate
        if gender:
            params["gender"] = gender

        result = await self._get("/Patient", params=params)
        return FHIRBundle(**result)

    async def search_observations(
        self,
        patient_id: str,
        category: Optional[str] = "vital-signs",
        code: Optional[str] = None,
        _count: int = 100,
    ) -> FHIRBundle:
        params = {"patient": patient_id, "_count": _count, "_sort": "-date"}
        if category:
            params["category"] = category
        if code:
            params["code"] = code

        result = await self._get("/Observation", params=params)
        return FHIRBundle(**result)

    async def get_latest_vitals(self, patient_id: str) -> Dict[str, Any]:
        vital_codes = {
            "heart-rate": "8867-4",
            "systolic-bp": "8480-6",
            "diastolic-bp": "8462-4",
            "body-temp": "8310-5",
            "resp-rate": "9279-1",
            "spo2": "2708-6",
            "lactate": "2519-8",
        }

        vitals = {}
        for name, loinc in vital_codes.items():
            bundle = await self.search_observations(patient_id, code=loinc, _count=1)
            if bundle.entry:
                entry = bundle.entry[0]
                value = entry.get("resource", {}).get("valueQuantity", {})
                if value:
                    vitals[name] = {
                        "value": value.get("value"),
                        "unit": value.get("unit"),
                        "timestamp": entry.get("resource", {}).get("effectiveDateTime"),
                    }
                component = entry.get("resource", {}).get("component", [])
                for comp in component:
                    comp_val = comp.get("valueQuantity", {})
                    if comp_val:
                        vitals[name] = {
                            "value": comp_val.get("value"),
                            "unit": comp_val.get("unit"),
                            "timestamp": entry.get("resource", {}).get("effectiveDateTime"),
                        }

        return vitals

    async def create_observation(self, patient_id: str, code: str, value: float, unit: str) -> Dict[str, Any]:
        observation = {
            "resourceType": "Observation",
            "status": "final",
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "vital-signs", "display": "Vital Signs"}]}],
            "subject": {"reference": f"Patient/{patient_id}"},
            "code": {"coding": [{"system": "http://loinc.org", "code": code}]},
            "effectiveDateTime": datetime.utcnow().isoformat(),
            "valueQuantity": {"value": value, "unit": unit},
        }
        return await self._post("/Observation", observation)

    async def search_lab_results(
        self,
        patient_id: str,
        category: str = "laboratory",
        _count: int = 50,
    ) -> FHIRBundle:
        params = {"patient": patient_id, "category": category, "_count": _count, "_sort": "-date"}
        result = await self._get("/Observation", params=params)
        return FHIRBundle(**result)

    async def search_medication_requests(
        self,
        patient_id: str,
        status: Optional[str] = None,
    ) -> FHIRBundle:
        params = {"patient": patient_id}
        if status:
            params["status"] = status

        result = await self._get("/MedicationRequest", params=params)
        return FHIRBundle(**result)

    async def search_allergy_intolerances(
        self,
        patient_id: str,
    ) -> FHIRBundle:
        params = {"patient": patient_id}
        result = await self._get("/AllergyIntolerance", params=params)
        return FHIRBundle(**result)

    async def search_conditions(
        self,
        patient_id: str,
        clinical_status: Optional[str] = None,
    ) -> FHIRBundle:
        params = {"patient": patient_id}
        if clinical_status:
            params["clinical-status"] = clinical_status

        result = await self._get("/Condition", params=params)
        return FHIRBundle(**result)

    async def search_encounters(
        self,
        patient_id: str,
        status: Optional[str] = None,
        _count: int = 10,
    ) -> FHIRBundle:
        params = {"patient": patient_id, "_count": _count, "_sort": "-date"}
        if status:
            params["status"] = status

        result = await self._get("/Encounter", params=params)
        return FHIRBundle(**result)

    async def create_communication(self, patient_id: str, content: str) -> Dict[str, Any]:
        communication = {
            "resourceType": "Communication",
            "status": "completed",
            "category": [{"coding": [{"code": "clinical-procedure", "display": "Clinical Procedure"}]}],
            "subject": {"reference": f"Patient/{patient_id}"},
            "sent": datetime.utcnow().isoformat(),
            "payload": [{"contentString": content}],
        }
        return await self._post("/Communication", communication)

    async def create_detected_issue(
        self,
        patient_id: str,
        severity: str,
        detail: str,
    ) -> Dict[str, Any]:
        detected_issue = {
            "resourceType": "DetectedIssue",
            "status": "preliminary",
            "severity": severity,
            "subject": {"reference": f"Patient/{patient_id}"},
            "detail": detail,
            "date": datetime.utcnow().isoformat(),
        }
        return await self._post("/DetectedIssue", detected_issue)

    async def create_care_plan(
        self,
        patient_id: str,
        title: str,
        description: str,
        status: str = "active",
    ) -> Dict[str, Any]:
        care_plan = {
            "resourceType": "CarePlan",
            "status": status,
            "intent": "plan",
            "title": title,
            "description": description,
            "subject": {"reference": f"Patient/{patient_id}"},
            "period": {"start": datetime.utcnow().isoformat()},
        }
        return await self._post("/CarePlan", care_plan)

    async def execute_batch(self, bundle: Dict[str, Any]) -> FHIRBundle:
        response = await self._post("/", bundle)
        return FHIRBundle(**response)

    async def health_check(self) -> bool:
        try:
            await self.get_capability_statement()
            return True
        except Exception:
            return False


class FHIRSyncService:
    def __init__(self, fhir_client: FHIRClient):
        self.client = fhir_client

    async def sync_patient_to_db(self, patient_id: str, db_session) -> Dict[str, Any]:
        from backend.models.models import Patient, VitalSign, LabResult, Medication, AllergyIntolerance

        try:
            fhir_patient = await self.client.get_patient(patient_id)
        except Exception as e:
            logger.error("fhir_sync_patient_fetch_failed", patient_id=patient_id, error=str(e))
            return {"status": "failed", "error": str(e)}

        identifiers = fhir_patient.get("identifier", [])
        mrn = next((id["value"] for id in identifiers if id.get("system", "").endswith("mrn")), patient_id)

        demographics = fhir_patient.get("name", [{}])[0]
        first_name = (demographics.get("given") or [""])[0]
        last_name = demographics.get("family", "")

        dob_str = fhir_patient.get("birthDate")
        dob = datetime.strptime(dob_str, "%Y-%m-%d") if dob_str else None

        gender_map = {"male": "M", "female": "F"}
        sex = gender_map.get(fhir_patient.get("gender", ""), "OTHER")

        observations = await self.client.search_observations(patient_id)
        for obs in observations.entry[:20]:
            resource = obs.get("resource", {})
            if resource.get("status") == "final":
                code_codings = resource.get("code", {}).get("coding", [])
                loinc = next((c.get("code") for c in code_codings if c.get("system", "").startswith("http://loinc.org")), None)
                value = resource.get("valueQuantity", {})
                effective = resource.get("effectiveDateTime")

                if loinc and value:
                    vital_sign = VitalSign(
                        id=resource.get("id", ""),
                        patient_id=patient_id,
                        timestamp=datetime.fromisoformat(effective) if effective else datetime.utcnow(),
                    )
                    if loinc == "8867-4":
                        vital_sign.heart_rate = value.get("value")
                    elif loinc == "8480-6":
                        vital_sign.systolic_bp = value.get("value")
                    elif loinc == "8462-4":
                        vital_sign.diastolic_bp = value.get("value")
                    elif loinc == "8310-5":
                        vital_sign.temperature = value.get("value")
                    elif loinc == "9279-1":
                        vital_sign.respiratory_rate = value.get("value")
                    elif loinc == "2708-6":
                        vital_sign.oxygen_saturation = value.get("value")
                        vital_sign.spo2 = value.get("value")

                    db_session.add(vital_sign)

        medications = await self.client.search_medication_requests(patient_id)
        for med in medications.entry:
            resource = med.get("resource", {})
            medication = Medication(
                id=resource.get("id", ""),
                patient_id=patient_id,
                name=resource.get("medicationReference", {}).get("display", "Unknown"),
                dosage=resource.get("dosageInstruction", [{}])[0].get("text", ""),
                route=resource.get("dosageInstruction", [{}])[0].get("route", {}).get("text", ""),
                is_active=resource.get("status") == "active",
            )
            db_session.add(medication)

        allergies = await self.client.search_allergy_intolerances(patient_id)
        allergy_list = []
        for allergy in allergies.entry:
            resource = allergy.get("resource", {})
            allergy_list.append(resource.get("code", {}).get("text", "Unknown"))

        db_patient = Patient(
            id=patient_id,
            mrn=mrn,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=dob,
            sex=sex,
            allergies=allergy_list,
        )
        db_session.add(db_patient)
        await db_session.commit()

        logger.info("fhir_sync_complete", patient_id=patient_id)
        return {"status": "synced", "patient_id": patient_id}
