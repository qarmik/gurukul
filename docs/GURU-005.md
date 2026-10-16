# GURU-005 — assistance-aware D01 evidence eligibility

Disposition: **implementation evidence ready for architect review; acceptance
pending**. Reference: `8322435f998bd566c479ac5036300420dd5d02e0`. GURU-004H and
GURU-004M remain accepted and closed. This increment adds no provider calls,
supervisor budget changes, assessment orchestration or retrieval scheduling.

## Meaning and authority

`eligibility` reads the retained D01 source and execution evidence, reuses the
existing deterministic checker, and appends a current eligibility decision.
It never reruns learner code. The existing `run` command executes the submitted
snapshot; exit-zero execution, `CHECKS_PASS`, conversational correctness and
independent mastery remain distinct observations.

| Result | Meaning |
| --- | --- |
| `HOLD` | Deterministic evidence is missing, failed, blocked or needs review; assistance is unresolved/conflicting; relevant help or solution exposure is recorded; or a complete exact-pair no-help declaration is absent. Practice evidence remains retained. |
| `READY_FOR_REVIEW` | Supported deterministic requirements pass, construction and repair have exact-pair no-help declarations, and no relevant disqualifying fact is recorded. **Declaration-only readiness requires review. It is not verified independence or a gate pass.** |

Every decision has `requires_review:true`, `grants_verified_independence:false`,
`grants_mastery:false`, `changes_session_phase:false` and
`advances_curriculum:false`. No code path in this increment awards a grade,
changes a session phase, retires a stored assessment object, unlocks curriculum,
or creates a fresh variant. Exposure is an eligibility exclusion, not assessment
orchestration.

Requirements come from `content/c0_b01/d01.json`, the existing
`content/checks/d01-v1.json`, and canonical curriculum v0.8.3. No stage-level
capabilities are added to the D01 exercise. The checker still cannot establish
reading/closing the book, starting from blank, deliberate intent or unassisted
repair. The canonical independent construction/debugging and applicable
reconstruction/variation requirements remain for later review, not automatic
credit from a declaration.

## Commands

Use real retained attempt UUIDs in place of `REPAIRED_UUID` and `FAILED_UUID`.
The two attempts must belong to the same session. Keep assistance input files
outside Git, for example under ignored `var/`.

```sh
PYTHONPATH=src python3 -m gurukul eligibility REPAIRED_UUID --failed-attempt FAILED_UUID
```

Without an assistance declaration, even a passing pair returns HOLD/UNKNOWN.
Without the failed attempt, the deterministic missing-evidence result remains
visible and readiness cannot be granted. The output includes both evidence IDs
and hashes, checker outcome/items, curriculum/policy provenance, scoped assistance
records, reasons and outstanding requirements.

For a truthful declaration, write `var/assistance.json` with this closed schema.
The example request ID is illustrative: use a new canonical UUID for each new
request, and reuse the same ID and unchanged contents only for an intentional
retry.

```json
{
  "request_id": "c6eeb494-12fb-4d89-a81b-a58ebcae7501",
  "kind": "none_declared",
  "steps": ["construction", "repair"],
  "timing": "during_work",
  "origin": "learner_declaration"
}
```

```sh
PYTHONPATH=src python3 -m gurukul assistance REPAIRED_UUID --failed-attempt FAILED_UUID --assistance-file var/assistance.json
PYTHONPATH=src python3 -m gurukul eligibility REPAIRED_UUID --failed-attempt FAILED_UUID
```

A passing pair with complete, unopposed declarations returns
READY_FOR_REVIEW/DECLARED_ONLY. The declaration states what the learner reports;
Gurukul does not treat it as proof of external assistance absence.

To record help later, submit another file with a new request ID, for example
`kind: "hint"`, `steps: ["repair"]`, `timing: "during_work"` and
`origin: "learner_declaration"`. Reissue `eligibility`: the current result is HOLD.
The earlier readiness result stays in the audit. There is no last-write-wins
rule that erases conflicting observations or restores independence.

`events` shows historical decisions; an old READY_FOR_REVIEW event is not a
current decision. Recompute with `eligibility` after new facts or restart.

## Assistance scope, provenance and timing

Allowed kinds are `none_declared`, `concept_support`, `hint`, `code_or_repair`,
`solution_exposure` and `unknown`. Steps are `construction`, `repair` or
`concept_practice`; timing is `before_work`, `during_work`, `after_submission` or
`unknown`. Unknown fields, duplicate steps, unsupported values and progression
claims are rejected. This explicit interface does not classify natural language
or grant authority to lexical hints or Guru/Maharishi labels.

- No-help declarations must use `learner_declaration`, cover work with
  `during_work`, and match the exact repaired/failed pair. Timing describes the
  claimed relationship to work, not the timestamp when the fact was recorded.
- `concept_support` is scoped only to conceptual practice. Ordinary explanation
  does not blanket-disqualify later construction or repair.
- Hints/code help before or during the affected work hold independent-credit
  readiness. Help genuinely scoped after that submission does not rewrite the
  work as assisted; resubmitting the same source does not inherit this exception.
- Unknown timing/extent remains unresolved. A later contradictory no-help claim
  cannot silently erase relevant assistance or unknown facts.
- Solution exposure excludes the pinned D01 exercise from independent-credit
  readiness, whether exposure was before, during or after submission. A changed
  source file, session or attempt UUID is not evidence of a fresh assessment
  variant. No fresh-variant generation or scheduling is implemented.
- Relevant negative facts follow overlapping attempts and identical retained
  source hashes for the same pinned exercise. Positive declarations never
  transfer to another pair. Equal source bytes do not prove copying or misconduct;
  they prevent a new identifier from manufacturing verified freshness. Practice
  evidence remains available throughout.

`assistance_provenance` distinguishes UNKNOWN, DECLARED_ONLY,
SUPPORTED_OBSERVATIONS and CONFLICTING. A supported observation additionally uses
`origin: "parent_event"`, `support_event_id` and `support_payload_sha256` (SHA-256
of canonical event payload). The event must be an actual successful
`teaching.integration_finished` event in the same artifact session with matching
parent source and exercise provenance. No-help claims cannot use this origin.
The assistance classification is explicitly recorded by the caller; support proves
the referenced parent event's identity/content, not that a model has certified
independence or that assistance history is exhaustive.

The normal submission ledger and dedicated live-teaching integration ledgers are
separate. **This slice rejects cross-ledger support imports.** A shared exercise
name or copied event ID is not an evidence link. External help may be declared,
but cannot be labelled a supported parent observation without an admitted local
record. No live-ledger joining, full-history ingestion, provider call or new
Maharishi authority is added.

## Persistence and integrity

Two narrowly typed Store methods append `assistance.recorded` and
`evidence.eligibility_recorded` in the existing event table. There is **no SQL
migration or learner-state backfill**; applied schema versions remain 1, 2 and 3.
Old evidence with no assistance records remains unknown.

Each assistance event binds the artifact session, pinned exercise hash, source
hashes, attempt IDs, scoped fact and provenance. Its request UUID is a global
idempotency key: identical retries return the existing record; a changed payload
or different target with the same key is refused. Events retain existing
source/correlation/causation fields and append-only protections.

Eligibility validates retained source/output hashes, the evaluation's canonical
context-derived identity, current checker/spec bindings, equality to its parent
`assessment.checked` event, and canonical curriculum hashes. It records the
complete relevant assistance event set with payload hashes, not a recent-history
window. Reading those facts and appending the derived decision happen under one
`BEGIN IMMEDIATE` transaction. Decisions have content-derived IDs including
policy/curriculum/evaluation/fact bindings. Identical decisions are idempotent;
later facts or checker revisions create new immutable decisions. Failed event
writes roll back; a separately committed deterministic evaluation remains valid
if the subsequent eligibility append fails.

These are local parent-owned audit records, not adversarial machine attestation
or proof that all external assistance was reported. Integrity failures refuse
admission; they do not delete practice evidence. Conflicts require review; this
slice has no automatic correction/override or progression path.

## Implementation evidence

`tests/test_evidence.py` covers declaration-only readiness, missing evidence,
conflicts, late facts/restart, exposure at all three timings, post-submission
hints, conceptual support, exact-pair and identical-source behavior, idempotency,
transaction failures, source/output/evaluation/curriculum integrity, parent-event
provenance, schema/authority rejection and separate-process CLI persistence.

See [captured verification and synthetic CLI output](GURU-005-verification.txt)
for the actual platform, commands and results. Tests use synthetic fixtures and
temporary databases; their passing status is implementation evidence, not learner
mastery. GURU-004H and GURU-004M remain closed. GURU-005 acceptance awaits architect
review of this implementation evidence.
