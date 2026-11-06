# Contributing

Use Python 3.11+ and keep the core dependency-free unless a dependency materially
improves correctness. Run the unittest suite and JavaScript syntax check described
in README. Add regression tests for policy, persistence and recovery changes.

Never use personal Hermes profiles, production secrets or real destructive
operations in a test. Preserve explicit distinctions between fixture, host
contract, and live model execution evidence. Document observable behavior and limitations in the public technical guides.

Frontend changes must preserve keyboard access, truthful empty states, native
approval boundaries, escaped event content, reduced motion, and responsive layouts.
Do not introduce fabricated telemetry. All new authorization must remain server-side.

See [testing](docs/TESTING.md) for all checks and test-layer disclosures. Keep generated reports, private runtime evidence, logs and recordings out of commits.
