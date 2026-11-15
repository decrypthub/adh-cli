"""Read-only, versioned inventory consumed by desktop applications and Agents."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from . import __version__
from .endpoint import HostEndpoint
from .http_mcp import probe_endpoint


def inventory(endpoints: list[HostEndpoint], *, timeout: float = 3.0) -> dict[str, Any]:
    unique = list({endpoint.key: endpoint for endpoint in endpoints}.values())
    with ThreadPoolExecutor(max_workers=max(1, min(8, len(unique)))) as pool:
        checked = list(pool.map(lambda endpoint: probe_endpoint(endpoint, timeout=timeout), unique))
    connections = []
    targets = []
    for endpoint in checked:
        online = endpoint.properties.get("status") == "online"
        connections.append({"endpoint": endpoint.mcp_url, "online": online,
                            "version": endpoint.properties.get("version"),
                            "error": None if online else "unreachable"})
        apps = endpoint.properties.get("apps")
        for app in apps if isinstance(apps, list) else []:
            if not isinstance(app, dict) or not isinstance(app.get("sessionId"), str):
                continue
            targets.append({"id": app["sessionId"], "name": str(app.get("package") or app["sessionId"]),
                            "package": app.get("package"), "pid": app.get("pid"),
                            "endpoint": endpoint.mcp_url, "online": online and app.get("online") is True})
    return {"schemaVersion": 1, "component": "adh", "version": __version__,
            "checkedAt": datetime.now(timezone.utc).isoformat(), "connections": connections, "targets": targets}
