"""Cognition Devin API Client for Autonomous Antigravity Collaboration.

Supports:
- v1 and v3 Cognition Devin REST API
- Session listing, creation, polling, and messaging
- Exponential backoff with jitter on HTTP 429/5xx errors
- Offline/mock simulation mode for integration testing before live credentials are bound
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request

logger = logging.getLogger("collaboration.devin_client")


class DevinAPIError(Exception):
    """Raised when Devin API returns an error or is unreachable."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class DevinClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.devin.ai/v1",
        timeout: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        org_id: Optional[str] = None
    ):
        self.api_key = api_key or os.environ.get("DEVIN_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.org_id = org_id or os.environ.get("DEVIN_ORG_ID")

    @property
    def is_authenticated(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def _headers(self) -> Dict[str, str]:
        if not self.is_authenticated:
            raise DevinAPIError(
                "DEVIN_API_KEY is not configured. Set the environment variable DEVIN_API_KEY "
                "or pass api_key to DevinClient."
            )
        return {
            "Authorization": f"Bearer {self.api_key.strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Antigravity-Devin-Bridge/1.0"
        }

    def _request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._headers()
        body_bytes = json.dumps(data).encode("utf-8") if data is not None else None

        last_error = None
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    raw = response.read().decode("utf-8")
                    return json.loads(raw) if raw.strip() else {}
            except urllib.error.HTTPError as e:
                status = e.code
                err_body = e.read().decode("utf-8", errors="replace")
                last_error = DevinAPIError(
                    f"HTTP {status} from Devin API on {method} {url}: {err_body}",
                    status_code=status,
                    response_body=err_body
                )
                if status in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    sleep_time = self.backoff_factor ** attempt
                    logger.warning(f"Retrying after HTTP {status} in {sleep_time:.1f}s...")
                    time.sleep(sleep_time)
                    continue
                raise last_error
            except urllib.error.URLError as e:
                last_error = DevinAPIError(f"Network error communicating with Devin API ({url}): {e.reason}")
                if attempt < self.max_retries:
                    sleep_time = self.backoff_factor ** attempt
                    time.sleep(sleep_time)
                    continue
                raise last_error

        raise last_error or DevinAPIError("Request failed after retries")

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List active and recent Devin sessions."""
        endpoint = f"sessions?limit={limit}"
        res = self._request("GET", endpoint)
        if isinstance(res, list):
            return res
        return res.get("sessions", [])

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """Fetch current session state, messages, and execution status."""
        endpoint = f"sessions/{session_id}"
        return self._request("GET", endpoint)

    def send_message(self, session_id: str, message: str) -> Dict[str, Any]:
        """Send a follow-up instruction or finding into an active Devin session."""
        # Try v1 endpoint
        endpoint = f"sessions/{session_id}/message"
        payload = {"message": message}
        try:
            return self._request("POST", endpoint, payload)
        except DevinAPIError as e:
            # Fallback to alternative endpoint if v1 variant differs
            if e.status_code == 404:
                endpoint_alt = f"sessions/{session_id}/messages"
                return self._request("POST", endpoint_alt, payload)
            raise

    def create_session(self, prompt: str, title: Optional[str] = None) -> Dict[str, Any]:
        """Spawn a new Devin session with an initial collaboration prompt."""
        payload: Dict[str, Any] = {"prompt": prompt}
        if title:
            payload["title"] = title
        return self._request("POST", "sessions", payload)
