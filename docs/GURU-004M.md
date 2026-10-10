# GURU-004M v0.1 — Maharishi pedagogical supervisor

Disposition: **PARTIAL PASS / BLOCKED**. The supplied live run verified the account
and model, deterministic fallback and a real approved Claude ORIENTATION directive.
The following Guru response failed on two missing parent identity echoes. The
[targeted contract repair](GURU-004M-contract.md) is offline verified; full integrated
live acceptance remains pending. GURU-005 remains blocked. Synthetic responses
do not count as live Guru or Maharishi acceptance.

## Architecture and authority

Guru remains the actual pinned NousResearch Hermes `AIAgent.run_conversation()`
path, revision `cc75e8f4021f7efab99158f57601be4d691a6da9`, using OpenAI GPT-6 Luna.
Maharishi is a separate Gurukul-owned Anthropic Messages adapter. It observes a
compact trajectory and proposes one approved profile. Gurukul validates and applies
it. Maharishi supplies no teaching text, arbitrary prompt, tool or executable action.

Guru teaches. Maharishi watches the teaching. Gurukul governs both. Retiring a bad
question does not satisfy the underlying evidence requirement. Later Maharishi
observer, auditor, industry and improvement-governor roles remain deferred.

## Small typed contract

Input is bounded to 20,000 UTF-8 bytes: location, current D01 objectives and evidence
requirements, pending question, active profile, up to six recent learner/Guru
exchanges, proposal strategy/activity/judgment, parent admissions/recoveries,
evidence yield, event references, repeat/recovery summaries and immutable controls.
Post-Guru observation also includes the current response and admission. Text is
bounded and is evidence, not instructions. The repeat count is an exact-text proxy;
Maharishi inspects the surrounding trajectory rather than treating it as semantic
proof. The snapshot digest and snapshot are recorded with the decision.

Output has exactly six fields:

```json
{
  "decision": "INTERVENE",
  "profile": "ORIENTATION",
  "reason_codes": ["REPETITION_LOOP", "HARNESS_CONFLICT"],
  "confidence": "high",
  "exit_condition": "TTL",
  "constitutional_change": false
}
```

`decision`: NO_CHANGE or INTERVENE. `confidence`: low, medium or high.
`exit_condition`: TTL or LEARNER_REQUESTS_CHECK; every intervention has a two-turn
maximum regardless of that selection. Allowed reason codes: REPETITION_LOOP,
NO_EVIDENCE_YIELD, LEARNER_CONFUSION, META_QUESTION, HARNESS_CONFLICT, GURU_PAUSE,
STRATEGY_CHANGE and ROUTING_RECOVERY. NO_CHANGE requires NORMAL, no reasons and TTL.
Unknown fields/controls and constitutional changes are rejected.

| Profile | Adaptive effects |
| --- | --- |
| NORMAL | Existing Guru behavior and evidence admission; no new controls. |
| ORIENTATION | Retire the pending question; suppress diagnostic questions and grading; address the concern, explain question origin if asked, acknowledge confusion/looping if present and change representation. |
| REMEDIATION | Retire the pending question; suspend grading; change representation and address the learner's request first. A fresh small question is permitted. |
| PAUSE_EVIDENCE | Suspend diagnostic questions and grading; address the learner's request without retiring the saved question. |

Profiles can relax requested-strategy/form routing. Hard output validation and
parent-bound input/span checks always run first. Controls only restrict evidence
admission; they never admit additional correctness evidence. Suppression is verified
deterministically. Semantic quality (whether Guru actually oriented the learner) is
explicitly marked `requires_live_review`, not certified from a strategy label.

## Hard boundary and temporary state

Profiles cannot alter input, normalization, verified spans, evidence history,
curriculum, mastery, progression, disclosure, credential/ledger/shell/network/tool
permissions, provider security, the Guru request budget or canonical source hashes.
Maharishi cannot open an assessment or move a session to remediation; its REMEDIATION
profile is a teaching control, separate from session phase. Supervision and tutoring
are refused during an assessment. Canonical v0.8.3/map/orientation hashes are retained.

Retired-question hashes survive restart and prevent that exact ghost question from
being displayed again. Only the working prompt's pending-question reference is
cleared; raw history and canonical requirements remain intact. The profile expires
after two turns. `check my understanding`, `ask me a new question`, or `resume the
check` exits it early; Guru must use a fresh question. Retiring a particular question
does not permanently mutate the exercise, curriculum or capability state.

## Invocation, budgets and failures

Healthy turns and a single explanation request do not wake Maharishi. Triggers
include explicit looping/unproductive-explanation complaints, learner meta-questions,
two repeat proxies or routing recoveries, three recent turns without admitted
evidence, rising confusion, and a Guru pause during deterioration or a recoverable
output rejection. An ordinary pause on the first explanation request is not a trigger.
Already handled history does not repeatedly retrigger while a profile is active.
Maharishi can run before Guru or observe a safe proposal afterward; never both in
one turn. A post-turn profile prepares the next Guru prompt and can immediately
suppress that turn's repeated question, without regenerating its explanation.

The Guru still permits one OpenAI request and 1,024 output tokens per submitted turn.
The explicit GURU-004M addition permits at most one supervisor generation per
triggered turn, 512 output tokens, and four supervisor generations per integration
session. Reservations commit before dispatch and survive failure/restart. Neither
adapter retries or chooses another model automatically. Normal turns add no Claude
generation. Exhaustion is a supervision failure, not permission to expand a budget.

Provider/invalid-directive failure records SUPERVISION_FAILED. A deterministically
detected loop, harness conflict or ignored pause enters bounded deterministic
orientation; its `fallback_directive` is separate from an absent model-approved
`directive`. Failure never claims Claude approval or learner failure. Current hard
protections, input and unresolved evidence remain. Security/runtime failures still
stop the teaching turn.

## Provider verification and configuration

Public Anthropic documentation checked 2026-10-10 identifies `claude-sonnet-5-5`
as a fixed model snapshot, with 1M input/128K output limits and standard pricing of
$2 input/$10 output per million tokens. This is a reviewed candidate, not proof
of access with the learner's account. `--model` is explicit during local setup.
The adapter/provider protocol is replaceable; this increment implements only
Anthropic direct. Guru escalation policy is separate and unchanged.

Transport is fixed HTTPS `api.anthropic.com`, GET `/v1/models/{model}` for local
account verification and POST `/v1/messages` for supervision; API version
2023-06-01. Requests contain system plus one structured user snapshot, `max_tokens`,
`stream:false` and `thinking:{type:"between_tools"}`. Sonnet 5.5 rejects disabled
thinking; between_tools avoids initial reasoning when no tools are supplied. There
are no tools, MCP servers, browser, files, connectors, external context fetches,
redirects or automatic retries. An incomplete response, wrong model, tool block or
invalid JSON directive is rejected. Model/HTTP/request ID/usage and estimated cost
are recorded; actual billed cost stays unknown. No cache pricing is invented.

Setup reads only an explicitly selected dedicated key or accepts hidden local input.
It verifies the account's resolved model and limits without generation, then writes
owner-only settings outside Git. No personal Claude/Hermes profile or environment
is read. The key is an HTTP authentication header owned by Gurukul, never model
context or a Hermes credential. The sandbox explicitly denies Hermes reading it,
and probes that denial before and after the Guru turn.

Verified primary references: [models](https://platform.claude.com/docs/en/models/overview),
[model versioning](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions),
[Messages](https://platform.claude.com/docs/en/api/messages/create),
[model account check](https://platform.claude.com/docs/en/api/models/retrieve),
[thinking](https://platform.claude.com/docs/en/build-with-claude/thinking),
[pricing](https://platform.claude.com/docs/en/about-claude/pricing).

## Audit and verification

Generic append-only events: `supervision.call_reserved`, `supervision.observed`
and `supervision.decision_recorded`. Decision/result events commit atomically with
the teaching result. The audit retains triggers, recent-state/event references,
typed directive or explicit fallback, old/new profile, controls and immutable
controls, duration/exit state, provider/token/cost metadata, deterministic compliance
and evidence yield. Only Gurukul appends them. No database migration is needed.

Offline tests cover the canonical failure trajectory, minimal intervention, pause,
question retirement, authority/input checks, provider failures, budget persistence,
expiry, configuration limits, model verification and ledger rollback/reload.
The full suite is recorded in [acceptance status](GURU-004M-acceptance.json).
Exact Mac setup and live checks: [GURU-004M Mac acceptance](GURU-004M-Mac.md).

Remaining limits: no new live run exists yet; semantic compliance, account API
parameters and the extra Mac credential denial need actual verification. Detection
uses a bounded recent window and exact repeat proxy, not a semantic repetition
guarantee. Existing hard schema/disclosure/scope validation still applies; Maharishi
does not silently accept malformed or unsafe Guru output. No claim is made that all
future pedagogical failures are eliminated.
