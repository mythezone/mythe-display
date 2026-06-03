# ADR 0001: Build a Custom Web-kiosk Runtime

Date: 2026-06-03

Status: Accepted

## Context

The project needs an Ubuntu secondary-screen display system for a PC case. Required customization includes display dimensions/resolution, layout regions, replaceable components, and a consistent component-authoring standard.

Existing projects are useful but incomplete:

- MagicMirror² has the best module/kiosk precedent but its layout and component contracts do not fully match this use case.
- Turing Smart Screen Python is excellent for supported USB smart screens but is not a generic monitor renderer.
- Conky and Eww are powerful Linux-native widget tools but would make a reusable component SDK harder.
- Grafana, Netdata, and Glances are strong for metrics but not optimized for a polished small hardware panel UI.

## Decision

Build Mythe Display as a custom web-kiosk runtime in this repository.

The initial implementation should target normal Ubuntu secondary monitors over HDMI/DisplayPort. USB output will be treated as a hardware transport question:

- USB-C DP Alt Mode/USB4/Thunderbolt: normal monitor path.
- DisplayLink: normal monitor path after driver installation.
- USB smart screen: future optional protocol renderer.

## Planned Technical Shape

- Frontend: React + TypeScript.
- Runtime: Chromium kiosk first; optional Electron/Tauri wrapper later only if packaging or multi-display control requires it.
- Backend: local Node.js metrics service with WebSocket updates.
- Config: declarative display/layout/component files.
- Components: manifest-driven folders with schema, typed props, and design tokens.
- Docs: all architecture, setup, and change records saved under `docs/` and `CHANGELOG.md`.

## Consequences

Positive:

- Full control over screen geometry, layout model, component contract, and visual design.
- Easier to make other users reproduce the same display with configuration files.
- Can integrate data from native collectors, Glances, Netdata, Prometheus, scripts, or device-specific adapters.

Tradeoffs:

- More implementation work than using MagicMirror² directly.
- We must build the component SDK, preview workflow, and metrics service ourselves.
- Hardware-specific USB smart screen support will need separate renderer work.

## First Milestone Definition

The first useful release should include:

- A runnable full-screen preview.
- One sample 800x480 and one 1024x600 layout.
- Core components: clock, CPU, memory, disk, network, temperature, fan/GPU placeholder.
- A documented component manifest and example custom component.
- Ubuntu kiosk launch notes.
