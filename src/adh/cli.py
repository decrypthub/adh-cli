from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections.abc import Sequence

from . import __version__
from .config import clear_endpoints, config_path, load_saved_endpoints, remove_endpoint, save_endpoint
from .endpoint import DEFAULT_PORT, HostEndpoint
from .http_mcp import MCPHTTPClient, MCPTransportError, probe_endpoint
from .stdio import TransparentProxy, configure_stdio_utf8, serve_stdio
from .status import inventory

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
    devices.add_argument("--endpoint", action="append", default=[])

    status = sub.add_parser("status", help="read-only service and target inventory for desktop Agents")
    status.add_argument("--endpoint", action="append", default=[])
    status.add_argument("--timeout", type=float, default=PROBE_TIMEOUT)
    status.add_argument("--json", action="store_true")

    tools = sub.add_parser("tools", help="list the Host's real MCP tools and argument schemas")
    tools.add_argument("--endpoint")
    tools.add_argument("--json", action="store_true")

    mcp = sub.add_parser("mcp", help="stdio MCP proxy to Host POST /mcp")
    mcp.add_argument("--endpoint", help="override saved address for this run")

    call = sub.add_parser("call", help="call one Host MCP tool")
    call.add_argument("tool_name")
    call.add_argument("--arguments", default="{}", metavar="JSON")
    call.add_argument("--endpoint")
    call.add_argument("--json", action="store_true")
    call.add_argument("--operation", help="explicit operation control metadata as JSON")
    call.add_argument("--operator", action="store_true", help="use ADH_OPERATOR_TOKEN explicitly")

    run = sub.add_parser("run", help="observe current control once and submit a durable tool operation")
    run.add_argument("tool_name")
    run.add_argument("--arguments", default="{}")
    run.add_argument("--task-id")
    run.add_argument("--idempotency-key")
    run.add_argument("--timeout-ms", type=int, default=120000)
    run.add_argument("--endpoint")
    run.add_argument("--operator", action="store_true")
    run.add_argument("--json", action="store_true")

    tasks = sub.add_parser("tasks", help="query/control persistent Host tasks and operations")
    tasks.add_argument("action", choices=["create", "list", "get", "pause", "resume", "cancel", "complete"])
    tasks.add_argument("id", nargs="?")
    tasks.add_argument("--task-id")
    tasks.add_argument("--title", default="analysis")
    tasks.add_argument("--include-result", action="store_true")
    tasks.add_argument("--limit", type=int, default=50)
    tasks.add_argument("--offset", type=int, default=0)
    tasks.add_argument("--endpoint")
    tasks.add_argument("--operator", action="store_true")
    tasks.add_argument("--json", action="store_true")

    control = sub.add_parser("control", help="read state versions or explicitly transfer operator control")
    control.add_argument("action", choices=["snapshot", "takeover", "release", "resolve", "hold"])
    control.add_argument("--session")
    control.add_argument("--resource")
    control.add_argument("--revision", type=int)
    control.add_argument("--epoch", type=int)
    control.add_argument("--host-epoch", type=int)
    control.add_argument("--acknowledge", action="store_true")
    control.add_argument("--endpoint")
    control.add_argument("--operator", action="store_true")
    control.add_argument("--json", action="store_true")
    return parser


def _resolve_saved(override: str | None) -> HostEndpoint:
    if override:
        return HostEndpoint.from_url(override)
    saved = load_saved_endpoints()
    if len(saved) == 1:
        return saved[0]
    if not saved:
        raise SystemExit("adh: no saved host; run `adh connect 127.0.0.1:8088`")
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
    saved = [HostEndpoint.from_url(value) for value in args.endpoint] if args.endpoint else load_saved_endpoints()
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
        print("adh: no saved hosts. `adh connect 127.0.0.1:8088`")
        return 0
    for item in rows:
        status = item.properties.get("status") or "unknown"
        extra = item.properties.get("service") or ""
        print(f"{status:12} {item.base_url}  {extra}".rstrip())
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    endpoints = [HostEndpoint.from_url(value) for value in args.endpoint] if args.endpoint else load_saved_endpoints()
    data = inventory(endpoints, timeout=args.timeout)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def _cmd_tools(args: argparse.Namespace) -> int:
    endpoint = _resolve_saved(args.endpoint)
    try:
        response = MCPHTTPClient(endpoint, timeout=10.0).send({"jsonrpc": "2.0", "id": "adh-tools", "method": "tools/list", "params": {}})
        result = response.get("result") if isinstance(response, dict) and "error" not in response else None
        if not isinstance(result, dict) or not isinstance(result.get("tools"), list):
            print("adh: invalid tools/list response", file=sys.stderr)
            return 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except MCPTransportError as exc:
        print(f"adh: {exc}", file=sys.stderr)
        return 1


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
    if args.operation:
        try:
            metadata = json.loads(args.operation)
            if not isinstance(metadata, dict) or "_operation" in arguments:
                raise ValueError("use one operation metadata object")
            arguments["_operation"] = metadata
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"adh: invalid --operation: {exc}", file=sys.stderr)
            return 2
    try:
        client = MCPHTTPClient(endpoint, operator=True) if args.operator else MCPHTTPClient(endpoint)
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
    result = response.get("result") if isinstance(response, dict) else None
    return 1 if not isinstance(result, dict) or result.get("isError") else 0


def _operation_rpc(client: MCPHTTPClient, arguments: dict) -> dict:
    response = client.send({"jsonrpc": "2.0", "id": uuid.uuid4().hex, "method": "tools/call",
                            "params": {"name": "operations", "arguments": arguments}})
    if not isinstance(response, dict) or "error" in response:
        raise MCPTransportError("Host rejected operation management request")
    result = response.get("result", {})
    try:
        value = json.loads(result["content"][0]["text"])
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise MCPTransportError("Host does not support P1 operation management") from exc
    if not isinstance(value, dict):
        raise MCPTransportError("invalid operation response")
    return value


def _cmd_operations(args: argparse.Namespace) -> int:
    try:
        endpoint = _resolve_saved(args.endpoint)
        client = MCPHTTPClient(endpoint, operator=True) if args.operator else MCPHTTPClient(endpoint)
        if args.command == "run":
            values = json.loads(args.arguments)
            if not isinstance(values, dict) or "_operation" in values:
                raise ValueError("--arguments must be an object without _operation; use call for explicit versions")
            snapshot = _operation_rpc(client, {"action": "snapshot", "tool": args.tool_name, "arguments": values})
            if snapshot.get("ok") is False:
                value = snapshot
            else:
                metadata = {"expectedRevision": snapshot["revision"], "controlEpoch": snapshot["epoch"],
                            "hostEpoch": snapshot["hostEpoch"], "idempotencyKey": args.idempotency_key or uuid.uuid4().hex,
                            "timeoutMs": args.timeout_ms}
                if args.task_id:
                    metadata["taskId"] = args.task_id
                value = _operation_rpc(client, {"action": "submit", "tool": args.tool_name, "arguments": values, "_operation": metadata})
        elif args.command == "control":
            target = {key: val for key, val in {"session": args.session, "resource": args.resource}.items() if val}
            values = {"action": args.action, **target}
            if args.action != "snapshot":
                numbers = [args.revision, args.epoch, args.host_epoch]
                if any(n is not None for n in numbers) and not all(n is not None for n in numbers):
                    raise ValueError("supply --revision, --epoch and --host-epoch together")
                if args.acknowledge and args.action != "resolve":
                    raise ValueError("--acknowledge only applies to resolve")
                snapshot = _operation_rpc(client, {"action": "snapshot", **target}) if numbers[0] is None else None
                if snapshot and snapshot.get("ok") is False:
                    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
                    return 1
                values["_operation"] = {"expectedRevision": snapshot["revision"] if snapshot else args.revision,
                                         "controlEpoch": snapshot["epoch"] if snapshot else args.epoch,
                                         "hostEpoch": snapshot["hostEpoch"] if snapshot else args.host_epoch}
                values["acknowledge"] = args.acknowledge
            value = _operation_rpc(client, values)
        else:
            values = {"action": args.action, "limit": args.limit, "offset":args.offset, "includeResult": args.include_result}
            if args.action == "create":
                values["title"] = args.title
            if args.task_id:
                values["taskId"] = args.task_id
            elif args.id:
                values["taskId" if args.action in ["pause", "resume", "complete"] else "id"] = args.id
            if args.action not in ["create", "list"] and not (args.id or args.task_id):
                raise ValueError("a task/operation id is required")
            value = _operation_rpc(client, values)
        print(json.dumps(value, ensure_ascii=False, indent=2 if args.json else None))
        # Queued/running acknowledges acceptance, never claims analysis succeeded.
        return 0 if value.get("ok") is not False else 1
    except (MCPTransportError, ValueError, KeyError) as exc:
        print(f"adh: {exc}", file=sys.stderr)
        return 1


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
        "status": _cmd_status,
        "tools": _cmd_tools,
        "mcp": _cmd_mcp,
        "call": _cmd_call,
        "run": _cmd_operations,
        "tasks": _cmd_operations,
        "control": _cmd_operations,
    }
    return commands[args.command](args)
