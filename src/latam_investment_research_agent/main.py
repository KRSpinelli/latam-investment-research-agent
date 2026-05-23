"""CLI entry points for the LatAm investment research agent."""

from __future__ import annotations

import os


from latam_investment_research_agent.env import load_env

load_env()


def run_api() -> None:
    """Start the FastAPI server (frontend entry point)."""
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("APP_ENV", "development") == "development"
    uvicorn.run(
        "latam_investment_research_agent.api.app:app",
        host=host,
        port=port,
        reload=reload,
    )


def main() -> None:
    run_api()


if __name__ == "__main__":
    main()
