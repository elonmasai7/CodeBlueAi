from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

DRUG_DB: Dict[str, Dict[str, Any]] = {
    "vancomycin": {
        "class": "Glycopeptide Antibiotic",
        "doses": {"normal": "1g IV q12h", "high": "1.5g IV q12h"},
        "renal_adjustment": "Adjust for CrCl < 50: extend interval to q24h or q48h. Avoid if CrCl < 10.",
        "interactions": {
            "aminoglycosides": {"severity": "HIGH", "description": "Synergistic nephrotoxicity risk"},
            "loop_diuretics": {"severity": "MODERATE", "description": "Increased ototoxicity risk"},
            "cisplatin": {"severity": "HIGH", "description": "Additive nephrotoxicity"},
        },
        "contraindications": ["Known vancomycin hypersensitivity"],
        "monitoring": ["Serum trough level (goal 10-20 mcg/mL)", "SCr q2-3d", "AUC/MIC if obese"],
    },
    "piperacillin-tazobactam": {
        "class": "Beta-lactam/Penicillinase Inhibitor",
        "doses": {"normal": "4.5g IV q6h", "extended": "3.375g IV q8h ( Extended infusion 4h )"},
        "renal_adjustment": "CrCl < 40: reduce to q8h or q12h. CrCl < 20: q12h or q24h.",
        "interactions": {
            "warfarin": {"severity": "MODERATE", "description": "Increased bleeding risk via vitamin K interference"},
            "methotrexate": {"severity": "HIGH", "description": "Decreased MTX clearance, increase toxicity"},
            "heparin": {"severity": "MODERATE", "description": "Increased bleeding risk"},
        },
        "contraindications": ["Penicillin allergy"],
        "monitoring": ["SCr", "WBC with differential", "Procalcitonin"],
    },
    "ceftriaxone": {
        "class": "3rd Generation Cephalosporin",
        "doses": {"normal": "1g IV q24h", "meningitis": "2g IV q12h"},
        "renal_adjustment": "No adjustment needed for renal impairment. Monitor if on dialysis.",
        "interactions": {
            "warfarin": {"severity": "HIGH", "description": "Increased bleeding risk"},
            "calcium-containing solutions": {"severity": "CONTRAINDICATED", "description": "Precipitation in lungs/kidneys - NEVER co-administer in neonates"},
            "probenecid": {"severity": "LOW", "description": "Increased ceftriaxone levels"},
        },
        "contraindications": ["Cephalosporin allergy", "Neonates with calcium-containing products"],
        "monitoring": ["LFTs", "PT/INR if on anticoagulation"],
    },
    "metronidazole": {
        "class": "Nitroimidazole Antibiotic",
        "doses": {"normal": "500mg IV q8h", "c-diff": "500mg PO q8h"},
        "renal_adjustment": "Severe renal impairment (CrCl < 10): reduce dose by 50%.",
        "interactions": {
            "warfarin": {"severity": "HIGH", "description": "SIGNIFICANT INR elevation - check INR frequently"},
            "lithium": {"severity": "HIGH", "description": "Increased lithium levels, toxicity risk"},
            "alcohol": {"severity": "CONTRAINDICATED", "description": "Disulfiram-like reaction"},
            "phenytoin": {"severity": "MODERATE", "description": "Decreased phenytoin efficacy"},
        },
        "contraindications": ["Metronidazole hypersensitivity", "First trimester pregnancy"],
        "monitoring": ["INR if on warfarin", "Lithium levels if on lithium", "Neuro exam for peripheral neuropathy"],
    },
    "norepinephrine": {
        "class": "Vasopressor",
        "doses": {"initial": "0.05-0.1 mcg/kg/min", "typical_range": "0.05-0.5 mcg/kg/min", "max": "3 mcg/kg/min"},
        "renal_adjustment": "No adjustment. Titrate to MAP > 65 mmHg.",
        "interactions": {
            "beta_blockers": {"severity": "HIGH", "description": "Blunted vasopressor response"},
            "maoi": {"severity": "CONTRAINDICATED", "description": "Severe hypertensive crisis"},
            "linezolid": {"severity": "MODERATE", "description": "Increased serotonergic effects if on serotonergics"},
            "tramadol": {"severity": "MODERATE", "description": "Serotonin syndrome risk"},
        },
        "contraindications": ["Mesenteric/peripheral vascular thrombosis (relative)"],
        "monitoring": ["MAP q5-15min until stable", "Urine output", "Peripheral perfusion", "ECG"],
    },
    "insulin": {
        "class": "Hormone",
        "doses": {"sliding_scale": "SSRI q4-6h", "glargine": "10-30 units SC q24h"},
        "renal_adjustment": "Reduce by 25% if CrCl < 50, 50% if CrCl < 30. Monitor q1-2h during insulin drip.",
        "interactions": {
            "corticosteroids": {"severity": "HIGH", "description": "Steroid-induced hyperglycemia - may need higher insulin doses"},
            "thiazolidinediones": {"severity": "HIGH", "description": "Fluid retention, worsen heart failure"},
            "beta_blockers": {"severity": "MODERATE", "description": "Blunts hypoglycemia symptoms (tachycardia masked)"},
        },
        "contraindications": ["Hypoglycemia without IV glucose available"],
        "monitoring": ["FSBG q1-4h", "Potassium", "Injection site"],
    },
    "lisinopril": {
        "class": "ACE Inhibitor",
        "doses": {"normal": "10mg PO q24h", "max": "40mg q24h"},
        "renal_adjustment": "Start 2.5-5mg if CrCl < 30. Avoid if CrCl < 10 or bilateral RAS.",
        "interactions": {
            "spironolactone": {"severity": "HIGH", "description": "Hyperkalemia risk - monitor K+ closely"},
            "nsaids": {"severity": "HIGH", "description": "Reduced antihypertensive effect, AKI risk"},
            "lithium": {"severity": "HIGH", "description": "Increased lithium levels"},
            "potassium": {"severity": "HIGH", "description": "Severe hyperkalemia risk"},
        },
        "contraindications": ["Pregnancy", "Bilateral renal artery stenosis", "ACE inhibitor angioedema history"],
        "monitoring": ["SCr within 1 week", "K+ within 1 week", "BP"],
    },
    "metoprolol": {
        "class": "Beta Blocker",
        "doses": {"normal": "25-50mg PO q12h", "IV": "2.5-5mg q5min x3"},
        "renal_adjustment": "No dose adjustment needed. Use IV cautiously in renal impairment.",
        "interactions": {
            "verapamil": {"severity": "CONTRAINDICATED", "description": "Cardiovascular collapse, asystole risk"},
            "diltiazem": {"severity": "CONTRAINDICATED", "description": "Severe bradycardia and AV block risk"},
            "clonidine": {"severity": "MODERATE", "description": "Rebound hypertension if clonidine stopped suddenly"},
            "amiodarone": {"severity": "HIGH", "description": "Severe bradycardia, AV block"},
        },
        "contraindications": ["Cardiogenic shock", "Decompensated HF", "2nd/3rd degree AV block", "Sick sinus syndrome"],
        "monitoring": ["HR (hold if < 60)", "BP (hold if SBP < 100)", "Signs of HF exacerbation"],
    },
    "furosemide": {
        "class": "Loop Diuretic",
        "doses": {"normal": "40mg IV/PO q12h", "high": "80-100mg IV q12h or continuous infusion"},
        "renal_adjustment": "CrCl < 30: double dose. CrCl < 10: may need 200mg+. Use IV for faster effect.",
        "interactions": {
            "aminoglycosides": {"severity": "HIGH", "description": "Synergistic ototoxicity and nephrotoxicity"},
            "cisplatin": {"severity": "HIGH", "description": "Synergistic ototoxicity"},
            "nsaids": {"severity": "HIGH", "description": "Reduced diuretic effect, AKI risk"},
            "digoxin": {"severity": "HIGH", "description": "Hypokalemia-induced digoxin toxicity"},
        },
        "contraindications": ["Anuria", "Hepatic coma", "Severe electrolyte depletion"],
        "monitoring": ["Urine output", "SCr q1-2d", "Na/K/Mg", "BP"],
    },
    "heparin": {
        "class": "Anticoagulant",
        "doses": {"prophylaxis": "5000 units SC q8-12h", "treatment": "80 units/kg bolus then 18 units/kg/h"},
        "renal_adjustment": "No adjustment (not renally cleared). Use with caution in renal impairment.",
        "interactions": {
            "nsaids": {"severity": "HIGH", "description": "Increased bleeding risk"},
            "aspirin": {"severity": "HIGH", "description": "Double antiplatelet effect - monitor closely"},
            "direct_oral_anticoagulants": {"severity": "CONTRAINDICATED", "description": "Switch protocols, do not overlap"},
        },
        "contraindications": ["Active bleeding", "HIT (use argatroban instead)", "Spinal/epidural puncture within 12h"],
        "monitoring": ["aPTT q6h until stable (goal 1.5-2.5x control)", "PLT for HIT", "Hgb/Hct"],
    },
}


class SeverityLevel(str, Enum):
    CONTRAINDICATED = "CONTRAINDICATED"
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    NONE = "NONE"


@dataclass
class DrugInteraction:
    drug1: str
    drug2: str
    severity: str
    description: str
    recommendation: str
    evidence_level: str = "B"


@dataclass
class RenalDosingRecommendation:
    drug: str
    indication: str
    crcl_threshold: float
    recommendation: str
    monitoring: List[str]


class DrugInteractionService:
    def __init__(self):
        self.db = DRUG_DB

    def check_interaction(self, drug1: str, drug2: str) -> DrugInteraction:
        d1_lower = drug1.lower()
        d2_lower = drug2.lower()

        for name, data in self.db.items():
            interactions = data.get("interactions", {})
            if name == d1_lower and d2_lower in interactions:
                return DrugInteraction(
                    drug1=name,
                    drug2=d2_lower,
                    severity=interactions[d2_lower]["severity"],
                    description=interactions[d2_lower]["description"],
                    recommendation=self._get_recommendation(name, d2_lower, interactions[d2_lower]["severity"]),
                )
            if name == d2_lower and d1_lower in interactions:
                return DrugInteraction(
                    drug1=d2_lower,
                    drug2=name,
                    severity=interactions[d1_lower]["severity"],
                    description=interactions[d1_lower]["description"],
                    recommendation=self._get_recommendation(d2_lower, name, interactions[d1_lower]["severity"]),
                )

        return DrugInteraction(
            drug1=d1_lower,
            drug2=d2_lower,
            severity="NONE",
            description="No known interaction",
            recommendation="No specific action required",
        )

    def check_multi_interactions(self, drugs: List[str]) -> List[DrugInteraction]:
        interactions = []
        checked = set()

        for i, drug_a in enumerate(drugs):
            for drug_b in drugs[i + 1:]:
                pair = tuple(sorted([drug_a.lower(), drug_b.lower()]))
                if pair in checked:
                    continue
                checked.add(pair)
                result = self.check_interaction(drug_a, drug_b)
                if result.severity != "NONE":
                    interactions.append(result)

        return interactions

    def get_renal_dosing(self, drug: str, crcl: float) -> RenalDosingRecommendation:
        drug_lower = drug.lower()

        for name, data in self.db.items():
            if name == drug_lower:
                adjustment = data.get("renal_adjustment", "No adjustment needed")
                monitoring = data.get("monitoring", ["Standard monitoring"])

                if crcl < 10:
                    level = "Severe impairment (CrCl < 10)"
                elif crcl < 30:
                    level = "Severe impairment (CrCl 10-29)"
                elif crcl < 50:
                    level = "Moderate impairment (CrCl 30-49)"
                else:
                    level = "Normal function (CrCl >= 50)"

                return RenalDosingRecommendation(
                    drug=name,
                    indication=level,
                    crcl_threshold=crcl,
                    recommendation=adjustment,
                    monitoring=monitoring,
                )

        return RenalDosingRecommendation(
            drug=drug_lower,
            indication="Unknown - consult pharmacist",
            crcl_threshold=crcl,
            recommendation="No data available. Consult clinical pharmacist.",
            monitoring=[],
        )

    def get_interaction_graph(self, drugs: List[str]) -> Dict[str, Any]:
        nodes = []
        edges = []
        interaction_map = {}

        for drug in drugs:
            drug_lower = drug.lower()
            if drug_lower in self.db:
                nodes.append({"id": drug_lower, "label": drug_lower, "group": "drug"})
            else:
                nodes.append({"id": drug_lower, "label": drug_lower, "group": "unknown"})

        interactions = self.check_multi_interactions(drugs)
        for interaction in interactions:
            severity_colors = {
                "CONTRAINDICATED": "#ff0000",
                "HIGH": "#ff6b35",
                "MODERATE": "#ffd93d",
                "LOW": "#6bff6b",
            }
            edges.append({
                "from": interaction.drug1,
                "to": interaction.drug2,
                "severity": interaction.severity,
                "color": severity_colors.get(interaction.severity, "#888"),
                "label": f"{interaction.severity}: {interaction.description[:50]}",
            })
            interaction_map[f"{interaction.drug1}-{interaction.drug2}"] = {
                "severity": interaction.severity,
                "description": interaction.description,
            }

        return {
            "nodes": nodes,
            "edges": edges,
            "interactions": interaction_map,
            "max_severity": self._get_max_severity(interactions),
        }

    def _get_recommendation(self, drug: str, interacting: str, severity: str) -> str:
        if severity == "CONTRAINDICATED":
            return f"AVOID combination of {drug} and {interacting}. Use alternative therapy."
        if severity == "HIGH":
            return f"Use with caution. Consider alternative or reduce {interacting}. Monitor closely."
        if severity == "MODERATE":
            return f"Monitor for adverse effects. May need dose adjustment of {interacting}."
        return f"No significant action required. Standard monitoring."

    def _get_max_severity(self, interactions: List[DrugInteraction]) -> str:
        severity_order = ["NONE", "LOW", "MODERATE", "HIGH", "CONTRAINDICATED"]
        max_sev = "NONE"
        for interaction in interactions:
            if severity_order.index(interaction.severity) > severity_order.index(max_sev):
                max_sev = interaction.severity
        return max_sev


drug_interaction_service = DrugInteractionService()
