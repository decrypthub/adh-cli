"""Opt-in, read-only receipt metadata for the owning desktop."""
from __future__ import annotations

import os
import re
from typing import Any

_META_KEY = "decrypthub/usage"
_NONCE = re.compile(r"[0-9a-f]{32}")


def observe_result(
    request: Any, response: Any, endpoint: str, response_url: str
) -> Any:
    """Stamp the service that answered this tool call, without changing routing."""
    nonce = os.environ.get("DECRYPTHUB_MCP_OBSERVATION", "")
    if not _NONCE.fullmatch(nonce) or not isinstance(request, dict) or request.get("method") != "tools/call":
        return response
    if not isinstance(response, dict) or "error" in response:
        return response
    result = response.get("result")
    if "id" not in request or response.get("id") != request["id"] or not isinstance(result, dict):
        return response
    incoming = result.get("_meta")
    metadata = dict(incoming) if isinstance(incoming, dict) else {}
    # The remote service cannot report on behalf of the local CLI.
    metadata.pop(_META_KEY, None)
    if response_url == endpoint and result.get("isError") is not True and isinstance(result.get("content"), list):
        metadata[_META_KEY] = {
            "schemaVersion": 1,
            "nonce": nonce,
            "component": "adh",
            "target": {"kind": "service", "id": endpoint, "endpoint": endpoint},
        }
    value = {key: item for key, item in result.items() if key != "_meta"}
    if metadata:
        value["_meta"] = metadata
    return {**response, "result": value}
