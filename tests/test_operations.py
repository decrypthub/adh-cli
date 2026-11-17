import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from adh import cli
from adh.endpoint import HostEndpoint
from adh.http_mcp import MCPHTTPClient, MCPTransportError


@pytest.fixture
def host():
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            args = data["params"]["arguments"]
            calls.append((data, dict(self.headers)))
            if args.get("action") == "snapshot":
                value = {"ok": True, "revision": 7, "epoch": 2, "hostEpoch": 1}
            elif args.get("action") == "submit":
                value = {"ok": False, "code": "STALE_CONTROL", "error": "human changed state"}
            else:
                value = {"ok": True, "operation": {"id": "fixture-operation", "state": "cancel_requested"}}
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"jsonrpc": "2.0", "id": data["id"], "result": {
                "content": [{"type": "text", "text": json.dumps(value)}], "isError": value.get("ok") is False,
            }}).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", calls
    server.shutdown()
    server.server_close()
    thread.join()


def test_run_observes_once_preserves_versions_and_never_rebases_after_conflict(host, capsys):
    endpoint, calls = host
    result = cli.main(["run", "memory_write", "--arguments", '{"session":"fixture","hex":"41"}',
                       "--task-id", "fixture-task", "--idempotency-key", "one-intent", "--timeout-ms", "4567",
                       "--endpoint", endpoint, "--json"])
    assert result == 1
    assert json.loads(capsys.readouterr().out)["code"] == "STALE_CONTROL"
    assert [call[0]["params"]["arguments"]["action"] for call in calls] == ["snapshot", "submit"]
    metadata = calls[-1][0]["params"]["arguments"]["_operation"]
    assert metadata == {"expectedRevision": 7, "controlEpoch": 2, "hostEpoch": 1,
                        "taskId": "fixture-task", "idempotencyKey": "one-intent", "timeoutMs": 4567}


def test_explicit_call_keeps_old_versions_for_host_to_reject(host):
    endpoint, calls = host
    assert cli.main(["call", "memory_write", "--arguments", '{"session":"fixture"}',
                     "--operation", '{"expectedRevision":0,"controlEpoch":0,"hostEpoch":0}',
                     "--endpoint", endpoint]) == 0
    assert len(calls) == 1
    assert calls[0][0]["params"]["arguments"]["_operation"]["expectedRevision"] == 0


def test_operator_access_is_explicit_and_stable_client_id_binds_notifications(host, monkeypatch):
    endpoint, calls = host
    monkeypatch.setenv("ADH_OPERATOR_TOKEN", "synthetic-operator-token")
    client = MCPHTTPClient(HostEndpoint.from_url(endpoint))
    message = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "operations", "arguments": {"action": "get"}}}
    client.send(message)
    client.send(message)
    assert "X-Adh-Operator-Key" not in calls[0][1]
    assert calls[0][1]["X-Adh-Client-Id"] == calls[1][1]["X-Adh-Client-Id"]
    MCPHTTPClient(HostEndpoint.from_url(endpoint), operator=True).send(message)
    assert calls[-1][1]["X-Adh-Operator-Key"] == "synthetic-operator-token"
    monkeypatch.delenv("ADH_OPERATOR_TOKEN")
    with pytest.raises(MCPTransportError, match="ADH_OPERATOR_TOKEN"):
        MCPHTTPClient(HostEndpoint.from_url(endpoint), operator=True)


def test_task_get_cancel_and_pagination_preserve_requested_meaning(host):
    endpoint, calls = host
    assert cli.main(["tasks", "get", "fixture-operation", "--include-result", "--endpoint", endpoint]) == 0
    assert calls[-1][0]["params"]["arguments"]["includeResult"] is True
    assert calls[-1][0]["params"]["arguments"]["id"] == "fixture-operation"
    assert cli.main(["tasks", "cancel", "--task-id", "fixture-task", "--endpoint", endpoint]) == 0
    assert calls[-1][0]["params"]["arguments"]["taskId"] == "fixture-task"
    assert cli.main(["tasks", "list", "--offset", "50", "--limit", "25", "--endpoint", endpoint]) == 0
    assert calls[-1][0]["params"]["arguments"]["offset"] == 50
    assert calls[-1][0]["params"]["arguments"]["limit"] == 25


def test_control_explicit_versions_are_not_refreshed_and_partial_versions_are_rejected(host):
    endpoint, calls = host
    assert cli.main(["control", "release", "--revision", "4", "--epoch", "3", "--host-epoch", "2",
                     "--endpoint", endpoint]) == 0
    assert len(calls) == 1
    assert calls[-1][0]["params"]["arguments"]["_operation"] == {"expectedRevision": 4, "controlEpoch": 3, "hostEpoch": 2}
    assert cli.main(["control", "release", "--revision", "4", "--endpoint", endpoint]) == 1
    assert len(calls) == 1


def test_http_timeout_does_not_report_confirmed_cancellation(monkeypatch):
    def timeout(*args, **kwargs):
        raise TimeoutError('synthetic network timeout')

    monkeypatch.setattr('adh.http_mcp.urlopen', timeout)
    client = MCPHTTPClient(HostEndpoint.from_url('127.0.0.1:1'))
    with pytest.raises(MCPTransportError, match='execution may continue'):
        client.send({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {}})
