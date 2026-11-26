# adh

**中文** | [English](README.en.md)

`adh` 是 AndroidDecryptHub 的本机连接与 MCP 网关。它保存 Host ADH Daemon 的地址，并把 `POST /mcp` 转成 Cursor / Claude Desktop 可用的 stdio MCP。

运行时只使用 Python 标准库，要求 Python 3.10 或更高版本。

```bash
pip install android-decrypt-hub
adh connect 127.0.0.1:8088
adh devices
```

源码在 [decrypthub/adh-cli](https://github.com/decrypthub/adh-cli)，PyPI 包名是 [android-decrypt-hub](https://pypi.org/project/android-decrypt-hub/)。产品仓库是 [AndroidDecryptHub](https://github.com/decrypthub/AndroidDecryptHub)。当前版本 **0.2.0**。

Host ADH Daemon 的完整连接认证与 TLS 尚未实现，P1 的 operator 凭据只协调人类控制权。只在可信局域网里使用，不要暴露到公网。不要把 HTTP `/mcp` 直接配进 MCP 客户端。

## P1 持久任务与接管（源码待发布）

本分支与 AndroidDecryptHub 的 P1 Host 配套，尚未发布到 PyPI；不会升级或重启已有 Host。新 Host 的写入要求 `_operation` 中的 expectedRevision/controlEpoch/hostEpoch，旧无版本写调用会返回 CONTROL_REQUIRED。普通读取与 stdio 透传仍兼容；AI 需要明确观察版本后提交。统一执行层与状态定义见产品仓库 `docs/P1_OPERATIONS.md`。

```bash
adh tasks create --title "请求分析" --endpoint 127.0.0.1:18088 --json
adh run TOOL --arguments JSON --task-id TASK_ID --idempotency-key INTENT_ID --endpoint 127.0.0.1:18088 --json
adh tasks get OPERATION_ID --include-result --endpoint 127.0.0.1:18088 --json
adh tasks cancel OPERATION_ID --endpoint 127.0.0.1:18088
adh tasks cancel --task-id TASK_ID --endpoint 127.0.0.1:18088
adh tasks list --limit 50 --offset 0 --endpoint 127.0.0.1:18088
adh control snapshot --session SESSION --endpoint 127.0.0.1:18088
```

`run` 观察一次状态并异步提交，返回 queued/running 只代表已接受；通过 `tasks get` 检查真实结果。AI 已有旧版本时用 `adh call TOOL --arguments JSON --operation METADATA_JSON` 保留原版本；发生冲突必须重新观察并规划，CLI 不替换版本重试。同一意图保持同一个 idempotency key。

人类在当前终端显式配置 ADH_OPERATOR_TOKEN 后，用 `adh control takeover|release --session SESSION --operator` 接管/释放；也可加 `--revision N --epoch N --host-epoch N` 使用已观察版本。完整 action 包括 snapshot/takeover/release/resolve/hold。`resolve --acknowledge --operator` 仅在检查未知副作用后使用，不代表停止或回滚目标。

默认 CLI 和 stdio AI 代理忽略继承的 operator 密钥；只有显式 `--operator` 才发送。任务可 pause/resume/complete；cancel 单个 operation 不取消整项 task。派发后取消仍可能执行成功，反馈 cancel_requested 或 succeeded + cancelRequested；派发后超时/断连为 unknown，保留晚到证据，不自动重放。HTTP 传输超时本身不能证明 Host 或目标已停止，使用持久 id/key 查询；不要直接重发旧写入。

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

先在电脑上启动 Host ADH Daemon，再保存它的地址。Daemon 和 CLI 的默认 HTTP 端口均为 `8088`。已保存或显式指定的其他端口继续有效：

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
| `adh connect [地址]` | 探测并保存 Host ADH Daemon。默认 `127.0.0.1:8088` |
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

## DecryptHub 桌面插件

在 DecryptHub 的「插件」入口安装官方网关，配置设备服务地址后即可启用 MCP。安装包只包含电脑端 CLI 和标准库启动器，要求 Python 3.10+；设备插件及 Host 服务仍按各自项目说明准备。

维护者构建组件：`python scripts/build_component.py`。输出 `dist/adh-<version>-any.zip`，包含 API 1 清单、源代码版本及逐文件 SHA-256，可独立通过 GitHub Releases 更新。`decrypthub-v<version>` 标签用于桌面组件分发，与 PyPI 发版独立。

## 桌面 Agent 与状态查询

```bash
adh status --json --endpoint http://127.0.0.1:8088
adh tools --json --endpoint http://127.0.0.1:8088
```

`status --json` 返回带 `schemaVersion: 1` 和 `checkedAt` 的只读快照，分别列出 `connections` 的服务在线事实及 `targets` 的应用/PID/目标标识；离线地址不会冒充在线目标。状态查询不保存地址、不注入、不启停应用，也不自动升级 CLI。`tools --json` 返回当前目标的真实 MCP 工具说明和参数 schema。先查询状态，再选择本次返回的唯一目标，最后通过现有 `call` 或持久 MCP 连接执行分析；多个候选必须让用户选择。

`configuration.source` 为 `explicit` 或 `saved`。显式 `--endpoint` 只检查传入地址，忽略已保存的地址。 桌面端可从同一个本机 stdio MCP 子进程收到有限的已验证使用回报。它不是工具输出，不改变权限、目标选择或调用逻辑；无相应回报时不能认定 AI 已使用。

ADH 省略端口时默认连接 8088；`devices --endpoint` 支持临时探测，`call` 收到 MCP 错误或 `isError` 时返回非零退出码。

## 开发验证

在源码目录运行 `python -m pytest`。测试配置优先导入本仓 `src`，避免误测电脑上已安装的旧版 `adh`。
发布前另运行 `python -m build` 与 `python -m twine check dist/*`，并在隔离环境验证构建后的 wheel。
