# GURU-004H follow-up — fresh-check and conversation contract repair

The later live fresh-check/partial-answer/correct-answer sequence and its narrow
parent-state follow-up are recorded in
[requested-check trajectory evidence and repair](GURU-004H-check-trajectory.md).
The disposition below describes the original follow-up verification.

Disposition: **offline PASS; integrated live acceptance pending**. GURU-005
remains **BLOCKED**. Baseline: `90547167bc9052940c052845a5a9574c935888c9`.
Curriculum v0.8.3, source hashes, assessment, provider/runtime isolation,
Maharishi profiles and budgets are unchanged. No additional inference call,
SDK, general-purpose JSON repair or NLP classifier is introduced.

The supplied Mac transcript proved that the original answer was accepted, the
`latest assigned value` collision was repaired, and one eventual fresh check
and its answer were admitted. It also exposed an initial schema failure, an
ignored fresh-check request and a later generic-recovery loop. Those successes
do not make the whole acceptance run pass.

## Five exact recovered responses

All five message bodies are stored verbatim in `tests/fixtures/guru_004h_*.json`.
Their input, historical errors, printed envelope hashes and independently
computed message-content hashes are recorded separately in
`tests/fixtures/guru_004h_control_failures-provenance.json`. The actual full
provider envelopes were not supplied; their printed hashes remain
user-reported, not independently verified here.

| Call | Reproduced baseline failure | Repaired behavior |
| --- | --- | --- |
| `ba8b8c0b-dce9-4340-8f5a-fb8ce20241f1` | Eleven core fields were inside `intent_responses`, together with misplaced `control_span` and `routing`; top-level schema saw them as absent. | Rehome exactly those thirteen supplied values in a separate validated copy, then run all hard checks. The missing fresh question still causes ungraded recovery; the useful explanation is visible. |
| `e34db245-2f5e-4430-a5fe-94fd8545872f` | The check command was recognized after inference, but the model returned `pause` and no question. | Expose the exact command as a parent control before inference. Replaying this already-failed body still reports the missing question, without fabricating one or hiding valid feedback. |
| `2392e6af-2d12-49a1-91e9-48fe2523fbd6` | A legitimate refusal to grant mastery/advance used `clarification`, not the required `defer` label; it also had an unsupported secondary control label. | Display the clarification ungraded; that secondary label has no admitted control action/span. Keep the original interpretation in the audit. |
| `d7aba191-350f-4c80-864f-a0c161736ca6` | A valid concern acknowledgment was hidden because `future_acknowledgement` required strategy `defer`. | Preserve the acknowledgment and its bound META_QUESTION/CONFUSION spans. |
| `780ff6d4-34ac-4d1b-855b-684ecf1330e4` | `future_topic_deferred: true` classified the entire reply as a future lesson; strategy and 100-word checks hid current-exercise guidance. | The flag alone has no scope authority. Display current guidance and the refusal to advance, without admitting an unsupported secondary control label. |

## Bounded repairs

The layout adapter recognizes only direct, known diagnostic siblings mistakenly
placed in `pedagogy.intent_responses`; `control_span` moves only into `intents`.
No value is inferred or defaulted. Unknown fields, duplicate destinations and
conflicts fail closed. A genuinely absent `grants_mastery`, invalid location or
version, unverified provenance, unsafe code or invalid span cannot be repaired
away. All normal validation runs after relocation.

The saved provider `message.content`, raw teaching object and response hash
remain original. A separate `response_layout_binding` records field paths and
raw/normalized object hashes. Continuation recomputes the mapping and refuses
a forged binding, including in ancestor history. Derived history uses the
validated diagnostic layout; it does not rewrite the original event. Optional
identity echoes relocated from the known container are checked normally and
are not falsely described as omitted.

Exact fresh-check commands now appear as a parent-owned `learner_control` in
the prompt, with an input hash and reference, a nonempty-question requirement,
no answer evidence and no mastery authority. The system prompt explicitly says
that a new check request overrides an earlier pause, while retired questions
and curriculum boundaries remain enforced. The nested contract now names
`control_span` inside `intents` and limits `intent_responses` to three reply
strings. Core fields and `routing` are direct pedagogy children.

An unsupported secondary PEDAGOGICAL_CONTROL label without a span and without
an action does not discard a legitimate META_QUESTION reply. It stays in the
raw model interpretation but has no admitted control authority. Explicit
actions still need a verified span; invalid supplied references still recover
without fabricated evidence or false credit.

Future deferral is not certified by a particular strategy label. An explicit
future-acknowledgment proposal still needs the deferral flag and no miniature
code; the global 180-word limit remains enforced. A deferral flag alone does
not reclassify current guidance. Explicit future-depth, unverified current or
regulatory claims, and uncertain routes still suppress the proposed claim and
recover. The model's actual prose remains subject to live semantic review.

If a fresh-check response lacks a question and has no other admission or
source/scope conflict, the structurally valid feedback is shown with one clear
parent recovery notice. The turn remains NEEDS_CLARIFICATION and ungraded,
never a successful fresh check. Unsafe or unbound proposals are still hidden.
No fallback question or automatic model retry is generated.

A bound, correctly answered learner-requested check closes only that
conversational question. It suppresses a further unsolicited recall question
and retains canonical requirements for a source file, failed run and successful
run. Partial answers can still request missing conceptual evidence. Completion
is saved and survives restart; it does not grant mastery, change phase, satisfy
the independent exercise or unlock another concept.

Verbose failure summaries now include the existing safe structural diagnostics,
so the missing/extra-field evidence is visible without opening a provider body.
Supplementary intent responses remain audit-only; the main reply is displayed
once. Maharishi code, roles, reservation limits and fallback eligibility are
unchanged. The supplied local supervisory failures showed zero outgoing
requests; this patch does not expand their budget or claim a new Claude run.

## Verification

Twenty-three new tests in `tests/test_control_contract.py` cover all five exact
bodies, their content hashes, raw-message persistence, the full save/restart
chain, correct/partial fresh-check answers, no fabricated questions, secondary
control authority, all existing profiles, malicious layout/conflict cases,
source/scope guards and layout-binding tampering.

Full suite: **229 tests; 228 passing, one macOS-only sandbox test skipped on
Linux**. No paid generation was performed. [Exact commands, test names and
captured output](GURU-004H-control-verification.txt).

Changed runtime files: `src/gurukul/pedagogy.py`, `intent_admission.py`,
`semantic_routing.py`, `teaching_output.py`, `hermes_continuation.py`, and
`scripts/hermes_live_teach.py`. Added the new test file, five exact JSON bodies,
their separate provenance record, and this verification documentation.

## Next micro-task: G004H-RECHECK — maximum 20 minutes

Objective: demonstrate a fresh check, normal answer admission and visible
current-exercise guidance without returning to the generic recovery loop.

1. At the Mac shell, synchronize and verify the published repair revision:

   ```sh
   cd /Users/qarmik/Documents/GitHub/gurukul
   git pull --ff-only
   git rev-parse --short HEAD
   PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_control_contract.py' -v &&
   python3 scripts/hermes_live_teach.py \
     --runtime-root /Users/qarmik/GurukulRuntime \
     --continue 780ff6d4-34ac-4d1b-855b-684ecf1330e4 \
     --maharishi --verbose
   ```

2. At the Gurukul prompt, submit `check my understanding` once. Require a saved
   CONTINUE turn, an ungraded REQUEST_FRESH_CHECK with no answer evidence and
   one fresh non-retired question. If rejected, stop and share the call ID;
   do not repeat paid calls.
3. Answer the question yourself. After a correct admitted answer, require no
   further unsolicited recall question and no mastery/progression claim.
4. Submit: `We have covered this explanation. Tell me what independent
   evidence is still required; do not repeat the check.` Require visible
   guidance within D01, no generic recovery notice, and no stage unlocking.
5. Enter `/quit` and share the transcript plus final call ID.

Done proof: the actual three-turn transcript and saved admission records;
all source/input/isolation checks remain valid, each message uses at most its
existing request budget, no retired question returns and mastery stays false.
Offline fixtures or a recovery notice do not complete live acceptance.
GURU-005 remains blocked.
