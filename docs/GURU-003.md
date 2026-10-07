# GURU-003 — deterministic D01 checks

GURU-002 Mac verification already passed: user supplied commit 7d86ca4 and 20 passing tests. That acceptance remains recorded; the new Mac verification below targets GURU-003 only.

## Check a saved answer

Use the attempt IDs returned by `run`. After a deliberate unquoted-text failure and its repair have both been saved:

```bash
PYTHONPATH=src python3 -m gurukul check REPAIRED_ATTEMPT_UUID --failed-attempt FAILED_ATTEMPT_UUID
```

Replace both placeholders with actual UUIDs. Without `--failed-attempt`, the final program is checked, but missing failure/repair evidence prevents CHECKS_PASS. This command reads saved snapshots and execution records. It never executes a solution, reruns learner code or edits the learner's file. JSON output is the evaluation; CLI exit 0 means a check was recorded, not that requirements passed. Read `outcome` and individual `checks`.

## Requirements and interpretation

The versioned specification is `content/checks/d01-v1.json`. It accepts the exact pinned hashes of D01 versions 1 and 2; no exercise content or existing session is rewritten. It requires at least five distinct assigned names; the printed initial values must include text and numbers. At least five initial values must be printed through variable references, not a hardcoded output string. At least two names must then be assigned changed values and printed after their initial values. Merely assigning the same value, reverting before printing, or changing a value without printing it does not demonstrate this requirement.

A narrow AST interpreter derives output from straight-line assignments and print calls without eval/exec. Supported expressions: string/numeric literals, names and signed numbers. Print accepts multiple literal/name arguments and literal sep/end. Rebinding print, control flow, functions, collections, f-strings and other unsupported constructs go to review; no claim that all valid Python is handled. The independently derived stdout must equal the saved stdout, and the saved process must have completed with exit zero. Unexpected syntax or undefined names fail a supported answer. Timeouts, output-limited captures, incomplete attempts and infrastructure errors block correctness evaluation.

Failure evidence must be a prior completed failed run in the same session. Its saved stderr must contain NameError, and AST interpretation must encounter an undefined name on an assignment RHS. A supported repair changes that name to the identical text in quotes, with the remainder of the AST unchanged. Whitespace/comments may differ. Broader edits require review rather than a false verdict. Other error types, wrong-session evidence and failure after the alleged repair do not satisfy this requirement.

This cannot verify that the error was deliberate, that the learner read/closed the book, started from blank, or repaired without external help. Those limitations are in every result. CHECKS_PASS means only the supported observable requirements passed. It never grants mastery, changes phase, advances a gate or establishes independence.

## Outcomes and persistence

- CHECKS_PASS: supported observable requirements and paired evidence pass.
- FAIL: one or more checked requirements demonstrably fail.
- NEEDS_EVIDENCE: final program checks pass but the required failed attempt is missing.
- NEEDS_REVIEW: unsupported code, exercise identity/hash or a broader repair needs review.
- BLOCKED: a complete usable execution is unavailable.

Each immutable evaluation records attempt ID, source hash, exercise ID/version/hash, checker ID/version/source hash, spec hash, execution digest and failed-attempt evidence hashes. Its content-derived ID makes repeated identical checks idempotent. Schema migration 3 adds evaluations without changing earlier session/execution data. Evaluation and assessment.checked event commit atomically. Source/output/exercise integrity failures refuse evaluation. Local file hashes are not an adversarial attestation system.

All learner results remain under ignored var/ (SQLite and snapshot artifacts). Only synthetic tests and their summary enter Git. Synthetic checker fixtures are engineering verification, not learner answers or capability evidence.

## Exact Mac verification (new increment only)

```bash
cd /Users/qarmik/Documents/GitHub/gurukul
 git pull --ff-only
 git rev-parse --short HEAD
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_checks.py' -v
```

Expected: 24 new tests, all passing. Tests include the check CLI in a separate process, full paired evidence, incorrect-but-running programs, output mismatch, missing/wrong/late evidence, review outcomes, integrity failure, idempotency, rollback, immutable records and migration preservation. They use temporary synthetic data and do not touch the learner database. The GURU-002 Mac commands need not be repeated.
