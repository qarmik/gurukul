# GURU-004A/B: isolated one-turn live acceptance

Status: **PASS**, based on user-supplied Mac terminal output. This record does not
claim that the Mac run was independently executed by the development environment.

- Tested Gurukul revision: `19eee63a95046338261d2d871c7974971a492db3`.
- Actual NousResearch Hermes revision: `cc75e8f4021f7efab99158f57601be4d691a6da9`.
- Real `AIAgent.run_conversation()` path witnessed in `agent/turn_facade.py` and
  `agent/conversation_loop.py`; no generic SDK substitution.
- Requested and returned model: `gpt-6-luna`, OpenAI direct through the parent relay.
- One provider request succeeded with HTTP 200; no provider error or relay rejection.
- Tool lists were empty before and after the turn.
- Ledger read/write/create, credential read, shell, other local network, external
  network and network listen probes were all denied before and after the turn.
- Known startup discovery routes remained denied and were not forwarded.
- Approved local D01 source provenance was retained by the harness.
- A real explanation and diagnostic question were returned. The parent-owned ledger
  record was verified after persistence.
- Transport translated `max_tokens` to `max_completion_tokens`, retaining the
  1,024-token limit, selected model, messages and one-request budget.

The recorded teaching response, raw runtime evidence, call identifiers and local
paths remain in ignored local runtime state; they are not copied into this record.
The source may be selected from iCloud Drive: Git membership is not required.

This accepts the standalone isolated teaching-turn milestone. It does not establish
learner mastery, a full interactive diagnosis/remediation loop, normal session CLI
tutor integration, Claude escalation, or production isolation on other platforms.
`skip_memory: true` remains appropriate for this milestone; Gurukul owns long-term
learner continuity and selectively supplied context.

The Mac boundary regression already passed. GURU-003's 24 new Mac tests also passed;
neither needs to be repeated to acknowledge this acceptance. Exact reproduction
commands remain in [the live integration instructions](GURU-004-live.md).
