# 标准组件草案

日期：2026-06-03

状态：草案

## 目标

本文件记录 Mythe Display 第一批标准组件的显示目标、数据契约和刷新策略。测试页已经实现这些组件的静态 Web 原型，正式运行时后续应把它们拆成独立组件包。

## core.diskMatrix

用途：紧凑展示 NAS 多磁盘容量状态，适合 10 到 24 个磁盘的长条屏布局。

显示规则：

- 每个磁盘用一个小图标表达类型和容量使用率。
- 图标外圈使用 `conic-gradient` 表示 `usedPercent`。
- 图标内部形状区分 `hdd`、`nvme`、`ssd`、`usb`。
- `metric.good/warn/bad` 表达正常、接近满、严重占满。
- 默认刷新周期是 `3600000ms`，也就是一小时一次。

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

当前 mock：

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

用途：用一个正方形区块展示 Docker 状态，视觉上参考 lazydocker 的 TUI 信息密度。

参考项目：[jesseduffield/lazydocker](https://github.com/jesseduffield/lazydocker)。该项目 README 描述它是用 Go 和 gocui 写成的 Docker / docker-compose 终端 UI。

显示规则：

- 保持方块形态，适合放在右上角。
- 上半部显示 running、stopped、CPU、memory。
- 下半部显示前 5 个容器的状态和资源占用。
- 默认刷新周期建议 `300000ms`。

数据契约：

```ts
type DockerSnapshot = {
  updatedAt: string;
  refreshMs: number;
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

当前 mock：

```text
public/kiosk-test/docker.mock.json
```

## core.telemetryTrend

用途：把 CPU、Memory、Network 三个原本分散的指标合并为一个趋势组件。

显示规则：

- 一个 canvas 折线图显示三条曲线。
- 底部保留当前数值，避免只看图难以读数。
- 测试页会动态滚动 mock 数据；正式运行时应由数据源推送或低频轮询。

数据契约：

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
    networkRx: string;
    networkTx?: string;
  };
};
```

当前 mock：

```text
public/kiosk-test/telemetry.mock.json
```

## core.systemHero

用途：展示设备身份、运行状态和主题核心视觉。

当前实现：

- 主题资源包提供 `hero.logo`。
- 测试页对图标叠加 CSS 发光和环形动画。
- Hero 背景优先使用 Three.js 绘制低透明度几何体，加载失败时降级到原生 Canvas 动态几何。

主题资源：

```text
public/themes/neon-dark/hero/mythenas-core.png
```

注意：生成式图标不负责显示文字，标题文字仍由 HTML/CSS 渲染，避免图片中文字不可控或缩放后发虚。
