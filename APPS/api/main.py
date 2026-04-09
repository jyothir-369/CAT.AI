"""
CAT AI — FastAPI application factory.

Mounts all routers, registers middleware, and handles lifespan events.
All services are modular; extraction to microservices happens at scale.
"""
import sys
import os

# Ensure the api/ directory is on sys.path so all local imports resolve
sys.path.insert(0, os.path.dirname(__file__))

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from core.exceptions import AppError

# ── Routers ───────────────────────────────────────────────────────────────────
from api.v1.auth import router as auth_router
from api.v1.chat import router as chat_router
from api.v1.conversations import router as conversations_router
from api.v1.files import router as files_router
from api.v1.knowledge import router as knowledge_router
from api.v1.workflows import router as workflows_router
from api.v1.integrations import router as integrations_router
from api.v1.webhooks import router as webhooks_router
from api.v1.usage import router as usage_router
from api.v1.billing import router as billing_router
from api.v1.admin import router as admin_router

# ── Middleware ────────────────────────────────────────────────────────────────
from middleware.logging import LoggingMiddleware
from middleware.rate_limit import RateLimitMiddleware


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Startup / shutdown lifecycle.
    - Creates DB tables in dev (use Alembic migrations in production).
    - Closes DB engine on shutdown.
    """
    # Import all models so SQLAlchemy metadata is populated before create_all
    import db.models.user          # noqa: F401
    import db.models.conversation  # noqa: F401
    import db.models.knowledge     # noqa: F401
    import db.models.memory        # noqa: F401
    import db.models.workflow      # noqa: F401
    import db.models.billing       # noqa: F401
    import db.models.audit         # noqa: F401
    import db.models.integrations  # noqa: F401

    from db.session import engine, Base

    if settings.debug:
        # Auto-create tables in development — use Alembic in staging/prod
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    print(f"✅  CAT AI API started — debug={settings.debug}")
    yield

    await engine.dispose()
    print("👋  CAT AI API shutdown complete")


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="CAT AI API",
        description=(
            "Production-grade AI assistant and automation platform. "
            "Conversational AI · Workflow Automation · RAG Knowledge Base · SaaS Platform"
        ),
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            settings.frontend_url,
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
    )

    # ── Custom middleware (order matters — outermost runs first) ──────────────
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RateLimitMiddleware, redis_url=settings.redis_url)

    # ── Global exception handler ──────────────────────────────────────────────
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # In production, Sentry would capture this automatically
        print(f"[ERROR] Unhandled exception on {request.url.path}: {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    # ── Routers — all under /api/v1 ───────────────────────────────────────────
    prefix = "/api/v1"

    app.include_router(auth_router,          prefix=prefix)
    app.include_router(chat_router,          prefix=prefix)
    app.include_router(conversations_router, prefix=prefix)
    app.include_router(files_router,         prefix=prefix)
    app.include_router(knowledge_router,     prefix=prefix)
    app.include_router(workflows_router,     prefix=prefix)
    app.include_router(integrations_router,  prefix=prefix)
    app.include_router(webhooks_router,      prefix=prefix)
    app.include_router(usage_router,         prefix=prefix)
    app.include_router(billing_router,       prefix=prefix)
    app.include_router(admin_router,         prefix=prefix)

    # ── Root health check (no auth, used by load balancer) ───────────────────
    @app.get("/health", tags=["health"], include_in_schema=False)
    async def root_health():
        return {"status": "ok", "service": "cat-ai-api"}

    @app.get("/", include_in_schema=False)
    async def root():
        return {"service": "CAT AI API", "version": "1.0.0", "docs": "/docs"}

    return app


# ── Entrypoint ────────────────────────────────────────────────────────────────

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )