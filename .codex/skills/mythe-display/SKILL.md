---
name: mythe-display
description: 适用于本仓库的所有工作：Ubuntu 机箱副屏显示项目开发、中文文档维护、README/CHANGELOG 更新、密钥保护，以及每次完成用户可见任务后提交并推送。
---

# Mythe Display 仓库工作规范

## 核心规则

- 除非用户另有要求，使用中文沟通和维护项目文档。
- 将本仓库视为 Ubuntu 机箱副屏/kiosk 显示项目。
- `.env` 和凭据只作本地使用，绝不打印、写入文档或提交。
- 长期有效的调研保存在 `docs/research/`。
- 长期技术决策保存在 `docs/decisions/`，以 ADR 形式记录。
- 实现说明、开发指南和组件规范保存在 `docs/development/`。
- 搭建方式、运行命令、架构方向或复现步骤变化时，更新 `README.md`。
- 每次有实质性仓库变化时，更新 `CHANGELOG.md`。

## 产品方向

- 默认渲染器：运行在普通 Ubuntu 第二显示器上的 Web kiosk 应用。
- 推荐输出方式：优先 HDMI/DisplayPort。
- USB-C 只有在硬件支持 DP Alt Mode、USB4 或雷电时，才能作为普通视频输出。
- DisplayLink 是可选 USB 显卡回退方案，但存在驱动和系统版本兼容风险。
- USB 智能小屏需要协议级渲染器，应作为适配器处理，而不是普通显示器。

## 工程方向

- 优先使用 React + TypeScript 前端和本地指标服务。
- 使用声明式显示屏/布局配置。
- 组件应包含 manifest、配置 schema、类型化运行时 props、预览数据和明确的 unavailable/error 状态。
- 配置中应保留任意显示尺寸、分辨率、像素密度、旋转方向和安全区域能力。

## Git 工作流

- 完成每个用户可见任务后，只 stage 相关文件，commit 并 push。
- 不要 stage `.env` 或本地生成截图/调试产物。
- 如果 push 因认证或远端配置失败，先检查非密钥 Git 配置。只有确实需要时才使用 `.env` 凭据，并且不要暴露凭据内容。
