"""HTTP JSON-RPC client for Host ADH Daemon POST /mcp."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import __version__
from .endpoint import HostEndpoint


class MCPTransportError(RuntimeError):
    pass


class MCPHTTPClient:
    def __init__(self, endpoint: HostEndpoint, *, timeout: float = 120.0, operator: bool = False) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self.session_id: str | None = None
        self.client_id = uuid.uuid4().hex
        self.operator_token = os.environ.get("ADH_OPERATOR_TOKEN") if operator else None
        if operator and not self.operator_token:
            raise MCPTransportError("--operator requires ADH_OPERATOR_TOKEN in this process environment")

    def update_endpoint(self, endpoint: HostEndpoint) -> None:
        if endpoint.mcp_url != self.endpoint.mcp_url:
            self.session_id = None
        self.endpoint = endpoint

    def send(self, message: Any) -> Any | None:
        body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"adh/{__version__}",
            "X-Adh-Client-Id": self.client_id,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        request = Request(self.endpoint.mcp_url, data=body, headers=headers, method="POST")
        if self.operator_token:
            request.add_unredirected_header("X-Adh-Operator-Key", self.operator_token)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                session_id = response.headers.get("Mcp-Session-Id")
                if session_id:
                    self.session_id = session_id
                payload = response.read()
                if response.status in (202, 204) or not payload:
                    return None
                return json.loads(payload)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise MCPTransportError(
                f"MCP HTTP {exc.code} ({self.endpoint.mcp_url}): {detail or exc.reason}"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise MCPTransportError(
                f"MCP HTTP exchange failed ({self.endpoint.mcp_url}): {exc}; "
                "Host/target execution may continue; inspect durable operations before retrying writes"
            ) from exc
        except json.JSONDecodeError as exc:
            raise MCPTransportError(f"host returned invalid JSON: {exc}") from exc


def probe_endpoint(endpoint: HostEndpoint, *, timeout: float = 3.0) -> HostEndpoint:
    request = Request(
        f"{endpoint.base_url}/health",
        headers={"Accept": "application/json", "User-Agent": f"adh/{__version__}"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            health = json.loads(response.read())
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return endpoint.with_properties({"status": "unreachable"})
    if not isinstance(health, dict) or health.get("ok") is not True:
        return endpoint.with_properties({"status": "unreachable"})
    return endpoint.with_properties(
        {
            "status": "online",
            "service": health.get("service") or health.get("name"),
            "version": health.get("version"),
            "agents": health.get("agents"),
            "mcp_tools": health.get("mcpTools"),
            "apps": health.get("apps", []),
        }
    )
