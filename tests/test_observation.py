"""Connection receipts are only produced at a verified local HTTP response."""
from __future__ import annotations

import json

from adh.http_mcp import MCPHTTPClient
from adh.endpoint import HostEndpoint
from adh.status import inventory


def test_status_keeps_configuration_separate_from_live_inventory():
    assert inventory([], source="explicit")["configuration"] == {
        "source": "explicit",
        "endpoints": [],
    }


def test_receipt_tracks_the_actual_responding_service(monkeypatch):
    a = HostEndpoint.from_url("http://127.0.0.1:49301")
    b = HostEndpoint.from_url("http://127.0.0.1:49302")
    nonce = "9e" * 16
    request = {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "fixture"}}
    result = {
        "jsonrpc": "2.0",
        "id": 7,
        "result": {
            "content": [{"type": "text", "text": "fixture"}],
            "_meta": {"unrelated": "retained", "decrypthub/usage": {"endpoint": b.mcp_url}},
        },
    }

    class Response:
        headers = {}
        status = 200
        url = a.mcp_url

        def read(self):
            return json.dumps(result).encode()

        def geturl(self):
            return self.url

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    response = Response()
    monkeypatch.setattr("adh.http_mcp.urlopen", lambda *_a, **_k: response)
    client = MCPHTTPClient(a)
    monkeypatch.delenv("DECRYPTHUB_MCP_OBSERVATION", raising=False)
    assert client.send(request) == result
    monkeypatch.setenv("DECRYPTHUB_MCP_OBSERVATION", nonce)
    received = client.send(request)["result"]["_meta"]
    assert received["unrelated"] == "retained"
    assert received["decrypthub/usage"] == {
        "schemaVersion": 1,
        "nonce": nonce,
        "component": "adh",
        "target": {"kind": "service", "id": a.mcp_url, "endpoint": a.mcp_url},
    }
    response.url = b.mcp_url
    assert client.send(request)["result"]["_meta"] == {"unrelated": "retained"}
    response.url = a.mcp_url
    result["result"]["isError"] = True
    assert client.send(request)["result"]["_meta"] == {"unrelated": "retained"}
