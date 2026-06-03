# 主题系统规范草案

日期：2026-06-03

状态：草案

## 目标

主题系统需要同时支持：

- 多种 UI 风格，例如极简、赛博、玻璃拟态、工业监控、终端风格。
- 同一套 widget 在不同主题下保持可读、稳定、统一。
- 用户通过配置切换主题，而不是修改组件源码。
- 主题可由插件分发。

## 设计原则

- 使用语义 token，不让组件直接依赖具体颜色值。
- 主题输出为 CSS custom properties，便于 Web runtime 使用。
- Widget 可以声明所需 token，宿主负责提供 fallback。
- 动画、圆角、阴影、字体、密度都属于主题，不只颜色属于主题。
- 主题应包含暗色优先，因为机箱副屏常在弱光环境中使用。
- 图片、精灵、动态背景和字体文件通过主题资源包管理，详见 [主题资源包规范草案](theme-resource-pack.md)。

## Token 分层

### 基础 Token

基础 token 是原始值：

```json
{
  "base.color.blue.500": "#0a84ff",
  "base.color.green.500": "#30d158",
  "base.space.2": "8px",
  "base.radius.2": "8px",
  "base.font.mono": "\"JetBrains Mono\", monospace"
}
```

### 语义 Token

Widget 主要使用语义 token：

```json
{
  "surface.canvas": "#05070a",
  "surface.panel": "rgba(18, 22, 30, 0.86)",
  "surface.panelMuted": "rgba(18, 22, 30, 0.56)",
  "text.primary": "#f4f7fb",
  "text.secondary": "#a8b3c7",
  "text.muted": "#657086",
  "accent.primary": "#0a84ff",
  "metric.good": "#30d158",
  "metric.warn": "#ffd60a",
  "metric.bad": "#ff453a"
}
```

### 组件 Token

组件 token 是可选层，用于同类组件细节：

```json
{
  "widget.cpu.ringTrack": "rgba(255,255,255,0.08)",
  "widget.cpu.ringValue": "var(--md-accent-primary)"
}
```

## Theme Manifest

```json
{
  "id": "core.neon-dark",
  "name": "Neon Dark",
  "version": "0.1.0",
  "description": "适合长条机箱屏的高对比暗色霓虹主题。",
  "mode": "dark",
  "density": "normal",
  "tokens": {
    "surface.canvas": "#05070a",
    "surface.panel": "rgba(18, 22, 30, 0.86)",
    "text.primary": "#f4f7fb",
    "accent.primary": "#0a84ff"
  },
  "effects": {
    "blur": "12px",
    "shadow": "0 12px 36px rgba(0,0,0,0.36)",
    "motion": "subtle"
  },
  "resourcePack": {
    "entry": "public/themes/neon-dark/theme.json"
  }
}
```

## 主题资源包

主题 manifest 可以只包含 token，也可以引用完整资源包。资源包负责保存可还原的视觉资产：

```text
public/themes/neon-dark/
  theme.json
  backgrounds/
  sprites/
```

当前默认资源包支持：

- 多层背景：`wallpaper.layers`。
- 纯色 fallback：`wallpaper.fallback`。
- 内置循环动画：`drift-slow`、`drift-medium`、`pulse`。
- 像素 Agent 基础状态精灵：`idle`、`working`、`error`、`offline`。

如果资源包没有提供动态背景，运行时必须退回纯色背景，不能让页面空白。

## CSS 变量输出

运行时应将 token 编译为 CSS 变量：

```css
:root {
  --md-surface-canvas: #05070a;
  --md-surface-panel: rgba(18, 22, 30, 0.86);
  --md-text-primary: #f4f7fb;
  --md-accent-primary: #0a84ff;
}
```

Widget 只使用 CSS 变量或 `theme.token()`：

```css
.widget {
  background: var(--md-surface-panel);
  color: var(--md-text-primary);
}
```

## 内置主题路线

第一批建议提供：

- `core.neon-dark`：暗色高对比，适合服务器状态和硬件监控。
- `core.terminal-green`：类终端样式，低装饰、高信息密度。
- `core.glass-dark`：半透明玻璃感，适合展示型副屏。
- `core.industrial`：更硬朗的边框、刻度和状态灯风格。

## Widget 对主题的要求

Widget 不能：

- 硬编码整套颜色。
- 假设背景一定是暗色或亮色。
- 用纯颜色表达状态而不提供文字/形状辅助。

Widget 必须：

- 在 `surface.canvas` 和 `surface.panel` 上都可读。
- 对 `metric.good/warn/bad` 做统一状态表达。
- 支持主题切换后无需重载页面即可重新渲染。

## 主题插件

主题可以由插件贡献：

```json
{
  "themes": [
    {
      "id": "vendor.matrix",
      "entry": "./themes/matrix.json"
    }
  ]
}
```

主题插件不应执行任意代码。第一版主题应只允许 JSON token 和静态资源。
