# 开源项目调研

日期：2026-06-03

范围：调研已有开源项目，判断它们是否适合用来构建 Ubuntu 机箱副屏系统监控/信息展示项目。

## 结论摘要

目前没有发现完全满足需求的开源项目。核心需求包括：任意屏幕几何配置、按区域放置组件、组件本身可快速自建且风格统一、Ubuntu 友好部署，以及兼容 HDMI 或可行 USB 显示路径。

最佳路线：在本仓库中自研 Mythe Display 运行时。架构上参考 MagicMirror² 的模块化屏幕组合方式，同时吸收 Grafana 的面板契约和 Turing Smart Screen Python 的主题配置思路。

## 对比矩阵

| 项目 | 能达到的效果 | 定制能力 | 与本项目匹配度 | 主要限制 |
| --- | --- | --- | --- | --- |
| MagicMirror² | 全屏智能镜/信息屏，可显示时钟、天气、新闻、日历和社区模块。 | 高。支持模块配置、位置配置、自定义 CSS、自定义模块和 Electron 运行。 | 很适合作为模块化 kiosk 参考。 | 默认布局是固定区域模型，偏智能镜场景；类型化组件契约和任意网格布局需要重做。 |
| Turing Smart Screen Python | 驱动部分 USB 小屏，直接渲染系统指标和主题。 | 中高。支持 YAML 主题、主题编辑器、自定义 Python 数据源。 | 如果硬件是受支持的 Turing/XuanFang/TURZX 类小屏，非常接近。 | 不是通用视频输出；依赖具体屏幕协议和分辨率。 |
| Conky | Linux 桌面系统监控，可显示文字、条形图、曲线、Lua 绘制内容。 | 高但偏底层。通过配置、Lua、脚本、字体和颜色定制。 | 适合快速原型和视觉参考。 | 现代组件模型弱，Wayland 有限制，难以形成可复用组件 SDK。 |
| Eww | Linux 自定义小组件系统，支持窗口、几何位置、可复用 widget 和 CSS/SCSS。 | 高。使用 `yuck` 定义 widget/window，使用 SCSS 定义样式。 | 对 Linux 原生 widget 布局有参考价值。 | 数据层需要自行拼装；GTK 样式/布局不如 Web 生态适合设计系统。 |
| Glances | 终端或 Web 实时系统监控。 | 低到中。可控制显示项并提供 API。 | 很适合作为早期指标数据源或原型。 | 视觉和布局定制不够，难以做精致副屏。 |
| Netdata | 丰富的实时监控面板，自动发现系统指标。 | 中。监控能力强，自定义面板偏产品化且较重。 | 适合作为可选数据源或指标覆盖参考。 | 对小尺寸固定副屏过重，视觉难以像素级控制。 |
| Grafana + Prometheus/node_exporter | 强大的数据面板和插件生态。 | 很高。支持面板、插件、dashboard-as-code。 | 适合作为面板契约和配置思想参考。 | 技术栈重，UI 偏运维 BI，不适合直接作为机箱副屏体验。 |

## MagicMirror²

来源：[MagicMirrorOrg/MagicMirror](https://github.com/MagicMirrorOrg/MagicMirror)、[模块配置文档](https://docs.magicmirror.builders/modules/configuration.html)、[模块开发文档](https://docs.magicmirror.builders/module-development/introduction.html)

MagicMirror² 是最接近本项目架构需求的现成项目。它是开源模块化智能镜平台，使用 Electron 作为应用壳，并拥有成熟的社区模块生态。它的配置支持模块、位置，例如 `top_left`、`top_right`、`bottom_bar`、`fullscreen_above`，也支持额外 CSS class。通过调整 HTML/CSS 还可以增加自定义位置。模块开发基于前端模块文件、可选的 `node_helper.js`，并通过 `getDom()` 或 Nunjucks 模板渲染。

效果示例：

![MagicMirror header](https://github.com/MagicMirrorOrg/MagicMirror/raw/master/.github/header.png)

![MagicMirror demo](https://magicmirror.builders/img/demo.gif)

![MagicMirror regions](https://docs.magicmirror.builders/assets/regions.DikKUofc.png)

评估：

- 优点：kiosk/智能显示模式成熟，Electron 打包可参考，模块生态丰富。
- 优点：可以开发并分发自定义模块。
- 问题：默认区域模型不如面向机箱副屏的像素/网格/卡片布局灵活。
- 问题：不是类型化配置和 schema 优先的组件体系，组件规范需要重新设计。

## Turing Smart Screen Python

来源：[mathoudebine/turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python)、[主题 wiki](https://github.com/mathoudebine/turing-smart-screen-python/wiki/System-monitor-%3A-themes)

该项目面向 Turing Smart Screen、XuanFang、TURZX 等 USB-C 小屏。它支持 Linux、Windows、macOS，可通过 GUI 向导或 `config.yaml` 配置屏幕，支持多种硬件指标、共享 YAML 主题、主题编辑器和自定义 Python 数据源。

效果示例：

![Turing theme preview 1](https://github.com/mathoudebine/turing-smart-screen-python/raw/main/res/themes/3.5inchTheme2/preview.png)

![Turing theme preview 2](https://github.com/mathoudebine/turing-smart-screen-python/raw/main/res/themes/Cyberpunk/preview.png)

![Turing community theme](https://user-images.githubusercontent.com/79225820/203648707-6f043068-5c9d-454d-9c0a-3d9ea02ece77.jpg)

评估：

- 优点：如果目标硬件是 USB 协议小屏，这是最接近的现成方案。
- 优点：YAML 主题和主题编辑器值得借鉴。
- 问题：它不是通用第二显示器渲染器。
- 问题：自定义主要围绕主题和数据源，不是完整 UI 组件 SDK。

## Conky

来源：[brndnmtthws/conky](https://github.com/brndnmtthws/conky)

Conky 是轻量 Linux 系统监控工具，主要面向 X 环境，Wayland 下有额外限制。它支持控制台、文件、HTTP 输出，内置大量对象，也可通过 Lua、Imlib2/Cairo 绘制文本、条形图、曲线、字体、颜色和鼠标事件。

效果示例：

![Conky screenshot 1](https://github.com/brndnmtthws/conky/wiki/configs/brenden/screenshot-thumb.png)

![Conky screenshot 2](https://github.com/brndnmtthws/conky/wiki/configs/ke49/screenshot-thumb.png)

![Conky screenshot 3](https://github.com/brndnmtthws/conky/wiki/configs/jc/screenshot-thumb.png)

评估：

- 优点：轻、快，适合展示系统传感器文字和简单图表。
- 优点：可通过桌面工具放到第二显示器上。
- 问题：现代组件 authoring、主题一致性和 schema 校验较难做好。

## Eww

来源：[elkowar/eww](https://github.com/elkowar/eww)、[配置文档](https://elkowar.github.io/eww/configuration.html)

Eww 是基于 Rust 的 Linux 独立 widget 系统。它使用 `yuck` 定义 widget/window，使用 CSS/SCSS 定义样式。窗口配置可以指定显示器、几何尺寸、宽高、锚点、层级和 Wayland layer 选项。

效果示例：

![Eww bar](https://github.com/elkowar/eww/raw/master/examples/eww-bar/eww-bar.png)

![Eww dashboard example](https://raw.githubusercontent.com/adi1090x/widgets/main/previews/dashboard.png)

评估：

- 优点：Linux 原生 widget 能力强，自定义程度高。
- 优点：可复用 widget 定义和显示器几何配置符合部分需求。
- 问题：传感器/数据源层需要自行建设。
- 问题：GTK CSS 限制较多，不如 Web 技术适合建立统一设计系统。

## Glances

来源：[nicolargo/glances](https://github.com/nicolargo/glances)

Glances 是跨平台开源监控工具，支持终端、Web、API、client/server 和导出模式。安装简单，能快速提供实时系统指标。

效果示例：

![Glances terminal](https://github.com/nicolargo/glances/raw/develop/docs/_static/glances-summary.png)

![Glances web](https://github.com/nicolargo/glances/raw/develop/docs/_static/screenshot-web.png)

评估：

- 优点：最快获得真实系统数据和 API 的方式之一。
- 优点：可嵌入或作为指标数据提供方。
- 问题：视觉定制能力不足，不能直接满足目标产品体验。

## Netdata

来源：[netdata/netdata](https://github.com/netdata/netdata)

Netdata 是开源实时基础设施监控平台，支持自动发现仪表盘、秒级指标、告警、异常检测、内置 dashboard、REST API 和可选云端功能。

在线演示：[Netdata demo 列表](https://github.com/netdata/netdata#live-demo-sites)

评估：

- 优点：指标覆盖最完整，接入成本低。
- 优点：适合作为可选数据源。
- 问题：功能范围和 UI 密度远超小型机箱副屏需要。

## Grafana

来源：[grafana/grafana](https://github.com/grafana/grafana)、[面板概览](https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/panel-overview/)、[面板插件教程](https://grafana.com/developers/plugin-tools/tutorials/build-a-panel-plugin)

Grafana 面板是基于查询的数据可视化单元，支持转换、可视化配置和插件。Grafana 支持面板插件、数据源插件和应用插件，面板插件会接收宽高等尺寸信息。

效果示例：

![Grafana sample dashboard](https://upload.wikimedia.org/wikipedia/commons/thumb/3/3b/Grafana_screenshot_%282018%29.png/1280px-Grafana_screenshot_%282018%29.png)

评估：

- 优点：面板/插件模型成熟，dashboard-as-code 思路非常值得借鉴。
- 优点：如果目标是可观测性 dashboard，它非常强。
- 问题：作为机箱副屏直接使用过重，视觉风格也偏通用运维。

## 推荐结论

不要把任一现成项目作为主代码库直接 fork。建议在本仓库中自研 Mythe Display Web kiosk 应用，并以 MagicMirror² 作为最接近的架构参考。

建议借鉴：

- MagicMirror²：模块化运行时和 kiosk 部署方式。
- Grafana：组件/面板 manifest、尺寸传入、数据契约和可检查配置。
- Turing Smart Screen Python：主题分享、主题预览和配置编辑器思路。
- Netdata/Glances：在需要时作为指标适配器。

这样最有机会满足完整需求，同时不会被现成项目的场景假设限制。
