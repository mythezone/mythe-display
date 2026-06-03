# 无桌面 Ubuntu Kiosk 可行性评估

日期：2026-06-03

## 结论

可行。

当前服务器虽未安装完整 Ubuntu 图形界面，但内核已经通过 `i915` 暴露了 DRM connector 和 `/dev/fb0`。已连接的 HDMI 长条屏是 `card0-HDMI-A-2`，当前 framebuffer 为 `3840x1100`、`32bpp`。后续测试确认：直接写 `/dev/fb0` 会改变 framebuffer 内存，但不可靠地改变屏幕可见画面；通过 DRM/KMS 设置 scanout 可以成功显示纯色和色条。这意味着：

- 可以用 DRM/KMS 做最小硬件控制验证，例如纯色填充、色条测试。
- framebuffer 只能作为内存诊断，不应作为真实屏幕控制依据。
- 可以在不安装完整桌面环境的情况下，用极简 kiosk 图形栈运行全屏网页。
- 开发时可以继续使用普通浏览器访问本地 dev server，实时预览布局和组件。

## 分层路线

### 1. DRM/KMS 颜色测试

用途：证明程序能控制屏幕像素。

优点：

- 不需要 Xorg、Wayland、桌面环境或浏览器。
- 很适合首个硬件连通性测试。
- 设置的是真实 scanout，比 fbdev emulation 可靠。

限制：

- 只适合底层测试或非常简单的原生渲染。
- 不适合长期开发复杂 UI、动画、组件系统和网页预览。

当前测试脚本：

```bash
python3 scripts/kms-color-test.py info
sg video -c "python3 scripts/kms-color-test.py fill --connector card0-HDMI-A-2 --mode 3840x1100 --color '#0047ff' --duration 5 --restore"
sg video -c "python3 scripts/kms-color-test.py bars --connector card0-HDMI-A-2 --mode 3840x1100 --duration 5 --restore"
```

`scripts/fb-color-test.py` 仍保留，用于读取和诊断 `/dev/fb0`，但不作为可见屏幕控制测试。

### 2. 极简 Wayland kiosk + 浏览器

用途：生产方向。启动后直接在唯一 HDMI 屏上显示全屏网页界面。

建议形态：

```text
systemd
  -> mythe-display 本地服务
    -> 本地 Web UI: http://127.0.0.1:<port>
    -> cage 或 weston kiosk compositor
      -> chromium/firefox --kiosk
```

优点：

- 不需要完整桌面环境。
- UI 就是网页，便于 React/Vite 开发和远程浏览器预览。
- 布局、组件、主题、插件都可以走 Web 生态。
- 与其他项目集成简单，用户也容易理解。

需要补充的系统依赖：

- kiosk compositor：优先评估 `cage`，备选 `weston`。
- 浏览器：Chromium 或 Firefox kiosk 模式。
- 权限：运行用户需要访问 DRM/render/input 设备，通常加入 `video`、`render`、`input` 组，或通过 seatd/logind 正确授予。
- 运行位置：优先从本地 active TTY 启动，不要用 `sudo` 从 SSH 会话启动；否则 wlroots 可能无法取得 DRM session。

### 3. DRM/KMS 原生渲染

用途：如果未来浏览器栈过重，或需要更强底层控制，可考虑原生 DRM/KMS 渲染。

优点：

- 不依赖浏览器。
- 启动快、控制强。

限制：

- UI/组件生态需要自建，开发效率远低于 Web。
- 不符合“网页端实时预览”的目标。

## 推荐实现路径

第一阶段：

1. 使用 `scripts/kms-color-test.py` 验证能控制 HDMI scanout。
2. 记录当前屏幕真实分辨率 `3840x1100`。
3. 搭建 Web UI 预览服务，先用浏览器访问。
4. 增加一个纯色页面/布局页面，作为网页层的第二个测试。

第二阶段：

1. 安装并验证 `cage` 或 `weston`。
2. 用命令启动全屏浏览器：

   ```bash
   scripts/run-kiosk-web-test.sh
   ```

3. 根据实际 Ubuntu 包和浏览器来源调整命令。
4. 增加 systemd 服务，实现开机自动运行。

第三阶段：

1. 定义组件 manifest、schema 和运行时 props。
2. 增加插件目录和 git 仓库安装机制。
3. 实现组件热加载/重载。
4. 实现布局编辑和组件预览。

## 需要注意的风险

- Ubuntu Server 上的 Chromium 可能来自 snap，和极简 Wayland kiosk 的组合需要实机验证。
- 唯一显示设备上运行 kiosk 后，调试最好通过 SSH 或 Web 远程预览进行，避免把本地 TTY 完全遮住后难以操作。
- 权限必须设计清楚。开发阶段可以用 `sudo` 做 framebuffer 测试，生产阶段应使用固定用户和 systemd/seatd/logind 授权。
