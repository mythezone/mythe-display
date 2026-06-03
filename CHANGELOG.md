# 更新记录

## 2026-06-03

- 初始化 Ubuntu 机箱副屏项目的调研与架构文档。
- 新增开源项目对比、显示输出调研、架构决策、组件系统草案、路线图、文档维护规范、`.gitignore` 和 `.env.example`。
- 新增项目本地 Codex skill，记录仓库工作规则。
- 将现有 README、docs 文档和本地 skill 中文化，便于后续基于中文文档继续讨论。
- 记录当前本机 HDMI 长条屏信息：`card0-HDMI-A-2`、`3840x1100`、`/dev/fb0`、`32bpp`。
- 新增无桌面 Ubuntu kiosk 可行性评估和插件式扩展模型草案。
- 新增 `scripts/fb-color-test.py`，用于读取显示信息、填充纯色或显示色条，验证 framebuffer 控制能力。
- 发现当前服务器上直接写 `/dev/fb0` 会改变 framebuffer 内存，但不可靠地改变 HDMI 屏幕可见画面；新增 `scripts/kms-color-test.py`，通过 DRM/KMS 直接设置 HDMI-A-2 scanout，纯色和色条测试均已成功执行并恢复。
- 新增 Web 主显示层 ADR、接口规范、主题系统规范、Web kiosk 测试说明、长条屏示例配置、静态测试页和 kiosk 启动脚本。
- 将默认 Web/kiosk 端口改为 `23456`，并修复 kiosk 启动失败时本地测试服务残留的问题；脚本现在会阻止 sudo/SSH 非 active seat 运行，避免 `Failed to start a DRM session` 这类误用。
- 增加无头 NAS 远程 sudo direct DRM 启动模式，root 下自动使用 `LIBSEAT_BACKEND=builtin`、`/dev/dri/card0`、禁用输入设备依赖并为 Chromium 添加 `--no-sandbox`；新增 systemd 服务模板和安装脚本。
- 禁用 Web kiosk Chromium 翻译 UI，并在测试页添加 `notranslate` 标记，减少右上角翻译气泡干扰。
- 新增默认主题资源包 `public/themes/neon-dark/`，包含 `theme.json`、多层循环 SVG 背景和像素 Agent 状态精灵。
- Web kiosk 测试页现在读取主题资源包，支持动态背景 fallback，并读取 `agents.mock.json` 渲染像素 Agent 原型。
- 新增运行时 URL 切换脚本 `scripts/kiosk-switch-url.py`，通过本机 Chromium DevTools 端口动态切换当前 kiosk 页面。
- 新增主题资源包、像素 Agent 组件、运行时控制和 OpenClaw/像素 Agent 参考项目调研文档。
