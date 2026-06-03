# Open-source Options Research

Date: 2026-06-03

Scope: existing open-source projects that can help build or inspire an Ubuntu chassis secondary-screen system monitor/dashboard.

## Summary

No reviewed project fully satisfies the requirement set: arbitrary screen geometry, per-region configurable components, a first-class component creation standard, Ubuntu-friendly deployment, and a clean path for either HDMI or supported USB displays.

Best path: build a custom Mythe Display runtime, using MagicMirror² as the closest architectural reference and borrowing discipline from Grafana panels and Turing Smart Screen themes.

## Comparison Matrix

| Project | What it can achieve | Customization | Fit for this project | Main limits |
| --- | --- | --- | --- | --- |
| MagicMirror² | Full-screen modular smart-display UI with clock/weather/news/calendar/community modules. | High. Configured modules, positions, custom CSS, custom module development, Electron runtime. | Strong reference for module ecosystem and kiosk display. | Built around fixed regions and smart-mirror assumptions; not chassis-monitor first; custom layout/typed component contract would need adaptation. |
| Turing Smart Screen Python | Drives supported small USB smart screens and renders system metrics/themes directly to the panel. | Medium-high for supported screens. Theme YAML, theme editor, custom Python data sources. | Excellent if the hardware is a supported Turing/XuanFang/TURZX-style USB serial screen. | Not generic video output; limited to supported screen protocols and resolutions. |
| Conky | Lightweight Linux desktop system monitor with text, bars, graphs, Lua drawing. | High but low-level. Config files, Lua, scripts, fonts/colors. | Useful for quick prototypes and visual inspiration. | Weak modern component model; Wayland caveats; hard to offer a reusable third-party component standard. |
| Eww | Linux custom widget system with windows, geometry, reusable widgets, CSS/SCSS styling. | High. `yuck` widgets, window geometry, monitor targeting, SCSS. | Interesting for native Linux widget layouts. | GTK CSS/layout limitations; not designed as a shareable chassis-dashboard app; sensor/data layer must be assembled separately. |
| Glances | Terminal or web dashboard for real-time system metrics. | Low-medium. Can filter/customize what is shown; exposes API. | Very fast data-source/prototype option. | Visual style and layout are not highly customizable enough for a polished side panel. |
| Netdata | Rich real-time monitoring dashboard with auto-discovery and per-second metrics. | Medium. Great monitoring; custom dashboards are more product-specific and heavier. | Good optional data provider or reference for metrics coverage. | Too broad/heavy for a tiny fixed screen; less suited to pixel-perfect custom UI. |
| Grafana + Prometheus/node_exporter | Highly capable dashboard and panel ecosystem. | Very high for data/panels/plugins. | Strong reference for panel contract and dashboard-as-code. | Heavy stack; UI is operational/BI oriented, not ideal for chassis display aesthetics. |

## MagicMirror²

Source: [MagicMirrorOrg/MagicMirror](https://github.com/MagicMirrorOrg/MagicMirror), [module configuration docs](https://docs.magicmirror.builders/modules/configuration.html), [module development docs](https://docs.magicmirror.builders/module-development/introduction.html)

MagicMirror² is the closest existing architectural fit. It is an open-source modular smart mirror platform, uses Electron as the application wrapper, and has an established module ecosystem. Its configuration supports modules, positions such as `top_left`, `top_right`, `bottom_bar`, `fullscreen_above`, and additional CSS classes. Custom positions can be added with matching HTML/CSS changes. Module development is based on frontend module files, optional `node_helper.js`, and rendering through `getDom()` or Nunjucks templates.

Effect examples:

![MagicMirror header](https://github.com/MagicMirrorOrg/MagicMirror/raw/master/.github/header.png)

![MagicMirror demo](https://magicmirror.builders/img/demo.gif)

![MagicMirror regions](https://docs.magicmirror.builders/assets/regions.DikKUofc.png)

Assessment:

- Good: proven kiosk/smart-display model, Electron packaging, many modules, strong community.
- Good: custom modules can be built and distributed.
- Concern: its region model is less flexible than a pixel/grid/card layout designed for arbitrary chassis panels.
- Concern: not typed/config-schema-first; component authoring can be looser than desired.

## Turing Smart Screen Python

Source: [mathoudebine/turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python), [theme wiki](https://github.com/mathoudebine/turing-smart-screen-python/wiki/System-monitor-%3A-themes)

This project targets small USB-C smart screens such as Turing Smart Screen, XuanFang, and TURZX. It supports Linux, Windows, and macOS, configurable display setup through a GUI wizard or `config.yaml`, multiple hardware metrics, shared YAML themes, a theme editor, and custom Python data sources.

Effect examples:

![Turing theme preview 1](https://github.com/mathoudebine/turing-smart-screen-python/raw/main/res/themes/3.5inchTheme2/preview.png)

![Turing theme preview 2](https://github.com/mathoudebine/turing-smart-screen-python/raw/main/res/themes/Cyberpunk/preview.png)

![Turing community theme](https://user-images.githubusercontent.com/79225820/203648707-6f043068-5c9d-454d-9c0a-3d9ea02ece77.jpg)

Assessment:

- Good: closest match for USB-connected non-video mini screens.
- Good: theme YAML and theme editor are worth copying conceptually.
- Concern: it is not a generic secondary monitor renderer.
- Concern: component customization is theme/data-source oriented, not a full UI component SDK.

## Conky

Source: [brndnmtthws/conky](https://github.com/brndnmtthws/conky)

Conky is a lightweight Linux system monitor for X, with Wayland caveats, console/file/HTTP output options, many built-in objects, Lua extensions, and drawing support through Imlib2/Cairo. It can display text, bars, graphs, fonts, colors, and mouse events.

Effect examples:

![Conky screenshot 1](https://github.com/brndnmtthws/conky/wiki/configs/brenden/screenshot-thumb.png)

![Conky screenshot 2](https://github.com/brndnmtthws/conky/wiki/configs/ke49/screenshot-thumb.png)

![Conky screenshot 3](https://github.com/brndnmtthws/conky/wiki/configs/jc/screenshot-thumb.png)

Assessment:

- Good: fast, tiny, excellent for sensor text/graphs.
- Good: can be positioned on a second display with normal desktop tooling.
- Concern: modern component authoring, theming consistency, and schema validation would be hard.

## Eww

Source: [elkowar/eww](https://github.com/elkowar/eww), [configuration docs](https://elkowar.github.io/eww/configuration.html)

Eww is a Rust-based standalone widget system for Linux. It uses `yuck` for widget/window definitions and CSS/SCSS for styling. Its window config can target monitors and define geometry, width, height, anchors, stacking, and Wayland layer options.

Effect examples:

![Eww bar](https://github.com/elkowar/eww/raw/master/examples/eww-bar/eww-bar.png)

![Eww dashboard example](https://raw.githubusercontent.com/adi1090x/widgets/main/previews/dashboard.png)

Assessment:

- Good: very customizable Linux-native widgets.
- Good: reusable widget definitions and monitor geometry fit the display requirement.
- Concern: sensor/data source and packaging would be our responsibility.
- Concern: GTK CSS limitations make a web-style design system harder.

## Glances

Source: [nicolargo/glances](https://github.com/nicolargo/glances)

Glances is a cross-platform open-source monitoring tool with terminal, web, API, client/server, and export modes. It is easy to install and exposes a useful real-time metrics surface.

Effect examples:

![Glances terminal](https://github.com/nicolargo/glances/raw/develop/docs/_static/glances-summary.png)

![Glances web](https://github.com/nicolargo/glances/raw/develop/docs/_static/screenshot-web.png)

Assessment:

- Good: quickest way to get real data and an API.
- Good: can be embedded or used as a metrics provider.
- Concern: not visually customizable enough for the target product experience.

## Netdata

Source: [netdata/netdata](https://github.com/netdata/netdata)

Netdata is an open-source real-time infrastructure monitoring platform with auto-discovered dashboards, per-second metrics, alerts, anomaly detection, an embedded dashboard, REST APIs, and optional cloud features.

Live demos: [Netdata demo list](https://github.com/netdata/netdata#live-demo-sites)

Assessment:

- Good: best metrics coverage and low setup friction.
- Good: useful as an optional data source.
- Concern: UI density and product scope are much larger than a small case-mounted panel needs.

## Grafana

Source: [grafana/grafana](https://github.com/grafana/grafana), [panel overview](https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/panel-overview/), [panel plugin tutorial](https://grafana.com/developers/plugin-tools/tutorials/build-a-panel-plugin)

Grafana panels are query-backed visualizations with transformations and visualization options. Grafana supports panel, data source, and app plugins, and panel plugins receive dimensions such as width and height.

Effect example:

![Grafana sample dashboard](https://upload.wikimedia.org/wikipedia/commons/thumb/3/3b/Grafana_screenshot_%282018%29.png/1280px-Grafana_screenshot_%282018%29.png)

Assessment:

- Good: mature panel/plugin model and dashboard-as-code ideas.
- Good: excellent if the goal is observability rather than a polished mini display.
- Concern: too heavy and visually generic for the intended chassis display.

## Recommendation

Do not fork any reviewed project as the primary codebase. Build Mythe Display as a custom web-kiosk app and treat MagicMirror² as the closest reference.

Borrow:

- MagicMirror²: module-first runtime and kiosk deployment.
- Grafana: component/panel manifest, dimensions, data contracts, inspectable config.
- Turing Smart Screen Python: theme sharing and simple preview/editor workflow.
- Netdata/Glances: metrics adapters where useful.

This gives the best chance to satisfy all core requirements without fighting the assumptions of an existing tool.
