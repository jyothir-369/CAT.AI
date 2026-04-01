from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1.routes import health


def create_app() -> FastAPI:
    app = FastAPI(
        title="CAT AI API",
        description="Production-grade AI SaaS backend",
        version="0.1.0",
    )

    # CORS — tighten origins before going to production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],  # Next.js dev server
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(health.router, tags=["System"])

    return app


app = create_app()