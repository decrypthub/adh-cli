# adh

[中文](README.md) | **English**

`adh` is the local connection and MCP gateway for AndroidDecryptHub. It stores the Host ADH Daemon address and bridges `POST /mcp` to stdio MCP for Cursor and Claude Desktop.

Runtime dependencies are the Python standard library only. Python 3.10 or newer is required.

```bash
pip install android-decrypt-hub
adh connect 127.0.0.1:8088
adh devices
```

This repository is the source of PyPI [android-decrypt-hub](https://pypi.org/project/android-decrypt-hub/) 0.1.1. The product repository is [AndroidDecryptHub](https://github.com/decrypthub/AndroidDecryptHub).

The Host ADH Daemon has no authentication. Use it only on a trusted LAN, and do not point an MCP client at the HTTP `/mcp` endpoint directly.

## Install

```bash
python -m pip install android-decrypt-hub
```

## Connect

Start the Host ADH Daemon first. Its current default HTTP port is `8088`. This CLI still defaults to `8760` when the port is omitted, matching the published 0.1.1 release, so pass the real port:

```bash
adh connect 127.0.0.1:8088
adh devices
```

Saved addresses live in `~/.config/adh/connections.json` (`ADH_CONFIG_PATH` overrides the path).

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

## License

[MIT](./LICENSE)
