# Mythe Display

Mythe Display 是一个面向 Ubuntu 机箱副屏的显示项目。目标是在小尺寸 HDMI/USB 屏幕上运行一个可复现、可高度定制的本地副屏运行时。

当前状态：已有无桌面 Web kiosk 测试页，可以通过 `cage + Chromium` 在 HDMI 长条屏上全屏显示；已提供默认主题资源包、动态背景、像素 Agent mock 组件和运行时 URL 切换脚本。

## 项目目标

- 在 Ubuntu 上以 kiosk/全屏方式运行到副屏。
- 支持自定义显示屏尺寸、分辨率、像素密度、旋转方向和安全区域。
- 布局通过配置声明，避免用户为了换界面而改应用源码。
- 每个区域都可以放置、替换、组合组件。
- 组件遵循稳定的 manifest 和运行时接口，便于快速构建统一风格、统一数据接口的新组件。
- 将调研、架构决策、技术文档、更新记录长期保存在仓库中。

## 推荐方向

在本仓库中自研一个 Web kiosk 运行时，而不是直接 fork 现成项目。可参考：

- MagicMirror²：模块化屏幕组合方式。
- Grafana：面板契约、dashboard-as-code、插件规范。
- Turing Smart Screen Python：主题分享和配置优先的工作流。
- Netdata/Glances：可选的系统指标数据来源。

第一版应优先支持 HDMI/DisplayPort 输出，因为它是原生显示路径，可靠、低延迟、少驱动问题。如果必须使用一根 USB 线，需要主机 USB-C 支持 DP Alt Mode/USB4/雷电，或者使用 DisplayLink USB 显卡类设备。普通数据型 USB-C 主板接口不能仅靠软件变成原生视频输出口。

## 文档入口

- [开源项目调研](docs/research/open-source-options.md)
- [显示输出方案](docs/research/display-output-options.md)
- [当前本机显示设备记录](docs/research/current-hardware-display.md)
- [推荐架构决策](docs/decisions/0001-build-custom-web-kiosk.md)
- [Web 主显示层决策](docs/decisions/0002-web-kiosk-runtime.md)
- [无桌面 Ubuntu kiosk 可行性](docs/development/headless-kiosk-feasibility.md)
- [接口规范草案](docs/development/interface-spec.md)
- [主题系统规范草案](docs/development/theme-system.md)
- [主题资源包规范草案](docs/development/theme-resource-pack.md)
- [组件系统草案](docs/development/component-system.md)
- [标准组件草案](docs/development/standard-widgets.md)
- [Codex Pet 兼容规范草案](docs/development/codex-pet-compat.md)
- [像素 Agent 组件规范草案](docs/development/pixel-agent-widget.md)
- [插件式扩展模型草案](docs/development/plugin-extension-model.md)
- [Web kiosk 测试说明](docs/development/web-kiosk-test.md)
- [运行时控制规范草案](docs/development/runtime-control.md)
- [OpenClaw / 像素 Agent 可视化参考调研](docs/research/openclaw-pixel-agent-options.md)
- [骨架动画与动态背景方案调研](docs/research/animation-and-background-options.md)
- [路线图](docs/development/roadmap.md)
- [文档维护规范](docs/development/documentation-policy.md)
- [更新记录](CHANGELOG.md)

## 目标架构

计划中的运行时：

- 前端：React + TypeScript，全屏渲染在 Chromium 或可选桌面壳中。
- 后端：本地 Node.js 服务，采集系统指标并提供 WebSocket/REST 数据。
- 配置：显示屏、布局、组件配置均以声明式文件保存。
- 组件：每个组件是独立目录，包含 `manifest.json`、类型化配置、React 入口和预览数据。
- 部署：为 Ubuntu 提供 systemd 用户服务和 kiosk 启动脚本。

计划中的组件目录：

```text
components/<component-id>/
  manifest.json
  index.tsx
  schema.json
  README.md
```

每个组件需要声明输入数据、刷新策略、尺寸约束、主题能力和降级状态。

## Web Kiosk 测试

当前仓库包含一个静态网页测试页面：

- [public/kiosk-test/index.html](public/kiosk-test/index.html)
- [public/kiosk-test/agents.mock.json](public/kiosk-test/agents.mock.json)
- [public/kiosk-test/disks.mock.json](public/kiosk-test/disks.mock.json)
- [public/kiosk-test/docker.mock.json](public/kiosk-test/docker.mock.json)
- [public/kiosk-test/telemetry.mock.json](public/kiosk-test/telemetry.mock.json)
- [public/themes/neon-dark/theme.json](public/themes/neon-dark/theme.json)

本地预览：

```bash
python3 scripts/serve-web-test.py --host 0.0.0.0 --port 23456
```

浏览器访问：

```text
http://<server-ip>:23456/kiosk-test/
```

无浏览器控制条上屏需要 kiosk compositor 和浏览器。当前服务器已检测到 `cage` 和 `chromium-browser`。

NAS 无头远程启动推荐使用 sudo direct DRM 模式：

```bash
sudo MYTHE_DISPLAY_PORT=23456 scripts/run-kiosk-web-test.sh
```

该模式会使用 `LIBSEAT_BACKEND=builtin`、`WLR_DRM_DEVICES=/dev/dri/card0` 和 `WLR_LIBINPUT_NO_DEVICES=1`，不依赖物理键鼠登录。

如果未来在本机 TTY 登录，也可以普通用户运行：

```bash
scripts/run-kiosk-web-test.sh
```

安装为 systemd 服务：

```bash
sudo scripts/install-kiosk-service.sh
mdp start
mdp enable
```

只安装/更新短命令入口：

```bash
sudo scripts/install-mdp-command.sh
```

如果只安装了短命令，也可以直接运行：

```bash
mdp start
```

`mdp start` 会在找不到 `mythe-display-kiosk.service` 时自动安装 systemd 服务，然后启动它。

也可以测试任意网页：

```bash
scripts/run-kiosk-web-test.sh https://example.com
```

运行后动态切换当前 kiosk 页面：

```bash
mdp list
mdp current
mdp switch '/kiosk-test/?theme=../themes/neon-dark/theme.json'
mdp switch https://example.com
mdp reload
```

安装为 systemd 后，刷新当前界面不需要重启服务：

```bash
sudo systemctl reload mythe-display-kiosk
```

`reload` 会通过 Chromium DevTools 控制当前页面，并追加 `assetCacheBust` 参数，让主题资源重新加载。它不会执行 `systemctl restart`，因此不会重新抢占 DRM seat。

日常建议使用更短的命令：

```bash
mdp reload
mdp status
mdp logs
```

导入已下载的 Codex/Petdex pet 包：

```bash
mdp pet ~/.codex/pets/<pet-name> --force
mdp reload
```

Chromium 控制端口默认只绑定本机：

```text
MYTHE_DISPLAY_REMOTE_DEBUG_PORT=23458
```

该切换能力依赖 Chromium DevTools 控制端口；Firefox kiosk 暂不支持。

测试页默认禁止浏览器翻译提示：页面设置 `translate="no"` 和 `notranslate`，Chromium 启动参数也会关闭翻译 UI。如果仍看到翻译气泡，先删除旧 kiosk profile 后重启：

```bash
sudo rm -rf /tmp/mythe-display-kiosk-profile
sudo MYTHE_DISPLAY_PORT=23456 scripts/run-kiosk-web-test.sh
```

## 主题资源包

默认主题资源包位于：

```text
public/themes/neon-dark/
```

它包含：

- `theme.json`：语义 token、动态背景层、Hero/Pet 资源和 Agent 精灵映射。
- `backgrounds/`：可循环播放的 SVG 背景层。
- `hero/`：透明 MytheNAS 科技感图标资源。
- `mascot/`：透明看板娘资源。
- `sprites/`：像素 Agent 的 `idle`、`walking`、`working`、`thinking`、`building`、`reviewing`、`blocked`、`error`、`offline` 状态资源。

用户可以复制整个目录创建新主题，并在预览 URL 中指定：

```text
http://<server-ip>:23456/kiosk-test/?theme=../themes/<theme-id>/theme.json
```

## 标准组件原型

测试页现在包含这些标准组件原型：

- `core.systemHero`：MytheNAS 图标、动态发光和本地 Canvas 三角网格背景。
- `core.telemetryTrend`：CPU、Memory、Network 合并折线图，单格显示，带颜色图例和坐标轴。
- `core.mascotAssistant`：二次元看板娘，默认每 5 分钟随机切换 CSS 动作和一句短格言；主题可选接入 Rive `.riv` 骨架动画资源。
- `core.diskMatrix`：紧凑磁盘矩阵，支持 HDD/NVMe/SSD/USB 图标和使用率外圈，默认一小时刷新。
- `core.dockerTui`：参考 lazydocker 信息密度的 Docker 只读方块。
- `core.pixelAgents`：OpenClaw 兼容的像素 Agent 状态原型。

真实磁盘快照可以这样生成：

```bash
scripts/collect-disk-snapshot.py --out public/runtime/disks.json --pretty
```

然后用真实数据预览：

```text
http://<server-ip>:23456/kiosk-test/?disks=/runtime/disks.json
```

## 像素 Agent 原型

测试页已包含 `core.pixelAgents` 原型。默认读取：

```text
public/kiosk-test/agents.mock.json
```

也可以通过 URL 参数接入任意同结构 JSON：

```text
http://<server-ip>:23456/kiosk-test/?agents=/api/agents/pixel
```

目标是后续用 `openclaw.compat` 适配器把 OpenClaw Agent 状态转换为统一的 `PixelAgentSnapshot`，而不是让 UI 直接依赖 OpenClaw 内部接口。

## 硬件建议

当前本机已检测到 HDMI 长条屏：

- connector：`card0-HDMI-A-2`
- framebuffer：`/dev/fb0`
- 分辨率：`3840x1100`
- 色深：`32bpp`
- framebuffer 驱动：`i915drmfb`

优先选择：

- 小尺寸 HDMI 屏，连接到独显、核显或主板 HDMI/DP 输出。
- Ubuntu 将它识别为普通第二显示器。

可以接受：

- USB-C 屏幕，但前提是主机接口支持 DP Alt Mode、USB4 或雷电视频输出。
- DisplayLink 屏幕/转接器，但需要接受专有驱动和 Ubuntu 版本兼容风险。

不建议作为主路径：

- 只有数据能力的普通 USB-C 主板接口。
- USB 串口类小屏，除非明确计划开发协议级渲染器。

## 本地准备

当前阶段仍是原型和接口规范阶段。后续正式应用实现后，预期步骤为：

1. 将 `.env.example` 复制为 `.env`。
2. 安装项目依赖。
3. 在 `config/` 中配置显示屏几何信息和组件布局。
4. 启动本地预览。
5. 在生产环境安装 kiosk/systemd 服务。

当前可用的真实屏幕控制测试命令：

```bash
python3 scripts/kms-color-test.py info
sg video -c "python3 scripts/kms-color-test.py fill --connector card0-HDMI-A-2 --mode 3840x1100 --color '#0047ff' --duration 5 --restore"
sg video -c "python3 scripts/kms-color-test.py bars --connector card0-HDMI-A-2 --mode 3840x1100 --duration 5 --restore"
```

如果已经重新登录刷新了 `video` 组权限，也可以不使用 `sg video -c`：

```bash
python3 scripts/kms-color-test.py fill --connector card0-HDMI-A-2 --mode 3840x1100 --color '#0047ff' --duration 5 --restore
```

`/dev/fb0` 测试脚本现在只建议作为 framebuffer 内存诊断使用。它可以写入并读回 `i915drmfb`，但在当前服务器上不一定会改变 HDMI 屏幕的真实可见 scanout：

```bash
python3 scripts/fb-color-test.py info
sudo python3 scripts/fb-color-test.py fill --color '#0047ff' --duration 5 --restore
sudo python3 scripts/fb-color-test.py bars --duration 5 --restore
```

如果不想每次写屏都使用 `sudo`，可以将运行用户加入图形设备相关组后重新登录或重启：

```bash
sudo usermod -aG video,render,input mythezone
```

## 仓库规则

- 密钥只放在 `.env`，不要提交。
- 用户可复现的搭建步骤写入本 README。
- 长期有效的调研和技术决策写入 `docs/`。
- 重要变化更新 `CHANGELOG.md`。
- 每次完成用户可见任务后，在可用时提交并推送。
