# Mythe Display 接口规范草案

日期：2026-06-03

状态：草案

## 参考项目

本规范借鉴以下成熟项目的设计方式：

- MagicMirror²：模块化屏幕和模块生命周期。
- Grafana：面板 manifest、数据输入、尺寸传入和插件生态。
- Home Assistant Lovelace：通过配置组合卡片、主题和 dashboard。
- VS Code Extensions：插件 manifest、贡献点和版本兼容约束。
- ComfyUI custom nodes：通过 Git 仓库扩展功能并被宿主扫描加载。

目标不是复制某个项目，而是形成适合 3840x1100 长条副屏的 Web kiosk 组件系统。

## 总体模型

```text
Display
  -> Layout
    -> Zones
      -> Widget instances
        -> Widget definition
          -> Data subscriptions
          -> Theme tokens
          -> Actions
Plugin package
  -> widgets
  -> data providers
  -> themes
  -> theme resource packs
  -> layouts
```

## 配置文件类型

建议长期保留这些配置边界：

```text
config/
  display.json
  layout.json
  theme.json
  plugins.json
```

运行时读取后合并为：

```ts
type RuntimeConfig = {
  display: DisplayConfig;
  layout: LayoutConfig;
  theme: ThemeConfig;
  plugins: PluginConfig[];
  runtime?: RuntimeControlConfig;
};
```

## DisplayConfig

描述物理屏幕和输出目标。

```ts
type DisplayConfig = {
  id: string;
  name: string;
  width: number;
  height: number;
  density: number;
  rotation: 0 | 90 | 180 | 270;
  safeArea: {
    top: number;
    right: number;
    bottom: number;
    left: number;
  };
  output?: {
    connector?: string;
    mode?: string;
    kioskUrl?: string;
  };
};
```

当前真实屏幕建议配置：

```json
{
  "id": "mythenas-longbar",
  "name": "MytheNAS HDMI Long Bar",
  "width": 3840,
  "height": 1100,
  "density": 1,
  "rotation": 0,
  "safeArea": { "top": 0, "right": 0, "bottom": 0, "left": 0 },
  "output": {
    "connector": "card0-HDMI-A-2",
    "mode": "3840x1100",
    "kioskUrl": "http://127.0.0.1:23456"
  }
}
```

## LayoutConfig

布局采用网格优先，允许绝对定位作为高级能力。

```ts
type LayoutConfig = {
  id: string;
  displayId: string;
  grid: {
    columns: number;
    rows: number;
    gap: number;
    padding: number;
  };
  zones?: ZoneConfig[];
  widgets: WidgetInstanceConfig[];
};
```

Widget 实例：

```ts
type WidgetInstanceConfig = {
  id: string;
  widget: string;
  area: {
    x: number;
    y: number;
    w: number;
    h: number;
  };
  zIndex?: number;
  visible?: boolean;
  config: Record<string, unknown>;
};
```

设计约束：

- `area` 坐标以 grid cell 为单位。
- Widget 不能假设固定像素尺寸，应通过运行时 `size` 获得实际宽高。
- 数字变化不能导致外层尺寸跳动。
- 布局编辑器必须能序列化为同一份配置。

## Widget Manifest

Widget 是最小可渲染单元。

```json
{
  "id": "core.cpu",
  "name": "CPU",
  "version": "0.1.0",
  "description": "CPU 使用率、温度和频率组件。",
  "entry": "./src/CpuWidget.tsx",
  "schema": "./src/cpu.schema.json",
  "preview": "./src/cpu.preview.json",
  "category": "system",
  "data": {
    "required": ["system.cpu"],
    "optional": ["system.temperatures"],
    "refreshMs": 1000
  },
  "layout": {
    "minWidth": 180,
    "minHeight": 120,
    "preferredAspectRatios": ["2:1", "3:2"]
  },
  "theme": {
    "tokens": ["surface.panel", "text.primary", "accent.primary", "metric.good"]
  }
}
```

## Widget 运行时接口

```ts
type WidgetStatus = "loading" | "ready" | "stale" | "error" | "unavailable";

type WidgetRuntimeProps<TConfig, TData> = {
  instanceId: string;
  widgetId: string;
  config: TConfig;
  data: TData;
  status: WidgetStatus;
  size: {
    width: number;
    height: number;
    density: number;
  };
  theme: ThemeRuntime;
  locale: string;
  now: number;
  actions: WidgetActions;
};

type WidgetActions = {
  emit(event: string, payload?: unknown): void;
  requestRefresh(topic?: string): void;
  openPanel(panelId: string, payload?: unknown): void;
};
```

生命周期：

```ts
type WidgetModule = {
  manifest: WidgetManifest;
  render(props: WidgetRuntimeProps<unknown, unknown>): React.ReactNode;
  onMount?(context: WidgetContext): void | (() => void);
  onConfigChange?(nextConfig: unknown): void;
};
```

## ThemeResourcePack

主题资源包保存可还原的视觉资产。运行时读取 `theme.json` 后，将 token 输出为 CSS 变量，并把背景、精灵、图标等资源传给 widget。

```ts
type ThemeResourcePack = {
  id: string;
  name: string;
  version: string;
  description?: string;
  tokens: Record<string, string>;
  wallpaper?: {
    fallback: string;
    layers?: WallpaperLayer[];
    effects?: string[];
  };
  sprites?: {
    agent?: Record<string, string>;
  };
  hero?: {
    logo?: string;
    background?: {
      engine?: "canvas-triangle-mesh" | string;
      pointCount?: "auto" | number;
      motion?: "slow" | "normal" | "fast";
    };
  };
  mascot?: {
    assistant?: string;
    rive?: {
      enabled: boolean;
      src?: string;
      runtime?: string;
      artboard?: string;
      stateMachine?: string;
      stateMachines?: string | string[];
    };
    codexPet?: {
      enabled: boolean;
      manifest?: string;
      spritesheet?: string;
      columns?: number;
      rows?: number;
      frameWidth?: number;
      frameHeight?: number;
      frames?: number;
      fps?: number;
      scale?: number;
      actionRows?: Record<string, number>;
    };
    actions?: {
      action: string;
      quote?: string;
    }[];
  };
};

type WallpaperLayer = {
  id: string;
  src: string;
  opacity?: number;
  blendMode?: string;
  animation?: "none" | "drift-slow" | "drift-medium" | "pulse";
};
```

## PixelAgentSnapshot

像素 Agent 组件使用统一状态快照，不直接绑定 OpenClaw。

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

## WeatherSnapshot

Clock 天气区域使用 Open-Meteo 快照，默认深圳坐标和 `Asia/Shanghai` 时区。

```ts
type WeatherSnapshot = {
  updatedAt: string;
  refreshMs: number;
  available?: boolean;
  source: "open-meteo" | "mock" | string;
  sourceUrl?: string;
  location: {
    name: string;
    latitude: number;
    longitude: number;
    timezone: string;
  };
  current: {
    observedAt?: string;
    temperatureC: number | null;
    apparentTemperatureC?: number | null;
    humidityPercent?: number | null;
    windSpeedKmh?: number | null;
    weatherCode?: number | null;
    condition: string;
  };
  daily: {
    date?: string;
    temperatureMaxC?: number | null;
    temperatureMinC?: number | null;
    precipitationProbabilityPercent?: number | null;
    weatherCode?: number | null;
    condition?: string;
  };
};
```

## DiskSnapshot

磁盘矩阵组件使用低频快照，默认 12 小时刷新一次。

```ts
type DiskType = "hdd" | "nvme" | "ssd" | "usb";
type DiskStatus = "ok" | "warn" | "bad" | "unknown";

type DiskSnapshot = {
  updatedAt: string;
  refreshMs: number;
  summary: {
    totalBytes: number;
    usedBytes: number;
    diskCount: number;
  };
  disks: {
    id: string;
    name: string;
    type: DiskType;
    role?: string;
    mount?: string | null;
    model?: string;
    usedPercent: number;
    totalBytes: number;
    usedBytes: number;
    status: DiskStatus;
  }[];
};
```

## TelemetryTrendSnapshot

CPU、Memory、Network 合并趋势组件使用同一份快照。

```ts
type TelemetryTrendSnapshot = {
  updatedAt: string;
  refreshMs: number;
  series: {
    cpu: number[];
    memory: number[];
    network: number[];
  };
  metrics: {
    cpuPercent: number;
    memoryPercent: number;
    networkPercent?: number;
    networkRx: string;
    networkTx?: string;
  };
};
```

## DockerSnapshot

Docker 竖栏组件参考 lazydocker 的信息结构，但只做只读监控。

```ts
type DockerSnapshot = {
  updatedAt: string;
  refreshMs: number;
  available?: boolean;
  error?: string;
  summary: {
    running: number;
    stopped: number;
    images: number;
    volumes: number;
    cpuPercent: number;
    memoryPercent: number;
    networkRx?: string;
    networkTx?: string;
  };
  containers: {
    name: string;
    state: "running" | "exited" | "paused" | "restarting";
    cpuPercent: number;
    memory: string;
  }[];
};
```

## Data Provider 接口

Data Provider 负责采集系统数据、网络 API 或插件数据。

```ts
type DataProviderManifest = {
  id: string;
  name: string;
  version: string;
  topics: string[];
  permissions: Permission[];
  refreshMs?: number;
};

type DataProvider = {
  manifest: DataProviderManifest;
  read(topic: string, context: DataContext): Promise<DataSnapshot>;
  subscribe?(
    topic: string,
    context: DataContext,
    emit: (snapshot: DataSnapshot) => void
  ): () => void;
};

type DataSnapshot = {
  topic: string;
  ts: number;
  staleAfterMs: number;
  value: unknown;
  error?: {
    code: string;
    message: string;
  };
};
```

内置 topic 命名建议：

- `system.cpu`
- `system.memory`
- `system.disk`
- `system.disks`
- `system.network`
- `system.temperatures`
- `system.gpu`
- `system.processes`
- `docker.summary`
- `docker.containers`
- `telemetry.trend`
- `agents.pixel`
- `time.now`
- `app.status`

## 事件和动作

Widget 默认只展示信息，但需要保留交互扩展能力：

- `widget.clicked`
- `widget.focused`
- `data.refresh.requested`
- `layout.panel.opened`
- `plugin.error`
- `display.route.changed`

事件载荷必须是 JSON serializable。

## RuntimeControlConfig

运行时控制负责切换显示内容、刷新主题或切换布局。当前测试实现先通过 Chromium DevTools 切换页面 URL。

```ts
type RuntimeControlConfig = {
  remoteDebugging?: {
    host: "127.0.0.1";
    port: number;
  };
  routes?: {
    id: string;
    name: string;
    url: string;
  }[];
};
```

长期正式 API：

```ts
type DisplayRouteRequest = {
  url: string;
  reason?: string;
  keepHistory?: boolean;
};
```

## 版本和兼容

- 所有 manifest 使用 semver。
- 插件声明 `mytheDisplay` 兼容范围。
- Widget manifest 的破坏性变化必须提升 major 版本。
- 布局引用 widget 时可以锁定版本，也可以使用兼容范围。

## 校验策略

第一版应先做这些校验：

- manifest JSON schema 校验。
- widget `id` 全局唯一。
- layout 引用的 widget 必须存在。
- widget 实例 config 必须通过对应 schema。
- theme 必须提供所有 required token，缺失时走 fallback。

## 错误降级

每个 widget 必须实现：

- loading：正在加载数据。
- stale：数据过期但仍可显示旧值。
- error：数据源错误。
- unavailable：传感器或权限不可用。

宿主负责保证单个 widget 异常不会导致整个界面崩溃。
