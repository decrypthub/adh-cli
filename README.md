# adh

**中文** | [English](README.en.md)

`adh` 是 AndroidDecryptHub 的本机连接与 MCP 网关。它保存 Host ADH Daemon 的地址，并把 `POST /mcp` 转成 Cursor / Claude Desktop 可用的 stdio MCP。

运行时只使用 Python 标准库，要求 Python 3.10 或更高版本。

```bash
pip install android-decrypt-hub
adh connect 127.0.0.1:8088
adh devices
```

源码在 [decrypthub/adh-cli](https://github.com/decrypthub/adh-cli)，PyPI 包名是 [android-decrypt-hub](https://pypi.org/project/android-decrypt-hub/)。产品仓库是 [AndroidDecryptHub](https://github.com/decrypthub/AndroidDecryptHub)。当前版本 **0.1.2**。

Host ADH Daemon 没有身份认证，只在可信局域网里使用，不要暴露到公网。不要把 HTTP `/mcp` 直接配进 MCP 客户端。

## 安装

```bash
python -m pip install -U android-decrypt-hub
```

也可以用 pipx：

```bash
pipx install android-decrypt-hub
pipx upgrade android-decrypt-hub
```

## 连接

先在电脑上启动 Host ADH Daemon，再保存它的地址。当前 Daemon 默认 HTTP 端口是 `8088`。这个 CLI 在省略端口时仍使用 `8760`，所以请带上实际端口：

```bash
adh connect 127.0.0.1:8088
adh connect --json
adh devices
adh devices --json
```

`connect` 会先请求 `/health`。在线时打印 `online`，并写入配置。Daemon 暂时离线但仍要保存地址时：

```bash
adh connect 127.0.0.1:8088 --force
```

连接写入 `~/.config/adh/connections.json`。可用 `ADH_CONFIG_PATH` 改这个文件的位置。查看或移除：

```bash
adh disconnect 127.0.0.1:8088
adh disconnect --all
```

只保存了一个地址时，后面的 `devices`、`call`、`mcp` 会自动用它。保存了多个地址时，给单次命令加上 `--endpoint`：

```bash
adh devices --endpoint http://127.0.0.1:8088
```

## MCP

Cursor / Claude Desktop 只配置这一次：

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

多个已保存地址时，在参数里指定本次使用的 Daemon：

```bash
adh mcp --endpoint http://127.0.0.1:8088
```

`adh mcp` 启动时会再探一次 `/health`，目标不在线就直接退出。日志写到 stderr，stdout 只留给逐行 JSON-RPC。

## 调用单个工具

```bash
adh call <tool_name>
adh call <tool_name> --arguments '{"limit":3}' --json
adh call <tool_name> --endpoint http://127.0.0.1:8088
```

`--arguments` 必须是一个 JSON 对象。

## 命令

| 命令 | 作用 |
| --- | --- |
| `adh connect [地址]` | 探测并保存 Host ADH Daemon。默认 `127.0.0.1:8760` |
| `adh disconnect [地址]` | 移除一个已保存地址；`--all` 清空 |
| `adh devices` | 列出已保存地址，并显示在线状态 |
| `adh mcp` | 把已保存 Daemon 的 `POST /mcp` 转成 stdio MCP |
| `adh call <工具名>` | 调用一个 Host MCP 工具 |
| `adh --version` | 打印版本 |

## 开发

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

## 发版

源码版本和 PyPI 版本一起更新。`pyproject.toml` 的 `version` 与 `src/adh/__init__.py` 的 `__version__` 必须相同。PyPI 不能覆盖已发布的版本，所以每次发布都要升版本号。

用户能看到的行为或文案有变化时，同时改 `README.md` 和 `README.en.md`。

| 变更 | 升法 |
| --- | --- |
| 文档、文案、小修 | `+0.0.1` |
| 新命令或可感知的行为 | `+0.1.0` |

```bash
python -m pytest
python -m build
python -m twine check dist/*
python -m twine upload --repository pypi dist/android_decrypt_hub-<version>*
```

上传凭证放在本机 `~/.config/pypi/token`，不要写进仓库。上传成功后，把同一个提交推到 `decrypthub/adh-cli`。

## 协议

[MIT](./LICENSE)
