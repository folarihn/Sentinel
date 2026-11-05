# Actual Hermes tool execution acceptance

Run with the installed Hermes Python environment:

```powershell
python scripts/host_acceptance.py
python -m unittest discover -s tests -p test_host_execution.py -v
```

The script creates a new disposable profile, copies the current plugin into its official plugin directory, enables it in that profile's configuration, and calls the real `model_tools.handle_function_call` dispatcher. Both pre- and post-tool hooks fire automatically. It does not replace the Hermes dispatcher or call Sentinel callbacks directly.

The harness verifies:

- A real harmless terminal echo executes.
- Hermes `write_file` changes an actual disposable file. Sentinel automatically checkpoints it before execution, seals it after execution, and restores the original bytes through authorized Recovery.
- A destructive command targeting a disposable marker is blocked and its marker remains. A synthetic secret read is blocked and its bytes appear in neither the response nor the journal.
- A fixture **deny** decision travels through native Hermes approval and prevents a disposable file-writing tool body. A fixture **once** decision permits a harmless real terminal printf. These callbacks are explicitly test decisions, not human interaction.
- A paused mission blocks its own session while another session can still read the permitted disposable fixture.
- Both session identities remain separate and journal data survives reopening storage.

The command returns an evidence directory containing `acceptance.json`, a disposable workspace, a credential-free profile and the SQLite journal. `--output` accepts a new directory only. Existing directories are rejected. No provider credentials are copied; no external model, gateway, deployment or financial operation is invoked.

## Verified result and limits

On November 5, 2026, installed Hermes 0.20.0 passed all six acceptance checks with eight registered hooks and 33 persisted events. This is actual local tool execution through the installed host, not an LLM-driven conversation or a claim that the personal agent was tested.

Windows sandbox execution reached the real terminal backend but its Bash process failed to load with exit code `3221225794`. The same acceptance succeeded outside that process sandbox. A future environment with a functioning terminal backend should run normally. The optional test intentionally fails rather than silently substituting fake terminal output when Hermes is installed but its terminal cannot execute.

Read-only checks of the configured primary profile found OpenRouter selected and a provider key present in that profile's `.env`; known Nous and OpenAI Codex auth-store entries also exist. Presence is not proof of valid credentials or account availability. Credential values were neither displayed nor copied into fixtures. The credential-free acceptance does not use these entries.

## Live model acceptance: verified with approved free-router fallback

`scripts/live_acceptance.py` prepares a separate opt-in model-driven test. It uses the installed `AIAgent` public constructor and `run_conversation`, the configured OpenRouter model, the official `https://openrouter.ai/api/v1` endpoint, five tool iterations maximum and 700 output tokens per response. The task is limited to a local `pwd` and a disposable file write. An active mission restricts tool and directory authority; a resulting checkpoint is restored if generated. No primary memory, sessions, configuration or credential files are changed.

The existing profile's OpenRouter key is parsed with the read-only `dotenv_values` API, passed in the child process environment, and never written to the disposable profile or command arguments. SDK output is held in memory and omitted from persisted evidence. Only an allowlisted operational summary is saved.

The initial execution request was rejected by automatic approval review pending destination-specific authorization. After the user explicitly approved the bounded OpenRouter request, one live acceptance run executed on November 5, 2026 using the configured `nvidia/nemotron-3-super-120b-a12b:free` model. It failed with provider HTTP 404. No terminal or write tool was invoked by that model, no checkpoint was generated, and only two mission/lifecycle journal events were captured. This configured-model route remains **failed/unverified**. No automatic retry followed; the fallback below required separate explicit user approval.

The run's `live-acceptance.json` records this sanitized outcome. A byte-for-byte audit across every file in its disposable evidence directory found zero occurrences of the configured provider key. The primary profile was not modified. Presence of a configured model and key therefore must not be presented as proof that the live provider route is operational.

After explicit user approval for a single bounded fallback, `python scripts/live_acceptance.py --model openrouter/free` passed on November 5, 2026. The real model performed a terminal operation and wrote the requested disposable file through Hermes. Sentinel captured ten events and automatically created and sealed one checkpoint. Authorized Recovery then restored the new file to its original absent state. A separate disposable observer plugin counted **two** `pre_api_request` attempts, matching the host's two API calls; the five-request budget was not exhausted. The configured 700-token output limit applied per response; host-reported total usage was 9,772 tokens including input context.

The successful run's sanitized evidence is `live-acceptance.json` in the returned evidence directory. Its provider-key artifact scan passed. No primary profile files or settings were modified. The original configured model's HTTP 404 remains a recorded provider limitation; the successful fallback is specifically `openrouter/free`. No additional live requests were made after success.

Portable, sanitized copies are committed as [LIVE_ACCEPTANCE.json](LIVE_ACCEPTANCE.json) and [HOST_ACCEPTANCE.json](HOST_ACCEPTANCE.json). Temporary personal paths are replaced with `<temporary>`. The successful live test covers safe terminal execution, an actual file write, mission authority configuration and checkpoint restoration. Destructive blocks, native approval fixture decisions and multi-session separation are verified by the separate actual-host fixture; they are not represented as model-driven live scenarios.

The harness now accepts `--model` only for the configured model or exact `openrouter/free`. A separate disposable budget hook counts API attempts and terminates the worker before attempt six. Official `agent.api_max_retries: 1` disables retry loops. The API key remains in process memory/environment only, and only numeric counters and operational booleans are recorded.

```powershell
# Requires explicit approval for this bounded configured OpenRouter request.
python scripts/live_acceptance.py
# Explicitly approved free-router fallback:
python scripts/live_acceptance.py --model openrouter/free
```
