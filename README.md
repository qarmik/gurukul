# Gurukul — GURU-003

Local session persistence and bounded execution for C0-B01-D01. Python 3.11+; this increment uses only the standard library.

From this project's root:

```bash
PYTHONPATH=src python3 -m gurukul start
PYTHONPATH=src python3 -m gurukul resume
PYTHONPATH=src python3 -m gurukul events
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The execution runner targets macOS and Linux; this release was tested on Linux. Windows execution is explicitly refused. Mac acceptance remains to be run on the learner machine.

Run from the project root or pass `--root /absolute/path/to/gurukul` before the command. Local state is created under `var/`. Close the terminal and run resume in a new process: the same session and pinned exercise return. Repeated start does not duplicate the session or its event.

Implemented: D01 package, version-pinned exercise storage, atomic session/event creation, append-only event guards, restart/resume and explicit Hermes-not-integrated status.

Not implemented: live Hermes teaching, hints, mastery decisions or retrieval transitions. No learner capability is claimed by these software tests. The initial teaching phase is persisted; do not mistake it for a completed lesson.

See docs/architecture-v0.1.md for the corrected design and docs/verification.txt for actual checks. The demonstration database is excluded from the deliverable; a fresh start creates your own session. Original curriculum and book files are not included.

## GURU-001 hardening

Resume verifies SHA-256 over stored exercise JSON bytes before parsing or returning content, and refuses a mismatch. This detects accidental content corruption; it is not protection against an owner changing both content and digest.

D01 version 2 references `content/sources.json`; see `docs/source-manifest.md` for the GURU-004 binding contract. Existing sessions retain their original version. Use a separate fresh project copy for the new-content smoke test; do not discard existing learner state.


## Submit and inspect (GURU-002)

Keep learner files under ignored `var/workspace/`. After starting a session, run your own file:

```bash
PYTHONPATH=src python3 -m gurukul run var/workspace/values_variables.py
PYTHONPATH=src python3 -m gurukul result ATTEMPT_UUID
```

Replace ATTEMPT_UUID with the returned `id`. Optional run flags: `--timeout 5 --output-limit 65536`. The capture command returns JSON with status, exit code and retained stdout/stderr. Command exit 0 means capture succeeded, not that the submitted program passed. Read `status`: completed, program_error, timed_out, output_limited, interrupted or runner_error. A submission with no committed completion is pending_or_interrupted, never assumed successful and never automatically rerun.

Only run your own beginner code. This is not a filesystem/network/memory sandbox. Run itself has no exercise correctness checks, tutoring or progression authority; the separate check command evaluates saved D01 evidence. It may be used while the session remains in the initial teaching phase; that phase is not updated by execution.

Source snapshots and raw output live under ignored `var/evidence/`; SQLite stores their hashes, metadata and append-only events. No learner evidence is automatically committed. See docs/GURU-002.md for limits, persistence behavior and acceptance proof.


## Check a saved D01 answer (GURU-003)

```bash
PYTHONPATH=src python3 -m gurukul check REPAIRED_ATTEMPT_UUID --failed-attempt FAILED_ATTEMPT_UUID
```

Use the UUIDs returned when you saved each run. The checker evaluates requirements and output, not just process exit. Missing failure evidence is incomplete; unsupported syntax is sent to review. CHECKS_PASS is not mastery or verified independence. No learner solution is generated. See [GURU-003](docs/GURU-003.md) for supported syntax, evidence rules and the new Mac verification commands. GURU-002 Mac verification has already passed.
