# Code Blue AI — Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CLINICAL COMMAND CENTER                              │
│                    Vanilla HTML/CSS/JS + WebSockets                        │
│         Patient Roster │ ICU Monitor │ Agent Feed │ Event Timeline           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ▲
                                      │ WebSocket / HTTP
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            FASTAPI BACKEND (Port 8000)                       │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌────────────────────┐  │
│  │ Auth API    │  │ Patient API  │  │ Analyze API │  │ System API        │  │
│  │ JWT/RBAC   │  │ CRUD/Roster  │  │ Multi-Agent  │  │ Health/CBs/Trace  │  │
│  │ SMART OAuth│  │ FHIR Proxy   │  │ Analysis    │  │ Audit Logs        │  │
│  └─────────────┘  └──────────────┘  └─────────────┘  └────────────────────┘  │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌────────────────────┐  │
│  │ Vitals API  │  │ MCP API      │  │ A2A API     │  │ Demo API          │  │
│  │ Ingest/Alert│  │ Tool Execute │  │ Status/DLQ  │  │ Scenario Runner   │  │
│  └─────────────┘  └──────────────┘  └─────────────┘  └────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
          ┌─────────────────┐ ┌───────────┐ ┌─────────────────────┐
          │  MONITOR AGENT  │ │ DIAGNOSTIC│ │    OTHER AGENTS     │
          │  NEWS2/SOFA/    │ │  AGENT    │ │ Guideline/Coord/    │
          │  qSOFA/Sepsis   │ │ Ddx/Risk  │ │ Documentation      │
          └────────┬────────┘ └─────┬─────┘ └──────────┬──────────┘
                   └───────────────┴──────────────────┘
                               │
                               ▼
          ┌─────────────────────────────────────────┐
          │            A2A MESSAGE BUS               │
          │  Contracts │ Retries │ DLQ │ Observability │
          │  OpenTelemetry Tracing                   │
          └─────────────────────────────────────────┘
                               │
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  MCP SERVER     │  │  EVENT BUS      │  │  FHIR CLIENT    │
│  Tool Registry  │  │  Redis PubSub   │  │  HAPI FHIR R4   │
│  6 Tool Servers │  │  Real-time      │  │  Full R4 API    │
│  FHIR/Scoring/  │  │  Streaming      │  │  LOINC codes    │
│  Drug/Protocol/ │  │                 │  │  Bulk export    │
│  Alert/Audit    │  │                 │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
                               │
                               ▼
          ┌─────────────────────────────────────────┐
          │        INFRASTRUCTURE (Docker Compose)     │
          │  PostgreSQL 16  │  Redis 7  │  HAPI FHIR    │
          │  Prometheus    │  Grafana  │  Nginx         │
          └─────────────────────────────────────────┘
```

## A2A Message Flow

```
[Patient Vitals] ──► [Monitor Agent]
                           │
                           ▼
                    [VITAL_ALERT]
                           │
                     ┌──────┴──────┐
                     ▼             ▼
              [Diagnostic]    [Coordinator]
                     │
                     ▼
             [DIAGNOSTIC_RESULT]
                     │
                     ▼
              [Guideline Agent]
                     │
                     ▼
             [GUIDELINE_RESPONSE]
                     │
                     ▼
              [Coordinator Agent]
                     │
                     ▼
             [ESCALATION + TASKS]
                     │
                     ▼
              [Documentation Agent]
                     │
                     ▼
             [SOAP NOTE + FHIR UPDATES]
```

## FHIR Resource Mapping

| FHIR Resource | Purpose | LOINC |
|---------------|---------|-------|
| Patient | Demographics, identifiers | — |
| Observation | Vitals (HR, BP, SpO2, RR, Temp, Lactate) | 8867-4, 8480-6, 2708-6, 9279-1, 8310-5, 2519-8 |
| Observation | Laboratory results | Variable |
| Condition | Active diagnoses | — |
| MedicationRequest | Active medications | — |
| AllergyIntolerance | Allergy records | — |
| Encounter | Admission/visit records | — |
| CarePlan | Treatment plans | — |
| Communication | Clinical notes | — |
| DetectedIssue | Clinical alerts | — |
| Task | Clinical tasks/orders | — |

## Clinical Scoring Systems

| Score | Range | High Risk Threshold | Purpose |
|-------|-------|---------------------|---------|
| NEWS2 | 0–20 | ≥7 | Early warning, acute deterioration |
| SOFA | 0–24 | ≥6 | Organ dysfunction, sepsis severity |
| qSOFA | 0–3 | ≥2 | Sepsis mortality screening |

## RBAC Permission Matrix

| Permission | Admin | Physician | Nurse | Resident | Pharmacist | Readonly |
|-----------|-------|-----------|-------|----------|------------|----------|
| read:patient | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| write:patient | ✓ | ✓ | ✓ | — | — | — |
| read:vitals | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| write:vitals | ✓ | ✓ | ✓ | ✓ | — | — |
| run:analysis | ✓ | ✓ | — | ✓ | — | — |
| dispatch:alert | ✓ | ✓ | ✓ | — | — | — |
| view:audit | ✓ | — | — | — | — | ✓ |
| fhir:read | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| fhir:write | ✓ | ✓ | — | — | — | — |

## Clinical Protocol Library

| Protocol | Code | Trigger | Timeframe | Key Interventions |
|----------|------|---------|-----------|-------------------|
| 1-Hour Sepsis Bundle | SEP-1HR | Septic shock | 60 min | Lactate, cultures, antibiotics, 30mL/kg fluids, vasopressors |
| Severe Sepsis Bundle | SEP-SEVERE | Severe sepsis | 3–6 hours | Lactate, cultures, antibiotics, fluids |
| STEMI Reperfusion | STEMI-PCI | STEMI | 90 min to PCI | Aspirin, P2Y12, heparin, cath lab |
| Acute Stroke | STROKE-ACUTE | Acute stroke | 25 min to CT | Stroke team, CT, tPA if eligible |
| ACLS | ACLS | Cardiac arrest | Immediate | CPR, epi, defibrillation |
| PE Workup | PE-WORKUP | PE suspected | 24 hours | Wells score, D-dimer, CTA, anticoagulation |
| DKA Protocol | DKA-MGMT | DKA | 12–24 hours | Fluids, insulin, potassium, transition to SC |

## Technology Stack

| Layer | Technology | Version |
|------|-----------|---------|
| Backend | Python | 3.13+ |
| Framework | FastAPI | 0.115 |
| ORM | SQLAlchemy | 2.0+ async |
| Database | PostgreSQL | 16+ |
| Cache/PubSub | Redis | 7+ |
| FHIR Server | HAPI FHIR | 7.4 |
| AI/Agents | Custom Python | — |
| Tracing | OpenTelemetry | 1.27 |
| Frontend | Vanilla JS | ES2022 |
| Container | Docker | Compose |
| Monitoring | Prometheus + Grafana | Latest |
