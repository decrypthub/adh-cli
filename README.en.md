# adh

[中文](README.md) | **English**

`adh` is the local connection and MCP gateway for AndroidDecryptHub. It stores the Host ADH Daemon address and bridges `POST /mcp` to stdio MCP for Cursor and Claude Desktop.

Runtime dependencies are the Python standard library only. Python 3.10 or newer is required.

```bash
pip install android-decrypt-hub
adh connect 127.0.0.1:8088
adh devices
```

Source: [decrypthub/adh-cli](https://github.com/decrypthub/adh-cli). PyPI project: [android-decrypt-hub](https://pypi.org/project/android-decrypt-hub/). Product repository: [AndroidDecryptHub](https://github.com/decrypthub/AndroidDecryptHub). Current version: **0.2.0**.

Full connection authentication and TLS are not implemented. P1 operator credentials coordinate human control only. Use the Host on a trusted LAN, and do not point an MCP client at the HTTP `/mcp` endpoint directly.

## P1 durable operations and control (unreleased source)

This branch pairs with the P1 AndroidDecryptHub Host. It has not been published to PyPI and does not upgrade or restart an existing Host. P1 writes require expectedRevision/controlEpoch/hostEpoch in `_operation`; unversioned writes return CONTROL_REQUIRED. Ordinary reads and stdio passthrough remain compatible. See the product repository's `docs/P1_OPERATIONS.md` for the shared execution contract.

```bash
adh tasks create --title "Request analysis" --endpoint 127.0.0.1:18088 --json
adh run TOOL --arguments JSON --task-id TASK_ID --idempotency-key INTENT_ID --endpoint 127.0.0.1:18088 --json
adh tasks get OPERATION_ID --include-result --endpoint 127.0.0.1:18088 --json
adh tasks cancel OPERATION_ID --endpoint 127.0.0.1:18088
adh tasks cancel --task-id TASK_ID --endpoint 127.0.0.1:18088
adh tasks list --limit 50 --offset 0 --endpoint 127.0.0.1:18088
adh control snapshot --session SESSION --endpoint 127.0.0.1:18088
```

`run` observes once and submits asynchronously. Queued/running means accepted; query `tasks get` for the outcome. Use `adh call TOOL --arguments JSON --operation METADATA_JSON` to preserve previously observed versions. On a conflict, observe and re-plan; the CLI never silently replaces stale versions or retries. Keep the same idempotency key for the same intent.

An operator explicitly sets ADH_OPERATOR_TOKEN in their terminal and uses `adh control takeover|release --session SESSION --operator`. Supply all of `--revision N --epoch N --host-epoch N` to use an existing observation. Actions are snapshot/takeover/release/resolve/hold. Use `resolve --acknowledge --operator` only after checking unknown effects; it does not stop or roll back the target.

CLI and stdio AI defaults ignore an inherited operator key; only explicit `--operator` sends it. Tasks support pause/resume/complete; cancelling one operation leaves its named task active. In-flight cancellation can still finish successfully: cancel_requested or succeeded with cancelRequested preserves that fact. Post-dispatch timeout/disconnect is unknown, with late evidence and no automatic replay. An HTTP timeout does not prove Host/target execution stopped; query the durable id/key before taking further action.

## Install

```bash
python -m pip install -U android-decrypt-hub
```

## Connect

Start the Host ADH Daemon first. Its current default HTTP port is `8088`. This CLI still uses `8088` when the port is omitted, so pass the real port:

```bash
adh connect 127.0.0.1:8088
adh devices
adh devices --json
```

`connect` probes `/health` before saving. Use `--force` to save an address that is offline. Saved addresses live in `~/.config/adh/connections.json` (`ADH_CONFIG_PATH` overrides the path).

```bash
adh disconnect 127.0.0.1:8088
adh disconnect --all
```

When more than one address is saved, pass `--endpoint` for a single command.

## MCP

```json
{
  "mcpServers": {
    "adh": {
      "command": "adh",
      "args": ["mcp"]
    }
  }
}
```

Logs go to stderr. stdout is reserved for line-delimited JSON-RPC.

## Call one tool

```bash
adh call <tool_name> --arguments '{"limit":3}' --json
```

`--arguments` must be a JSON object.

## Release

Update the source version and the PyPI release together. `version` in `pyproject.toml` and `__version__` in `src/adh/__init__.py` must match. PyPI rejects an upload that reuses a version, so every release increments the version.

Update `README.md` and `README.en.md` when user-visible behavior or wording changes.

| Change | Bump |
| --- | --- |
| Docs, wording, small fixes | `+0.0.1` |
| A new command or user-visible behavior | `+0.1.0` |

```bash
python -m pytest
python -m build
python -m twine check dist/*
python -m twine upload --repository pypi dist/android_decrypt_hub-<version>*
```

Keep the upload token in `~/.config/pypi/token` on the release machine. Do not commit it. Push the same commit to `decrypthub/adh-cli` after the upload succeeds.

## License

[MIT](./LICENSE)

## DecryptHub desktop plugin

Install the official gateway from DecryptHub → Plugins, then configure your device service address. The component contains the PC CLI and a standard-library launcher and requires Python 3.10+. Device plugins and Host services are deployed separately.

Maintainers: run `python scripts/build_component.py` to build `dist/adh-<version>-any.zip`, including an API 1 manifest, source revision and per-file SHA-256 checksums. GitHub Releases tags `decrypthub-v<version>` distribute desktop components independently of PyPI releases.

## Desktop Agent status and discovery

```bash
adh status --json --endpoint http://127.0.0.1:8088
adh tools --json --endpoint http://127.0.0.1:8088
```

`status --json` returns a read-only snapshot with `schemaVersion: 1`, `checkedAt`, service observations in `connections`, and current app/PID identifiers in `targets`. An offline address is never reported as an online target. Status does not save connections, inject, restart apps, or upgrade the CLI. `tools --json` reads the real MCP tool descriptions and argument schemas. Refresh status, select a unique returned target, then use `call` or the persistent MCP connection; ask the user when multiple targets match.

`configuration.source` is `explicit` or `saved`. An explicit `--endpoint` checks only the given addresses and ignores saved ones. The desktop can receive limited verified usage receipts from the same local stdio MCP subprocess. They are not tool output and do not change permissions, target selection, or call logic; without such a receipt, AI usage cannot be assumed.

ADH defaults to port 8088. `devices --endpoint` inspects a temporary address. `call` exits nonzero for an MCP error or `isError` result.

## Development checks

Run `python -m pytest` from the source checkout. The test configuration imports this repository's `src` first, avoiding an older globally installed `adh`.
Before publishing, also run `python -m build` and `python -m twine check dist/*`, then verify the built wheel in an isolated environment.
