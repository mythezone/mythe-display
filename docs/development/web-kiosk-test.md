# Web Kiosk 测试说明

日期：2026-06-03

## 目标

验证 Mythe Display 的主界面可以作为网页内容运行，并在生产模式中以无浏览器控制条方式显示到唯一 HDMI 屏。

## 当前状态

仓库已提供一个静态测试页：

- [public/kiosk-test/index.html](../../public/kiosk-test/index.html)

该页面不依赖构建工具，可通过 Python 静态服务器预览。

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

安装依赖后可运行：

```bash
scripts/run-kiosk-web-test.sh
```

如果默认端口被占用：

```bash
MYTHE_DISPLAY_PORT=23457 scripts/run-kiosk-web-test.sh
```

注意：真正接管 HDMI 屏幕时，kiosk 命令最好在本地 tty 登录会话中运行，或后续由 systemd 服务管理。纯 SSH、VS Code Remote、Codex 后台会话通常没有 seat/DRM master 权限，即使用户在 `video` 组中也可能无法启动 compositor。

不要使用 `sudo` 运行：

```bash
scripts/run-kiosk-web-test.sh
```

不要这样运行：

```bash
sudo scripts/run-kiosk-web-test.sh
```

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

如果当前是 SSH、VS Code Remote 或 Codex 后台会话，通常不会满足这些条件。请在本机屏幕的 `tty1` 登录后运行脚本。若服务器没有可用的本地 logind session，可再评估安装并启用 `seatd`。

也可以测试任意网页：

```bash
scripts/run-kiosk-web-test.sh https://example.com
```

脚本会自动检测 `cage`/`weston` 和浏览器。如果依赖缺失，会输出建议安装命令。

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
