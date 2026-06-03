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

该能力依赖 Chromium DevTools HTTP API。Firefox kiosk 可以作为显示回退方案，但当前不支持 `scripts/kiosk-control.py` 动态切换。

控制脚本：

```bash
scripts/kiosk-control.py switch http://127.0.0.1:23456/kiosk-test/
```

查看当前页面：

```bash
scripts/kiosk-control.py list
scripts/kiosk-control.py current
```

切换到本地相对路径：

```bash
scripts/kiosk-control.py switch '/kiosk-test/?theme=../themes/neon-dark/theme.json'
```

切换到外部网页：

```bash
scripts/kiosk-control.py switch https://example.com
```

刷新当前页面，不重启服务：

```bash
scripts/kiosk-control.py reload
```

`reload` 默认会追加 `assetCacheBust=<timestamp>` 查询参数，配合测试页重新加载主题资源。它通过创建新 page target 并关闭旧 target 实现，不会重启 `cage`、Chromium 或 systemd 服务。

默认会关闭旧的 page target，只保留新页面。如果需要保留旧页面：

```bash
scripts/kiosk-control.py switch --keep-existing https://example.com
scripts/kiosk-control.py reload --keep-existing
```

注意：如果使用 zsh，带 `?`、`&` 的 URL 需要加引号，避免被 shell 当作通配符。

旧兼容脚本 `scripts/kiosk-switch-url.py` 仍可使用，但新开发默认使用 `scripts/kiosk-control.py`。

## 环境变量

```text
MYTHE_DISPLAY_PORT=23456
MYTHE_DISPLAY_HOST=127.0.0.1
MYTHE_DISPLAY_REMOTE_DEBUG_PORT=23458
MYTHE_DISPLAY_REMOTE_DEBUG_HOST=127.0.0.1
```

systemd 服务模板也使用同样默认值。

systemd 服务模板包含：

```ini
ExecReload=/home/mythezone/services/mythe/mythe-display/scripts/kiosk-control.py reload
```

因此服务安装后可以这样刷新当前界面：

```bash
sudo systemctl reload mythe-display-kiosk
```

这不是重启服务，不会释放再重新抢占 DRM seat。

## 测试页自动刷新参数

测试页支持可选 URL 参数：

```text
themeRefreshMs=30000
pageRefreshMs=900000
assetCacheBust=<timestamp>
```

- `themeRefreshMs`：定期重新读取 `theme.json`，并刷新主题资源 URL。
- `pageRefreshMs`：定期刷新整个页面，最小间隔为 60000ms。
- `assetCacheBust`：手动给主题资源追加 cache-bust 参数，常由 `kiosk-control.py reload` 自动添加。

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
