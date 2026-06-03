# 插件式扩展模型草案

日期：2026-06-03

目标：让用户像使用 ComfyUI custom nodes 一样，通过添加 Git 仓库扩展 Mythe Display 的组件、数据源和主题。

## 设计目标

- 用户可以通过 Git URL 添加第三方组件仓库。
- 新组件在开发模式下可被实时检测并加载。
- 插件必须声明 manifest，不能靠约定扫描任意代码。
- 插件可以提供组件、数据源、主题、布局模板和资源文件。
- 插件可以提供主题资源包，例如背景图、像素精灵、字体和图标。
- 插件可以提供 Agent 状态适配器，把 OpenClaw、Codex 或 CI 状态转换为统一的 `PixelAgentSnapshot`。
- 插件 API 要足够稳定，避免每个组件都依赖内部实现细节。

## 初步目录结构

```text
plugins/
  installed/
    vendor-my-plugin/
      mythe-plugin.json
      package.json
      src/
  assets/
      themes/
      sprites/

components/
  core/
```

未来可以提供命令：

```bash
mythe-display plugin add https://github.com/example/mythe-display-weather.git
mythe-display plugin remove vendor.weather
mythe-display plugin list
```

## 插件 Manifest 草案

```json
{
  "id": "vendor.weather",
  "name": "Weather Components",
  "version": "0.1.0",
  "mytheDisplay": ">=0.1.0",
  "components": [
    {
      "id": "vendor.weather.current",
      "name": "Current Weather",
      "entry": "./src/CurrentWeather.tsx",
      "schema": "./src/current-weather.schema.json",
      "preview": "./src/current-weather.preview.json"
    }
  ],
  "dataProviders": [
    {
      "id": "vendor.weather.openweather",
      "entry": "./src/server/openweather.ts",
      "permissions": ["network.fetch"]
    },
    {
      "id": "openclaw.compat",
      "entry": "./src/server/openclaw-provider.ts",
      "topics": ["agents.pixel"],
      "permissions": ["network.local"]
    }
  ],
  "themes": [
    {
      "id": "vendor.weather.glass",
      "entry": "./themes/glass/theme.json"
    }
  ]
}
```

## 加载机制草案

开发模式：

1. 监听 `plugins/installed/*/mythe-plugin.json`。
2. manifest 变化时重新校验。
3. 组件入口由 Vite 动态导入。
4. schema 和 preview 数据即时刷新。
5. 主题资源包变化时刷新 token、背景和精灵资源。
6. 如果插件构建失败，只禁用该插件，不影响核心界面。

生产模式：

1. 启动时扫描已安装插件。
2. 校验 manifest、兼容版本和权限声明。
3. 构建或加载插件 bundle。
4. 注册组件、数据源、主题和布局模板。

## 权限与安全

插件机制必须承认一个事实：从 Git 仓库安装的插件可能运行代码。初期应采用明确边界：

- 前端组件只运行在浏览器环境，不能直接读取本机文件。
- 服务端数据源必须声明权限，例如 `network.fetch`、`system.sensors.read`。
- OpenClaw/Codex 等本地 Agent 适配器应优先声明 `network.local`，不得默认访问公网。
- 默认不允许插件执行任意 shell 命令。
- 安装插件时应显示 manifest 摘要和权限列表。
- 后续可以增加签名、锁文件和插件来源白名单。

## 与组件系统的关系

插件是分发单位，组件是运行单位。

- 一个插件可以包含多个组件。
- 一个组件必须有自己的 schema、preview 数据和尺寸约束。
- 布局配置只引用组件 ID，不关心组件来自 core 还是插件。

示例：

```json
{
  "id": "weather-top",
  "component": "vendor.weather.current",
  "area": { "x": 8, "y": 0, "w": 4, "h": 2 },
  "config": {
    "provider": "vendor.weather.openweather",
    "location": "Shanghai"
  }
}
```

## 待决策问题

- 插件依赖管理使用 npm/pnpm，还是要求插件预构建 bundle。
- 是否允许服务端插件，还是第一版只允许纯前端组件。
- 插件热加载失败时的 UI 提示方式。
- 插件版本锁定和升级回滚策略。
