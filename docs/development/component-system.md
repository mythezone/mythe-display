# Component System Draft

Date: 2026-06-03

Goal: define the initial standard for user-built components.

## Design Principles

- Components must be reusable across screen sizes.
- Component behavior must be declared in a manifest.
- Component visual style must use shared tokens, not one-off hardcoded themes.
- Data inputs must be explicit and mockable for preview/testing.
- A component should fail visibly but gracefully when a sensor or API is unavailable.

## Planned Folder Shape

```text
components/<component-id>/
  manifest.json
  index.tsx
  schema.json
  README.md
  preview.json
```

## Manifest Draft

```json
{
  "id": "core.cpu",
  "name": "CPU",
  "version": "0.1.0",
  "description": "CPU usage, temperature, and frequency widget.",
  "entry": "./index.tsx",
  "schema": "./schema.json",
  "data": {
    "required": ["system.cpu"],
    "refreshMs": 1000
  },
  "layout": {
    "minWidth": 160,
    "minHeight": 96,
    "aspectRatios": ["1:1", "2:1", "3:2"]
  },
  "theme": {
    "tokens": ["color.surface", "color.text", "color.accent", "font.mono"]
  }
}
```

## Runtime Props Draft

```ts
type DisplayComponentProps<TConfig, TData> = {
  id: string;
  config: TConfig;
  data: TData;
  status: "ok" | "loading" | "stale" | "error";
  size: {
    width: number;
    height: number;
    density: number;
  };
  theme: ThemeTokens;
  now: number;
};
```

## Layout Draft

```json
{
  "display": {
    "name": "case-panel-7in",
    "width": 1024,
    "height": 600,
    "density": 1,
    "rotation": 0
  },
  "layout": {
    "grid": {
      "columns": 12,
      "rows": 8,
      "gap": 8,
      "padding": 12
    },
    "components": [
      {
        "id": "cpu-main",
        "component": "core.cpu",
        "area": { "x": 0, "y": 0, "w": 4, "h": 3 },
        "config": { "variant": "radial" }
      }
    ]
  }
}
```

## Core Component Candidates

- `core.clock`: time/date.
- `core.cpu`: usage/frequency/temperature.
- `core.memory`: RAM/swap.
- `core.disk`: filesystem usage and activity.
- `core.network`: throughput/IP/interface state.
- `core.gpu`: NVIDIA/AMD/Intel metrics when available.
- `core.temperatures`: lm-sensors labels and values.
- `core.fans`: fan speed and curves where available.
- `core.processes`: top CPU/RAM processes.
- `core.text`: static markdown/status label.

## Component Quality Requirements

- Responsive at declared minimum size.
- No layout shift when values change.
- Loading, stale, error, and unavailable states.
- Preview data committed with the component.
- Screenshot or visual test for common display sizes once test tooling exists.
