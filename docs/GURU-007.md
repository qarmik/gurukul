# GURU-007 — minimal local workspace

Status: **PARTIAL — implementation committed for architect review; browser workflow and Mac launch verification outstanding.** Main is unchanged. Base: `4d33a9a04944052141aaf46c631d700525fa1c54`. No provider calls or real learner-state writes were made. GURU-004H/M and GURU-005 remain closed; GURU-006 acceptance stands. Book companion PR #1 is unchanged.

## Learner surface

One local browser page provides task, plain Python editor, saved revision, evidence-version selector, Run, Submit for review, captured output, canonical status, deadline/countdown, reservations, exact assistance statement, Help/Exit and separate review display. The learner selects deliberate-error or repaired evidence; paths, UUIDs and receipt assembly are internal. Receipts remain optional diagnostics.

Preparation starts with an empty draft. Approved variant task data is returned only after the existing canonical opening succeeds. Start requires the readiness checkbox. It consumes one existing obligation; it never schedules another. Run preserves a version. Submit captures or reuses the matching repaired version and asks the canonical controller to complete using the assessment-owned failure. Only confirmed canonical completion displays `COMPLETION_CONFIRMED`. Successful execution and saved drafts are separate states.

Prior learning is legitimate. Exact statements remain `declared_only`; the interface neither verifies absence of outside help nor labels unsupported syntax misconduct. Ask Guru is explicitly unavailable. No substitute tutor or provider relay is implemented.

## Installation and launch

An operator must supply Python **3.11 or newer**, an installed project and an existing canonical session before learner use. The project already requires 3.11; the workspace enforces this before opening state. A Mac's old system Python 3.9 is not silently substituted. Example operator setup:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install .
```

The learner then double-clicks `scripts/Gurukul.command` in Finder. It uses the repository `.venv/bin/python`, or an explicitly configured `GURUKUL_PYTHON`. It opens the browser automatically. Operator alternative: `gurukul-workspace --root /absolute/repository`. No session is created automatically. Launch against real learner state is outside this build verification and awaits review.

Learner execution uses that same interpreter through the accepted runner; each execution retains `python_version`. Startup and state expose the exact interpreter. Historical Python 3.9 execution records are untouched. The wheel contains all three assets and the console entry point. Finder execution itself is not verified on this Linux host.

## Storage and authority

| Operation | Durable record / guard | Retry and crash behavior |
| --- | --- | --- |
| Draft save | `workspace_drafts`, schema version 4, session/context, revision, exact UTF-8 hash, update time; BEGIN IMMEDIATE compare-and-swap | Stale revisions are rejected; editor contents remain visible for explicit reconciliation. Drafts are mutable; submitted snapshots are not. |
| Run / Submit | `workspace.operation_requested` binds context, revision, source/hash, role, action and existing pair before worker dispatch | Deterministic operation identity plus shared workspace lock prevents duplicate dispatch. Immutable `source.py` and canonical attempt/reservation follow. Replays reconcile, never rerun an interrupted operation. |
| Execution | Existing submissions/runner and assessment controller | Practice attempts receive a durable parent-bound identity. Assessment reservations, snapshots, role immutability, limits and canonical lock remain authoritative. |
| Completion | Existing `complete` command plus `workspace.operation_finished` causally linked to the request | Completed command survives a lost response. Crash between execution and completion reports preserved execution/completion unresolved; it does not automatically retry completion or extend the deadline. |
| Declaration | Existing typed `assistance.recorded`, optional exact text/source/reported statement time | Scope binds the selected attempt and original failed pair. Actual event recording time remains current; reported assistance timing remains a separate field. Conflicting facts are retained under existing eligibility rules. |
| Human review | Separate `evidence.review_recorded`, reviewer identity, criterion findings, rationale, both source and canonical result hashes | Requires a closed assessment, explicit configured reviewer identity and separate reviewer credential. Idempotent transaction. Cannot close an assessment, change historical outcome/eligibility or grant capability. |
| Help / Exit | Existing canonical exit command | Exit commits before any teaching could be authorized. Teaching remains unavailable in this slice. |

No deadline, checker, catalogue, curriculum, eligibility policy or mastery rule is changed. An existing completed evidence role cannot be replaced with edited source. The UI reports this instead of silently submitting an older version. A fresh revision is not a retry of an uncertain earlier operation; unresolved reservations remain counted and require explicit reconciliation.

Unsupported syntax preserves `NEEDS_REVIEW`, source, execution and the open lifecycle; the learner must explicitly exit for review. There is no automatic acceptance of arbitrary syntax. Infrastructure failure, pending execution, program error, deadline expiry and interruption retain their distinct canonical observations.

The separate workspace orchestration lock does not own idle browser input time. The existing canonical assessment/tutoring lock authorizes execution and opening. Direct practice and teaching requests cannot bypass an active assessment. Historical review writes do not authorize tutoring.

## Local request boundary

The learner server is separate from the provider relay and binds only `127.0.0.1` on an ephemeral port. Root and active session are fixed at launch. Host is exact; write Origin must match; API reads reject foreign Origins. API requests require a random per-launch credential. The initial URL fragment is exchanged for an HttpOnly SameSite=Strict cookie and removed from the address. Provider and reviewer credentials are never returned to learner assets/state. Fixed asset routes, request size/schema limits, CSP and no-store responses apply. No request accepts a filesystem path or root.

This reuses the existing local Python runner, not a new hostile-code sandbox. The source itself runs with existing runner permissions. Local operator/process trust remains necessary; this is not a multi-user or remote service.

Reviewer configuration is operator-only: `--reviewer-id` plus `--reviewer-token-file` (private regular file, at least 32 characters). `POST /api/review` requires that separate bearer token and exact Origin/Host. Payload names: `context`, `request_id`, `source_hashes`, `result_hashes`, `criteria`, `rationale`. Reviewer identity comes from launch configuration, not learner input. Criteria: five_variables, text_and_numbers, print_initial_values, reassign_and_reprint, quoted_text_repair, variant_conformity; findings are demonstrated/not_demonstrated/unresolved. This first slice provides a narrow administrative API, not a reviewer dashboard.

## Verification and limitations

Actual completed Linux x86_64 / Python 3.12.14 captures:

- [Workspace suite](GURU-007-workspace-verification.txt): `Ran 25 tests in 4.507s`, `OK`.
- [Full suite](GURU-007-full-verification.txt): `Ran 340 tests in 18.301s`, `OK (skipped=1)`.
- [Synthetic HTTP workflow](GURU-007-synthetic-workflow.json): neutral preparation → practice failed Run → repaired Submit/CHECKS_PASS → explicit assessment Start → own failed Run → repaired Submit → CLOSED/COMPLETED_FOR_REVIEW, two reservations, unchanged deadline, no grants.
- [Packaging and environment](GURU-007-packaging-verification.txt): wheel assets/entry point checked, shell and JavaScript syntax checks passed.

Focused cases cover restart/CAS, double-click replay, completed roles, private request binding, concurrent lock denial, crashes before worker/before snapshot/between execution and completion/after completion commit, late completion, unsupported syntax/review exit, declarations, reviewer isolation, direct tutoring denial, auth/Host/Origin/path restrictions and packaged assets.

The synthetic anchor is deliberately backdated in disposable test fixtures. It is not actual delayed learner retrieval. No real ledger, learner artifacts or provider is used for these tests. Earlier partial tool invocations were not counted as completed results. An initial completed terminal summary (340 tests, 17.934s) had a truncated saved capture; a capture-only repeat produced the complete 18.301s result linked above. No code changed between those full runs.

**Missing acceptance evidence:** the cloud browser returned `net::ERR_CONNECTION_REFUSED` on authenticated loopback navigation, including with the synthetic server held open. No public tunnel or broader binding was used. Therefore the browser edit/Run/Submit workflow, reconnect UI behavior and visual layout are not claimed verified. HTTP/service checks and JS syntax do not substitute for that proof. A local target-browser workflow and Mac Finder launch remain required before a full workspace PASS. No real learner attempt should be started for that verification; use disposable synthetic state.

The old interrupted learner attempt has a separate local supplied-receipt reconciliation. That learner-specific report is excluded from publication and supplied privately with the handoff. The attempt is not regraded, reopened or used as a fixture here.
