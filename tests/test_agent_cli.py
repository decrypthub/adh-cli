import json
import os
from pathlib import Path
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest


@pytest.fixture
def host():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "service": "adhd", "version": "test", "apps": [
                {"package": "com.example.live", "sessionId": "live-session", "pid": 42, "online": True},
                {"package": "com.example.old", "sessionId": "old-session", "pid": 43, "online": False},
            ]}).encode())

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            result = {"tools": [{"name": "sessions", "description": "Live sessions", "inputSchema": {"type": "object"}}]} if data["method"] == "tools/list" else {"isError": True, "content": []}
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"jsonrpc": "2.0", "id": data["id"], "result": result}).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def run(tmp_path, *args):
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
           "ADH_CONFIG_PATH": str(tmp_path / "connections.json"), "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, "-m", "adh", *args], env=env, capture_output=True, text=True, encoding="utf-8", timeout=15)


def test_status_reads_actual_health_without_saving_or_claiming_an_old_session_online(tmp_path, host):
    result = run(tmp_path, "status", "--endpoint", host, "--json")
    assert result.returncode == 0, result.stderr
    status = json.loads(result.stdout)
    assert status["component"] == "adh" and status["schemaVersion"] == 1
    assert status["connections"][0]["online"] is True
    assert [(row["id"], row["online"]) for row in status["targets"]] == [("live-session", True), ("old-session", False)]
    assert not (tmp_path / "connections.json").exists()


def test_unreachable_host_is_an_observation_not_a_fake_target(tmp_path):
    result = run(tmp_path, "status", "--endpoint", "127.0.0.1:1", "--timeout", "0.1", "--json")
    assert result.returncode == 0, result.stderr
    status = json.loads(result.stdout)
    assert status["connections"][0]["online"] is False
    assert status["targets"] == []


def test_tools_returns_real_schema_and_call_failure_has_nonzero_exit(tmp_path, host):
    result = run(tmp_path, "tools", "--endpoint", host, "--json")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["tools"][0]["inputSchema"] == {"type": "object"}
    result = run(tmp_path, "call", "failure", "--endpoint", host, "--json")
    assert result.returncode == 1
