# Genuine human native-approval acceptance

This bridge uses installed Hermes' public `set_approval_callback` with the real `model_tools.handle_function_call` dispatcher. It sends no model traffic, uses no credentials and creates a new isolated profile. The primary profile is not changed. The callback receives an actual owner's answer relayed through this chat; it contains no predefined decision. It is not a native CLI button or gateway UI demonstration.

Start from the reviewed checkout, supplying a new directory outside that checkout:

```powershell
python scripts/human_acceptance.py --output NEW_DISPOSABLE_DIRECTORY
```

The literal directory argument above is a choice the operator must make; it is not an existing evidence path. Run in the background so the owner can answer while the callback waits. On Windows use the functioning native Hermes Python environment; the process sandbox's Bash loader may fail.

## Relay protocol

The worker publishes `pending-1.json` followed by `pending-2.json`. Each contains a fresh nonce, exact terminal command and arguments, operation hash, native reason, session/call identity and UTC expiration. Each request waits at most 180 seconds. No file means no approval; timeout or malformed/expired/mismatched decisions fail closed to deny.

Ask the owner about the concrete pending operation. For the requested scenario, the first operation should be **denied** and the second approved **once**. Both are harmless writes to separate new marker files in the disposable workspace. Never synthesize the owner's answer or reuse prior generic approval. If the owner chooses differently, record their actual answer and the observed effects rather than forcing a passing result.

Only after the owner's actual reply, atomically write `decision-1.json` or `decision-2.json` with that request's exact nonce and these fields:

```json
{"nonce":"copy the actual pending nonce","choice":"deny","actor":"owner-via-chat"}
```

For an actually approved second operation, use `choice: "once"`. The bridge rejects session/always grants. The nonce binds a decision to that exact pending request; the local trusted relay attributes `owner-via-chat`. This is local operator attribution, not a cryptographic identity assertion. Keep the evidence directory inaccessible to untrusted writers.

The bridge writes `outcome-1.json`, `outcome-2.json` and final `human-acceptance.json`. The successful requested scenario requires both actual owner answers, first deny leaving no marker, and second once producing the expected marker content. It must not pass on timeout decisions or fixtures. The unit tests validate only parsing, expiry and scope; they do not establish that a human interaction has occurred.

## Observed owner interaction

On November 5 the owner answered **once** at all four actual checkpoints: Sentinel's native approval escalation and Hermes' own Python-command guard for each of two different disposable marker writes. Both files were created with the expected bytes. The changed operation received separate nonce-bound requests; no prior approval silently authorized it. See `ACTUAL_HUMAN_ACCEPTANCE.json`.

This establishes actual human approval and real tool effects through the native callback bridge. It does **not** establish actual human rejection: the owner did not choose deny, despite that option being offered. Native denial remains verified by the separately labeled host fixture. No owner answer was fabricated or changed to force the proposed deny-then-once scenario to pass.

The original harness assumed exactly two callbacks and initially mislabeled the four real checkpoints as non-genuine. The summary logic now separates genuine answers, observed execution effects and whether both approval/rejection outcomes occurred; a regression test preserves this distinction. Additional native checkpoints are host behavior, not a reason to bypass either gate.

Run the parser tests with `python -m unittest discover -s tests -p test_human_bridge.py -v`. These tests verify parsing and summaries; only the recorded interaction establishes actual human input. A native CLI-button or gateway UI interaction is not claimed.
