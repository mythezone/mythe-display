# 当前本机显示设备记录

日期：2026-06-03

本文件记录当前服务器上实际连接的显示设备信息，用于后续开发时避免只停留在抽象假设。

## 系统环境

- 主机名：`mythenas`
- 内核：`Linux 6.8.0-117-generic`
- 显卡：
  - Intel UHD Graphics 630，驱动 `i915`
  - NVIDIA Tesla P4，驱动 `nvidia`，作为 3D controller 暴露
- 当前没有检测到 `xrandr`、`weston`、`chromium`、`cage`、`sway`、`modetest`、`fbset` 等桌面/kiosk 辅助命令。

## 已连接显示器

DRM connector：

- `card0-HDMI-A-1`：`disconnected`
- `card0-HDMI-A-2`：`connected`
- `card0-DP-1`：`disconnected`

已连接屏幕：

- connector：`card0-HDMI-A-2`
- 状态：`connected`
- enabled：`enabled`
- DPMS：`On`
- 可用模式列表首项：`3840x1100`
- framebuffer：`/dev/fb0`
- framebuffer 名称：`i915drmfb`
- framebuffer 尺寸：`3840,1100`
- 色深：`32bpp`
- stride：`15360`
- EDID 显示名称：`HDMI`
- EDID 物理尺寸字段：约 `120cm x 34cm`

这与“长条形 HDMI 副屏作为唯一显示设备”的描述吻合。后续开发可先以 `3840x1100` 作为真实目标分辨率。

## 当前权限状态

`/dev/fb0` 权限：

```text
crw-rw---- root video /dev/fb0
```

当前用户 `mythezone` 不在 `video` 组，因此无法直接写 framebuffer。`sudo -n true` 返回需要密码，所以当前 Codex 会话不能无交互执行写屏测试。

要实际运行颜色测试，需要二选一：

```bash
sudo python3 scripts/fb-color-test.py fill --color '#0047ff' --duration 5 --restore
```

或将当前用户加入图形设备相关组后重新登录/重启：

```bash
sudo usermod -aG video,render,input mythezone
```

## 结论

技术上可以控制这块屏幕。最低层验证路径是直接写 `/dev/fb0`。生产图形界面不建议长期直接写 framebuffer，而建议使用最小 Wayland kiosk 运行本地网页界面。
