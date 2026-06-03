# Mythe Display

Mythe Display 是一个面向 Ubuntu 机箱副屏的显示项目。目标是在小尺寸 HDMI/USB 屏幕上运行一个可复现、可高度定制的本地副屏运行时。

当前状态：调研与架构规划阶段。项目还没有实现可运行的显示应用。

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
- [无桌面 Ubuntu kiosk 可行性](docs/development/headless-kiosk-feasibility.md)
- [组件系统草案](docs/development/component-system.md)
- [插件式扩展模型草案](docs/development/plugin-extension-model.md)
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

当前阶段还没有应用可运行。后续实现开始后，预期步骤为：

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
