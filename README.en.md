# adh

[中文](README.md) | **English**

`adh` is the local connection and MCP gateway for AndroidDecryptHub. It stores the Host ADH Daemon address and bridges `POST /mcp` to stdio MCP for Cursor and Claude Desktop.

Runtime dependencies are the Python standard library only. Python 3.10 or newer is required.

```bash
pip install android-decrypt-hub
adh connect 127.0.0.1:8088
adh devices
```

Source: [decrypthub/adh-cli](https://github.com/decrypthub/adh-cli). PyPI project: [android-decrypt-hub](https://pypi.org/project/android-decrypt-hub/). Product repository: [AndroidDecryptHub](https://github.com/decrypthub/AndroidDecryptHub). Current version: **0.1.2**.

The Host ADH Daemon has no authentication. Use it only on a trusted LAN, and do not point an MCP client at the HTTP `/mcp` endpoint directly.

## Install

```bash
python -m pip install -U android-decrypt-hub
```

## Connect

Start the Host ADH Daemon first. Its current default HTTP port is `8088`. This CLI still uses `8760` when the port is omitted, so pass the real port:

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
