# Web Kiosk 测试说明

日期：2026-06-03

## 目标

验证 Mythe Display 的主界面可以作为网页内容运行，并在生产模式中以无浏览器控制条方式显示到唯一 HDMI 屏。

## 当前状态

仓库已提供一个静态测试页：

- [public/kiosk-test/index.html](../../public/kiosk-test/index.html)

该页面不依赖构建工具，可通过 Python 静态服务器预览。

测试页当前包含：

- 默认主题资源包：`public/themes/neon-dark/theme.json`。
- 多层循环背景和纯色 fallback。
- FAIO 一起听歌只读组件：展示当前专辑封面、歌词和待播放列表，并通过本机代理播放 NAS 音频。
- MytheNAS hero 图标和动态几何背景，默认缩为右下角身份组件。
- Clock 组件固定 `Asia/Shanghai` 东八区时间，并默认读取 `public/runtime/weather-shenzhen.json` 展示深圳当天 Open-Meteo 天气。
- CPU、Memory、Network 单格合并趋势图，默认读取 `public/runtime/telemetry.json` 真实快照，mock 仅作为兜底。
- 看板娘透明资源和随机动作/格言。
- 磁盘矩阵，默认读取 `public/runtime/disks.json` 真实快照，mock 仅作为兜底。
- LazyDocker 风格 Docker 竖栏，默认读取 `public/runtime/docker.json` 真实快照，mock 仅作为兜底。
- Codex Agent 采集仍保留为运行时数据源；默认界面不再展示 Agent 面板。
- 页面级禁翻译标记：`translate="no"` 和 `notranslate`。

生产上屏需要的组件：

- `cage` 或 `weston`
- `chromium`、`chromium-browser`、`google-chrome`、`firefox` 或 `firefox-esr`

当前服务器已经检测到 `cage` 和 `chromium-browser`。如果换机器部署，需要先确认这些依赖存在。

## 本地预览

启动静态服务：

```bash
python3 scripts/serve-web-test.py --host 0.0.0.0 --port 23456
```

然后在任意浏览器打开：

```text
http://<server-ip>:23456/kiosk-test/
```

如果 `23456` 已被其他服务占用，可以换端口：

```bash
python3 scripts/serve-web-test.py --host 0.0.0.0 --port 23457
```

当前 shell 如果设置了 HTTP 代理，命令行请求本地服务时可能需要绕过代理：

```bash
curl --noproxy '*' http://127.0.0.1:23457/kiosk-test/
```

## Kiosk 上屏

### NAS 无头远程模式

这台机器不会接鼠标键盘，也不会在物理屏幕上登录。推荐用 sudo direct DRM 模式：

```bash
sudo MYTHE_DISPLAY_PORT=23456 scripts/run-kiosk-web-test.sh
```

脚本在 root 模式下会自动设置：

```text
XDG_RUNTIME_DIR=/run/user/0
LIBSEAT_BACKEND=builtin
WLR_BACKENDS=drm
WLR_DRM_DEVICES=<auto-detected connected DRM card>
WLR_LIBINPUT_NO_DEVICES=1
WLR_DRM_NO_ATOMIC=1
WLR_DRM_NO_MODIFIERS=1
```

`MYTHE_DISPLAY_DRM_DEVICE` 默认是 `auto`。脚本会扫描 `/sys/class/drm/card*-*/status`，选择拥有 `connected` HDMI/DP connector 的 `/dev/dri/cardN`。这可以避免重启后 Linux 把 i915/NVIDIA/AMD card 编号重排，例如实际长条屏从 `/dev/dri/card0` 变成 `/dev/dri/card1` 时，服务仍然能启动。只有需要强制固定设备时才设置 `MYTHE_DISPLAY_DRM_DEVICE=/dev/dri/cardN` 和 `MYTHE_DISPLAY_DRM_DEVICE_STRICT=1`。

`WLR_DRM_NO_ATOMIC=1` 和 `WLR_DRM_NO_MODIFIERS=1` 是默认兼容模式，用于规避部分长条屏/i915 组合在运行数分钟后出现 `Atomic commit failed: Device or resource busy` 并导致画面卡住。可以通过 `.env` 中的 `MYTHE_DISPLAY_DISABLE_DRM_ATOMIC=0` 或 `MYTHE_DISPLAY_DISABLE_DRM_MODIFIERS=0` 关闭。

并且 Chromium 会自动加上 root 运行需要的 `--no-sandbox`。

默认本地测试页启动时，脚本会先生成一次真实快照，再启动低频运行时采集器：

```text
public/runtime/disks.json       默认 12 小时刷新
public/runtime/telemetry.json   默认 10 分钟刷新
public/runtime/docker.json      默认 10 分钟刷新
public/runtime/weather-shenzhen.json 默认 30 分钟刷新
public/runtime/codex-agents.json 默认 5 分钟刷新
public/runtime/faio-listen.json 默认 10 秒刷新
```

这些文件已被 `.gitignore` 忽略。需要临时禁用采集器时可设置：

```bash
sudo MYTHE_DISPLAY_DISABLE_RUNTIME_COLLECTOR=1 MYTHE_DISPLAY_PORT=23456 scripts/run-kiosk-web-test.sh
```

Chromium 同时会禁用翻译 UI，并打开本机控制端口：

```text
--disable-translate
--disable-features=Translate,TranslateUI
--remote-debugging-address=127.0.0.1
--remote-debugging-port=23458
```

动态切换页面依赖 Chromium DevTools 控制端口。Firefox kiosk 可作为显示回退方案，但当前不支持 `scripts/kiosk-control.py`。

### Systemd 服务模式

安装：

```bash
sudo scripts/install-kiosk-service.sh
```

启动：

```bash
sudo systemctl start mythe-display-kiosk
```

查看日志：

```bash
journalctl -u mythe-display-kiosk -f
```

开机自启：

```bash
sudo systemctl enable mythe-display-kiosk
```

### 本地 TTY 普通用户模式

如果未来接键盘并在本机 TTY 登录，也可以普通用户运行：

```bash
scripts/run-kiosk-web-test.sh
```

如果默认端口被占用：

```bash
MYTHE_DISPLAY_PORT=23457 scripts/run-kiosk-web-test.sh
```

普通用户模式下，真正接管 HDMI 屏幕时，kiosk 命令最好在本地 tty 登录会话中运行。纯 SSH、VS Code Remote、Codex 后台会话通常没有 seat/DRM master 权限，即使用户在 `video` 组中也可能无法启动 compositor。

如果看到：

```text
Timeout waiting session to become active
Failed to start a DRM session
Unable to create the wlroots backend
```

优先检查：

```bash
id
tty
loginctl show-session "$XDG_SESSION_ID" -p Active -p Remote -p Seat -p TTY
```

期望：

```text
Active=yes
Remote=no
Seat=seat0
```

如果当前是 SSH、VS Code Remote 或 Codex 后台会话，通常不会满足这些条件。无头 NAS 应使用上面的 sudo direct DRM 模式或 systemd 服务模式。

也可以测试任意网页：

```bash
scripts/run-kiosk-web-test.sh https://example.com
```

脚本会自动检测 `cage`/`weston` 和浏览器。如果依赖缺失，会输出建议安装命令。

## 动态切换显示内容

kiosk 运行后可以使用 DevTools 控制端口切换当前页面：

```bash
mdp list
mdp current
mdp switch /kiosk-test/
mdp switch https://example.com
mdp reload
```

默认控制端口：

```text
MYTHE_DISPLAY_REMOTE_DEBUG_PORT=23458
```

该端口只绑定 `127.0.0.1`。如果未来要提供局域网控制入口，应由 Mythe Display 后端提供鉴权 API，再由后端调用本地控制端口。

安装为 systemd 服务后，可以直接刷新当前页面而不重启服务：

```bash
sudo systemctl reload mythe-display-kiosk
```

该命令对应服务模板中的 `ExecReload=scripts/kiosk-control.py reload`。它会创建一个刷新后的 Chromium page target，并关闭旧 target；这比 `systemctl restart` 更适合正在占用 HDMI/DRM 的 kiosk。

`mdp reload` 默认会追加 `assetCacheBust` 查询参数，避免 Chromium profile 使用旧 HTML 或旧主题资源。`scripts/run-kiosk-web-test.sh` 启动默认本地页面时也会追加该参数，可用 `MYTHE_DISPLAY_START_CACHE_BUST=0` 关闭。`scripts/serve-web-test.py` 会对本地 kiosk/runtime 响应发送 `Cache-Control: no-store`，发布调试时不应依赖浏览器缓存。

日常操作可直接使用短命令：

```bash
mdp start
mdp reload
mdp status
mdp logs
```

如果只安装了 `/usr/bin/mdp`，还没有安装 systemd 服务，`mdp start` 会自动安装并启动 `mythe-display-kiosk.service`。

## 主题和数据源预览参数

切换主题：

```text
http://<server-ip>:23456/kiosk-test/?theme=../themes/neon-dark/theme.json
```

默认数据源：

```text
http://<server-ip>:23456/kiosk-test/
```

该页面会优先读取 `/runtime/faio-listen.json`、`/runtime/disks.json`、`/runtime/telemetry.json`、`/runtime/docker.json`、`/runtime/weather-shenzhen.json`、`/runtime/codex-agents.json`。如果 runtime 文件还不存在，页面会回退到 `public/kiosk-test/*.mock.json`，便于开发预览。

切换 FAIO 一起听歌数据源：

```text
http://<server-ip>:23456/kiosk-test/?faioListen=/runtime/faio-listen.json
```

FAIO 一起听歌默认 10 秒刷新一次：

```text
http://<server-ip>:23456/kiosk-test/?faioListenRefreshMs=10000
```

默认房间通过本机 FAIO Webapp 代理访问：

```text
MYTHE_DISPLAY_FAIO_LISTEN_ROOM_URL=http://127.0.0.1:4173/listen/XatSqhcP6LmROQyKrjCULXyD-zcynwRZO5QaLO5Oeyg
MYTHE_DISPLAY_FAIO_LISTEN_DISPLAY_NAME=MytheNAS
```

副屏页面不直接跨端口访问 FAIO。`scripts/collect-faio-listen-snapshot.py` 负责维护私有房间 session，并写入 `/runtime/faio-listen.json`；`scripts/serve-web-test.py` 提供 `/faio-listen/media/<file_id>` 和 `/faio-listen/cover/<file_id>` 本地代理，让 kiosk 能读取音频和封面。

当前 NAS 的 ALSA 设备来自同一个 `HDA Intel PCH` 声卡：

```text
hw:0,0  ALCS1200A Analog   主板模拟音频口
hw:0,1  ALCS1200A Digital  数字音频口
hw:0,3  HDMI 0             当前在线 HDMI 副屏音频端点
hw:0,7  HDMI 1
hw:0,8  HDMI 2
```

`/proc/asound/card0/eld#2.3` 显示当前 HDMI 副屏上报了 2 声道 LPCM 音频能力。当前 NAS 默认设置为 `MYTHE_DISPLAY_ALSA_OUTPUT_DEVICE=plughw:0,3`，由 `scripts/faio-listen-audio-player.py` 使用 FFmpeg 直接输出到 HDMI ALSA 端点。这样可以绕过无桌面 snap Chromium 中 HTML audio 显示播放但不打开 ALSA PCM 的问题。

需要切换输出时可在 `.env` 中设置：

```bash
MYTHE_DISPLAY_ALSA_OUTPUT_DEVICE=plughw:0,3  # HDMI 副屏音频，推荐
MYTHE_DISPLAY_ALSA_OUTPUT_DEVICE=hw:0,0      # 主板模拟音频口
```

默认运行时会启动独立音频播放器，并给 kiosk 页面追加 `browserAudio=0`，让浏览器只负责显示播放状态。可用以下变量调整：

```bash
MYTHE_DISPLAY_DISABLE_FAIO_AUDIO_PLAYER=1  # 禁用独立音频播放器
MYTHE_DISPLAY_FAIO_BROWSER_AUDIO=1         # 保留浏览器内置 FAIO audio
MYTHE_DISPLAY_FAIO_AUDIO_POLL_MS=2000      # 独立播放器轮询快照间隔
```

修改后需要 `sudo mdp restart`，因为这是服务启动行为。

显式切换磁盘数据源：

```text
http://<server-ip>:23456/kiosk-test/?disks=/runtime/disks.json
```

磁盘组件默认 12 小时刷新一次：

```text
http://<server-ip>:23456/kiosk-test/?disksRefreshMs=43200000
```

生成一次真实运行时快照：

```bash
scripts/collect-runtime-snapshots.py --once --pretty
```

持续生成真实运行时快照：

```bash
scripts/collect-runtime-snapshots.py
```

切换 Docker 状态数据源：

```text
http://<server-ip>:23456/kiosk-test/?docker=/api/docker/summary
```

切换 Telemetry 趋势数据源：

```text
http://<server-ip>:23456/kiosk-test/?telemetry=/api/system/telemetry
```

切换天气数据源：

```text
http://<server-ip>:23456/kiosk-test/?weather=/runtime/weather-shenzhen.json
```

天气组件默认 30 分钟刷新一次：

```text
http://<server-ip>:23456/kiosk-test/?weatherRefreshMs=1800000
```

切换 Agent 状态数据源：

```text
http://<server-ip>:23456/kiosk-test/?agents=/api/agents/pixel
```

调整 Agent 轮询间隔：

```text
http://<server-ip>:23456/kiosk-test/?agentsRefreshMs=300000
```

## 推荐安装

Ubuntu 24.04 上建议优先测试：

```bash
sudo apt install cage chromium-browser
```

如果 snap 版 Chromium 在 kiosk 环境中不稳定，可改用 Firefox：

```bash
sudo apt install cage firefox
```

或者使用 Weston：

```bash
sudo apt install weston chromium-browser
```

## 生产预期

最终 systemd 启动顺序应是：

1. 启动 Mythe Display 本地 Web 服务。
2. 启动 kiosk compositor。
3. 启动浏览器 kiosk 模式打开本地 URL。
4. 浏览器只显示页面内容，不显示地址栏、标签栏或控制按钮。
