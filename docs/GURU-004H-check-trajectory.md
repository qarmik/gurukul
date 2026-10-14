# GURU-004H — requested-check follow-up state

Disposition: **scoped live behavior PASS; parent-state automated verification
PASS on Linux and macOS**. The Mac verification below ran at repair commit
`f2f94be1cbed076503ad7ff405f40cb40fa71bd8`. No new live inference under the repaired
policy is claimed. GURU-005 remains **BLOCKED**. Repair baseline:
`7a334a2063bb1f93dd6a44405d8daeb0ab31f7c9`.

## Supplied live evidence

The attached `Pasted markdown(20261014-014611).md` is 143,872 bytes;
its SHA-256 is
`1adbbf95e674d4127087808d808ac5f2fdc1da80d751ddbe4aba16a0191e668c`.
The six top-level reports include three earlier turns already reviewed and
these three new linked turns under policy `d01-pedagogy-11-control-contract`:

| Call | Learner input | Observed result |
| --- | --- | --- |
| `3069be6e-3f7f-40ae-806f-1714413ab3be` | `check my understanding` | PASS/CONTINUE; bound REQUEST_FRESH_CHECK, ungraded, no answer evidence; a fresh question asks about reassignment from 4 to 9. |
| `66ca9d0a-359d-4647-a7f5-d6876a1f8b47` | `9 because it is the first value the variable will look for on running the code` | PASS/CONTINUE; exact answer admitted, provisional judgment partial; targeted correction and a variation from 9 to 4. |
| `b6840d25-7dbb-4074-8eab-dae9477cc2ea` | `the value would change to 4 because it has been reassigned` | PASS/CONTINUE; exact answer admitted, provisional judgment correct; feedback shown once, no further displayed diagnostic question, mastery false. |

The first prediction is right; its explanation suggests a search for a first
value. The targeted follow-up is justified by that partial explanation, rather
than repetition after a correctly completed check. The learner's correction
answers that follow-up. These observations do not prove independent construction.

All six reported learner-input hashes and nine exact span bindings were
independently checked against the transcript. Parent call links and supervisor
trigger evidence also match. Each report records one Guru request, HTTP 200,
no provider error, empty tool lists, denied boundary probes, verified parent
ledger record, unchanged curriculum v0.8.3 and no mastery grant. The on-device
SQLite database and full provider response bodies were not supplied or read.

The final supervisor attempt records ValueError before reservation or provider
generation, no structural fallback grounds, and no profile change. This is not
evidence of a Claude outage or a new successful Claude request. Earlier
submission-process questions were still answered inadequately; they are not
counted as a pedagogical success. No submission workflow or supervisor role is
added by this repair.

## Confirmed parent-state defect and minimal repair

Although the last displayed reply pauses, its parent admission still has
`requested_check_completed: false` and keeps the answered variation as
`pending_question`. The old parent policy recognizes a requested check only
when the immediately preceding admission has REQUEST_FRESH_CHECK. A partial
answer and its follow-up therefore erase that association. A later correct
answer could admit another unsolicited check, and a pause can leave the
answered question pending across restart.

`src/gurukul/pedagogy.py` now derives `requested_check_active` from the existing
bounded, parent-verified history. A check begins only with an admitted, bound
REQUEST_FRESH_CHECK and an actually displayed question. Each later exchange
must be linked by its parent `question_answered` to the tracked question.
Partial answers, clarification and recoverable reference rejection can retain
that chain. A correct admitted answer or an existing completion ends it;
unlinked questions, missing origins and unbound/rejected controls cannot
activate it. The current question must still match the linked pending question.

The existing completion consumer now closes the check after a correct follow-up,
suppresses a further unsolicited diagnostic question, clears conversational
pending state and retains the canonical source-file/failed-run/successful-run
requirement. Existing save/reload code preserves that derived completion.
Policy version is `d01-pedagogy-12-check-trajectory`.

No surface word or raw model intent label supplies this state. The learner's
command and admitted question links supply it. Conversational correctness
remains a model observation; completion grants no mastery, independence,
curriculum advancement or additional provider permission. Historical raw
responses and on-device events are not rewritten.

## Exact regression tests added

Six tests added to `tests/test_control_contract.py`:

1. `test_requested_check_survives_partial_followup_and_closes_after_correct_answer`
2. `test_correct_followup_pause_clears_the_answered_pending_question`
3. `test_requested_check_survives_ungraded_clarification_without_a_new_question`
4. `test_requested_check_survives_reference_recovery_without_false_completion`
5. `test_requested_check_does_not_attach_to_an_unlinked_followup`
6. `test_unbound_or_rejected_control_cannot_start_a_requested_check_trajectory`

The first two use the supplied learner wording and question sequence with
synthetic response envelopes. They verify both an unwanted proposed extra
question and the observed pause, exact span binding, raw proposal preservation,
canonical artifact requirements, no mastery and persistence through restart.
The tests do not claim to contain recovered provider bytes. The existing
partial-answer fixture now includes the parent admission's bound/display/status
fields instead of an action label alone.

Before repair, 29 control tests ran with seven assertion failures across five
new tests. After repair:

```text
$ PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_control_contract.py' -v
Ran 29 tests in 0.147s
OK

$ PYTHONPATH=src python3 -m unittest discover -s tests -v
Ran 235 tests in 4.932s
OK (skipped=1)
```

The full suite has 234 passing tests and the existing macOS-only sandbox skip
on Linux. [Complete captured output](GURU-004H-trajectory-verification.txt)
also contains the pre-repair failures. A derived replay using the report's
model proposals and actually displayed content now produces:

```text
3069be6e-3f7f-40ae-806f-1714413ab3be CONTINUE not_applicable active=False completed=False
66ca9d0a-359d-4647-a7f5-d6876a1f8b47 CONTINUE partial active=True completed=False
b6840d25-7dbb-4074-8eab-dae9477cc2ea CONTINUE correct active=True completed=True pending=''
```

That replay validates the parent repair against supplied observations, not a
new live generation. No paid inference was performed during this repair.

Changed files: `src/gurukul/pedagogy.py`, `tests/test_control_contract.py`, this
report, `docs/GURU-004H-trajectory-verification.txt`, and the follow-up link in
`docs/GURU-004H-control-contract.md`. GURU-005 remains blocked.

## Mac verification — G004H-TRAJECTORY-VERIFY — PASS

On 2026-10-14 the learner supplied the complete Mac terminal result for:

```sh
cd /Users/qarmik/Documents/GitHub/gurukul &&
git pull --ff-only &&
git rev-parse --short HEAD &&
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_control_contract.py' -v
```

The pull fast-forwarded `7a334a2..f2f94be`, the printed revision was `f2f94be`,
and all 29 named test entries ended in `ok`. Exact result summary:

```text
----------------------------------------------------------------------
Ran 29 tests in 0.177s

OK
```

This is learner-supplied Mac execution evidence, not a local Linux rerun. It
meets this micro-task's done criteria, including the partial-answer chain,
clarification/recovery, pending-question closure and persisted restart tests.
The earlier live final call remains
`b6840d25-7dbb-4074-8eab-dae9477cc2ea`; no new paid inference was requested.
The receipt update changes documentation only, so it does not require another
code-test cycle.

The GURU-004H build is ready for architect review with the initial
[semantic authority audit](GURU-004H.md), the
[control-contract repair](GURU-004H-control-contract.md), and this trajectory
repair and Mac receipt. The limited live teaching coverage and earlier
submission-process/supervisor findings above remain explicit. This verification
does not grant mastery or unblock GURU-005.
