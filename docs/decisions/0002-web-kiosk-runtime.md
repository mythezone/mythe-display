# ADR 0002：以 Web 页面作为主显示层

日期：2026-06-03

状态：已接受

## 背景

当前服务器没有完整 Ubuntu 桌面环境，但已经确认可以通过 DRM/KMS 控制 HDMI 长条屏。项目后续需要：

- 开发时在网页端实时预览布局和组件。
- 生产时在唯一 HDMI 屏上显示图形界面。
- 不显示浏览器地址栏、标签页、控制按钮等浏览器控制组件。
- 支持主题、布局、组件和插件生态。

## 决策

Mythe Display 的主显示层采用 Web 技术：

- UI 内容：HTML/CSS/JavaScript，应用层使用 React + TypeScript。
- 开发预览：本地 Web server，普通浏览器访问。
- 生产显示：极简 Wayland kiosk compositor + 浏览器 kiosk 模式。
- 底层验证：保留 DRM/KMS 测试脚本，不作为主 UI 渲染方式。

生产路径：

```text
systemd
  -> mythe-display server
    -> http://127.0.0.1:23456
  -> kiosk compositor, such as cage or weston
    -> chromium/firefox --kiosk http://127.0.0.1:23456
      -> DRM/KMS -> HDMI-A-2 -> 3840x1100 screen
```

## 为什么选择 Web

- 组件系统成熟，适合快速构建 widget、主题和布局编辑器。
- CSS 变量、设计 token、容器查询、grid/flex 能很好支持多尺寸屏幕。
- 用户可以通过普通浏览器远程预览，不必每次占用唯一显示屏。
- 插件可以用 npm/Vite 生态打包，也可以通过 Git 仓库分发。
- kiosk 浏览器可以隐藏浏览器控制条，只显示页面内容。

## 不选择的方案

- 直接写 framebuffer：当前测试显示 `/dev/fb0` 可写但不可靠改变可见画面。
- 直接写 DRM/KMS 渲染 UI：启动快、控制强，但组件生态和预览体验差。
- 完整 Ubuntu 桌面环境：依赖多、启动重，不适合服务器副屏。

## 当前依赖状态

本机当前已有：

- Node/pnpm，可用于开发 Web 应用。
- `cage` 和 `chromium-browser`，可用于 kiosk 路径测试。
- Xorg core，但生产路径优先使用 Wayland kiosk。
- DRM/KMS 可用，`card0-HDMI-A-2` 可被控制。

当前限制：

- Codex/SSH 后台普通用户会话不是本地 active seat，不能通过 logind 直接启动 `cage` 接管 DRM。
- 由于这台 NAS 不接键鼠，远程启动应使用 sudo direct DRM 模式或 systemd 服务模式。

因此当前可以创建和预览网页内容，并能验证脚本依赖；真正“无浏览器控制条上屏”应通过 root/builtin libseat 或后续 systemd 服务启动。

## 后续影响

- 第一版 Web UI 可先用静态 HTML 验证，再迁移到 React/Vite。
- 所有主题都应编译为 CSS 变量和设计 token。
- 所有 widget 都应在浏览器内运行，通过受控数据 API 获取系统信息。
- 系统级数据采集和插件数据源运行在本地 server 中，不直接暴露给前端任意执行。
