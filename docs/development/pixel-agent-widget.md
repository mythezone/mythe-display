# 像素 Agent 组件规范草案

日期：2026-06-03

状态：草案

## 目标

`core.pixelAgents` 把服务器中的 Agent、任务或项目状态显示成像素角色。它不直接绑定 OpenClaw，而是定义一层标准状态模型，再由适配器把 OpenClaw、Codex、CI、队列任务等外部状态转换进来。

当前测试页已经实现一个静态原型：

- 页面：[public/kiosk-test/index.html](../../public/kiosk-test/index.html)
- Mock 数据：[public/kiosk-test/agents.mock.json](../../public/kiosk-test/agents.mock.json)
- 默认精灵：[public/themes/neon-dark/sprites/](../../public/themes/neon-dark/sprites)

## 数据模型

```ts
type PixelAgentStatus =
  | "idle"
  | "walking"
  | "working"
  | "thinking"
  | "building"
  | "reviewing"
  | "blocked"
  | "error"
  | "offline";

type PixelAgent = {
  id: string;
  name: string;
  project?: string;
  status: PixelAgentStatus;
  action?: PixelAgentStatus;
  activity?: string;
  progress?: number;
  health?: "ok" | "warn" | "bad" | "unknown";
  lastEvent?: string;
  updatedAt?: string;
  avatar?: string;
};

type PixelAgentSnapshot = {
  updatedAt: string;
  agents: PixelAgent[];
};
```

## JSON 示例

```json
{
  "updatedAt": "2026-06-03T00:00:00Z",
  "agents": [
    {
      "id": "planner",
      "name": "Planner",
      "project": "mythe-display",
      "status": "working",
      "activity": "planning widget bridge",
      "progress": 72
    }
  ]
}
```

## 状态语义

- `idle`：在线但没有正在执行的动作。
- `walking`：巡视、搬运、切换上下文或在像素办公室中移动。
- `working`：正在调用工具、执行任务、生成内容或处理队列。
- `thinking`：正在分析、规划或等待模型推理。
- `building`：正在生成代码、构建、打包或执行命令。
- `reviewing`：等待人工确认、代码审查或策略判断。
- `blocked`：被外部条件阻塞，例如凭据缺失、依赖失败、权限不足。
- `error`：任务执行失败或适配器报告异常。
- `offline`：Agent 或上游服务不可达。

## Widget 配置

```json
{
  "id": "openclaw-agents",
  "widget": "core.pixelAgents",
  "area": { "x": 6, "y": 3, "w": 8, "h": 3 },
  "config": {
    "source": "openclaw.compat",
    "mock": "public/kiosk-test/agents.mock.json",
    "refreshMs": 3000
  }
}
```

运行时第一版配置：

```ts
type PixelAgentsConfig = {
  source: string;
  refreshMs: number;
  maxAgents?: number;
  showProgress?: boolean;
  showProject?: boolean;
  mock?: string;
};
```

## OpenClaw 兼容适配器

OpenClaw 侧不要直接驱动 UI。推荐适配器输出 `PixelAgentSnapshot`：

```text
OpenClaw Gateway / plugin
  -> openclaw.compat adapter
    -> PixelAgentSnapshot JSON
      -> core.pixelAgents widget
```

建议映射：

```text
OpenClaw session active/tool_call/running -> working
OpenClaw model reasoning/planning        -> thinking
OpenClaw command/build/test running      -> building
OpenClaw pending approval/input needed    -> reviewing
OpenClaw waiting/complete                 -> idle
OpenClaw blocked by permission/config     -> blocked
OpenClaw failed/exception                 -> error
OpenClaw gateway unreachable              -> offline
```

## 插件化扩展

后续插件可以贡献：

- `dataProviders`：例如 `openclaw.compat`、`codex.sessions`、`github.actions`。
- `widgets`：替换展示方式，例如像素办公室、单个宠物、任务看板。
- `themes`：不同像素角色、办公室、背景、家具资源。

插件 manifest 示例：

```json
{
  "id": "vendor.openclaw-agent-bridge",
  "name": "OpenClaw Agent Bridge",
  "version": "0.1.0",
  "dataProviders": [
    {
      "id": "openclaw.compat",
      "entry": "./src/openclaw-provider.ts",
      "topics": ["agents.pixel"],
      "permissions": ["network.local"]
    }
  ],
  "themes": [
    {
      "id": "vendor.pixel-office",
      "entry": "./themes/pixel-office/theme.json"
    }
  ]
}
```

## 第三方像素资源接入

默认主题使用仓库自有 SVG 精灵，保证可以随项目直接分发。后续要接入第三方行走图或动作图，推荐流程：

1. 从 OpenGameArt、itch.io 等来源筛选 CC0 或明确允许商用/再分发的 sprite sheet。
2. 把资源放进主题包，例如 `public/themes/<theme-id>/sprites/agents/worker-walk.png`。
3. 在 `theme.json` 中映射到 `sprites.agent.walking`、`sprites.agent.building` 等状态。
4. 在主题 README 中记录来源链接、作者、许可证和是否修改过。

参考资源入口：

- [OpenGameArt CC0 Walk Cycles](https://opengameart.org/content/cc0-walk-cycles)
- [OpenGameArt Character Walking](https://opengameart.org/content/character-walking)
- [itch.io CC0 Pixel Art Sprites](https://itch.io/game-assets/free/tag-cc0/tag-pixel-art/tag-sprites)

## 第一版实现范围

已完成：

- 测试页读取 `agents.mock.json`。
- 支持 `?agents=<url>` 指向任意同结构 JSON。
- 每 3 秒轮询一次，可用 `?agentsRefreshMs=1000` 调整。
- 状态颜色跟随主题 token。
- Agent 精灵从主题资源包读取。
- 默认主题内置更大的自有像素 SVG 精灵，覆盖 `idle`、`walking`、`working`、`thinking`、`building`、`reviewing`、`blocked`、`error`、`offline`。

未完成：

- 真实 OpenClaw Gateway 数据读取。
- 角色行走、座位、办公室地图。
- 外部像素资产包导入和许可证校验。
