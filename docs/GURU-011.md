# GURU-011 — One live Ask Guru turn, prepared

Base: `7dcc31f3fba04a1dcb63543712dab31d0ff5eb85`.

The normal workspace remains offline. The separate Mac trial launcher
requires `--live-once` and creates a new temporary workspace and ledger.
It connects the existing TeachingPipeline to the same sandboxed Hermes
worker runner and loopback provider relay used by terminal teaching.

The canonical teaching lock stays held through dispatch and reply admission.
The relay forwards the parent system instruction and approved D01 prompt
(including the typed question); it drops worker-added system text and
metadata. No draft, history, or learner ledger is sent. The provider key is
read by the server-side relay and explicitly denied in the worker sandbox.
The transport consumes its one-turn permit even on failure. The relay
independently reserves at most one upstream request before network I/O.
No retry, fallback, tools, provider storage request, or escalation is enabled.

## Verification

Linux; simulated sandbox subprocess, real local workspace and relay HTTP,
fake upstream. **Zero live provider requests.** Five new connection tests
passed: validated reply and second-turn rejection, assessment denial before
worker or upstream, timeout, rejected response, and semantic non-admission.
The tests checked unchanged draft and progress, bounded error messages,
and confirmed that assessment opening is denied during upstream dispatch.
Existing focused suites passed: workspace 29, Hermes relay 21, assessment 33,
workspace JavaScript 23.

## Proposed Mac run (requires separate authorization)

From this branch's checkout, use the rebuilt Python 3.11+ interpreter.
Supply the path to the original, approved local D01 HTML (SHA-256
`6d301250bb4d6177f818133baaed8ebd2cd00f114aa8453f375d93e849e38f17`).

```sh
"$HOME/Documents/GitHub/gurukul-g007-synthetic.vRnida/.venv-g008/bin/python" -B \
  scripts/ask_guru_live.py --live-once \
  --runtime-root "$HOME/GurukulRuntime" --source "/absolute/path/to/C0-B01_Values_and_Variables.html"
```

Replace `--live-once` with `--preflight` to check local setup without
launching the workspace or making a provider request. Preflight checks macOS,
sandbox-exec, the clean pinned Hermes checkout and installed dependency venv,
the owner-only local OpenAI credential, and source and curriculum binding.
These Mac prerequisites were not checked in the Linux environment. Provider
availability and the previously observed Hermes context-window issue cannot
be resolved by preflight.

Type one question, such as “What changes after reassignment?”, then
press Control+C in the launcher after the reply or error. Model: OpenAI
`gpt-6-luna`; output cap: 1024 completion tokens; maximum: one upstream
request for this launch, including failures. Do not relaunch on failure
under a one-request authorization.

The terminal emits `ASK_GURU_LIVE_RECEIPT` after the transport finishes
and `ASK_GURU_LIVE_FINAL` at shutdown. A successful transport has
`relay_reservations: 1`, one upstream entry with
`max_completion_tokens <= 1024`, and a provider request ID when returned.
A blocked or timed-out attempt can have zero or one reservation; one
reservation without a response is not proof of provider completion or no
charge. The browser's admitted reply is separate evidence that teaching
validation passed. Receipts exclude prompts, replies and credentials.
