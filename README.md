# adh

**中文** | [English](README.en.md)

`adh` 是 AndroidDecryptHub 的本机连接与 MCP 网关。它保存 Host ADH Daemon 的地址，并把 `POST /mcp` 转成 Cursor / Claude Desktop 可用的 stdio MCP。

运行时只使用 Python 标准库，要求 Python 3.10 或更高版本。

```bash
pip install android-decrypt-hub
adh connect 127.0.0.1:8088
adh devices
```

本仓库对应 PyPI 上已发布的 [android-decrypt-hub](https://pypi.org/project/android-decrypt-hub/) 0.1.1。产品仓库是 [AndroidDecryptHub](https://github.com/decrypthub/AndroidDecryptHub)。

Host ADH Daemon 没有身份认证，只在可信局域网里使用，不要暴露到公网。不要把 HTTP `/mcp` 直接配进 MCP 客户端。

## 安装

```bash
python -m pip install android-decrypt-hub
```

也可以用 pipx：

```bash
pipx install android-decrypt-hub
```

## 连接

先在电脑上启动 Host ADH Daemon，再保存它的地址。当前 Daemon 默认 HTTP 端口是 `8088`。这个 CLI 在未写端口时仍按已发布的 0.1.1 使用 `8760`，所以请带上实际端口：

```bash
adh connect 127.0.0.1:8088
adh devices
```

连接写入 `~/.config/adh/connections.json`（可用 `ADH_CONFIG_PATH` 改位置）。查看或移除：

```bash
adh devices --json
adh disconnect 127.0.0.1:8088
adh disconnect --all
```

`connect` 会先请求 `/health`。Daemon 暂时离线但仍要保存地址时加 `--force`。

## MCP

Cursor / Claude Desktop：

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

只保存了一个地址时，`adh mcp` 会用它。多个地址时加上 `--endpoint`：

```bash
adh mcp --endpoint http://127.0.0.1:8088
```

日志写到 stderr，stdout 只留给逐行 JSON-RPC。

## 调用单个工具

```bash
adh call <tool_name> --arguments '{"limit":3}' --json
```

## 开发

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

## 协议

[MIT](./LICENSE)
