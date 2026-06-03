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
- 优化 Web kiosk 主界面：新增 MytheNAS 生成式科技图标、Hero 动态几何背景、CPU/Memory/Network 合并趋势图、紧凑磁盘矩阵和 LazyDocker 风格 Docker 方块。
- 新增 `public/kiosk-test/disks.mock.json`、`docker.mock.json`、`telemetry.mock.json`，并新增 `scripts/collect-disk-snapshot.py` 用于生成真实磁盘快照。
- 新增标准组件草案，定义 `core.diskMatrix`、`core.dockerTui`、`core.telemetryTrend` 和 `core.systemHero` 的数据契约与刷新策略。
- 将 Telemetry 调整为单格组件，增加 CPU/Memory/Network 颜色图例与坐标轴；新增 `core.mascotAssistant` 看板娘组件原型，并把 MytheNAS LOGO 改为透明 PNG。
- 将 MytheNAS Hero 背景改为本地 Canvas 三角网格动画；为看板娘预留 Rive `.riv` 骨架动画接口并保留 PNG/CSS fallback；放大 Agent 像素角色并新增 walking/thinking/building/reviewing/blocked 状态精灵。
- 新增骨架动画与动态背景调研文档，记录 Rive、Live2D、Vanta.js、tsParticles、Trianglify 的取舍。
- 新增 `scripts/kiosk-control.py`，支持 `list/current/switch/open/reload` 控制运行中的 Chromium kiosk；systemd 模板新增 `ExecReload`，可用 `sudo systemctl reload mythe-display-kiosk` 刷新当前界面而不重启服务。
- 新增 `/usr/bin/mdp` 短命令入口和 `scripts/install-mdp-command.sh`，支持 `mdp reload`、`mdp switch`、`mdp start`、`mdp status`、`mdp logs` 等常用操作。
- 增强 `mdp`：`mdp start` 在 systemd unit 缺失时会自动安装服务，`mdp reload/switch/theme` 在控制端口不可用时会先尝试确保 kiosk 服务已安装并启动。
- 增强 Pet/Assistant 组件：新增更多 PNG fallback 动作，增加 Codex/Petdex `pet.json` + spritesheet atlas 兼容层，并新增 `scripts/import-codex-pet.py` 与 `mdp pet` 导入命令。
- 将 Storage、Telemetry、Docker 默认数据源从 mock 切换为运行时真实快照；新增 Telemetry/Docker/Runtime 采集脚本，kiosk 启动时先采集一次再进入低频循环，磁盘默认 12 小时刷新，CPU/内存/网络和 Docker 默认 10 分钟刷新；Storage 改为两格，Docker 改为竖栏并提高容器列表密度。
