<div align="center">
  <div style="display: flex; align-items: center; justify-content: center; gap: 20px;">
    <img src="https://github.com/jyothir-369/CAT.AI/blob/main/cat%20ai.jpeg" alt="CAT AI Logo" width="130" />
    <h1 style="margin: 0; padding: 0; font-size: 3.2em;">CAT AI</h1>
  </div>
</div>

**Complete Production-Grade AI Platform**  
*Conversational AI • Workflow Automation • RAG Knowledge Base • Multi-Tenant SaaS*

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![Next.js](https://img.shields.io/badge/Next.js-14-black)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
---

### ✨ What is CAT AI?

CAT AI is a **fully open-source, production-ready AI assistant and automation platform** that brings together:

- **Streaming conversational AI** with multi-model routing (OpenAI, Anthropic, Groq, Gemini, vLLM)
- **Durable workflow automation engine** (inspired by Zapier + LangGraph)
- **Enterprise RAG knowledge base** with hybrid retrieval + citations
- **Long-term memory** (semantic + session)
- **Multi-tenant SaaS architecture** with RBAC, billing, audit logs, and workspace isolation

Built from scratch as a **modular monolith** that can scale to microservices.

**Live Demo** • [Architecture Blueprint (PDF)](https://github.com/jyothir-369/CAT.AI/blob/main/CAT_AI_Architecture_Blueprint.pdf) • [API Docs (soon)](https://github.com/jyothir-369/CAT.AI/tree/main/docs/api)

---

### 🚀 Core Features

| Feature                  | Description |
|--------------------------|-------------|
| **Unified AI Workspace** | Chat + Workflows + Knowledge Base in one place |
| **Multi-Model Routing**  | Smart routing based on cost, speed, context, tool support |
| **Workflow Engine**      | JSON/YAML DAGs, triggers (webhook/cron/manual), human-in-the-loop approvals |
| **RAG Knowledge Base**   | File upload → hybrid (vector + BM25) retrieval → citations |
| **Memory System**        | Short-term, session summary, long-term semantic memory |
| **Tool Calling**         | Built-in tools + sandboxed code execution |
| **Enterprise Ready**     | RBAC, SSO path, Stripe billing, audit logs, GDPR deletion |
| **Streaming UX**         | Token-by-token SSE responses |

---

### 🛠️ Tech Stack

**Frontend**  
- Next.js 14 (App Router) + TypeScript  
- Tailwind + shadcn/ui + React Flow  
- Zustand + TanStack Query + SSE streaming  

**Backend**  
- FastAPI (Python 3.12) + Pydantic v2 + SQLAlchemy 2.0  
- Modular monolith with clean service boundaries  

**AI Layer**  
- Provider abstraction (OpenAI, Anthropic, Groq, Gemini, vLLM)  
- Prompt assembly pipeline, circuit breaker, token budgeting  

**Data & Storage**  
- PostgreSQL 16 + pgvector (MVP) → Qdrant (scale)  
- Redis (cache, rate limiting, Celery queue)  
- AWS S3 (files)  

**Async & Workers**  
- Celery + Redis broker  

**Infra**  
- Docker + docker-compose (local)  
- AWS ECS Fargate + RDS + ElastiCache + Terraform (prod)

---

### 🛠️ Tech Stack

**Frontend**
- Next.js 14 (App Router) + TypeScript
- Tailwind + shadcn/ui + React Flow
- Zustand + TanStack Query + SSE streaming

**Backend**
- FastAPI (Python 3.12) + Pydantic v2 + SQLAlchemy 2.0
- Modular monolith with clean service boundaries

**AI Layer**
- Provider abstraction (OpenAI, Anthropic, Groq, Gemini, vLLM)
- Prompt assembly pipeline, circuit breaker, token budgeting

**Data & Storage**
- PostgreSQL 16 + pgvector (MVP) → Qdrant (scale)
- Redis (cache, rate limiting, Celery queue)
- AWS S3 (files)

**Async & Workers**
- Celery + Redis broker

**Infra**
- Docker + docker-compose (local)
- AWS ECS Fargate + RDS + ElastiCache + Terraform (prod)

---

📁 Monorepo Structure
```
cat-ai/
├── apps/
│   ├── web/                          # Next.js 14 App Router — main customer-facing UI
│   │   ├── app/
│   │   │   ├── (auth)/               # login · register · forgot-password · verify-email
│   │   │   ├── (dashboard)/          # All authenticated routes (layout.tsx wraps with auth guard)
│   │   │   │   ├── chat/[conversationId]/   # Main SSE chat interface
│   │   │   │   ├── knowledge/        # KB list · file uploader · source citations
│   │   │   │   ├── workflows/        # React Flow DAG builder + run history
│   │   │   │   ├── integrations/     # OAuth connector cards (Slack, Gmail, Notion…)
│   │   │   │   ├── settings/         # Workspace · API keys · memory · billing portal
│   │   │   │   └── admin/            # Role-gated: users · cost dashboard · audit logs
│   │   │   └── api/                  # Next.js route handlers — thin proxy layer only
│   │   ├── components/
│   │   │   ├── chat/                 # MessageList · ChatInput · StreamingMessage · ToolCallBubble
│   │   │   ├── workflow/             # WorkflowCanvas · StepPalette · RunLogs · ApprovalBanner
│   │   │   ├── knowledge/            # FileUploader · KBCard · SourceCitation · ChunkPreview
│   │   │   ├── billing/              # PlanCard · UsageMeter · UpgradeModal
│   │   │   └── ui/                   # shadcn/ui base components
│   │   ├── hooks/                    # useChat · useStreaming · useWorkflow · useKnowledge · useAuth
│   │   ├── lib/
│   │   │   ├── api.ts                # Axios client — injects JWT, handles 401 refresh
│   │   │   ├── streaming.ts          # SSE parser + token accumulator
│   │   │   └── store/                # Zustand slices: auth · workspace · conversation · ui
│   │   ├── middleware/               # Next.js middleware: auth guard · workspace resolver
│   │   ├── .env.local
│   │   └── next.config.ts
│   │
│   ├── api/                          # FastAPI modular monolith — all backend logic
│   │   ├── main.py                   # App factory: mounts routers, CORS, middleware, lifespan
│   │   ├── .env
│   │   ├── api/v1/
│   │   │   ├── auth.py
│   │   │   ├── chat.py               # /chat/stream — SSE streaming endpoint
│   │   │   ├── conversations.py
│   │   │   ├── files.py
│   │   │   ├── knowledge.py
│   │   │   ├── workflows.py
│   │   │   ├── integrations.py
│   │   │   ├── webhooks.py
│   │   │   ├── usage.py
│   │   │   ├── billing.py
│   │   │   └── admin.py
│   │   ├── services/
│   │   │   ├── auth_service.py
│   │   │   ├── chat_service.py
│   │   │   ├── conversation_service.py
│   │   │   ├── rag_service.py
│   │   │   ├── memory_service.py
│   │   │   ├── workflow_service.py
│   │   │   ├── tool_service.py
│   │   │   ├── billing_service.py
│   │   │   └── notification_service.py
│   │   ├── ai/
│   │   │   ├── providers/
│   │   │   │   ├── base.py
│   │   │   │   ├── openai.py
│   │   │   │   ├── anthropic.py
│   │   │   │   ├── groq.py
│   │   │   │   ├── gemini.py
│   │   │   │   └── vllm.py
│   │   │   ├── router.py
│   │   │   ├── orchestrator.py
│   │   │   ├── circuit_breaker.py
│   │   │   ├── token_counter.py
│   │   │   └── guardrails.py
│   │   ├── db/
│   │   │   ├── models/
│   │   │   │   ├── user.py
│   │   │   │   ├── conversation.py
│   │   │   │   ├── knowledge.py
│   │   │   │   ├── memory.py
│   │   │   │   ├── workflow.py
│   │   │   │   ├── billing.py
│   │   │   │   └── audit.py
│   │   │   ├── repos/
│   │   │   │   ├── user_repo.py
│   │   │   │   ├── conversation_repo.py
│   │   │   │   ├── knowledge_repo.py
│   │   │   │   ├── memory_repo.py
│   │   │   │   └── workflow_repo.py
│   │   │   ├── session.py
│   │   │   └── migrations/           # Alembic migrations
│   │   ├── middleware/
│   │   │   ├── auth.py
│   │   │   ├── tenant.py
│   │   │   ├── rate_limit.py
│   │   │   └── logging.py
│   │   └── core/
│   │       ├── config.py
│   │       ├── exceptions.py
│   │       ├── security.py
│   │       └── deps.py
│   │
│   ├── worker/                        # Celery workers — all async / background processing
│   │   ├── celery_app.py
│   │   ├── tasks/
│   │   │   ├── ingestion.py
│   │   │   ├── memory.py
│   │   │   ├── workflow_exec.py
│   │   │   ├── summarize.py
│   │   │   ├── usage_rollup.py
│   │   │   └── notifications.py
│   │   ├── parsers/
│   │   │   ├── pdf.py
│   │   │   ├── docx.py
│   │   │   ├── csv_xlsx.py
│   │   │   └── web.py
│   │   ├── chunkers/
│   │   │   ├── fixed.py
│   │   │   ├── sentence.py
│   │   │   └── semantic.py
│   │   └── .env
│   │
│   └── admin/                         # Internal ops tooling — not customer-facing (optional)
│
├── packages/
│   ├── ai-sdk/                       # Provider adapters + orchestration core
│   │   ├── providers/
│   │   ├── orchestrator.py
│   │   └── router.py
│   │
│   ├── workflow-engine/              # DAG runner — step executors, durable state
│   │   ├── dag.py
│   │   ├── executor.py
│   │   ├── state.py
│   │   └── steps/
│   │
│   ├── tool-registry/                # Tool definitions + sandboxed execution
│   │   ├── registry.py
│   │   ├── executor.py
│   │   └── tools/
│   │
│   ├── rag-pipeline/                 # File parsing, chunking, embedding, retrieval
│   │   ├── ingest.py
│   │   ├── retriever.py
│   │   └── embedder.py
│   │
│   ├── shared-types/                 # Pydantic models + generated TypeScript types
│   │   ├── python/
│   │   └── typescript/
│   │
│   ├── ui/                           # Shared React component library
│   │   ├── components/
│   │   └── icons/
│   │
│   └── prompts/                      # Versioned prompt templates
│       ├── system_default.md
│       ├── memory_extraction.md
│       ├── summarization.md
│       └── rag_citation.md
│
├── infra/
│   ├── terraform/                    # AWS Infrastructure as Code
│   │   ├── modules/
│   │   ├── environments/
│   │   └── main.tf
│   │
│   └── docker/
│       ├── Dockerfile.api
│       ├── Dockerfile.worker
│       ├── Dockerfile.web
│       └── docker-compose.yml
│
├── scripts/
│   ├── seed.py
│   └── migrate.sh
│
├── tests/
│   ├── unit/
│   │   ├── test_orchestrator.py
│   │   ├── test_router.py
│   │   ├── test_chunkers.py
│   │   └── test_dag.py
│   ├── integration/
│   │   ├── test_chat_api.py
│   │   ├── test_rag_pipeline.py
│   │   ├── test_workflow_exec.py
│   │   └── test_billing.py
│   ├── e2e/
│   │   ├── auth.spec.ts
│   │   ├── chat.spec.ts
│   │   ├── upload.spec.ts
│   │   └── workflow.spec.ts
│   └── fixtures/
│
├── .github/workflows/
│   ├── ci.yml
│   ├── deploy-staging.yml
│   └── deploy-prod.yml
│
├── turbo.json
├── pnpm-workspace.yaml
├── pyproject.toml
├── .env.example
└── ARCHITECTURE.md

```
### 🏁 Quick Start (Local Development)

#### Prerequisites
- Docker + Docker Compose
- Node.js 20+ + pnpm
- Python 3.12 + uv (recommended) or poetry

#### 1. Clone & Setup
```bash
git clone https://github.com/jyothir-369/CAT.AI.git
cd CAT.AI
cp .env.example .env
```

2. Start Everything
# Frontend + Backend + DB + Redis
docker compose up --build
```
3. Run Migrations & Seed
# Frontend + Backend + DB + Redis
docker compose up --build

```
📖 Detailed Documentation

Full Architecture Blueprint (38 pages)
API Reference
Development Guide
Deployment Guide

Open http://localhost:3000 → Register → Start chatting!

📖 Detailed Documentation

Full Architecture Blueprint (38 pages)
API Reference
Development Guide
Deployment Guide


🗺️ Roadmap
MVP (Done)

Core chat + streaming
Auth + multi-tenant workspaces
Basic RAG + file upload
OpenAI & Anthropic support

Next (v1.1)

Groq + Gemini + model routing
Full workflow engine + human approvals
Tool calling framework
Memory extraction

Future

Self-hosted vLLM
SSO / SAML
Advanced analytics + LLM evaluation
Mobile apps


🤝 Contributing
We welcome contributions! Please see CONTRIBUTING.md

Fork the repo
Create a feature branch
Run pnpm lint && pnpm test (frontend) + pytest (backend)
Open a PR with clear description


📜 License
MIT License — feel free to use, modify, and deploy commercially.
See LICENSE for details.

Built with ❤️ by Ra'ghav
From idea → production-grade blueprint → fully working open-source platform
