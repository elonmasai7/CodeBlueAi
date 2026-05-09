# Code Blue AI - README

**"When seconds matter, agents assemble instantly."**

Autonomous Clinical Emergency Agent Network - A healthcare hackathon-winning platform demonstrating interoperable healthcare agents collaborating in real-time.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Clinical Command Center                        │
│              (Vanilla JS + WebSockets + CSS)                     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ Monitor  │ │Diagnostc │ │Guideline │ │Coordintor│ │Document  │ │
│  │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ │
│       └────────────┴────────────┴────────────┴────────────┘       │
│                                │                                 │
│  ┌─────────────────────────────┴─────────────────────────────┐  │
│  │                    A2A Message Bus                           │  │
│  │              (Contracts, Retries, DLQ, Observability)         │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                │                                 │
│  ┌─────────────────┐  ┌───────────┐  ┌───────────────────────┐  │
│  │   MCP Server     │  │  Event    │  │     FHIR Client       │  │
│  │ (Tool Registry)  │  │   Bus     │  │ (HAPI FHIR R4)        │  │
│  └─────────────────┘  └───────────┘  └───────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                   Infrastructure Layer                           │
│   PostgreSQL │ Redis │ Celery │ Prometheus │ Grafana │ Nginx   │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Clone and start
git clone https://github.com/yourorg/code-blue-ai
cd code-blue-ai

# Copy environment
cp .env.example .env

# Start with Docker
docker-compose up -d

# Or for development
make dev

# Run tests
make test
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/patients` | List all patients |
| GET | `/api/v1/patients/{id}` | Get patient details |
| POST | `/api/v1/analyze/{id}` | Full multi-agent analysis |
| POST | `/api/v1/vitals` | Submit vital signs |
| POST | `/api/v1/demo/trigger` | Trigger demo scenario |
| WS | `/ws/clinical` | WebSocket for real-time updates |

## Agents

- **Monitor Agent**: Continuous vitals monitoring, NEWS2/SOFA/qSOFA scoring, sepsis detection
- **Diagnostic Agent**: Differential diagnosis with evidence, risk prediction
- **Guideline Agent**: Protocol retrieval (Sepsis, STEMI, Stroke, ACLS)
- **Coordinator Agent**: Escalation handling, task generation, notifications
- **Documentation Agent**: SOAP note generation, FHIR updates

## Tech Stack

- **Backend**: Python 3.13+, FastAPI, Pydantic, SQLAlchemy
- **Database**: PostgreSQL + Redis
- **Agents**: Custom orchestration (no LangGraph/npm)
- **Interop**: MCP, A2A, FHIR R4
- **Frontend**: Vanilla HTML5/CSS/JS, Web Components

## Demo Mode

Click "DEMO SEPTIC SHOCK" to see the full agent collaboration:

1. Patient deterioration detected
2. Agents analyze, diagnose, protocol
3. Escalation triggered
4. Documentation auto-generated
5. Full explainability shown

## License

MIT
