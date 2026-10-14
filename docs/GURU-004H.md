# GURU-004H — semantic heuristic authority audit and minimal repair

Architect_4 accepted the completed GURU-004H scoped repair on 2026-10-14.
See the [recorded decision and final verification](GURU-004H-check-trajectory.md).
The subsequent repairs are documented in the
[exact five-response follow-up](GURU-004H-control-contract.md) and the requested-check
trajectory report. The original disposition and verification below remain
historical evidence. Broader integrated live acceptance is not asserted;
GURU-005 remains **BLOCKED**.

Disposition: **offline PASS; integrated live acceptance pending**. GURU-005
remains **BLOCKED**. This increment changes only the confirmed semantic-routing,
learner-control, supervisor-fallback and terminal-composition paths. Curriculum
v0.8.3, assessment, provider/runtime isolation, model selection and budgets are
unchanged. No new inference call, dependency or general-purpose NLP framework is
introduced.

Baseline: `ec484369f9be821b2bb89972e08ad52029adf048`. The baseline commit and its
entire tree were verified against the connected repository; the four dispatch
sites match their exact baseline blob hashes. The repair commit descends from
this baseline.

## Exact failure evidence

The exact Guru JSON supplied for call
`b81269bd-bbc3-4aa8-8608-c788545c630d` is preserved in
`tests/fixtures/guru_004h_b81269bd.json`. Its separate provenance record preserves
the exact learner input and active question from the supplied terminal transcript.
The full original provider envelope was not supplied. Its SHA-256
`529b98d3926d27366e37b20d47d07dfee7616e6ffbbeb466fd17b60d6382c863` is a
**user-reported envelope hash**, not a hash independently verified against these
fixture bytes.

An isolated checkout of the actual baseline reproduced this exact response's
failure:

```text
Baseline: ec484369f9be821b2bb89972e08ad52029adf048
Exact fixture: b81269bd-bbc3-4aa8-8608-c788545c630d
Parent knowledge_task_hint: version_sensitive
Reproduced: ValueError: Current authoritative source unavailable; defer claim
```

After repair, the same unmodified response is accepted with its `ANSWER` intent,
`partial` model judgment and exact full learner span. Its explanation and next
question are preserved. Parent location/version are bound separately, mastery
stays false, and save/reload retains both raw content and admission evidence.
The question mark in the learner's answer no longer creates a punctuation veto.

## Authority audit

| Site | Previous consequence | Repair and authority boundary |
| --- | --- | --- |
| `pedagogy.classify()` | A surface guess could force labels or an ungraded verdict through legacy validation | Advisory prompt hint; live admission uses bound intent proposals. Exact fresh-check commands have a separate parent control record. |
| `pedagogy.turn_context()` knowledge-task regexes | `latest`, `legal`, `book`, `source` or `page` could require an unavailable source and hard-fail | Matches remain in `surface_signals` with `authority: none`. They are not consumed by validation/admission. Parent task metadata has precedence over an optional finite model routing proposal. |
| `pedagogy.validate_response()` future-topic regex | A name such as `agent` or text such as `AST` could force deferral | Remove lexical depth authority. A proposed future-depth/uncertain route produces recoverable clarification and suppresses the proposal. Actual teaching depth still requires live semantic review. |
| `intent_admission.explanation_request()` / `intent_hint()` | A guessed representation or clarification could veto useful feedback | Hints remain advisory. Representation checking uses an optional model-proposed strategy with a verified explanation span. |
| `intent_admission.candidate_answers()` | Question marks, leading confusion and mixed segments could discard exact answer evidence | Advisory only. Admit a model-proposed answer span bound to the active question, reject contradictory overlap with non-answer spans, preserve secondary intents and immutable source input. |
| `maharishi.check_requested()` | The supervisor recognized a fresh-check command while answer admission did not | Share the three existing exact fresh-check command forms; parent control has no answer span or answer judgment. Raw model interpretation remains separate. |
| `maharishi.triggers()` / failure fallback | Programming `loop` vocabulary could request intervention and then authorize deterministic ORIENTATION on provider failure | Narrow conversational review hints; separate candidates from structural evidence. Failure fallback requires recorded trajectory facts, not hint reason codes. |
| `hermes_live_teach.py` rendering | Supplementary `intent_responses` printed again after the explanation | Print one complete explanation, its separate bounded example and diagnostic question. Keep supplementary responses in audit evidence. |

The small `semantic_routing.py` helper extends the existing closed proposal
contract with four optional finite fields: knowledge task, teaching scope,
control action and requested representation. It is not a separate classifier.
Omitting it preserves compatibility with the exact live fixture. It cannot
change curriculum, evidence, permissions, mastery or provider controls.

Semantic source/scope/intent uncertainty becomes `NEEDS_CLARIFICATION`, ungraded,
with the input and pending evidence retained and the proposed claim hidden.
Current-version and regulatory proposals still require deferral in this
source-unverified harness. Source and curriculum proposals still need their
proper grounding. A model proposal cannot override a parent-required task class.
Unknown contract fields, invalid parent state, forged provenance, unsafe code,
mastery/progression claims and all existing isolation/integrity guards fail closed.

Deterministic fallback requires at least one recorded structural condition:
two routing recoveries; two exact repeated questions; two consecutive saved
Guru pause activities without admitted answers; or an attempted replay of a
question already retired by the parent. Counts use the window after the last
intervention. Full question hashes, not truncated previews, establish identity.
The audit records candidates, structural reasons and fallback eligibility
separately. A successful model decision can still intervene; a failed hint-only
review cannot change profile or retire a question. Existing TTL, reservation,
session-budget and no-retry behavior remain enforced.

## Files changed

| File | Purpose |
| --- | --- |
| `src/gurukul/pedagogy.py` | Demote lexical decisions; align the optional semantic proposal prompt/contract. |
| `src/gurukul/intent_admission.py` | Bind mixed evidence; separate fresh-check control; make semantic recovery explicit. |
| `src/gurukul/maharishi.py` | Separate review hints from structural fallback; hash full questions. |
| `src/gurukul/semantic_routing.py` | Finite optional proposal validation and parent metadata precedence. |
| `scripts/hermes_live_teach.py` | One learner-facing response composition. |
| `tests/test_semantic_authority.py` | Thirty new regressions; exact names and output in the verification record. |
| `tests/fixtures/guru_004h_b81269bd.json` | Exact recovered Guru content, without invented fields. |
| `tests/fixtures/guru_004h_b81269bd-provenance.json` | Separate source/hash/input provenance. |
| `tests/test_explanation_requests.py` | Have synthetic model fixtures propose requested representation explicitly. |
| `tests/test_pedagogy.py` | Preserve existing source/scope/confusion/progression/repetition checks at recoverable live admission instead of lexical hard failure. |
| `tests/test_maharishi.py` | Require structural history in the existing deterministic fallback regression. |
| `tests/test_supervised_contract.py` | Keep schema diagnostics and HTTP-200 failure tests aligned with optional routing and structural fallback. |
| `docs/GURU-004H.md` | Audit, boundaries, evidence and next live micro-task. |
| `docs/GURU-004H-verification.txt` | Exact commands, new test names and captured successful command output. |

Verification: **30 new tests pass; full suite 206 tests, 205 passing and one
macOS-only sandbox test skipped on Linux**. No paid inference was performed.
See [the exact verification output](GURU-004H-verification.txt).

## Next micro-task: G004H-LIVE (20–40 minutes)

Objective: verify the repaired answer path and fresh-check control in the real
Mac session. The supplied transcript's last successful call is
`627b2754-9d6d-4a4c-9260-39b112c46848`; the failed `b81269bd` call is not resumable.
The published repair must be present before this run.

1. At the Mac shell, synchronize, verify the repair commit, then run:

   ```sh
   cd /Users/qarmik/Documents/GitHub/gurukul
   git pull --ff-only
   git rev-parse --short HEAD
   PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_semantic_authority.py' -v &&
   python3 scripts/hermes_live_teach.py \
     --runtime-root /Users/qarmik/GurukulRuntime \
     --continue 627b2754-9d6d-4a4c-9260-39b112c46848 \
     --maharishi --verbose
   ```

2. At the Gurukul prompt, submit the original answer as one line:

   ```text
   quotes make it easy for python, it does not have to look anywhere to find what it means or what its value is? It simply prints/outputs the whatever that exists within those quotes - that is it for python. But when it encounters any unquoted word as the value of a variable, it starts looking for its latest assigned value. it can also be None. It outputs whatever the latest assigned value of the variable is. In case, the variable has no assigned value, python throws the NameError.
   ```

3. After accepted feedback, submit `check my understanding`. Require an
   ungraded `REQUEST_FRESH_CHECK` control, no admitted answer evidence, an exit
   from temporary supervision and a fresh, non-retired question.
4. Answer that question yourself; then `/quit`. If a turn is rejected or
   blocked, stop and share it instead of repeating paid calls.
5. Share the terminal output, commit ID and final call ID. Keep the raw provider
   and saved parent admission evidence locally.

Done criteria: the original answer's exact span is admitted; `latest assigned
value` creates no source-routing hard failure; semantic routing reflects stable
fundamentals; mixed/secondary evidence is retained where present; fresh-check
control is not answer evidence; no retired question reappears; the response is
displayed once; the session remains resumable; mastery and progression stay
unchanged; all recorded isolation and budget checks pass. A recovery notice is
safe handling but does not count as successful teaching.

Proof: actual transcript and corresponding saved call/admission records. Offline
fixtures do not complete integrated live acceptance. GURU-005 remains blocked.
