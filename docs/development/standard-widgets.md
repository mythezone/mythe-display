# 标准组件草案

日期：2026-06-03

状态：草案

## 目标

本文件记录 Mythe Display 第一批标准组件的显示目标、数据契约和刷新策略。测试页已经实现这些组件的静态 Web 原型，正式运行时后续应把它们拆成独立组件包。

## core.clockWeather

用途：在单个标准网格块中显示固定东八区时间、日期和深圳当天基础天气。

显示规则：

- 时间必须使用 `Asia/Shanghai`，不能依赖服务器本地时区。
- 时间字号使用大号数字，适合远距离快速读取。
- 日期、时区和天气信息应围绕时间重排，避免只显示一行小字。
- 天气默认展示城市、当前温度、天气状态、今日最高/最低、体感、湿度、风速和更新时间。
- 天气数据默认 30 分钟刷新一次。

数据契约：

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
    timezone: "Asia/Shanghai" | string;
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

默认运行时数据：

```text
public/runtime/weather-shenzhen.json
```

当前 mock 仅用于开发预览兜底：

```text
public/kiosk-test/weather.mock.json
```

真实采集脚本：

```bash
scripts/collect-weather-snapshot.py --out public/runtime/weather-shenzhen.json --pretty
```

## core.diskMatrix

用途：紧凑展示 NAS 多磁盘容量状态，适合 10 到 24 个磁盘的长条屏布局。

显示规则：

- 每个磁盘用一个小图标表达类型和容量使用率。
- 图标外圈使用 `conic-gradient` 表示 `usedPercent`。
- 图标内部形状区分 `hdd`、`nvme`、`ssd`、`usb`。
- `metric.good/warn/bad` 表达正常、接近满、严重占满。
- 默认占用一个标准网格块，使用更紧凑的单列密度展示 16 盘位 NAS。
- 默认刷新周期是 `43200000ms`，也就是 12 小时一次。

数据契约：

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
  disks: DiskItem[];
};

type DiskItem = {
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
};
```

默认运行时数据：

```text
public/runtime/disks.json
```

当前 mock 仅用于开发预览兜底：

```text
public/kiosk-test/disks.mock.json
```

真实采集脚本：

```bash
scripts/collect-disk-snapshot.py --out public/runtime/disks.json --pretty
```

预览真实数据：

```text
http://<server-ip>:23456/kiosk-test/?disks=/runtime/disks.json
```

## core.dockerTui

用途：用一个竖向区块展示 Docker 状态，视觉上参考 lazydocker 的 TUI 信息密度。

参考项目：[jesseduffield/lazydocker](https://github.com/jesseduffield/lazydocker)。该项目 README 描述它是用 Go 和 gocui 写成的 Docker / docker-compose 终端 UI。

显示规则：

- 占用一整条竖栏，适合在长条屏右侧显示更多容器。
- 上半部显示 running、stopped、CPU、memory。
- 下半部用紧凑行高显示前 16 个容器的状态和资源占用。
- 默认刷新周期建议 `600000ms`，也就是 10 分钟一次。
- Docker CLI 不可用或权限不足时，组件显示 unavailable 状态，不回退成假真实数据。

数据契约：

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

默认运行时数据：

```text
public/runtime/docker.json
```

真实采集脚本：

```bash
scripts/collect-docker-snapshot.py --out public/runtime/docker.json --pretty
```

当前 mock 仅用于开发预览兜底：

```text
public/kiosk-test/docker.mock.json
```

## core.telemetryTrend

用途：把 CPU、Memory、GPU、Network 四个常用指标合并为一个趋势组件。

显示规则：

- 默认占用一个标准网格块，不再横跨两格。
- 一个 canvas 折线图显示四条曲线。
- 必须显示颜色图例：CPU 使用 `accent.primary`，Memory 使用 `accent.secondary`，GPU 使用 `metric.warn`，Network 使用 `metric.good`。
- 必须显示基础坐标轴：纵轴 `0/50/100`，横轴 `history/now`。
- 底部保留当前数值，避免只看图难以读数。
- 正式运行时默认读取 `/proc`、`nvidia-smi` 或 sysfs 采集快照，每 10 分钟刷新一次。
- GPU 优先使用 `nvidia-smi`，其次使用 `/sys/class/drm/card*/device/gpu_busy_percent`；不可用时显示 unavailable。
- 同一个快照提供 Health 组件需要的 uptime、load 和温度传感器摘要。
- mock 只作为开发预览兜底；测试页不再用随机数伪造趋势。

数据契约：

```ts
type TelemetryTrendSnapshot = {
  updatedAt: string;
  refreshMs: number;
  series: {
    cpu: number[];
    memory: number[];
    gpu: number[];
    network: number[];
  };
  metrics: {
    cpuPercent: number;
    memoryPercent: number;
    gpuAvailable: boolean;
    gpuPercent?: number | null;
    gpuName?: string;
    gpuTemperatureC?: number | null;
    gpuMemoryUsedMiB?: number | null;
    gpuMemoryTotalMiB?: number | null;
    gpuMemoryPercent?: number | null;
    networkPercent?: number;
    networkRx: string;
    networkTx?: string;
  };
  health?: {
    uptimeSeconds: number;
    uptime: string;
    load: {
      one: number;
      five: number;
      fifteen: number;
    };
    temperatures: {
      label: string;
      celsius: number;
    }[];
    maxTemperatureC?: number;
    maxTemperatureLabel?: string;
  };
};
```

默认运行时数据：

```text
public/runtime/telemetry.json
```

真实采集脚本：

```bash
scripts/collect-telemetry-snapshot.py --out public/runtime/telemetry.json --state public/runtime/telemetry-state.json --pretty
```

当前 mock 仅用于开发预览兜底：

```text
public/kiosk-test/telemetry.mock.json
```

## core.systemHealth

用途：在一个标准网格块中展示系统健康摘要，适合 NAS 常驻副屏快速判断温度、负载、GPU 和 uptime。

显示规则：

- 默认占用一个标准网格块，放在 Storage 缩减后腾出的单格位置。
- 读取 `core.telemetryTrend` 同一个 `/runtime/telemetry.json` 快照，不新增采集频率。
- 顶部展示最高温度、GPU 当前负载、1 分钟 load 和 uptime。
- 下方展示最热的前几个温度传感器。
- 温度颜色遵循 `metric.good/warn/bad`。
- GPU 或温度传感器不可用时必须显示 unavailable/no sensor，不使用 mock 冒充真实数据。

数据契约：

```ts
type SystemHealthSnapshot = Pick<TelemetryTrendSnapshot, "updatedAt" | "refreshMs" | "health"> & {
  metrics: Pick<
    TelemetryTrendSnapshot["metrics"],
    "gpuAvailable" | "gpuPercent" | "gpuName" | "gpuTemperatureC" | "gpuMemoryPercent"
  >;
};
```

## core.systemHero

用途：展示设备身份、运行状态和主题核心视觉。

当前实现：

- 主题资源包提供 `hero.logo`。
- 测试页对图标叠加 CSS 发光和环形动画。
- Hero 背景使用本地 Canvas 三角网格动画：随机点缓慢运动，近邻点连线并填充半透明三角面。
- 默认不依赖 CDN 或 WebGL，适合 NAS 开机后无桌面 kiosk 自动启动。

主题资源：

```text
public/themes/neon-dark/hero/mythenas-core.png
```

注意：生成式图标不负责显示文字，标题文字仍由 HTML/CSS 渲染，避免图片中文字不可控或缩放后发虚。

## core.mascotAssistant

用途：在空出的标准网格块中展示一位主题化看板娘，提供轻量状态陪伴和随机格言。

显示规则：

- 默认占用一个标准网格块。
- 主题资源包提供透明角色图：`mascot.assistant`。
- 运行时通过 CSS class 切换 PNG fallback 动作，不要求主题包提供多张动作图。
- 如果主题资源包提供 `mascot.rive.enabled=true` 和本地 `.riv` 文件，运行时优先使用 Rive canvas 骨架动画。
- 如果主题资源包提供 `mascot.codexPet.enabled=true` 和 `pet.json`，运行时使用 Codex/Petdex sprite atlas。
- Rive 加载失败时必须回退到 PNG/CSS，不能让整个页面空白。
- 默认每 `300000ms`，也就是 5 分钟，随机切换一次动作和格言。
- 格言在角色头部气泡中显示，长度应短，避免遮挡主体。

当前动作：

```text
idle
wave
think
scan
celebrate
patrol
focus
sleep
type
guard
alert
boot
nod
```

主题资源：

```text
public/themes/neon-dark/mascot/assistant.png
```

可选 Rive 资源：

```json
{
  "mascot": {
    "rive": {
      "enabled": true,
      "src": "mascot/assistant.riv",
      "runtime": "vendor/rive/rive.js",
      "stateMachine": "AssistantState"
    }
  }
}
```

后续路线：

- Live2D、Spine 或自定义 JS 应作为 `core.liveMascot` 或插件组件处理。
- 第三方模型或看板娘素材必须先做许可证和再分发审查。
