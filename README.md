# Code Blue AI

**When seconds matter, agents assemble instantly.**

A production-grade clinical decision support platform built for healthcare environments where early deterioration detection and rapid response can mean the difference between life and death. This project was built to demonstrate what modern agent orchestration looks like when applied to real clinical workflows.

---

## What This Is

Code Blue AI is a multi-agent system that monitors hospital patients and coordinates autonomous responses when clinical deterioration is detected. It connects five specialist agents through a shared message bus, each handling a distinct piece of the clinical decision chain.

The system monitors vital signs, generates differential diagnoses, retrieves evidence-based protocols, handles escalation workflows, and auto-generates documentation. Every recommendation is explainable with evidence traces back to source vitals and labs.

This was built as a proof-of-concept for healthcare hackathons and clinical innovation demonstrations. It's not FDA-cleared software and should not be used in actual patient care.

---

## The Agents

Each agent is a self-contained Python service with a defined responsibility:

**Monitor Agent** watches for deterioration patterns using NEWS2, SOFA, and qSOFA scoring systems. It flags sepsis, AKI, and stroke risk. When vitals cross configurable thresholds, it publishes alerts to the message bus.

**Diagnostic Agent** takes vitals, labs, medications, allergies, and comorbidities and produces a ranked differential diagnosis. It generates risk predictions for ICU admission, mortality, and 30-day readmission.

**Guideline Agent** retrieves appropriate clinical protocols when a diagnosis is suspected. Supported protocols include the 1-hour Sepsis Bundle, STEMI pathway, acute stroke pathway, ACLS algorithms, PE workup, and DKA management.

**Coordinator Agent** handles escalation. Based on risk level, it generates notifications (pages, alerts, broadcasts), creates task lists, and assigns actions to nursing, ICU, and physician teams.

**Documentation Agent** auto-generates SOAP notes with clinical rationale. It writes to FHIR Communication and DetectedIssue resources for the medical record.

---

## Architecture Overview

```
Patient Vitals → Monitor Agent → Alert
                          ↓
                    Diagnostic Agent → Differential Diagnosis
                          ↓
                    Guideline Agent → Protocol + Interventions
                          ↓
                    Coordinator Agent → Escalation + Tasks
                          ↓
                  Documentation Agent → SOAP Note + FHIR Updates
```

All agents communicate through an A2A (Agent-to-Agent) message bus. Messages follow defined contracts with JSON schemas, retry logic, and a dead-letter queue for failed deliveries. OpenTelemetry tracing links every message across the chain.

The MCP (Model Context Protocol) layer exposes tools for FHIR queries, clinical scoring, drug interaction checks, protocol retrieval, alert dispatch, and audit logging.

Frontend is a single HTML file with vanilla JavaScript. No React, Vue, Angular, or any JavaScript framework. WebSockets handle real-time updates to the clinical command center. Sessions persist across page refreshes via localStorage.

---

## What's Implemented

### Authentication and RBAC
JWT-based authentication with role-based access control. Six roles: Admin, Physician, Nurse, Resident, Pharmacist, Readonly. Each role has a defined permission set enforced at the endpoint level. Demo accounts are pre-seeded for testing.

### FHIR R4 Integration
A dedicated FHIR client connects to any HAPI FHIR R4-compatible server. Supports patient search, observation queries, medication requests, allergy lookups, condition records, and encounter data. Observation writes use LOINC codes. The sync service bridges FHIR resources into the local database.

### SMART-on-FHIR OAuth
A complete OAuth 2.0 authorization code flow with PKCE support. Handles launch URLs, state management, token exchange, and token introspection. Supports patient and provider launch contexts with scope management.

### Circuit Breakers
Per-service circuit breakers protect against cascading failures. Closed/open/half-open states with configurable thresholds. Health endpoint reports circuit breaker status for monitoring.

### OpenTelemetry Tracing
Every A2A message carries trace context. Agents create spans for each operation. Events are recorded on spans. Stats track total spans, error rates, average duration, and spans by agent.

### Session Persistence
Selected patient survives page refresh. Auth tokens persist in localStorage. Auto-login with cached credentials on page load. 8-hour session validity.

---

## Quick Start

```bash
git clone https://github.com/elonmasai7/CodeBlueAi.git
cd CodeBlueAi

cp .env.example .env
docker-compose up -d

pytest tests/ -v

python -m backend.db.init
```

Once running:
- Command center UI: `http://localhost:3000`
- API documentation: `http://localhost:8000/docs`
- Prometheus metrics: `http://localhost:9090`
- Grafana dashboards: `http://localhost:3001`

### Demo Credentials

| Username | Password | Role |
|----------|----------|------|
| admin | Admin123! | Admin |
| physician | Physician123! | Physician |
| nurse | Nurse123! | Nurse |

---

## Key Endpoints

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| POST | `/api/v1/auth/login` | No | Get JWT tokens |
| POST | `/api/v1/auth/refresh` | No | Refresh access token |
| GET | `/api/v1/auth/me` | Yes | Current user info |
| GET | `/api/v1/patients` | Yes | List patients |
| GET | `/api/v1/patients/{id}` | Yes | Full patient record |
| POST | `/api/v1/analyze/{id}` | Yes | Full multi-agent analysis |
| POST | `/api/v1/vitals` | Yes | Submit vital signs |
| POST | `/api/v1/demo/trigger` | Yes | Run septic shock demo |
| WS | `/ws/clinical` | Token | Real-time event stream |
| GET | `/smart/launch` | No | SMART launch URL |
| POST | `/smart/token` | No | SMART token exchange |
| GET | `/system/circuit-breakers` | Yes | Circuit breaker states |
| GET | `/system/tracing/stats` | Yes | OpenTelemetry stats |
| GET | `/system/audit-log` | Yes | Audit trail |

---

## The Demo Scenario

Click "DEMO SEPTIC SHOCK" in the UI to watch the full agent chain execute in sequence:

1. **Detection** — Vitals update (BP drops to 82, HR rises to 128, SpO2 falls to 87, lactate climbs to 4.8)
2. **Monitor** flags NEWS2 of 12, qSOFA of 3, and septic shock with 92% confidence
3. **Diagnostic** generates a ranked differential with sepsis as primary
4. **Guideline** retrieves the 1-hour Sepsis Bundle with antibiotics, fluids, and vasopressor threshold
5. **Coordinator** triggers a Rapid Response, pages ICU, and generates nursing tasks
6. **Documentation** writes a complete SOAP note with clinical rationale

The agent collaboration feed on the right side of the UI shows each agent's output in real time.

---

## Project Structure

```
code_blue_ai/
├── agents/
│   ├── monitor/           # Clinical scoring + vital monitoring
│   ├── diagnostic/        # Differential diagnosis engine
│   ├── guideline/         # Protocol retrieval
│   ├── coordinator/       # Escalation workflow
│   └── documentation/     # SOAP note generation
├── backend/
│   ├── api/               # FastAPI route handlers + auth, SMART, system
│   ├── db/                # SQLAlchemy session + seeding
│   ├── models/            # Database models
│   ├── services/          # Auth, security, circuit breakers, FHIR, SMART
│   └── main.py            # FastAPI application entry
├── mcp_server/           # MCP tool registry
├── a2a_bus/              # Agent message bus + OpenTelemetry tracing
├── fhir/                 # FHIR client + synthetic patient data generator
├── frontend/             # Clinical command center UI
├── tests/                # pytest unit tests
├── docker/               # Docker configs, nginx, prometheus
└── k8s/                  # Kubernetes manifests
```

---

## Technical Decisions

**No Node.js, no npm, no JavaScript frameworks.** Frontend is vanilla HTML, CSS, and JavaScript. WebSockets handle real-time updates. No SPA framework needed for this use case.

**Python 3.13+ with asyncio.** All database operations are async via SQLAlchemy 2.0 and asyncpg. The agent logic is synchronous by design for predictability in a clinical context.

**No LangGraph.** Agent orchestration uses a custom message bus with contracts and DLQ. Lighter and more explicit than a full orchestration framework.

**FHIR R4 via HAPI FHIR.** The FHIR client connects to any R4-compatible server. Synthetic data generator produces FHIR-compatible records for demos.

**Clinical protocols are hardcoded.** Protocols are embedded as Python dataclasses for self-contained, deterministic demos.

**OpenTelemetry for observability.** Traces flow through the A2A bus. No external Jaeger or collector required in dev mode—ConsoleSpanExporter is used by default.

---

## Running Without Docker

```bash
python3.13 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

export DATABASE_URL=postgresql+asyncpg://codeblue:codeblue_secret@localhost:5432/codeblue
export REDIS_URL=redis://localhost:6379
export JWT_SECRET=change_this_32chars_minimum

python -m backend.db.init
uvicorn backend.main:app --reload --port 8000
```

PostgreSQL 16+ and Redis 7 required separately.

---

## Tests

```bash
pytest tests/ -v
pytest tests/ --cov=agents --cov=mcp_server --cov=a2a_bus --cov=backend
```

Tests cover each agent independently. No integration tests requiring external services are included in the default test run.

---

## Deployment

Development uses `docker-compose up`. Production uses `docker-compose.prod.yml` with environment-specific settings, or the Kubernetes manifests in `/k8s/` for cluster deployment.

Required environment variables for production:
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `JWT_SECRET` — Secret for JWT token signing (minimum 32 characters)
- `FHIR_BASE_URL` — HAPI FHIR server URL

---

## Known Gaps

These were intentionally deferred rather than implemented poorly:

- Real HAPI FHIR server integration is wired but not end-to-end tested with a live server
- Audit log is written to the database but the frontend doesn't display it
- Drug interaction MCP tool returns empty results (requires a real drug database)
- Kubernetes manifests cover only the backend deployment, not the full stack
- No rate limiting on API endpoints

---

## Contributing

This was built for demonstration purposes. If you're adapting it for a project, fork the repository and replace the synthetic data layer with your actual FHIR integration, wire up the authentication, and add OpenTelemetry tracing.

---

## License

MIT
