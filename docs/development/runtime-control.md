# 运行时控制规范草案

日期：2026-06-03

状态：草案

## 目标

Mythe Display 启动后，应支持通过命令或本地 API 动态切换显示内容。因为主显示层是 Web kiosk，最小可行方式就是切换当前 Chromium page 的 URL。

## 当前实现

`scripts/run-kiosk-web-test.sh` 启动 Chromium 时默认增加：

```text
--remote-debugging-address=127.0.0.1
--remote-debugging-port=23458
```

控制端口只绑定 `127.0.0.1`，避免直接暴露到局域网。

该能力依赖 Chromium DevTools HTTP API。Firefox kiosk 可以作为显示回退方案，但当前不支持 `scripts/kiosk-switch-url.py` 动态切换。

切换脚本：

```bash
scripts/kiosk-switch-url.py http://127.0.0.1:23456/kiosk-test/
```

查看当前页面：

```bash
scripts/kiosk-switch-url.py --list
```

切换到本地相对路径：

```bash
scripts/kiosk-switch-url.py /kiosk-test/?theme=../themes/neon-dark/theme.json
```

切换到外部网页：

```bash
scripts/kiosk-switch-url.py https://example.com
```

默认会关闭旧的 page target，只保留新页面。如果需要保留旧页面：

```bash
scripts/kiosk-switch-url.py --keep-existing https://example.com
```

## 环境变量

```text
MYTHE_DISPLAY_PORT=23456
MYTHE_DISPLAY_HOST=127.0.0.1
MYTHE_DISPLAY_REMOTE_DEBUG_PORT=23458
MYTHE_DISPLAY_REMOTE_DEBUG_HOST=127.0.0.1
```

systemd 服务模板也使用同样默认值。

## 设计边界

当前方式适合：

- 在多个本地 dashboard 页面之间切换。
- 临时打开某个监控网页。
- 开发时快速切换主题、布局、mock 数据。

不适合：

- 让局域网任意设备直接控制 kiosk。
- 通过 Chromium DevTools 传递敏感凭据。
- 作为长期公开 API。

## 后续正式 API

后续运行时服务应提供一个更稳定的控制 API：

```http
POST /api/display/route
Content-Type: application/json

{
  "url": "http://127.0.0.1:23456/dashboard/main",
  "reason": "manual-switch"
}
```

运行时服务内部再决定是调用 Chromium DevTools、WebSocket，还是直接在单页应用中切换 route。

## 禁用浏览器翻译 UI

当前 kiosk 启动脚本同时做了两层处理：

- 页面层：`html` 和 `body` 使用 `translate="no"`，并设置 `meta name="google" content="notranslate"`。
- Chromium 层：默认加 `--disable-translate`、`--disable-features=Translate,TranslateUI`、`--lang=zh-CN` 和 `--accept-lang=zh-CN,zh,en`。

如果右上角仍出现翻译气泡，优先删除 kiosk profile 后重启：

```bash
sudo rm -rf /tmp/mythe-display-kiosk-profile
sudo MYTHE_DISPLAY_PORT=23456 scripts/run-kiosk-web-test.sh
```
