# 主题资源包规范草案

日期：2026-06-03

状态：草案

## 目标

主题资源包用于把一个界面风格完整复现出来。用户只要复制或修改一个资源包目录，就能改变背景、状态精灵、图标、字体引用和语义 token，而不需要改 widget 源码。

默认资源包：

```text
public/themes/neon-dark/
  theme.json
  backgrounds/
  sprites/
  hero/
  mascot/
```

## 最小结构

```text
public/themes/<theme-id>/
  theme.json
  backgrounds/        # 可选
  sprites/            # 可选
  hero/               # 可选
  mascot/             # 可选
  fonts/              # 可选
  icons/              # 可选
```

`theme.json` 是唯一必需文件。没有动态背景资源时，运行时必须使用 `wallpaper.fallback` 或 `tokens.surface.canvas` 作为纯色背景。

## Theme Manifest

```json
{
  "id": "core.neon-dark",
  "name": "Neon Dark",
  "version": "0.3.0",
  "description": "适合 3840x1100 长条副屏的暗色霓虹资源包。",
  "tokens": {
    "surface.canvas": "#05070a",
    "surface.panel": "rgba(18, 22, 30, 0.84)",
    "text.primary": "#f4f7fb",
    "accent.primary": "#0a84ff"
  },
  "wallpaper": {
    "fallback": "#05070a",
    "layers": [
      {
        "id": "circuit-grid",
        "src": "backgrounds/circuit-grid.svg",
        "opacity": 0.72,
        "blendMode": "screen",
        "animation": "drift-slow"
      }
    ],
    "effects": ["scanlines", "vignette"]
  },
  "hero": {
    "logo": "hero/mythenas-core.png",
    "background": {
      "engine": "canvas-triangle-mesh",
      "pointCount": "auto",
      "motion": "slow"
    }
  },
  "mascot": {
    "assistant": "mascot/assistant.png",
    "rive": {
      "enabled": false,
      "src": "",
      "runtime": "https://unpkg.com/@rive-app/canvas@2.21.0/rive.js",
      "stateMachine": ""
    }
  },
  "sprites": {
    "agent": {
      "idle": "sprites/agent-idle.svg",
      "walking": "sprites/agent-walking.svg",
      "working": "sprites/agent-working.svg",
      "thinking": "sprites/agent-thinking.svg",
      "building": "sprites/agent-building.svg",
      "reviewing": "sprites/agent-reviewing.svg",
      "blocked": "sprites/agent-blocked.svg",
      "error": "sprites/agent-error.svg",
      "offline": "sprites/agent-offline.svg"
    }
  }
}
```

## 必需 Token

第一版 widget 运行时至少要求这些语义 token：

```text
surface.canvas
surface.panel
surface.panelMuted
text.primary
text.secondary
text.muted
accent.primary
accent.secondary
metric.good
metric.warn
metric.bad
border.subtle
shadow.panel
```

组件只能读取语义 token。主题可以在资源包内部定义更多基础 token 或组件 token，但组件不能硬编码整套颜色。

## 动态背景

`wallpaper.layers` 是可选数组。每一层都是一个可循环播放的背景资源：

- `src`：相对 `theme.json` 的资源路径。
- `opacity`：0 到 1。
- `blendMode`：CSS `mix-blend-mode`。
- `animation`：运行时支持的动画名称，例如 `drift-slow`、`drift-medium`、`pulse`。

未来可以扩展 `type`：

- `image`：SVG、PNG、WebP、AVIF 静态图。
- `video`：短循环视频，适合接近 Wallpaper Engine 的效果。
- `canvas`：由主题或插件提供的安全前端背景模块。

第一版只允许静态资源加内置 CSS 动画，避免主题包执行任意代码。

## Hero 资源

`hero.logo` 用于系统标题组件。默认资源：

```text
public/themes/neon-dark/hero/mythenas-core.png
```

标题文字仍由 HTML/CSS 渲染，图片只承担图标/视觉锚点角色。这样可以避免生成式图片中文字不准，也能让主题切换时保留统一排版。

Hero 的动态效果由运行时提供：

- CSS 发光和环形动画。
- 本地 Canvas 三角网格背景，效果是随机点缓慢运动、近邻点连线并填充半透明三角面。
- `hero.background.engine` 当前支持 `canvas-triangle-mesh`。如果省略，运行时仍可使用默认背景。

主题资源包只提供图片资源，不执行任意代码。

## Mascot 资源

`mascot.assistant` 用于二次元看板娘组件。默认资源：

```text
public/themes/neon-dark/mascot/assistant.png
```

该资源应是透明 PNG/WebP。动作由运行时通过 CSS 动画实现；默认主题已经提供 `idle`、`wave`、`think`、`scan`、`celebrate`、`patrol`、`focus`、`sleep`、`type`、`guard`、`alert`、`boot`、`nod` 等动作名。

主题可以选择提供 Rive 骨架动画资源：

```json
{
  "mascot": {
    "assistant": "mascot/assistant.png",
    "rive": {
      "enabled": true,
      "src": "mascot/assistant.riv",
      "runtime": "vendor/rive/rive.js",
      "artboard": "Assistant",
      "stateMachine": "AssistantState"
    }
  }
}
```

规则：

- `mascot.rive.src` 必须指向主题包内部的 `.riv` 文件。
- `runtime` 建议指向本地 vendored runtime，避免 kiosk 开机时依赖外网；测试阶段也可以使用 CDN。
- Rive 加载失败时，运行时必须回退到 `mascot.assistant`。
- Live2D、Spine 或自定义 JS 应作为单独组件或插件能力声明，不让主题包执行任意 JS。

主题可以选择提供 Codex/Petdex 风格资源：

```json
{
  "mascot": {
    "codexPet": {
      "enabled": true,
      "manifest": "mascot/pets/fox/pet.json",
      "columns": 8,
      "rows": 9,
      "frameWidth": 192,
      "frameHeight": 208,
      "frames": 8,
      "fps": 9,
      "actionRows": {
        "idle": 0,
        "wave": 3,
        "alert": 5,
        "scan": 8
      }
    }
  }
}
```

导入命令：

```bash
mdp pet ~/.codex/pets/fox --force
```

详见：[Codex Pet 兼容规范草案](codex-pet-compat.md)。

## Agent 精灵资源

像素 Agent 组件的最小状态资源：

```text
sprites.agent.idle
sprites.agent.walking
sprites.agent.working
sprites.agent.thinking
sprites.agent.building
sprites.agent.reviewing
sprites.agent.blocked
sprites.agent.error
sprites.agent.offline
```

推荐额外状态可继续扩展，例如：

```text
sprites.agent.celebrating
sprites.agent.sleeping
sprites.agent.deploying
```

如果主题没有提供某个状态，运行时可以回退到 `working` 或 `offline` 精灵。默认资源包中的精灵是仓库自有 SVG；第三方 sprite sheet 必须先确认许可证允许再分发。

## 用户修改方式

用户创建新主题时建议：

1. 复制 `public/themes/neon-dark/` 为 `public/themes/<new-theme>/`。
2. 修改 `theme.json` 的 `id`、`name`、`version`。
3. 替换 `backgrounds/` 和 `sprites/` 中的文件。
4. 在预览 URL 中使用 `?theme=../themes/<new-theme>/theme.json`。
5. 后续正式应用中把主题写入 `config/theme.*.json`。

## 插件分发

插件可以贡献主题资源包，但主题包本身不执行代码：

```json
{
  "themes": [
    {
      "id": "vendor.cyber-grid",
      "entry": "./themes/cyber-grid/theme.json"
    }
  ]
}
```

宿主加载插件主题时必须校验路径只指向插件目录内部，避免主题引用任意本机文件。
