# 组件系统草案

日期：2026-06-03

目标：定义用户自建组件的第一版标准。

说明：本文件保留早期组件草案。更完整的运行时接口、数据源、事件和版本约束以 [接口规范草案](interface-spec.md) 为准；主题 token 以 [主题系统规范草案](theme-system.md) 为准。

## 设计原则

- 组件必须能在不同屏幕尺寸上复用。
- 组件行为必须通过 manifest 声明。
- 组件视觉样式必须使用共享 token，避免每个组件硬编码一套主题。
- 数据输入必须显式声明，并且可以用 mock 数据预览/测试。
- 当传感器或 API 不可用时，组件应清晰降级，而不是破坏整个界面。

## 计划目录结构

```text
components/<component-id>/
  manifest.json
  index.tsx
  schema.json
  README.md
  preview.json
```

## Manifest 草案

```json
{
  "id": "core.cpu",
  "name": "CPU",
  "version": "0.1.0",
  "description": "CPU 使用率、温度和频率组件。",
  "entry": "./index.tsx",
  "schema": "./schema.json",
  "data": {
    "required": ["system.cpu"],
    "refreshMs": 1000
  },
  "layout": {
    "minWidth": 160,
    "minHeight": 96,
    "aspectRatios": ["1:1", "2:1", "3:2"]
  },
  "theme": {
    "tokens": ["color.surface", "color.text", "color.accent", "font.mono"]
  }
}
```

## 运行时 Props 草案

```ts
type DisplayComponentProps<TConfig, TData> = {
  id: string;
  config: TConfig;
  data: TData;
  status: "ok" | "loading" | "stale" | "error";
  size: {
    width: number;
    height: number;
    density: number;
  };
  theme: ThemeTokens;
  now: number;
};
```

## 布局草案

```json
{
  "display": {
    "name": "case-panel-7in",
    "width": 1024,
    "height": 600,
    "density": 1,
    "rotation": 0
  },
  "layout": {
    "grid": {
      "columns": 12,
      "rows": 8,
      "gap": 8,
      "padding": 12
    },
    "components": [
      {
        "id": "cpu-main",
        "component": "core.cpu",
        "area": { "x": 0, "y": 0, "w": 4, "h": 3 },
        "config": { "variant": "radial" }
      }
    ]
  }
}
```

## 核心组件候选

- `core.clock`：时间/日期。
- `core.cpu`：使用率、频率、温度。
- `core.memory`：内存和 swap。
- `core.disk`：文件系统占用和磁盘活动。
- `core.diskMatrix`：适合 NAS 多盘位的紧凑磁盘矩阵，默认 12 小时刷新。
- `core.network`：吞吐、IP、网卡状态。
- `core.telemetryTrend`：合并 CPU、Memory、Network 的动态折线趋势。
- `core.dockerTui`：参考 lazydocker 信息密度的 Docker 只读状态竖栏。
- `core.systemHero`：设备标题、主题图标和本地 Canvas 三角网格背景。
- `core.mascotAssistant`：透明看板娘资源、CSS 动作状态、随机格言、可选 Rive 骨架动画和 Codex/Petdex sprite atlas。
- `core.gpu`：NVIDIA/AMD/Intel 指标，按可用性提供。
- `core.temperatures`：lm-sensors 标签和值。
- `core.fans`：可用时显示风扇转速和曲线。
- `core.processes`：CPU/内存占用最高进程。
- `core.text`：静态 markdown 或状态文本。

## 组件质量要求

- 在 manifest 声明的最小尺寸下仍能正常显示。
- 数值变化时不产生布局跳动。
- 具备 loading、stale、error、unavailable 状态。
- 每个组件提交预览数据。
- 测试工具建立后，为常见显示尺寸提供截图或视觉测试。
