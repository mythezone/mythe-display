# Ubuntu 显示输出方案

日期：2026-06-03

目标：判断 Ubuntu 主机能否通过 USB 给机箱副屏输出视频，并确定可行的备用路径。

## 简短结论

如果主板 USB-C 接口只是普通数据口，它不能仅靠软件配置输出原生视频。

想通过一根 USB 线实现视频显示，必须满足以下条件之一：

- USB-C 主机接口支持 DisplayPort Alt Mode、USB4 或雷电视频输出。
- 屏幕、扩展坞或转接器内部包含 DisplayLink 类 USB 显卡芯片，并且 Ubuntu 安装了兼容驱动。
- 屏幕本身不是通用视频显示器，而是协议型 USB 小屏，例如部分 Turing/XuanFang/TURZX 屏。

否则应使用 GPU 或主板的 HDMI/DisplayPort 输出。

## 为什么数据型 USB-C 不能变成视频口

VESA 对 DisplayPort Alt Mode 的说明是：USB-C 在支持该模式时，可以复用高速通道承载 DisplayPort 音视频信号，同时在部分配置中继续传输 USB 数据和供电。支持 DisplayPort Alt Mode 的视频源设备可以驱动 DisplayPort/HDMI/DVI/VGA 转接器。

来源：[VESA DisplayPort Alt Mode announcement](https://vesa.org/featured-articles/vesa-brings-displayport-to-new-usb-type-c-connector/)

实际含义：

- 只有 USB-C 接口形状不够。
- 主机接口、线缆、显示器或转接链路都必须支持对应视频模式。
- 如果主板说明书只把接口标为 USB 数据口，就应按“不支持视频输出”处理。

## 方案对比

| 方案 | Ubuntu 是否识别为普通显示器 | 线缆数量 | 可靠性 | 说明 |
| --- | --- | --- | --- | --- |
| HDMI/DisplayPort 小屏 | 是 | 通常 HDMI + 供电；机箱内可单独供电 | 最高 | 推荐默认方案。 |
| USB-C DP Alt Mode 小屏 | 是 | 若供电足够，可一根 USB-C 同时传视频和供电 | 高，前提是硬件支持 | 主机接口必须支持 DP Alt Mode/USB4/雷电。 |
| DisplayLink USB 显示器/转接器 | 是，但依赖 USB 显卡驱动 | 一根 USB 或 USB + 供电 | 中 | 使用 DisplayLink 芯片和驱动，不是原生 GPU 输出。 |
| Turing/XuanFang/TURZX USB 智能小屏 | 否，是协议级 framebuffer/控制命令 | 一根 USB | 对受支持型号中到高 | 需要库直接渲染到设备协议，不是普通桌面显示器。 |
| 数据型 USB-C 转 HDMI/USB-C 显示器 | 否 | 不适用 | 不可行 | 被动转接器需要 Alt Mode，软件无法补出缺失的 GPU 通道。 |

## Ubuntu 上的 DisplayLink

当主机没有原生 USB-C 视频路径，但屏幕或转接器包含 USB 显卡芯片时，DisplayLink 是实际可用的 USB 视频替代方案。

Synaptics 官方 DisplayLink Ubuntu 页面当前列出的最新 Ubuntu 驱动为 Release 6.2，发布日期 2025-09-11，面向 Ubuntu 20.04、22.04、23.04、24.04。

来源：[Synaptics DisplayLink Ubuntu downloads](https://drivers.synaptics.com/products/displaylink-graphics/downloads/ubuntu)

重要注意事项：

- 这是驱动依赖路径，不是原生 GPU 输出。
- 开启 Secure Boot 时，可能需要 DKMS/MOK 模块签名流程。Ubuntu 官方文档介绍了 Secure Boot 下第三方 DKMS 模块的 MOK 处理。
- 对比 Synaptics 页面列出的系统版本，更新版本 Ubuntu 的兼容性需要重新确认。
- DisplayLink 可能带来 CPU 占用和延迟。对静态指标副屏通常可以接受，但不适合高帧率动画。

来源：[Ubuntu Secure Boot documentation](https://documentation.ubuntu.com/security/docs/security-features/platform-protections/secure-boot/)、[DisplayLink Secure Boot support article](https://support.displaylink.com/knowledgebase/articles/1181617-how-to-use-displaylink-ubuntu-driver-with-uefi-sec)

## USB 智能小屏

部分机箱小屏以 USB-C 形式连接，但它们并不是通用视频显示器，而是使用 USB 串口/HID 协议和厂商绘图命令。Turing Smart Screen Python 对这类屏幕有价值，因为它封装了多种受支持屏幕协议，并能直接渲染主题和系统指标。

来源：[turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python)

这条路线适合 3.5 英寸左右的小屏，但它和“作为 Ubuntu 普通视频输出显示器”不是同一种模型。应用需要额外实现一个渲染后端，将画面帧或绘图命令发送到设备协议。

## 推荐硬件路径

第一版推荐：

1. 使用 HDMI 或 DisplayPort 小屏。
2. 根据屏幕情况从机箱内部 USB/SATA/Molex 等路径供电。
3. 让 Ubuntu 把它识别为普通第二显示器。
4. 将 Mythe Display 全屏运行在该显示器上。

如果必须一根 USB 线：

1. 查主板说明书，确认 USB-C 是否支持 DP Alt Mode、USB4 或雷电。
2. 如果不支持，选择 DisplayLink 显示器/转接器，并固定 Ubuntu/驱动兼容范围。
3. 不要在数据型 USB-C 口上使用普通 USB-C-to-HDMI 被动转接器。

实机验证步骤：

- 查看主板说明书和后置 I/O 标识，确认是否有 DP、Thunderbolt、USB4 等标识。
- 使用已知可用的 USB-C DP Alt Mode 显示器和全功能线缆测试。
- 在 Ubuntu 显示设置中确认屏幕是否出现为普通显示器。
- 对 DisplayLink，检查 `lsusb` 是否识别适配器，以及 DisplayLink/evdi 驱动是否加载。

## 对 Mythe Display 的影响

应用不应绑定具体 USB 传输方式。第一版应先渲染到普通浏览器窗口或全屏窗口。后续可以添加硬件适配层：

- `video-monitor`：默认浏览器/Electron 全屏渲染器。
- `displaylink-monitor`：安装驱动后仍按普通显示器处理。
- `turing-smart-screen`：未来为受支持 USB 智能小屏增加协议渲染器。
