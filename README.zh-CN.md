# Mythe Display

[English README](README.md)

![Mythe Display LOGO](public/brand/mythe-display-logo.png)

Mythe Display 是一个面向 Ubuntu 服务器、NAS 和机箱副屏的开源 Web kiosk 显示运行时。它可以在没有完整 Ubuntu 桌面环境的机器上，把本地 Web 界面全屏输出到 HDMI/DisplayPort 长条屏。

当前版本保留轻量架构：静态 Web 页面、Python 运行时采集脚本、主题资源包和 `mdp` 控制命令。这样更容易复现、调试和自定义。

![Mythe Display 桌面截图](examples/screenshots/kiosk-desktop.png)

## 功能特性

- 支持无桌面 Ubuntu 的 `cage + Chromium` 全屏 kiosk。
- 已在 `3840x1100` HDMI 长条屏上验证。
- 默认静态页面位于 `public/kiosk-test/`。
- 运行时 JSON 快照支持 FAIO 一起听歌、磁盘、CPU、内存、GPU、网络、系统健康、Docker、深圳天气和本机 Codex 会话元数据。
- 一起听歌只读组件展示专辑封面、歌词和待播放列表，支持本地曲库、普通外链和在线平台点歌，并通过 NAS 本机音频接口播放。
- 通过 `mdp` 支持启动、刷新、切换页面、查看日志、导入 pet 资源。
- 主题资源包支持语义 token、动态背景、Hero 图、看板娘和像素 Agent 精灵。
- 已包含 NAS 场景常用的紧凑监控组件原型。
- 仓库内置本地 Codex skill，便于 Agent 按规范定制主题和 Widget。

## 当前实现状态

当前版本是可运行的静态 Web kiosk 原型，不是 React/TypeScript 组件包。本轮发布前整理选择保留现有架构，避免在核心上屏流程稳定前引入大规模迁移风险。

已实现：

- `cage + Chromium` direct DRM kiosk 启动。
- 静态 Web 服务和 Python runtime collector。
- `mdp` 短命令。
- `core.faioListenRoom`、`core.systemHero`、`core.clockWeather`、`core.telemetryTrend`、`core.systemHealth`、`core.diskMatrix`、`core.dockerTui`、`core.mascotAssistant` 原型。
- 默认 `neon-dark` 主题资源包。

未来路线：

- 组件 manifest、schema 和类型化接口。
- React/TypeScript 前端运行时。
- 插件化 Widget 和数据源。
- 更多显示适配器。

## 项目结构

| 路径 | 用途 |
| --- | --- |
| `public/kiosk-test/` | 当前静态 kiosk Web UI 和 mock 数据。 |
| `public/themes/` | 主题资源包。 |
| `public/brand/` | README 和发布使用的公开品牌资产。 |
| `scripts/` | kiosk 启动器、`mdp`、运行时采集器、显示测试和导入工具。 |
| `systemd/` | 由安装脚本渲染的服务模板。 |
| `docs/` | 调研、ADR、接口规范、运行时控制和路线图。 |
| `examples/` | README 引用的公开截图和示例。 |
| `.codex/skills/mythe-display/` | 让 Codex 理解本项目的本地 Skill。 |

## 硬件要求

推荐：

- Ubuntu server 或 desktop。
- 通过 HDMI/DisplayPort 连接的普通显示屏。
- 支持 DRM/KMS 的 GPU。
- 长条屏，例如 `3840x1100`。

关于 USB 显示：

- 普通 USB-C 数据口不能靠软件变成原生视频输出。
- USB-C 视频需要硬件支持 DP Alt Mode、USB4 或雷电。
- DisplayLink USB 显卡可作为备选方案，但需要额外驱动，不是默认路径。

## 快速开始

安装依赖：

```bash
sudo apt update
sudo apt install cage chromium-browser python3
```

克隆并预览：

```bash
git clone <repo-url> mythe-display
cd mythe-display
python3 scripts/serve-web-test.py --host 0.0.0.0 --port 23456
```

浏览器打开：

```text
http://<server-ip>:23456/kiosk-test/
```

生成一次运行时数据：

```bash
scripts/collect-runtime-snapshots.py --once --pretty
```

无头 NAS 直接上屏：

```bash
sudo MYTHE_DISPLAY_PORT=23456 scripts/run-kiosk-web-test.sh
```

## 安装为服务

安装 systemd 服务和 `mdp` 命令：

```bash
sudo scripts/install-kiosk-service.sh
```

安装脚本会用当前仓库路径渲染 `systemd/mythe-display-kiosk.service`，因此项目不需要固定放在某个个人目录或 `/opt` 下。

安装器同时会部署 DRM 热插拔监测服务。HDMI/DP 断开再稳定恢复后，它会自动重启 kiosk，让 Cage/wlroots 重新选择当前已连接的 DRM card。这样可以处理 compositor 进程仍然存活、但插拔或显示器断电后 scanout 已失效的情况。

启动并设置开机自启：

```bash
mdp start
mdp enable
```

常用命令：

```bash
mdp status
mdp logs
mdp reload
mdp switch /kiosk-test/
mdp restart
```

已有安装升级到热插拔恢复功能时，执行一次安装器并重启 kiosk：

```bash
sudo scripts/install-kiosk-service.sh
sudo mdp restart
```

查看热插拔恢复日志：

```bash
journalctl -u mythe-display-hotplug.service -f
```

如果当前这块 `3840x1100` 长条屏在开关屏后出现 `i2c NAK`、错误 HDMI
VIC，或降级为 `1920x1080`，可安装项目保存的固定 EDID 后重启：

```bash
sudo mdp install-edid
sudo reboot
```

该 EDID 只适用于当前验证过的屏幕型号，不能直接用于其他显示器。

注意：

- `mdp reload` 只刷新当前 Chromium 页面。
- 修改 collector 脚本或服务环境变量后，应使用 `mdp restart`。

## 配置

复制 `.env.example` 到 `.env`：

```bash
cp .env.example .env
```

`.env.example` 只包含非敏感默认值和空占位。真实 `.env` 绝不能提交。
当 `.env` 存在时，kiosk 启动脚本、安装后的 systemd 服务和 `mdp` 命令都会读取它；直接命令行中显式导出的环境变量优先级更高。

常用变量：

- `MYTHE_DISPLAY_HOST`：本地 Web 服务监听地址。
- `MYTHE_DISPLAY_PORT`：本地 Web 服务端口，默认 `23456`。
- `MYTHE_DISPLAY_REMOTE_DEBUG_HOST`：Chromium DevTools 监听地址，默认 `127.0.0.1`。
- `MYTHE_DISPLAY_REMOTE_DEBUG_PORT`：Chromium DevTools 控制端口，默认 `23458`。
- `MYTHE_DISPLAY_BROWSER`：浏览器命令，例如 `chromium-browser`。
- `MYTHE_DISPLAY_ALSA_OUTPUT_DEVICE`：FAIO 音频使用的 ALSA 输出设备，当前 NAS 默认 `plughw:0,3` 走在线 HDMI 副屏音频端点；如需主板模拟音频口可改为 `hw:0,0`。
- `MYTHE_DISPLAY_FAIO_RESUME_PUBLIC_OUTPUT`：无人值守音频进程启动时恢复 FAIO 独立的公共扬声器状态，默认 `1`；启动后仍响应远程暂停和音量调整。
- `MYTHE_DISPLAY_DRM_DEVICE`：Cage/wlroots 使用的 DRM 设备，默认 `auto`，会选择带 connected 显示连接器的 card。
- `MYTHE_DISPLAY_DRM_DEVICE_STRICT`：设为 `1` 时强制使用配置的 DRM card，即使另一个 card 才连接了显示器。
- `MYTHE_DISPLAY_DISABLE_DRM_ATOMIC`：设为 `1` 使用 wlroots legacy DRM commit，默认 `1`，提高长条屏稳定性。
- `MYTHE_DISPLAY_DISABLE_DRM_MODIFIERS`：设为 `1` 禁用 DRM modifiers，默认 `1`，提高兼容性。
- `MYTHE_DISPLAY_DISABLE_RUNTIME_COLLECTOR`：设为 `1` 可禁用运行时采集。
- `MYTHE_DISPLAY_START_CACHE_BUST`：设为 `0` 可关闭默认本地 kiosk 页面启动时追加的 cache-bust 查询参数。
- `MYTHE_DISPLAY_FAIO_LISTEN_ROOM_URL`：FAIO 一起听歌房间 URL，默认 `http://127.0.0.1:4173/listen/XatSqhcP6LmROQyKrjCULXyD-zcynwRZO5QaLO5Oeyg`。
- `MYTHE_DISPLAY_FAIO_LISTEN_DISPLAY_NAME`：副屏只读听众名称，默认 `MytheNAS Speaker`。
- `MYTHE_DISPLAY_FAIO_LISTEN_REFRESH_MS`：FAIO 房间快照刷新间隔，默认 `10000`。
- `MYTHE_DISPLAY_FAIO_PUBLIC_OUTPUT_REFRESH_MS`：公共暂停与音量轻量状态刷新间隔，默认 `1000`；不会重新加载房间播放进度。
- `MYTHE_DISPLAY_DISABLE_FAIO_AUDIO_PLAYER`：设为 `1` 可禁用 FFmpeg/ALSA FAIO 独立音频播放器。
- `MYTHE_DISPLAY_FAIO_BROWSER_AUDIO`：设为 `1` 可在独立播放器运行时仍保留浏览器内置 FAIO 音频。
- `MYTHE_DISPLAY_CODEX_AGENT_SHOW_THREAD_NAMES`：设为 `1` 才会在副屏显示 Codex 线程标题。

FAIO 音频会按来源类型处理：本地曲库和在线平台曲目都通过带私有房间 session 的 Mythe Display 本地代理读取，其中在线曲目仍由 FAIO 动态生成 stream ticket；普通外链保持直连。房间 Cookie 只保存在被忽略的 `tmp/` 目录，不会写入公开 runtime JSON 或提交到 Git。

## 运行时数据

默认页面读取 `public/runtime/` 中的本地 JSON 快照。该目录已被 Git 忽略。

| 快照 | 默认刷新 | 采集脚本 |
| --- | ---: | --- |
| `/runtime/disks.json` | 12 小时 | `scripts/collect-disk-snapshot.py` |
| `/runtime/telemetry.json` | 10 分钟 | `scripts/collect-telemetry-snapshot.py` |
| `/runtime/docker.json` | 10 分钟 | `scripts/collect-docker-snapshot.py` |
| `/runtime/weather-shenzhen.json` | 30 分钟 | `scripts/collect-weather-snapshot.py` |
| `/runtime/codex-agents.json` | 5 分钟 | `scripts/collect-codex-agents-snapshot.py` |
| `/runtime/faio-listen.json` | 10 秒 | `scripts/collect-faio-listen-snapshot.py` |

验证采集器但不写入默认 runtime 目录时，可以使用临时目录：

```bash
scripts/collect-runtime-snapshots.py --once --pretty --runtime-dir tmp/verify-runtime
```

## 主题定制

默认主题位于：

```text
public/themes/neon-dark/
```

复制主题：

```bash
cp -R public/themes/neon-dark public/themes/my-theme
```

预览主题：

```text
http://<server-ip>:23456/kiosk-test/?theme=../themes/my-theme/theme.json
```

详细规范：

- [主题资源包规范](docs/development/theme-resource-pack.md)
- [主题系统规范](docs/development/theme-system.md)

## 自定义 Widget

当前第一版 Widget 仍在 `public/kiosk-test/index.html` 中实现。推荐流程：

1. 定义或复用 JSON 快照结构。
2. 增加 collector 或数据源，写入 `public/runtime/<name>.json`。
3. 在 `public/kiosk-test/` 增加 mock 数据。
4. 在 kiosk 页面渲染 Widget。
5. 在 `docs/development/interface-spec.md` 记录数据契约。

参考文档：

- [接口规范](docs/development/interface-spec.md)
- [标准组件](docs/development/standard-widgets.md)
- [像素 Agent 组件](docs/development/pixel-agent-widget.md)
- [Codex Agent 本机追踪](docs/development/codex-agent-tracking.md)

## Agent 辅助定制

本仓库内置本地 Codex skill：

```text
.codex/skills/mythe-display/SKILL.md
```

它帮助 Agent 理解本项目，并按规范完成主题制作、Widget 数据契约、collector、新截图和文档更新等任务。

## 示例

长条屏截图：

![长条屏截图](examples/screenshots/kiosk-desktop.png)

窄屏预览：

![窄屏预览](examples/screenshots/kiosk-mobile.png)

## 参与开发

除非已明确规划迁移，改动应围绕当前静态 kiosk 架构展开。用户可见行为变化需要同步更新英文 README、中文 README、`CHANGELOG.md` 和相关 `docs/`。不要提交 `.env`、runtime 快照、本地截图、缓存目录或私有凭据。

推荐提交前检查：

```bash
python3 -m py_compile scripts/*.py
bash -n scripts/*.sh scripts/mdp
scripts/collect-runtime-snapshots.py --once --pretty --runtime-dir tmp/verify-runtime
git status --ignored --short
```

## 致谢

本项目参考了：

- [MagicMirror²](https://magicmirror.builders/)
- [Grafana](https://grafana.com/)
- [Netdata](https://www.netdata.cloud/)
- [Glances](https://nicolargo.github.io/glances/)
- [lazydocker](https://github.com/jesseduffield/lazydocker)
- Codex/Petdex 风格 sprite pet 生态

完整调研见：[开源项目调研](docs/research/open-source-options.md)。

## 许可证

MIT。见 [LICENSE](LICENSE)。
