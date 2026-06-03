# Documentation Policy

Date: 2026-06-03

## Required Documents

- `README.md`: user-facing setup and current project state.
- `CHANGELOG.md`: material changes by date.
- `docs/research/`: research notes and source-backed comparisons.
- `docs/decisions/`: architecture decision records.
- `docs/development/`: technical design, implementation notes, and future developer guides.

## Update Rules

- Update `README.md` whenever setup, runtime commands, or user-facing behavior changes.
- Update `CHANGELOG.md` for each meaningful documentation, architecture, or code change.
- Add an ADR under `docs/decisions/` when a technical direction becomes durable.
- Keep raw secrets, local paths with credentials, and private tokens out of all documentation.
- Link sources for external research so future contributors can verify assumptions.

## Naming Rules

- Research: `docs/research/<topic>.md`.
- ADRs: `docs/decisions/NNNN-short-title.md`.
- Development guides: `docs/development/<topic>.md`.

## Screenshots and Assets

- Prefer upstream image URLs in research docs when evaluating existing open-source projects.
- Store original generated screenshots under `docs/assets/` only when they are project-owned or clearly reusable.
- Store local debugging captures under `screenshots/local/`; this path is ignored by Git.
