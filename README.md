# SupportFlow

An autonomous, cloud hybrid customer support triage engine built for small to medium enterprises (SMEs).

## Overview

Customer support teams at growing businesses face a common bottleneck: every incoming ticket, regardless of complexity, lands in the same queue and demands the same manual attention. Simple questions about business hours or password resets compete for agent time alongside sensitive refund disputes and escalation requests. The result is slower response times, inconsistent quality, and burned out support staff.

SupportFlow eliminates this inefficiency by introducing a Hybrid Autopilot pipeline that classifies, routes, and resolves tickets through two distinct execution tracks.

### Autopilot Mode (Fully Autonomous)

When an incoming ticket meets all three gatekeeping conditions, SupportFlow handles it end to end without human involvement:

1. **Vector Similarity Check** queries the company FAQ knowledge base stored in Qdrant Cloud. If the ticket content scores above the confidence threshold against existing documentation, the system considers it a known question.
2. **Sentiment Analysis** evaluates the tone of the message. Only tickets with positive or neutral sentiment proceed through the autonomous track.
3. **Category Risk Filter** screens for high risk categories such as refund requests, legal inquiries, or account security issues. These are never auto resolved.

If all three gates pass, the Groq Cloud API generates a contextual response using the `llama-3.1-8b-instant` model, and the ticket is resolved in sub second time with no agent involvement.

### Co Pilot Mode (Human in the Loop)

When any gatekeeping condition fails, the ticket is routed to the agent dashboard along with a pre drafted AI response card. The agent reviews the suggestion, edits it if necessary, and approves it with a single click. This preserves human judgment for sensitive cases while still reducing the cognitive load of composing responses from scratch.

## Architecture and Tech Stack

| Layer              | Technology                                         |
|--------------------|----------------------------------------------------|
| Backend API        | FastAPI with async/await architecture               |
| ORM and Database   | Async SQLAlchemy with PostgreSQL                    |
| Validation         | Pydantic v2 with pydantic settings                  |
| AI Inference       | Groq Cloud API (`llama-3.1-8b-instant`)             |
| Vector Database    | Qdrant Cloud (managed vector search)                |
| Task Queue         | Redis 7 with Celery (background processing)         |
| Containerization   | Docker Compose (PostgreSQL 15, Redis 7)             |

## Directory Structure

```
supportflow-backend/
    .env.example
    .gitignore
    docker-compose.yml
    requirements.txt
    README.md
    src/
        __init__.py
        main.py
        api/
            __init__.py
            v1/
                __init__.py
                endpoints/
                    __init__.py
        core/
            __init__.py
            config.py
            database.py
        models/
            __init__.py
        schemas/
            __init__.py
        services/
            __init__.py
        tasks/
            __init__.py
```

