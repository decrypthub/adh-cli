from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from . import __version__
from .config import clear_endpoints, config_path, load_saved_endpoints, remove_endpoint, save_endpoint
from .endpoint import DEFAULT_PORT, HostEndpoint
from .http_mcp import MCPHTTPClient, MCPTransportError, probe_endpoint
from .stdio import TransparentProxy, configure_stdio_utf8, serve_stdio

PROBE_TIMEOUT = 3.0
DEFAULT_CONNECT = f"127.0.0.1:{DEFAULT_PORT}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adh",
        description="AndroidDecryptHub connection & MCP gateway for Host ADH Daemon",
    )
    parser.add_argument("--version", action="version", version=f"adh {__version__}")
    sub = parser.add_subparsers(dest="command")

    connect = sub.add_parser("connect", help="save and probe a Host ADH Daemon address")
    connect.add_argument("endpoint", nargs="?", default=DEFAULT_CONNECT, help=f"host address (default {DEFAULT_CONNECT})")
    connect.add_argument("--timeout", type=float, default=PROBE_TIMEOUT)
    connect.add_argument("--force", action="store_true", help="save even when unreachable")
    connect.add_argument("--json", action="store_true")

    disconnect = sub.add_parser("disconnect", help="remove a saved Host address")
    disconnect.add_argument("endpoint", nargs="?")
    disconnect.add_argument("--all", action="store_true")

    devices = sub.add_parser("devices", help="list saved Host daemons")
    devices.add_argument("--json", action="store_true")

    mcp = sub.add_parser("mcp", help="stdio MCP proxy to Host POST /mcp")
    mcp.add_argument("--endpoint", help="override saved address for this run")

    call = sub.add_parser("call", help="call one Host MCP tool")
    call.add_argument("tool_name")
    call.add_argument("--arguments", default="{}", metavar="JSON")
    call.add_argument("--endpoint")
    call.add_argument("--json", action="store_true")
    return parser


def _resolve_saved(override: str | None) -> HostEndpoint:
    if override:
        return HostEndpoint.from_url(override)
    saved = load_saved_endpoints()
    if len(saved) == 1:
        return saved[0]
    if not saved:
        raise SystemExit("adh: no saved host; run `adh connect 127.0.0.1:8760`")
    raise SystemExit(
        "adh: multiple saved hosts; pass --endpoint <url>\n"
        + "\n".join(f"  {item.mcp_url}" for item in saved)
    )


def _cmd_connect(args: argparse.Namespace) -> int:
    endpoint = HostEndpoint.from_url(args.endpoint)
    probed = probe_endpoint(endpoint, timeout=args.timeout)
    status = probed.properties.get("status")
    if status != "online" and not args.force:
        print(f"adh: unreachable {probed.base_url} (need Host ADH Daemon on :{DEFAULT_PORT})", file=sys.stderr)
        return 1
    added = save_endpoint(endpoint)
    payload = {
        "url": probed.mcp_url,
        "status": status,
        "saved": True,
        "added": added,
        "config": str(config_path()),
        "service": probed.properties.get("service"),
        "version": probed.properties.get("version"),
        "agents": probed.properties.get("agents"),
        "mcp_tools": probed.properties.get("mcp_tools"),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        state = "online" if status == "online" else "saved (offline)"
        print(f"adh: {state} {probed.base_url}")
        print(f"  mcp {probed.mcp_url}")
        print(f"  config {config_path()}")
    return 0


def _cmd_disconnect(args: argparse.Namespace) -> int:
    if args.all:
        n = clear_endpoints()
        print(f"adh: removed {n} saved host(s)")
        return 0
    if not args.endpoint:
        print("adh: disconnect needs an address or --all", file=sys.stderr)
        return 2
    if remove_endpoint(args.endpoint):
        print(f"adh: removed {HostEndpoint.from_url(args.endpoint).mcp_url}")
        return 0
    print("adh: address not saved", file=sys.stderr)
    return 1


def _cmd_devices(args: argparse.Namespace) -> int:
    saved = load_saved_endpoints()
    rows = [probe_endpoint(item) for item in saved]
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "url": item.mcp_url,
                        "status": item.properties.get("status"),
                        "service": item.properties.get("service"),
                        "version": item.properties.get("version"),
                        "agents": item.properties.get("agents"),
                    }
                    for item in rows
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if not rows:
        print("adh: no saved hosts. `adh connect 127.0.0.1:8760`")
        return 0
    for item in rows:
        status = item.properties.get("status") or "unknown"
        extra = item.properties.get("service") or ""
        print(f"{status:12} {item.base_url}  {extra}".rstrip())
    return 0


def _cmd_mcp(args: argparse.Namespace) -> int:
    endpoint = _resolve_saved(args.endpoint)
    probed = probe_endpoint(endpoint)
    if probed.properties.get("status") != "online":
        print(f"adh: host unreachable {endpoint.base_url}", file=sys.stderr)
        return 1
    serve_stdio(TransparentProxy(endpoint).handle)
    return 0


def _cmd_call(args: argparse.Namespace) -> int:
    endpoint = _resolve_saved(args.endpoint)
    try:
        arguments = json.loads(args.arguments)
    except json.JSONDecodeError as exc:
        print(f"adh: --arguments must be a JSON object: {exc}", file=sys.stderr)
        return 2
    if not isinstance(arguments, dict):
        print("adh: --arguments must be a JSON object", file=sys.stderr)
        return 2
    client = MCPHTTPClient(endpoint)
    try:
        response = client.send(
            {
                "jsonrpc": "2.0",
                "id": "adh-call",
                "method": "tools/call",
                "params": {"name": args.tool_name, "arguments": arguments},
            }
        )
    except MCPTransportError as exc:
        print(f"adh: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(response, ensure_ascii=False, indent=2))
    else:
        result = response.get("result") if isinstance(response, dict) else response
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    configure_stdio_utf8()
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if not args.command:
        parser.print_help()
        return 2
    commands = {
        "connect": _cmd_connect,
        "disconnect": _cmd_disconnect,
        "devices": _cmd_devices,
        "mcp": _cmd_mcp,
        "call": _cmd_call,
    }
    return commands[args.command](args)
