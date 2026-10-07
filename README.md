# Gurukul — GURU-001

Local session persistence for C0-B01-D01. Python 3.11+; this increment uses only the standard library.

From this project's root:

```bash
PYTHONPATH=src python3 -m gurukul start
PYTHONPATH=src python3 -m gurukul resume
PYTHONPATH=src python3 -m gurukul events
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

PowerShell: set `$env:PYTHONPATH="src"` first, then use `python -m gurukul start` (and the other commands without the PYTHONPATH prefix). This build was verified on Linux; Windows has not been tested.

Run from the project root or pass `--root /absolute/path/to/gurukul` before the command. Local state is created under `var/`. Close the terminal and run resume in a new process: the same session and pinned exercise return. Repeated start does not duplicate the session or its event.

Implemented: D01 package, version-pinned exercise storage, atomic session/event creation, append-only event guards, restart/resume and explicit Hermes-not-integrated status.

Not implemented: learner code execution, automatic checks, live Hermes teaching, hints, mastery decisions or retrieval transitions. No learner capability is claimed by these software tests. The initial teaching phase is persisted; do not mistake it for a completed lesson.

See docs/architecture-v0.1.md for the corrected design and docs/verification.txt for actual checks. The demonstration database is excluded from the deliverable; a fresh start creates your own session. Original curriculum and book files are not included.

## GURU-001 hardening

Resume verifies SHA-256 over stored exercise JSON bytes before parsing or returning content, and refuses a mismatch. This detects accidental content corruption; it is not protection against an owner changing both content and digest.

D01 version 2 references `content/sources.json`; see `docs/source-manifest.md` for the GURU-004 binding contract. Existing sessions retain their original version. Use a separate fresh project copy for the new-content smoke test; do not discard existing learner state.
