"""Line-delimited JSON-RPC stdio loop and transparent Host MCP proxy."""

from __future__ import annotations

import json
import sys
from typing import Any, Callable, TextIO

from .endpoint import HostEndpoint
from .http_mcp import MCPHTTPClient, MCPTransportError


class TransparentProxy:
    def __init__(self, endpoint: HostEndpoint) -> None:
        self._endpoint = endpoint
        self._client = MCPHTTPClient(endpoint)

    def handle(self, message: Any) -> Any | None:
        is_notification = isinstance(message, dict) and "id" not in message
        try:
            return self._client.send(message)
        except MCPTransportError as exc:
            if is_notification:
                print(f"adh: {exc}", file=sys.stderr, flush=True)
                return None
            request_id = message.get("id") if isinstance(message, dict) else None
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32000, "message": str(exc)},
            }


def configure_stdio_utf8() -> None:
    """MCP stdio is UTF-8. Windows consoles default to GBK and crash on tool text."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def serve_stdio(
    handler: Callable[[Any], Any | None],
    *,
    input_stream: TextIO = sys.stdin,
    output_stream: TextIO = sys.stdout,
) -> None:
    if input_stream is sys.stdin or output_stream is sys.stdout:
        configure_stdio_utf8()
    for raw_line in input_stream:
        if not raw_line.strip():
            continue
        try:
            message = json.loads(raw_line)
            response = handler(message)
        except json.JSONDecodeError:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }
        except Exception as exc:  # noqa: BLE001 — one bad message must not kill stdio
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": f"Internal error: {exc}"},
            }
        if response is not None:
            output_stream.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")))
            output_stream.write("\n")
            output_stream.flush()
