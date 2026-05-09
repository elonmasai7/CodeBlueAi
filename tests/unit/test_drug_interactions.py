import pytest
from mcp_server.drug_db import DrugInteractionService, DRUG_DB


@pytest.fixture
def service():
    return DrugInteractionService()


class TestDrugInteractionService:
    def test_vancomycin_norepinephrine_no_interaction(self, service):
        result = service.check_interaction("vancomycin", "norepinephrine")
        assert result.severity == "NONE"

    def test_vancomycin_aminoglycoside_interaction(self, service):
        result = service.check_interaction("vancomycin", "aminoglycosides")
        assert result.severity == "HIGH"
        assert "nephrotoxicity" in result.description.lower()

    def test_heparin_nsaids_interaction(self, service):
        result = service.check_interaction("heparin", "nsaids")
        assert result.severity == "HIGH"
        assert "bleeding" in result.description.lower()

    def test_metronidazole_alcohol_contraindicated(self, service):
        result = service.check_interaction("metronidazole", "alcohol")
        assert result.severity == "CONTRAINDICATED"
        assert "disulfiram" in result.description.lower()

    def test_metoprolol_verapamil_contraindicated(self, service):
        result = service.check_interaction("metoprolol", "verapamil")
        assert result.severity == "CONTRAINDICATED"
        assert "asystole" in result.description.lower() or "collapse" in result.description.lower()

    def test_furosemide_aminoglycosides_interaction(self, service):
        result = service.check_interaction("furosemide", "aminoglycosides")
        assert result.severity == "HIGH"
        assert "ototoxicity" in result.description.lower()

    def test_lisinopril_spironolactone_hyperkalemia(self, service):
        result = service.check_interaction("lisinopril", "spironolactone")
        assert result.severity == "HIGH"
        assert "hyperkalemia" in result.description.lower()

    def test_unknown_drug_pair(self, service):
        result = service.check_interaction("aspirin", "metformin")
        assert result.severity == "NONE"

    def test_case_insensitive(self, service):
        result = service.check_interaction("VANCOMYCIN", "AMINOGLYCOSIDES")
        assert result.severity == "HIGH"

    def test_multi_drug_interactions(self, service):
        drugs = ["vancomycin", "heparin", "furosemide", "metronidazole"]
        interactions = service.check_multi_interactions(drugs)
        assert len(interactions) >= 4
        severities = [i.severity for i in interactions]
        assert "HIGH" in severities
        assert "CONTRAINDICATED" in severities

    def test_renal_dosing_vancomycin_normal(self, service):
        result = service.get_renal_dosing("vancomycin", 90)
        assert result.drug == "vancomycin"
        assert "CrCl >= 50" in result.indication
        assert len(result.monitoring) > 0

    def test_renal_dosing_vancomycin_severe(self, service):
        result = service.get_renal_dosing("vancomycin", 8)
        assert result.crcl_threshold == 8
        assert "Severe" in result.indication
        assert "adjust" in result.recommendation.lower()

    def test_renal_dosing_unknown_drug(self, service):
        result = service.get_renal_dosing("random_drug", 30)
        assert "Unknown" in result.indication or result.recommendation == "No data available."

    def test_interaction_graph(self, service):
        drugs = ["vancomycin", "heparin", "norepinephrine", "insulin"]
        graph = service.get_interaction_graph(drugs)
        assert "nodes" in graph
        assert "edges" in graph
        assert len(graph["nodes"]) == 4
        assert "max_severity" in graph
        assert graph["max_severity"] == "HIGH"

    def test_interaction_graph_contraindication(self, service):
        drugs = ["metoprolol", "verapamil"]
        graph = service.get_interaction_graph(drugs)
        assert graph["max_severity"] == "CONTRAINDICATED"
        assert len(graph["edges"]) == 1
        assert graph["edges"][0]["severity"] == "CONTRAINDICATED"

    def test_drug_db_completeness(self):
        for drug_name, data in DRUG_DB.items():
            assert "class" in data
            assert "doses" in data
            assert "interactions" in data
            assert "monitoring" in data


class TestMEWSCalculation:
    def test_mews_low_risk(self):
        from agents.monitor.clinical_scoring import ClinicalScoringService, VitalReading

        service = ClinicalScoringService()
        reading = VitalReading(
            heart_rate=70,
            systolic_bp=120,
            diastolic_bp=80,
            respiratory_rate=16,
            temperature=37.0,
            spo2=98,
            map=90,
            lactate=1.0,
        )
        score = service.calculate_news2(reading)
        assert score.value <= 2

    def test_mews_high_risk(self):
        from agents.monitor.clinical_scoring import ClinicalScoringService, VitalReading

        service = ClinicalScoringService()
        reading = VitalReading(
            heart_rate=140,
            systolic_bp=85,
            diastolic_bp=50,
            respiratory_rate=30,
            temperature=39.5,
            spo2=84,
            map=62,
            lactate=5.0,
        )
        score = service.calculate_news2(reading)
        assert score.value >= 12
        assert score.risk_level == "CRITICAL"
