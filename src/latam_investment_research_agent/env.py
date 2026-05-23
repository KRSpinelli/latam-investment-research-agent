"""Load environment variables from the project `.env` file."""

from pathlib import Path

_LOADED = False


def load_env() -> None:
    """Load repo-root `.env` once (no-op if python-dotenv is unavailable)."""
    global _LOADED
    if _LOADED:
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        _LOADED = True
        return

    repo_root = Path(__file__).resolve().parents[2]
    load_dotenv(repo_root / ".env")
    _LOADED = True
