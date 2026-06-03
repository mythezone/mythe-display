# Mythe Display

Mythe Display is a planned Ubuntu chassis secondary-screen project. The goal is a reproducible, highly customizable display runtime for small HDMI/USB displays mounted in a PC case.

Current status: research and architecture planning. No runnable display app has been implemented yet.

## Goals

- Run on Ubuntu as a kiosk-style secondary display.
- Support arbitrary display size, resolution, pixel density, rotation, and safe-area settings.
- Let users define layouts as configuration, not by editing application code.
- Let each region host replaceable components.
- Let components follow a stable manifest and runtime interface so new widgets are quick to build and visually consistent.
- Preserve research notes, architecture decisions, technical docs, and change history in this repository.

## Recommended Direction

Build a custom web-kiosk runtime in this repo, inspired by these projects:

- MagicMirror² for module-driven screen composition.
- Grafana for panel contracts, dashboard-as-code, and plugin discipline.
- Turing Smart Screen Python for shareable themes and a simple editor-first workflow.
- Netdata/Glances for optional metrics data sources.

The first implementation should prefer HDMI output because it is native, reliable, and driver-light. If a one-cable USB display is mandatory, use a USB-C DP Alt Mode capable port/monitor or a DisplayLink-based USB graphics device. A normal data-only USB-C motherboard port cannot be converted into native video output by software alone.

## Documentation

- [Open-source options research](docs/research/open-source-options.md)
- [Display output options](docs/research/display-output-options.md)
- [Recommended architecture decision](docs/decisions/0001-build-custom-web-kiosk.md)
- [Component system draft](docs/development/component-system.md)
- [Roadmap](docs/development/roadmap.md)
- [Documentation policy](docs/development/documentation-policy.md)
- [Changelog](CHANGELOG.md)

## Target Architecture

Planned runtime:

- Frontend: React + TypeScript rendered full-screen in Chromium or an optional desktop shell.
- Backend: local Node.js service that collects system metrics and exposes WebSocket/REST data streams.
- Configuration: declarative display and layout files under `config/`.
- Components: self-contained folders with `manifest.json`, typed props, and a React entrypoint.
- Packaging: systemd user service plus kiosk launch scripts for Ubuntu.

Planned component contract:

```text
components/<component-id>/
  manifest.json
  index.tsx
  schema.json
  README.md
```

Each component will declare its inputs, refresh behavior, size expectations, theming support, and fallback state.

## Hardware Guidance

Preferred:

- Small HDMI panel, connected to GPU or motherboard HDMI/DP output.
- Ubuntu sees it as a normal secondary monitor.

Acceptable:

- USB-C display only if the source port supports DP Alt Mode/USB4/Thunderbolt video.
- DisplayLink USB monitor/adapter if you accept proprietary driver and Ubuntu compatibility risk.

Not recommended as the primary path:

- Generic USB-C data-only motherboard port.
- USB serial smart screens unless using a protocol-specific renderer.

## Local Setup

At this stage there is nothing to run. For future local setup:

1. Copy `.env.example` to `.env`.
2. Install project dependencies once implementation begins.
3. Configure display geometry and components in `config/`.
4. Run the local preview.
5. Install the kiosk/systemd service for production use.

## Repository Rules

- Keep secrets in `.env`; never commit them.
- Keep user-facing setup steps in this README.
- Save durable research and technical decisions in `docs/`.
- Update `CHANGELOG.md` for material repository changes.
- Commit and push after each completed user-facing turn when Git access is available.
