# GURU-004M — ledger verification and scoped acceptance

Architect decision: **PASS — GURU-004M scoped integrated acceptance**, recorded
under the learner-supplied **G004M-CLOSE** authorization on 2026-10-16
(Asia/Calcutta). **GURU-004H remains accepted and closed. GURU-005 remains
BLOCKED pending a separate authorized dispatch.**

## Evidence origin and acceptance boundary

This report records **learner-supplied Mac execution**, followed by review of its
verification output and existing saved evidence. It does not claim that the build
agent executed the Mac verifier or accessed the original Mac database directly.
The supplied output is `Pasted markdown(20261015-010351).md`, 38,973 bytes. The
four distinct evidence hashes are recorded below. The database, credentials and
full provider bodies remain outside this repository.

The original Mac checkout stopped at the revision check because it was at
`f2f94be1cbed076503ad7ff405f40cb40fa71bd8`. The architect then authorized alignment
to `85e109c22dab8796e712713edc2fd12ccd086e17` and the unchanged read-only verifier.
The subsequent supplied output confirms that exact revision on `darwin` and
successful completion without exceptions. This was evidence verification with
zero new Guru or Maharishi calls, not a new live teaching run or a test rerun.

Acceptance covers the saved integrated sequence: a real approved Anthropic
ORIENTATION directive, Gurukul application, direct handling of the learner's
concern, stale-question suppression, profile exit and linked ordinary answer
admission, with authority and provider boundaries unchanged. Later GURU-004H
evidence is used only where verified parent lineage and admission records link it
to this sequence. Transcript resemblance alone is not acceptance proof.

## Supplied verification receipt

The following is the learner-supplied final receipt, formatted without changing
its fields or values. Its original `REVIEW_PENDING` result is preserved; the later
architect decision is recorded separately below.

```json
{
  "GURU_005": "BLOCKED",
  "ancestry_count": 36,
  "authority": "unchanged",
  "exceptions": [],
  "historical_records_rewritten": false,
  "kind": "receipt",
  "ledger_whole_file_sha256": "5448eae2d5d7b317289b1bc16d8f5ec21931a17cce5e18b563fffa5b24018f5e",
  "new_guru_calls": 0,
  "new_maharishi_calls": 0,
  "reservations": 4,
  "result": "READ_ONLY_CHECKS_COMPLETE_REVIEW_PENDING",
  "revision": "85e109c22dab8796e712713edc2fd12ccd086e17",
  "root": "bf6dd9ef-7429-41f6-b537-fa542560245f",
  "session": "a411f23c-851b-4b75-9211-09f0fdf62701",
  "session_event_count": 91,
  "session_result_count": 63,
  "span_count": 39,
  "target": "b6840d25-7dbb-4074-8eab-dae9477cc2ea"
}
```

The existing `load_previous()` succeeded using the repository's actual manifest,
configuration and pinned exercise, with SQLite opened read-only and Python
bytecode writes disabled. It returned:

| Field | Value |
| --- | --- |
| Continuation parent call | `b6840d25-7dbb-4074-8eab-dae9477cc2ea` |
| Continuation parent event | `45508521-844b-41cb-bcc2-da99236b35c7` |
| Root call / ledger | `bf6dd9ef-7429-41f6-b537-fa542560245f` |
| Session | `a411f23c-851b-4b75-9211-09f0fdf62701` |
| Loader history window | 20 events |

The returned continuation parent identifies the selected saved call. The target's
incoming parent is `66ca9d0a-359d-4647-a7f5-d6876a1f8b47`. Loadability does not
authorize another teaching process or provider call.

Explicit ancestry verification extended beyond the loader window: 36 unique
successful records and 35 continuous parent links reached the root. Checks
covered report-to-ledger equality, event/causation links, continuation parent IDs
and canonical parent-report hashes, question bindings, 39 learner spans, source
provenance and corresponding saved Guru content. Session-wide inspection covered
63 result records and 91 events, including the failed sibling branch. The final
read checks confirmed unchanged session/event records and ledger whole-file hash.

## Verified lineage used for acceptance

Short call prefixes in the matrix refer to these full identifiers. The table
identifies the relevant successful ancestry and the separately reconciled failed
sibling. Intervening successful records are not implied to be absent.

| Call | Relationship and historical observation |
| --- | --- |
| `e24861e2-f318-416a-9bef-97a8fb0a0049` | Supervisor response rejected; deterministic ORIENTATION fallback; Guru PASS. Not evidence of an approved Anthropic directive. |
| `198b081e-17f5-4d71-87e1-5cb1152a5cf0` | Child of `e24861e2`; historical targeted resume point. |
| `543dfff7-3f8f-4eb6-a92c-3f3e54c5dd03` | Child of `198b081e`; approved ORIENTATION, followed by the documented Guru contract failure. Failed sibling of `157126e5`, included in the session budget. |
| `157126e5-1563-4c59-8992-714fc9da4b7c` | Child of `198b081e`; approved ORIENTATION, Guru PASS, ungraded; one profile turn remaining. |
| `f12eb0b1-87e7-462d-a327-b4a39ff3434d` | Child of `157126e5`; question-origin explanation; ORIENTATION TTL reaches zero. |
| `7b07b082-edaf-4a55-ae38-373369ff0524` | Child of `f12eb0b1`; approved ORIENTATION, Guru PASS, ungraded; one profile turn remaining. |
| `627b2754-9d6d-4a4c-9260-39b112c46848` | Child of `7b07b082`; explicit check request exits to NORMAL, zero remaining turns; no answer admitted. |
| `1210e270-d513-4290-bdfa-6cd229980eac` | Child of `627b2754`; ordinary answer admitted with partial judgment under NORMAL. |
| `3069be6e-3f7f-40ae-806f-1714413ab3be` | Later descendant; exact-command, bound PEDAGOGICAL_CONTROL / REQUEST_FRESH_CHECK; ungraded, no answer evidence. |
| `66ca9d0a-359d-4647-a7f5-d6876a1f8b47` | Child of `3069be6e`; bound answer admitted, partial judgment. |
| `b6840d25-7dbb-4074-8eab-dae9477cc2ea` | Child of `66ca9d0a`; bound answer admitted, correct judgment; verified continuation target. |

Review matched the saved explanation hashes for `157126e5`, `f12eb0b1` and
`7b07b082` to the earlier learner-supplied targeted Mac evidence. Those responses
address repetition, identify the question as provisional rather than book-sourced,
and retire it. The linked requested-check evidence is also documented in
[the accepted GURU-004H report](GURU-004H-check-trajectory.md).

## Evidence matrix

| Acceptance criterion | Classification | Evidence |
| --- | --- | --- |
| Account/model verification | PROVEN | Previously established account verification in `GURU-004M-acceptance.json`; saved request records identify `claude-sonnet-5-5` and `gpt-6-luna`. |
| Real contract-valid Anthropic directive | PROVEN | `543dfff7`, `157126e5` and `7b07b082`: HTTP 200, approved ORIENTATION directives; directive validation passed. |
| Gurukul validation and application of ORIENTATION | PROVEN | `157126e5` and `7b07b082`: runtime PASS, ORIENTATION applied, ungraded admission. |
| Direct handling of confusion or learner meta-question | PROVEN | Hash-matched saved explanations for `157126e5`, `f12eb0b1` and `7b07b082` address repetition and question origin. |
| Stale-question suppression | PROVEN | Retired-question state persists through the verified lineage; saved displays passed suppression checks. |
| Profile TTL or explicit fresh-check exit | PROVEN | `157126e5` to `f12eb0b1` reaches TTL zero; `7b07b082` to `627b2754` exits to NORMAL on the explicit check request. |
| Resumed ordinary answer admission | PROVEN | `1210e270` admits a partial answer after exit. Later, `3069be6e` to `66ca9d0a` to `b6840d25` links the check to admitted partial and correct answers. |
| Unchanged mastery, progression and curriculum | PROVEN | Session-wide records and provenance checks show no mastery grant or authority transition; session remains in teaching. |
| Request-budget compliance | PROVEN | All four reservations reconciled across the entire original session; failures and sibling branches remain counted. |
| Guru/supervisor credential isolation | PROVEN | Saved before/after probes deny both credential reads and ledger access; worker tool lists remain empty. |
| Parent-ledger and continuation integrity | PROVEN | Report equality, canonical hashes, event/parent/causation links, question bindings, learner spans, provenance and saved Guru content passed verification. |
| Historical instruction to resume from `198b081e` | SUPERSEDED | Later successful descendants and validated `b6840d25` establish the completed trajectory. No rerun is required or authorized by closure. |
| `M-SUPERVISOR-RAW-01` | NONBLOCKING_OPEN_DEFECT | Rejected supervisor body for `e24861e2` remains unavailable; exact rejection cause remains unknown. This is the previously accepted nonblocking defect. |

## Entire-session reservation reconciliation

All `supervision.call_reserved` events in original session
`a411f23c-851b-4b75-9211-09f0fdf62701` were included. Each reservation records one
Anthropic generation, HTTP 200 and resolved model `claude-sonnet-5-5`. Provider
HTTP success, directive acceptance and Guru admission are separate outcomes.

| Ordinal | Associated call ID | Reservation event ID | Recorded generations | Supervisor outcome | Guru outcome |
| --- | --- | --- | --- | --- | --- |
| 1 | `e24861e2-f318-416a-9bef-97a8fb0a0049` | `2421c124-0920-4a2c-9da9-5b2bb86290ad` | 1 | SUPERVISION_FAILED | PASS |
| 2 | `543dfff7-3f8f-4eb6-a92c-3f3e54c5dd03` | `a6a127ba-a9d7-4b61-b8f0-16b50f066c92` | 1 | APPROVED ORIENTATION | BLOCKED |
| 3 | `157126e5-1563-4c59-8992-714fc9da4b7c` | `99706ab5-fb01-4e76-a00d-b0031c6ec4cc` | 1 | APPROVED ORIENTATION | PASS |
| 4 | `7b07b082-edaf-4a55-ae38-373369ff0524` | `f28afcfc-557e-449b-acd9-bab0ac9d0376` | 1 | APPROVED ORIENTATION | PASS |

Total: **4/4 reservations consumed; zero remaining**. The failed `543dfff7` call
consumed its reservation. Failure, branching or restarting does not refund or
reset this budget. The counts do not establish an outage or the precise cause of
later errors. Closure grants no further provider-call permission.

## Four distinctly labelled evidence hashes

All values below are SHA-256. The covered objects differ; these hashes are not
interchangeable.

| Covered object | SHA-256 |
| --- | --- |
| Learner-supplied Mac-output attachment, whole file: `Pasted markdown(20261015-010351).md` | `76ed1565d7d728cbe0ec27ca60afe943e3d869340cce3636a50ee37baaeb5820` |
| Original Mac ledger, unchanged whole file | `5448eae2d5d7b317289b1bc16d8f5ec21931a17cce5e18b563fffa5b24018f5e` |
| Target `b6840d25`, canonical report | `69f61d5b08347c68e688c2ee552086763bd844b48a80ce727e7c407cd3262cd4` |
| Target `b6840d25`, Guru message content, not the whole provider-response file | `dfc9247b8f669df11e736424f2fdd39278f4828e2e008af3f4b51c541d9fbb8d` |

## Architect decision and retained limitations

Following the PASS CANDIDATE recommendation based on this receipt, the architect's
learner-supplied **G004M-CLOSE** dispatch authorized recording this acceptance in
the repository. Recorded decision: **PASS — GURU-004M scoped integrated
acceptance** for the evidence and authority boundary described above. No further
live acceptance check is required for this closure.

- Historical policy versions and records remain unchanged. Later replay or
  repaired behavior is not substituted for historical observations. In particular,
  the final requested-check sequence remains evidence under its saved
  `d01-pedagogy-11-control-contract` policy; it is not rewritten to claim the later
  repaired trajectory state.
- Live coverage remains limited to the saved sequence. No new paid inference
  under the final GURU-004H repair is claimed, and no claim is made that every
  future pedagogical failure has been eliminated.
- `M-SUPERVISOR-RAW-01` remains open and nonblocking. Its missing rejected body is
  not a new acceptance requirement, and its exact rejection cause is unresolved.
- The session budget remains exhausted at four reservations. No reset, new
  session, expanded Maharishi role or submission workflow is authorized.
- No mastery, progression, curriculum unlock, security permission or provider
  authority is granted. The independent learner artifact/evidence requirements
  remain unresolved by conversational correctness alone. Earlier submission-process
  findings are not claimed to be repaired by this acceptance.
- The documentation closure changes no code, configuration, curriculum, ledger
  or provider evidence. It requires no test rerun or provider call.

[Current acceptance status](GURU-004M-acceptance.json),
[GURU-004M overview](GURU-004M.md),
[historical contract findings](GURU-004M-contract.md) and
[historical Mac procedure](GURU-004M-Mac.md) retain the supporting record.
**GURU-004H remains closed. GURU-005 remains BLOCKED pending a separate authorized
dispatch.**
