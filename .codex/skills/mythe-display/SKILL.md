---
name: mythe-display
description: Use for all work in this repository: building an Ubuntu chassis secondary-screen display project, maintaining research/docs/changelog/README, protecting local secrets, and committing/pushing after each completed user-facing turn.
---

# Mythe Display Repository Workflow

## Core rules

- Communicate with the user in Chinese unless they ask otherwise.
- Treat this repo as an Ubuntu secondary-screen/kiosk display project.
- Keep `.env` and credentials private. Never print, document, or commit secrets.
- Save durable research under `docs/research/`.
- Save durable architecture choices under `docs/decisions/` as ADRs.
- Save implementation guides under `docs/development/`.
- Update `README.md` when setup, usage, architecture, or reproduction steps change.
- Update `CHANGELOG.md` for each meaningful repo change.

## Product direction

- Default renderer: web-kiosk app on a normal Ubuntu secondary monitor.
- Preferred output: HDMI/DisplayPort first.
- USB-C output only works as normal video when hardware supports DP Alt Mode, USB4, or Thunderbolt.
- DisplayLink is an optional USB graphics fallback with driver/version caveats.
- USB smart screens require protocol-specific renderers and should be treated as adapters, not normal monitors.

## Engineering direction

- Prefer React + TypeScript frontend and a local metrics service.
- Use declarative display/layout configuration.
- Components should have a manifest, config schema, typed runtime props, preview data, and documented unavailable/error states.
- Preserve arbitrary display size, resolution, density, rotation, and safe-area assumptions in config.

## Git workflow

- After completing a user-facing turn, stage only relevant files, commit, and push.
- Do not stage `.env` or generated local captures.
- If push fails because authentication or remote setup is missing, inspect non-secret Git configuration first. Use `.env` credentials only when necessary and never expose them.
