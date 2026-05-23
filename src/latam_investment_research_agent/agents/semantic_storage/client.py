import os
from typing import Any

import httpx


BASE_URL = "https://apiv2.senso.ai/api/v1"
_DEFAULT_TIMEOUT = 30.0


class SensoClient:
    """Thin async wrapper around the Senso REST API."""

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.environ.get("SENSO_API_KEY")
        if not key:
            raise ValueError("SENSO_API_KEY not set — pass api_key or export the env var")
        self._headers = {"X-API-Key": key, "Content-Type": "application/json"}

    # ------------------------------------------------------------------
    # KB folders
    # ------------------------------------------------------------------

    async def create_folder(self, path: str) -> dict[str, Any]:
        """Create a KB folder at the given path (idempotent — returns existing if found)."""
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as http:
            r = await http.post(
                f"{BASE_URL}/kb/folders",
                headers=self._headers,
                json={"path": path},
            )
            r.raise_for_status()
            return dict(r.json())

    async def list_folders(self, prefix: str = "") -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as http:
            r = await http.get(
                f"{BASE_URL}/kb/folders",
                headers=self._headers,
                params={"prefix": prefix} if prefix else {},
            )
            r.raise_for_status()
            return list(r.json())

    # ------------------------------------------------------------------
    # Documents (chunks / citeables)
    # ------------------------------------------------------------------

    async def upsert_document(self, folder_path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Ingest a document chunk into a KB folder."""
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as http:
            r = await http.post(
                f"{BASE_URL}/kb/documents",
                headers=self._headers,
                json={"folder_path": folder_path, **payload},
            )
            r.raise_for_status()
            return dict(r.json())

    # ------------------------------------------------------------------
    # Semantic search
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        folder_prefix: str = "latam-alpha",
        top_k: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        body: dict[str, Any] = {
            "query": query,
            "folder_prefix": folder_prefix,
            "top_k": top_k,
        }
        if filters:
            body["filters"] = filters
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as http:
            r = await http.post(
                f"{BASE_URL}/kb/search",
                headers=self._headers,
                json=body,
            )
            r.raise_for_status()
            return list(r.json().get("results", []))
