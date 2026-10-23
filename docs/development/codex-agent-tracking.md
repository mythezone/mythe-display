# Codex Agent 本机追踪方案

日期：2026-06-04

状态：原型

更新：2026-10-23，接入原版 ChatGPT Pet 与官方账号周额度接口。

## 结论

Agent 活动继续使用本机只读元信息适配器。账号周额度独立通过官方 Codex app-server 读取，不从进程数量或会话活跃度推断。

当前本机可用信号：

- Codex 进程：`codex app-server`、`app-server proxy`、VS Code 扩展内的 Codex app-server。
- Codex app-server socket：`~/.codex/app-server-control/*.sock`。
- Codex 会话索引：`~/.codex/session_index.jsonl`，只包含 `id`、`thread_name`、`updated_at` 这类元数据。

不应默认读取：

- `~/.codex/auth.json`：认证信息。
- `~/.codex/history.jsonl`：用户输入历史。
- archived session JSONL：可能包含完整会话正文和工具调用内容。
- app-server websocket/control 协议内部内容：当前没有在项目内确认稳定公开契约。

## ChatGPT Pet 与周用量

Assistant 使用 ChatGPT Pets 中稳定 ID 为 `codex` 的原版素材，原图保存在主题资源内，不保存下载链接。使用原生九行动作及每行的实际帧数（6/8/8/4/5/8/6/6/6），避免播到透明占位帧；行位置按显示帧高计算，挥手、跳跃与失败短动作播放后回到待机。减少动态效果设置会暂停精灵动画。宠物展示动作与 Agent 元信息状态独立。

现有采集器每五分钟启动一次有 12 秒总期限的 `codex app-server --listen stdio://`，完成初始化后只调用 `account/read`（`refreshToken=false`）和 `account/rateLimits/read`。依据[官方契约](https://learn.chatgpt.com/docs/app-server)，优先取 `rateLimitsByLimitId.codex`，在 primary 或 secondary 中识别 `windowDurationMins=10080` 的七天窗口；`resetsAt` 为服务端 Unix 秒时间戳。没有模型请求、会话创建、额度重置或登录操作。

`CODEX_HOME` 与 `--codex-home` 保留现有覆盖能力。sudo 启动优先使用 `SUDO_USER`；systemd 以 root 启动且没有覆盖时，使用仓库文件所有者的 Codex 目录。账号查询子进程使用该目录所有者的 UID/GID 与用户环境，避免 root 刷新登录后改变凭据文件归属。采集器不解析认证文件，Codex 自行管理登录凭据。

`codex-agents.json` 新增可选 `usage`，只输出这些字段：

| 字段 | 含义 |
| --- | --- |
| available / status | 是否可用；ready、unavailable、not-signed-in 或 no-weekly-window |
| usedPercent / windowMinutes | 服务端七天窗口的已用百分比与 10080 分钟 |
| resetsAt | 服务端给出的下次重置时刻，Unix 秒 |
| updatedAt / planType | 查询时间与套餐类型 |

账号标识、邮箱、token、Cookie、余额和重置券信息不进入快照。未登录、短窗口、无周额度或请求失败时不伪造零用量。页面每秒重算倒计时；默认超过 15 分钟的数据视为过期，达到重置时刻后等待下一次真实数据更新，不在浏览器自行清零。

即使页面不显示 Agent 列表，也会读取快照供周用量展示。采集仍沿用已有进程与刷新周期，更新脚本后在下一周期生效，页面资源更新需刷新。检查：`python3 -m unittest discover -s tests -p test_codex_usage.py`、`node tests/test_chatgpt_pet.cjs`。

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
- 如果 kiosk 通过 `sudo` 运行，优先从 `SUDO_USER` 推断用户目录；root systemd 启动时回退到仓库所有者，避免误读 root 的 Codex 目录。
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
