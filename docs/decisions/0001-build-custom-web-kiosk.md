# ADR 0001：自研 Web kiosk 运行时

日期：2026-06-03

状态：已接受

## 背景

本项目需要为 Ubuntu 机箱副屏构建一个显示系统。核心需求包括：自定义显示尺寸/分辨率、布局区域、可替换组件，以及统一的组件开发规范。

现有项目都有价值，但都不完整：

- MagicMirror² 的模块化和 kiosk 模式最接近，但布局模型和组件契约不完全适合本项目。
- Turing Smart Screen Python 很适合受支持的 USB 智能小屏，但不是通用显示器渲染器。
- Conky 和 Eww 是强大的 Linux 原生 widget 工具，但难以形成面向第三方的现代组件 SDK。
- Grafana、Netdata、Glances 在指标能力上很强，但不适合直接作为精致小屏产品体验。

## 决策

在本仓库中自研 Mythe Display Web kiosk 运行时。

初始实现优先面向 Ubuntu 普通第二显示器，使用 HDMI/DisplayPort 输出。USB 输出作为硬件传输问题处理：

- USB-C DP Alt Mode/USB4/雷电：按普通显示器处理。
- DisplayLink：安装驱动后按普通显示器处理。
- USB 智能小屏：未来作为可选协议渲染器处理。

## 计划中的技术形态

- 前端：React + TypeScript。
- 运行方式：优先 Chromium kiosk；只有在打包或多显示器控制确实需要时，再考虑 Electron/Tauri。
- 后端：本地 Node.js 指标服务，通过 WebSocket 更新数据。
- 配置：声明式显示屏、布局和组件配置。
- 组件：基于 manifest 的目录结构，包含 schema、类型化 props 和设计 token。
- 文档：所有架构、部署、变更记录保存到 `docs/` 和 `CHANGELOG.md`。

## 影响

正面影响：

- 完整控制屏幕几何、布局模型、组件契约和视觉设计。
- 更容易让其他用户通过配置文件复现自己的副屏。
- 可以按需接入原生采集器、Glances、Netdata、Prometheus、脚本或设备适配器。

代价：

- 比直接使用 MagicMirror² 工作量更大。
- 需要自建组件 SDK、预览工作流和指标服务。
- USB 智能小屏支持需要单独开发协议渲染层。

## 第一个里程碑定义

第一版可用版本应包含：

- 可运行的全屏预览。
- 一个 800x480 布局示例和一个 1024x600 布局示例。
- 核心组件：时钟、CPU、内存、磁盘、网络、温度、风扇/GPU 占位。
- 已文档化的组件 manifest 和一个自定义组件示例。
- Ubuntu kiosk 启动说明。
