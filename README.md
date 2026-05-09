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

All agents communicate through an A2A (Agent-to-Agent) message bus. Messages follow defined contracts with JSON schemas, retry logic, and a dead-letter queue for failed deliveries. Observability is built in.

The MCP (Model Context Protocol) layer exposes tools for FHIR queries, clinical scoring, drug interaction checks, protocol retrieval, alert dispatch, and audit logging.

Frontend is a single HTML file with vanilla JavaScript. No React, Vue, Angular, or any JavaScript framework. WebSocket connection handles real-time updates to the clinical command center.

---

## Quick Start

```bash
# Clone the repo
git clone https://github.com/elonmasai7/CodeBlueAi.git
cd CodeBlueAi

# Copy environment config
cp .env.example .env

# Start the full stack (PostgreSQL, Redis, Backend, Frontend, Nginx)
docker-compose up -d

# Run the unit tests
pytest tests/ -v

# Seed the database with 1000 synthetic patients
python -m backend.db.init
```

Once running:
- Command center UI: `http://localhost:3000`
- API documentation: `http://localhost:8000/docs`
- Prometheus metrics: `http://localhost:9090`
- Grafana dashboards: `http://localhost:3001`

---

## Key Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/patients` | List patients (filter by unit, risk level) |
| GET | `/api/v1/patients/{id}` | Full patient record with vitals, labs, meds |
| POST | `/api/v1/analyze/{id}` | Trigger full multi-agent analysis |
| POST | `/api/v1/vitals` | Submit new vital signs |
| POST | `/api/v1/demo/trigger` | Run the septic shock demo scenario |
| WS | `/ws/clinical` | Real-time event stream |

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
│   ├── diagnostic/      # Differential diagnosis engine
│   ├── guideline/        # Protocol retrieval
│   ├── coordinator/      # Escalation workflow
│   └── documentation/    # SOAP note generation
├── backend/
│   ├── api/             # FastAPI route handlers
│   ├── db/              # SQLAlchemy session + seeding
│   ├── models/          # Database models
│   └── services/        # Event bus
├── mcp_server/          # MCP tool registry
├── a2a_bus/            # Agent message bus
├── fhir/               # Synthetic patient data generator
├── frontend/            # Clinical command center UI
├── tests/              # pytest unit tests
├── docker/             # Docker configs
└── k8s/                # Kubernetes manifests
```

---

## Technical Decisions

**No Node.js, no npm, no JavaScript frameworks.** Frontend is vanilla HTML, CSS, and JavaScript. WebSockets handle real-time updates. HTMX could have been used for some interactions but wasn't needed.

**Python 3.13+ with asyncio.** All database operations are async via SQLAlchemy 2.0 and asyncpg. The agent logic is synchronous by design for predictability in a clinical context.

**No LangGraph.** The agent orchestration uses a simple message bus pattern. LangGraph is excellent but adds complexity and a JavaScript dependency. A custom bus with contracts and DLQ is lighter and more explicit.

**FHIR R4 via HAPI FHIR.** The project integrates with a HAPI FHIR server running in Docker. Synthetic patient data is generated in FHIR-compatible format.

**Clinical protocols are hardcoded.** Rather than fetching from external guideline APIs, protocols are embedded as Python dataclasses. This keeps the system self-contained and deterministic for demos.

---

## Running Without Docker

```bash
# Create virtual environment
python3.13 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Set environment variables
export DATABASE_URL=postgresql+asyncpg://codeblue:codeblue_secret@localhost:5432/codeblue
export REDIS_URL=redis://localhost:6379

# Initialize database
python -m backend.db.init

# Start backend
uvicorn backend.main:app --reload --port 8000
```

You'll need PostgreSQL 16+ and Redis 7 running separately.

---

## Tests

```bash
pytest tests/ -v
pytest tests/ --cov=agents --cov=mcp_server --cov=a2a_bus
```

Tests cover each agent independently. No integration tests requiring external services are included in the default test run.

---

## Deployment

Development uses `docker-compose up`. Production uses the `docker-compose.prod.yml` with environment-specific settings, or the Kubernetes manifests in `/k8s/` for cluster deployment.

Required environment variables for production:
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `JWT_SECRET` — Secret for JWT token signing
- `FHIR_BASE_URL` — HAPI FHIR server URL

---

## What's Working

- Patient roster with filtering and search
- Real-time vital sign display with waveform visualization
- All five agents executing the full analysis chain
- MCP tool execution via API
- WebSocket streaming to the UI
- Demo mode with the septic shock scenario
- SOAP note generation
- FHIR-compatible data models
- Docker-based deployment

## What's Missing

- Real FHIR server integration (currently uses synthetic data only)
- Authentication and RBAC (JWT scaffolding exists but isn't enforced)
- Persistence across page refreshes in the UI
- Production-grade error handling and circuit breakers
- Actual SMART-on-FHIR OAuth flow
- Full A2A bus observability with OpenTelemetry traces

These are gaps that would be filled in a production system.

---

## Contributing

This was built for demonstration purposes. If you're adapting it for a project, fork the repository and replace the synthetic data layer with your actual FHIR integration, wire up the authentication, and add OpenTelemetry tracing.

---

## License

MIT
