from __future__ import annotations

import os
from typing import Any

import httpx

BASE_URL = "https://apiv2.senso.ai/api/v1"
_TIMEOUT = 30.0


class SensoClient:
    """Async wrapper around the Senso REST API (apiv2.senso.ai/api/v1)."""

    def __init__(self, api_key: str | None = None, base_url: str = BASE_URL) -> None:
        key = api_key or os.environ.get("SENSO_API_KEY")
        if not key:
            raise ValueError("SENSO_API_KEY not set — pass api_key or export the env var")
        self._base = base_url.rstrip("/")
        self._headers = {"X-API-Key": key, "Content-Type": "application/json"}

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            r = await http.get(f"{self._base}{path}", headers=self._headers, params=params)
            r.raise_for_status()
            return r.json()

    async def _post(self, path: str, body: dict[str, Any]) -> Any:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            r = await http.post(f"{self._base}{path}", headers=self._headers, json=body)
            r.raise_for_status()
            return r.json()

    async def _put(self, path: str, body: dict[str, Any]) -> Any:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            r = await http.put(f"{self._base}{path}", headers=self._headers, json=body)
            r.raise_for_status()
            return r.json()

    # ------------------------------------------------------------------
    # KB — folders
    # ------------------------------------------------------------------

    async def kb_root(self) -> dict[str, Any]:
        """Return the root KB node (contains the root folder ID)."""
        return dict(await self._get("/org/kb/root"))

    async def kb_children(
        self,
        parent_id: str,
        node_type: str | None = "folder",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List children of a folder node.

        Args:
            parent_id: Parent folder node ID.
            node_type: Optional Senso node type filter; ``None`` lists all types.
            limit: Maximum nodes to return.

        Returns:
            Child node dicts from the Senso API.
        """
        params: dict[str, Any] = {"limit": limit, "offset": 0}
        if node_type is not None:
            params["type"] = node_type
        data = await self._get(
            f"/org/kb/nodes/{parent_id}/children",
            params=params,
        )
        return list(data.get("nodes", []))

    async def kb_create_folder(self, name: str, parent_id: str | None = None) -> dict[str, Any]:
        """Create a KB folder. Returns the new node (kb_node_id, name, ...)."""
        body: dict[str, Any] = {"name": name}
        if parent_id:
            body["parent_id"] = parent_id
        return dict(await self._post("/org/kb/folders", body))

    async def kb_find_or_create_folder(
        self, name: str, parent_id: str | None = None
    ) -> dict[str, Any]:
        """Return existing folder by name under parent, or create it."""
        if parent_id:
            children = await self.kb_children(parent_id)
            for node in children:
                if node.get("name") == name and node.get("type") == "folder":
                    return node
        return await self.kb_create_folder(name, parent_id)

    # ------------------------------------------------------------------
    # KB — raw text content
    # ------------------------------------------------------------------

    async def _find_child_by_title(
        self,
        parent_id: str,
        title: str,
    ) -> dict[str, Any] | None:
        """Return a child KB node with the given display name, if present.

        Args:
            parent_id: Folder to search.
            title: Expected node name / title.

        Returns:
            Matching node dict or ``None``.
        """
        for node in await self.kb_children(parent_id, node_type=None):
            if node.get("name") == title or node.get("title") == title:
                return node
        return None

    async def _reuse_or_update_raw(
        self,
        folder_id: str,
        title: str,
        text: str,
    ) -> dict[str, Any]:
        """On duplicate ingest (HTTP 409), update existing raw content in place.

        Args:
            folder_id: Target folder node ID.
            title: Document title used for create.
            text: Full document text.

        Returns:
            Response shaped like :meth:`kb_create_raw`.

        Raises:
            httpx.HTTPStatusError: If no matching node exists to update.
        """
        existing = await self._find_child_by_title(folder_id, title)
        if existing is None:
            raise httpx.HTTPStatusError(
                "Senso returned 409 Conflict but no existing node matched the title",
                request=httpx.Request("POST", f"{self._base}/org/kb/raw"),
                response=httpx.Response(409),
            )
        node_id = existing.get("kb_node_id") or existing.get("content_id")
        if not node_id:
            raise httpx.HTTPStatusError(
                "Senso duplicate node is missing kb_node_id",
                request=httpx.Request("POST", f"{self._base}/org/kb/raw"),
                response=httpx.Response(409),
            )
        updated = await self.kb_update_raw(node_id, text)
        content = updated.get("content", updated)
        if isinstance(content, dict):
            processing_status = content.get("processing_status")
        else:
            processing_status = None
        return {
            "kb_node_id": node_id,
            "content_id": node_id,
            "content": {"processing_status": processing_status},
            "reused_existing": True,
        }

    async def kb_create_raw(
        self,
        title: str,
        text: str,
        folder_id: str,
        tag_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Ingest raw text into a KB folder. Senso handles chunking and embedding.

        If Senso reports a duplicate (HTTP 409), updates the existing node text
        and returns its identifiers instead of failing.
        """
        body: dict[str, Any] = {
            "title": title,
            "text": text,
            "kb_folder_node_id": folder_id,
        }
        if tag_ids:
            body["tag_ids"] = tag_ids
        try:
            return dict(await self._post("/org/kb/raw", body))
        except httpx.HTTPStatusError as error:
            if error.response.status_code != 409:
                raise
            return await self._reuse_or_update_raw(folder_id, title, text)

    async def kb_update_raw(self, node_id: str, text: str) -> dict[str, Any]:
        """Replace the full text of an existing raw content node."""
        return dict(await self._put(f"/org/kb/nodes/{node_id}/raw", {"text": text}))

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search_context(
        self,
        query: str,
        max_results: int = 8,
        content_ids: list[str] | None = None,
        require_scoped_ids: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Return raw content chunks for grounding — no AI answer generation.
        Pass content_ids to scope search to specific documents.
        """
        body: dict[str, Any] = {"query": query, "max_results": max_results}
        if content_ids:
            body["content_ids"] = content_ids
        if require_scoped_ids:
            body["require_scoped_ids"] = True
        data = await self._post("/org/search/context", body)
        if isinstance(data, dict):
            return list(data.get("results", []))
        return list(data)
