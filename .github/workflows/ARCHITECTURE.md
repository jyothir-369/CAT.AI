# CAT AI — Architecture Overview

> **Start here.** This document is the onboarding entry point for engineers joining the project.

## Quick Links

| Resource | Location |
|---|---|
| Full blueprint (PDF) | `docs/CAT_AI_Architecture_Blueprint.pdf` |
| API docs (dev) | `http://localhost:8000/docs` |
| Env template | `apps/api/.env.example` |
| DB seed | `scripts/seed.py` |
| Migrations | `scripts/migrate.sh` |

## Stack at a glance

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind, shadcn/ui |
| Backend API | FastAPI, Python 3.12, Pydantic v2, SQLAlchemy 2.0 |
| Database | PostgreSQL 16 + pgvector |
| Cache / Queue | Redis 7 + Celery |
| Object Storage | AWS S3 |
| LLM Providers | OpenAI, Anthropic (+ Groq, Gemini in Phase 2) |
| Billing | Stripe |
| Deployment | Docker, ECS Fargate, GitHub Actions |

## Running locally in 60 seconds

```bash
# 1. Clone and install
git clone <repo> && cd cat-ai

# 2. Copy env template
cp apps/api/.env.example apps/api/.env
# Edit .env — at minimum set JWT_SECRET, SECRET_KEY, OPENAI_API_KEY

# 3. Start infrastructure
docker compose -f infra/docker/docker-compose.yml up -d postgres redis

# 4. Install Python deps
cd apps/api && pip install -r requirements.txt

# 5. Seed database
python ../../scripts/seed.py

# 6. Start the API
uvicorn main:app --reload --port 8000

# 7. Start the worker (separate terminal)
cd ../../apps/worker
celery -A celery_app worker --loglevel=info

# 8. Visit http://localhost:8000/docs
```

## Module map

```
apps/api/
├── main.py               ← FastAPI app factory, all routers mounted here
├── api/v1/               ← HTTP routes (thin — delegate to services)
│   ├── auth.py           POST /auth/register|login|refresh|me|logout
│   ├── chat.py           POST /chat/stream  (SSE)
│   ├── conversations.py  GET|POST|DELETE /conversations
│   ├── files.py          POST /files/upload, GET /files
│   ├── knowledge.py      CRUD /knowledge + /query
│   ├── workflows.py      CRUD /workflows + /run + /approve
│   ├── integrations.py   OAuth /integrations/connect|callback
│   ├── webhooks.py       POST /webhooks/{provider}
│   ├── usage.py          GET /usage/summary|models|daily
│   ├── billing.py        POST /billing/checkout|portal|webhook
│   └── admin.py          GET /admin/metrics|users|audit-logs
├── services/             ← Business logic (no HTTP concerns)
├── ai/                   ← LLM provider adapters + model router
├── db/models/            ← SQLAlchemy models (one file per domain)
├── db/repos/             ← Data access (ORM queries, no business logic)
├── db/migrations/        ← Alembic migrations
├── middleware/           ← CORS, logging, rate limiting
└── core/                 ← Config, security, deps, exceptions

apps/worker/
├── celery_app.py         ← Celery factory + beat schedule
├── tasks/                ← Async task handlers
├── parsers/              ← Document text extraction
└── chunkers/             ← Text chunking strategies
```

## Key architecture decisions

| Decision | Choice | Rationale |
|---|---|---|
| Architecture | Modular monolith | Ship fast, extract microservices at scale |
| Streaming | SSE via `StreamingResponse` | Simpler than WebSockets for one-directional AI output |
| Vector store | pgvector (MVP) → Qdrant (>500K chunks) | One DB to manage in dev |
| Auth | Custom JWT + refresh tokens | No vendor lock-in; Auth0 added for enterprise SSO |
| Workflow engine | Celery DAG runner | Battle-tested, easy local dev |
| Orchestration | Custom provider adapters | Avoids LangChain abstraction leaks |

## Development phases

| Phase | Weeks | Focus |
|---|---|---|
| 1 | 1–3 | Core chat + auth + SSE streaming |
| 2 | 4–5 | History + model routing + workspaces |
| 3 | 6–8 | File upload + RAG pipeline |
| 4 | 9–11 | Tool calling + integrations |
| 5 | 12–15 | Workflow automation engine |
| 6 | 16–18 | Billing + analytics + hardening |