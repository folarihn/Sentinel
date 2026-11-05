# Contributing

Use Python 3.11+ and keep the core dependency-free unless a dependency materially
improves correctness. Run the unittest suite and JavaScript syntax check described
in README. Add regression tests for policy, persistence and recovery changes.

Never use personal Hermes profiles, production secrets or real destructive
operations in a test. Preserve explicit distinctions between fixture, host
contract, and live model execution evidence. Keep docs/BUILD_STATUS.md current.

Frontend changes must preserve keyboard access, truthful empty states, native
approval boundaries, escaped event content, reduced motion, and responsive layouts.
Do not introduce fabricated telemetry. All new authorization must remain server-side.
