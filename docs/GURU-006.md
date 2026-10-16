# GURU-006 — bounded D01 retrieval and assessment

Disposition: **implementation evidence ready for architect review; acceptance
pending**. Parent reference `8f2c34588652ebea03f1fe05c33ab91a51a9a608`.
GURU-004H, GURU-004M and GURU-005 remain accepted and closed. This increment
uses synthetic data and mocked providers only. No learner assessment, provider
call, verified independence, mastery or curriculum advancement was performed.

## Authority and persistence

`src/gurukul/assessment.py` owns the narrow lifecycle commands and typed event
constructors. Existing append-only `events`, attempts, executions and evaluations
remain the storage mechanism; **no schema migration or historical backfill**.
Each command uses an explicit UUID, exact replay identity, `BEGIN IMMEDIATE`, and
an append-only command receipt. Phase updates and lifecycle events commit or roll
back together. The existing checker may separately retain its observation before
a completion transition; a crash there never closes the assessment or grants
credit. A new completion request can reuse that verified observation.

The canonical authority is the root's `var/gurukul.sqlite3`, with its explicit
active session and pinned exercise. `learning_authority.py` serializes lifecycle
operations and teaching with the same nonblocking POSIX file lock. Teaching holds
the lease across dispatch, admission and display. Missing, expired, inconsistent
or assessment-phase authority denies tutoring. This covers the live CLI's new
turns, continuations, cached display, and Maharishi `supervise`/`reserve` paths.
A continuation additionally must match the saved `learner_authority` session and
exercise hash. Historical unbound reports remain readable as evidence but cannot
be inferred into a new tutoring authorization. No historical records are rewritten.
New live teaching requires `--session-id SESSION_UUID` after canonical `start`.
The integration ledger remains separate; it receives the parent-owned lease,
not authority from a matching model label or transcript wording.

The lock/lease is local parent-process coordination, not protection against a
machine owner modifying Python, the filesystem or SQLite. No cross-ledger imports,
remote time attestation or external assistance attestation are added.

## Lifecycle and limits

| Existing state | Explicit action / evidence | Event and permitted result | Tutor access |
| --- | --- | --- | --- |
| Teaching, verified passing practice | Schedule with the local checked-event anchor | `retrieval.scheduled`; one unconsumed obligation | Allowed |
| Scheduled | Parent clock reaches due time; explicit due command | `retrieval.became_due`; no automatic opening | Allowed |
| Due, teaching/remediation | Explicit open; approved unused descriptor; pinned exercise; exposure review | `assessment.opened`; phase assessment | Denied before dispatch |
| Open | Reserve role/source/limits/request identity before execution | `assessment.run_reserved`, atomic `assessment.submission_bound` with ordinary submission; retained snapshot/result | Denied |
| Open | Missing failed/repaired IDs | `assessment.observation_recorded` NEEDS_EVIDENCE, stays open | Denied |
| Open | Infrastructure, timeout or output-limited evidence | EXECUTION_BLOCKED, remains distinct from learner failure | Denied |
| Open/pending | Worker/process interruption or elapsed deadline | Interrupted status; reservation and snapshot retained | Denied |
| Interrupted, within deadline | Explicit resume | `assessment.resumed`, acknowledges old pending IDs, never reruns them | Denied |
| Open | Own failed/repaired pair, base checks pass and admitted variant conforms | `assessment.closed` COMPLETED_FOR_REVIEW; teaching | Allowed after commit |
| Open | Completed final program fails checks/conformity | `assessment.closed` FAILED; remediation | Allowed after commit |
| Open/interrupted | Explicit help exit | `assessment.closed` HELP_REQUESTED; remediation | Allowed after commit |
| Open/interrupted | Explicit abandon/interrupted/review exit | Closed with distinct outcome; teaching | Allowed after commit |
| Remediation | Newly submitted local failed/repaired practice after exit, verified CHECKS_PASS | `remediation.completed`; teaching; usable scheduling anchor | Allowed |
| Later due obligation | Separately approved unused descriptor | New bounded assessment; old facts remain immutable | Denied while open |

Policy `d01-assessment-1` schedules **24 hours after the verified practice or
remediation anchor**, not 24 hours after the scheduling command. This is an
operational first policy, not a newly invented canonical learning requirement.
Explicit due observation and opening remain necessary. Backwards observed clock
movement is refused. Each assessment pins a **20-minute deadline and four
execution reservations**; failed/infrastructure/interrupted reservations are not
refunded. Limits and identity are saved per reservation. Elapsed deadlines require
an explicit interruption/review exit; restart cannot reset them. Completed roles
cannot be overwritten. Infrastructure roles may be retried explicitly within the
original bounds. A deliberate NameError is required artifact evidence, not an
automatic failed assessment. Duplicate execution requests inspect their original
pending/result record and cannot execute again. Orphaned reservations stay pending;
explicit recovery does not erase them. There is no automatic retry.

Opening pins exercise, catalogue descriptor/rules/approval, base checker/spec,
canonical curriculum/orientation and lifecycle-policy hashes. Execution/recovery/
completion refuse changed checker/curriculum/policy; completion also revalidates
the approved descriptor. There is always an explicit review exit. Base D01 exercise,
checker and check specification are unchanged. Assessment-owned role bindings are
mandatory: an ordinary practice pair cannot be borrowed for completion.

## Commands

Run with `PYTHONPATH=src python3 -B -m gurukul --root ROOT` followed by:

```text
retrieval-schedule CHECKED_EVENT_UUID --request-id UUID
retrieval-due RETRIEVAL_UUID --request-id UUID
assessment-open RETRIEVAL_UUID --variant-id CANDIDATE_ID --request-id UUID
assessment-status [ASSESSMENT_UUID]
assessment-run ASSESSMENT_UUID --role deliberate_failure --source broken.py --request-id UUID
assessment-run ASSESSMENT_UUID --role repaired --source repaired.py --request-id UUID
assessment-complete ASSESSMENT_UUID --attempt-id REPAIRED_UUID --failed-attempt FAILED_UUID --request-id UUID
assessment-resume ASSESSMENT_UUID --request-id UUID
assessment-exit ASSESSMENT_UUID --reason help --request-id UUID
remediation-complete EVALUATION_ID --request-id UUID
```

Exit reasons: `help`, `abandon`, `interrupted`, `review`. Completion without pair
IDs records missing evidence rather than fabricating a failure. Existing `result`,
`check`, `assistance`, `eligibility` and `events` commands remain available as
observational evidence tools. Ordinary `run` cannot bypass an open assessment.
No CLI simulated-clock or approval-override option exists. For assistance commands
and current eligibility use the accepted [GURU-005 policy](GURU-005.md).

Completion records historical G005 eligibility and assistance provenance alongside
`requires_review: true`. Unknown assistance remains UNKNOWN/HOLD; a declaration
alone remains DECLARED_ONLY. Later assistance is evaluated by the existing current
eligibility command, without rewriting the earlier completion. Neither
CHECKS_PASS, READY_FOR_REVIEW nor COMPLETED_FOR_REVIEW grants independent credit,
mastery, progression, or a curriculum gate. A help exit records the request and
phase change; it does not falsely claim help was actually delivered.

## Candidate catalogue for architect review

`content/assessments/d01-candidates.json` contains two **unapproved** candidates.
Production opening refuses both. Approval requires an explicit reference and the
exact reviewed descriptor/rule hashes; tests approve temporary copies only.
Hashes below cover canonical JSON objects, not whole files.

| Candidate | Five initial values | Two reassignments | Descriptor SHA-256 |
| --- | --- | --- | --- |
| `d01-counter-a` | label="cedar", city="Pune", count=4, rate=1.5, limit=12 | count=9, label="birch" | `c86dabca70790a631150cb0ecac3ddf126b4d1279ba6bc6826657fe0bfcf33dd` |
| `d01-stock-b` | tag="amber", zone="west", boxes=6, unit=2.5, ceiling=20 | zone="east", unit=3.5 | `8185f84147c0c5f6ba737f609618c309f543db891ea1b8d12423e572a292ee53` |

Both use the exact prompt:

> From a blank file, construct the D01 program using the supplied five initial
> values; print them, apply the two supplied changed values and print those again.
> Preserve a deliberate bare-text NameError and its unassisted quoted-text repair.
> No book, prior source or tutoring during this attempt.

Both bind base exercise canonical hash
`758e6091ea4c8093fe97d32b35e93383179289afded0b1e616f6806b1f30b19c`
and rules `{"kind":"d01-task-data-1","preserve_base_checker":true}`;
canonical rules hash
`c8b8bc914b99843047c860a8a66fc761cd2bdd8ede783e50ffe324ebe51d59f6`.
Conformity conjunctively requires the descriptor's initial assignments and prints,
then its two changed values printed through their variable names. The unchanged
base checker still validates the full D01 construction and linked NameError/quote
repair. These add task data, not new learning requirements or a looser checker.

Opening consumes the descriptor permanently in the local ledger, including an
abandoned/help/interrupted attempt. New session/attempt/source identifiers do not
refresh it. Historical unscoped solution exposure blocks opening pending review.
Exposure tied to an assessment-owned attempt remains associated with its used
variant; a distinct reviewed unused descriptor may open, while unchanged G005
policy can still conservatively HOLD its eligibility. No general G005 exposure
restriction is narrowed, and no form of opening proves independence. Prior
failures, assistance, reservations and decisions remain immutable.

## Verification and remaining acceptance limits

[Captured verification](GURU-006-verification.txt) records Linux x86_64,
Python 3.12.14:

- Focused lifecycle and affected integration suites: **124 tests, OK**, including
  32 new lifecycle tests in `tests/test_assessment.py`.
- Completed full suite: **306 tests, OK (skipped=1)**. The skip requires actual
  macOS sandbox-exec. Incomplete earlier process invocations are explicitly
  retained in the capture and are not passing results.
- Separate-process synthetic CLI: unapproved opening denied; temporary test-only
  approval; explicit open; tutoring denied before dispatch (zero calls); worker
  interruption; restart and duplicate request preserve the snapshot/reservation;
  explicit resume; own NameError/repaired pair; declaration-only completion for
  review. Three reservations include the preserved interrupted attempt.
- Focused cases also cover help exit, program failure/remediation, later new
  practice/retrieval, wrong variants, exposure, clock rollback, four-reservation
  exhaustion, borrowed evidence, transaction rollback and cross-process locking.
  Existing supervisor/render tests supply explicit synthetic canonical leases.

Simulated clocks and a backdated synthetic practice anchor prove scheduling
behavior only, **not actual delayed learner retrieval**. The CLI capture used a
temporary database and temporary catalogue approvals, never real learner state.
Catalogue approval, actual delayed retrieval and GURU-006 acceptance remain
separate architect decisions. No new Mac/provider evidence is claimed. There is
no daemon scheduler, external identity/clock attestation, assessment orchestration
beyond this D01 slice, generic NLP mechanism, mastery award or gate advancement.
