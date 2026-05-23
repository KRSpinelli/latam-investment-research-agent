"""FastAPI application factory."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from latam_investment_research_agent.api.routes import health, research


from latam_investment_research_agent.env import load_env

load_env()


def create_app() -> FastAPI:
    app = FastAPI(
        title="LatAm Investment Research Agent",
        description=(
            "Research API: web search and crawl sources, classify signals, "
            "and route to ClickHouse, Senso, and the analysis agent."
        ),
        version="0.1.0",
    )

    origins = os.getenv("API_CORS_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in origins if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(research.router)
    return app


app = create_app()
