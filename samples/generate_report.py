"""Sample script: start an analyst report job and download the PDF when ready.

Usage:
    uv run python samples/generate_report.py
    uv run python samples/generate_report.py "What were total export revenues by year?"

Requires API server:
    uv run latam-api

Or set API_BASE_URL to a running instance (default http://127.0.0.1:8000).
"""

from __future__ import annotations

import os
import sys
import time

import httpx

DEFAULT_QUERY = "What were total export revenues by year for coffee exporters in Brazil?"
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
POLL_INTERVAL_SECONDS = 5
POLL_REQUEST_TIMEOUT_SECONDS = 120.0
MAX_POLL_RETRIES = 12


def main(query: str, base_url: str) -> None:
    """Create a report job, poll until complete, and save the PDF locally.

    Args:
        query: Research question for the report.
        base_url: API base URL including scheme and host.
    """
    print(f"API:     {base_url}")
    print(f"Query:   {query}\n")

    with httpx.Client(timeout=POLL_REQUEST_TIMEOUT_SECONDS) as client:
        create_response = client.post(
            f"{base_url}/api/v1/research/report/jobs",
            json={"query": query},
        )
        create_response.raise_for_status()
        job = create_response.json()
        job_id = job["job_id"]
        print(f"Job ID:  {job_id}")
        print(f"Status:  {job['status']}\n")

        while True:
            status_response = _get_with_retries(
                client,
                f"{base_url}/api/v1/research/report/jobs/{job_id}",
            )
            status_response.raise_for_status()
            status_body = status_response.json()
            status = status_body["status"]
            print(f"  [{status}] rows={status_body.get('clickhouse_rows', 0)} "
                  f"docs={status_body.get('documents_ingested', 0)}")

            if status == "completed":
                break
            if status == "failed":
                print(f"\nJob failed: {status_body.get('error')}")
                sys.exit(1)
            time.sleep(POLL_INTERVAL_SECONDS)

        pdf_response = _get_with_retries(
            client,
            f"{base_url}/api/v1/research/report/jobs/{job_id}/pdf",
        )
        pdf_response.raise_for_status()

    output_path = f"report_{job_id}.pdf"
    with open(output_path, "wb") as pdf_file:
        pdf_file.write(pdf_response.content)

    print(f"\nSaved: {output_path} ({len(pdf_response.content)} bytes)")


def _get_with_retries(client: httpx.Client, url: str) -> httpx.Response:
    """GET with retries when the API restarts (e.g. uvicorn reload during dev).

    Args:
        client: HTTP client.
        url: Request URL.

    Returns:
        Successful HTTP response.

    Raises:
        httpx.HTTPError: When retries are exhausted.
    """
    last_error: Exception | None = None
    for attempt in range(MAX_POLL_RETRIES):
        try:
            return client.get(url)
        except (httpx.ReadError, httpx.ConnectError) as error:
            last_error = error
            if attempt + 1 >= MAX_POLL_RETRIES:
                break
            wait_seconds = min(30, POLL_INTERVAL_SECONDS * (attempt + 1))
            print(
                f"  (API unreachable, retrying in {wait_seconds}s — "
                "restart latam-api without --reload if this persists)"
            )
            time.sleep(wait_seconds)
    if last_error is not None:
        raise last_error
    raise RuntimeError("GET failed without an exception")


if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUERY
    api_base = os.getenv("API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    main(question, api_base)
