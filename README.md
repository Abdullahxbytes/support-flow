# SupportFlow Backend

Autonomous, cloud-hybrid B2B customer support triage and helpdesk platform for SMEs.

## Architecture

SupportFlow uses a **Hybrid Autopilot** dual-execution pipeline:

- **Autopilot Track** — Fully autonomous ticket resolution via Groq LLM + Qdrant RAG with gatekeeping rules (vector similarity, sentiment, risk category).
- **Co-Pilot Track** — Human-in-the-loop escalation with pre-drafted AI response cards for single-click agent approval.

## Tech Stack

| Layer            | Technology                          |
|------------------|-------------------------------------|
| Backend API      | FastAPI (async/await)               |
| Database         | PostgreSQL 15                       |
| Async Queue      | Redis 7 + Celery                    |
| AI Inference     | Groq Cloud (`llama-3.1-8b-instant`) |
| Vector Database  | Qdrant Cloud                        |

## Quick Start

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Start infrastructure services
docker-compose up -d

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Run the development server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

## Project Structure

```
supportflow-backend/
├── src/
│   ├── main.py              # FastAPI application entry point
│   ├── api/v1/endpoints/    # Versioned API route handlers
│   ├── core/                # Config, database, and shared utilities
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic request/response schemas
│   ├── services/            # Business logic layer
│   └── tasks/               # Celery async task definitions
├── docker-compose.yml       # PostgreSQL + Redis containers
├── requirements.txt         # Python dependencies
└── .env.example             # Environment variable template
```
