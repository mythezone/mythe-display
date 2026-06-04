# Codex Agent 本机追踪方案

日期：2026-06-04

状态：原型

## 结论

可以追踪，但目前应按“本机只读状态适配器”处理，而不是假设 Codex 提供了稳定的 Agent 状态 API。

当前本机可用信号：

- Codex 进程：`codex app-server`、`app-server proxy`、VS Code 扩展内的 Codex app-server。
- Codex app-server socket：`~/.codex/app-server-control/*.sock`。
- Codex 会话索引：`~/.codex/session_index.jsonl`，只包含 `id`、`thread_name`、`updated_at` 这类元数据。

不应默认读取：

- `~/.codex/auth.json`：认证信息。
- `~/.codex/history.jsonl`：用户输入历史。
- archived session JSONL：可能包含完整会话正文和工具调用内容。
- app-server websocket/control 协议内部内容：当前没有在项目内确认稳定公开契约。

## 当前实现

新增脚本：

```bash
scripts/collect-codex-agents-snapshot.py --out public/runtime/codex-agents.json --pretty
```

默认输出：

```text
public/runtime/codex-agents.json
```

刷新周期：

```text
300000ms，也就是 5 分钟一次
```

该脚本会：

- 自动推断 Codex 主目录。
- 如果 kiosk 通过 `sudo` 运行，优先从 `SUDO_USER` 推断 `/home/<user>/.codex`，避免误读 `/root/.codex`。
- 读取 `session_index.jsonl` 的会话元数据。
- 读取本机 Codex 进程数量和类型。
- 输出符合 `PixelAgentSnapshot` 的 JSON。

## 隐私策略

默认不把线程标题显示到 `name` 或 `meta.threadName`，只显示：

```text
Codex Runtime
Codex 1
Codex 2
Codex 3
```

活动文案只显示状态和更新时间，例如：

```text
recent activity · 4m ago
idle · 6h ago
```

如果确实希望副屏显示 Codex 线程标题，可显式开启：

```bash
MYTHE_DISPLAY_CODEX_AGENT_SHOW_THREAD_NAMES=1 scripts/collect-codex-agents-snapshot.py --pretty
```

或在 kiosk/systemd 环境中设置：

```text
MYTHE_DISPLAY_CODEX_AGENT_SHOW_THREAD_NAMES=1
```

注意：线程标题可能包含项目名、任务名或敏感上下文。只有在副屏显示环境可信时才建议开启。

## 状态映射

当前状态是启发式判断：

- 本机存在 Codex 进程：增加 `Codex Runtime`，状态为 `working`。
- 最近 15 分钟更新且本机存在 Codex 进程：`working`。
- 最近 2 小时更新：`thinking`。
- 最近 24 小时更新：`idle`。
- 超过 24 小时：`offline`。

这不是 Codex 内部任务状态，只是基于本机元数据推断出的显示状态。

## 接入方式

Web kiosk 默认读取：

```text
/runtime/codex-agents.json
```

开发预览或采集失败时回退：

```text
public/kiosk-test/agents.mock.json
```

仍可通过 URL 参数覆盖：

```text
http://<server-ip>:23456/kiosk-test/?agents=/api/agents/pixel
```

## 后续改进

- 增加更稳定的 Codex app-server 只读状态接口，前提是确认协议稳定。
- 把 Codex Cloud 任务、VS Code extension host、CLI session 分开显示。
- 为每个会话关联 workspace 路径和 git 分支，但必须避免读取完整会话正文。
- 增加 `stale` 或 `waiting` 状态，减少把旧会话误判为离线。
