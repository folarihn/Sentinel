# Changelog

## Unreleased

- Chat commands for any Hermes platform, including Telegram: `/sentinel status`,
  `/sentinel blocks`, `/sentinel missions` and `/sentinel alerts on|off`.
- Optional high-risk block alerts sent through Hermes' own delivery engine;
  rate limited, argument-free, off-thread and recorded as `alert.sent` or
  `alert.failed`. Alerts never change a decision.
- Terminal commands: `hermes sentinel doctor`, `hermes sentinel dashboard`,
  `status`, `blocks` and `missions`. The dashboard no longer needs a separate
  install and prints a one-time login link.
- VPS and Telegram setup guide.

## 0.2.0 (2026-11-08)

- ATLAS interface replaces BLACKSITE: soft black surfaces, monochrome accent and
  colour reserved for meaning; Instrument Serif, Inter and JetBrains Mono bundled
  locally under OFL 1.1, replacing IBM Plex and Space Grotesk.
- Overview: session timeline with zoom, decision flow linked by recorded
  tool-call IDs, event inspector with keyboard navigation, sparklines, linked
  session highlighting and a loading skeleton.
- Command palette (`Ctrl+K` or `/`) for modules, sessions, rules and events.
- Guard example requests and rule activity; Replay history timeline; checkpoint
  lifecycle stepper; mission status summary and relative expiry; per-session
  tracks in Mesh; keyboard shortcuts in Settings.
- The dashboard serves a local favicon, so browsers no longer log a 404.

## 0.1.1

- BLACKSITE interface: persistent sidebar, accessible mobile drawer, local OFL
  typography, responsive session registry, grouped mission authority, policy
  explanations, checkpoint integrity details and explicit offline snapshots.

- Deterministic command/path protections, restrictive operator rules, mission
  authority, and exact-operation native approval scope.
- Local redacted SQLite events, session visibility, read-only Replay, retention,
  and scoped exports. Safe journal mode selection for affected SQLite builds.
- Mission lifecycle and seven templates, including pause and expiry enforcement.
- Checkpoints for supported structured file writes, conflict-aware restoration,
  and recovery provenance.
- Authenticated local Control Room, responsive layouts, filter synchronization,
  accessible event controls, and native approval session attribution.

## 0.1.0

- Initial Hermes plugin, policy/event contracts, tests, and local Control Room.
