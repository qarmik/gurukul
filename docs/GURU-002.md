# GURU-002 — bounded execution and evidence

## Scope and boundary
The dedicated private `qarmik/gurukul` repository is the monorepo boundary. `gurukul-runtime` is the Python package. Parent baseline e4af77ca8fc5aae6eb4359b43769203ead8b5b77 was verified at GitHub main before implementation. Only source, documentation and synthetic verification enter Git. All actual learner files, databases, activity, camera data, credentials and telemetry stay outside tracked content (runtime state under var/).

## Execution contract
Accept a regular .py file (maximum 256 KiB). Save a unique, read-only source snapshot, hash it, and atomically record submission plus execution.submitted event before launching. Read back and verify the snapshot; run these bytes in a disposable directory, leaving the source file untouched. Each explicit run creates a new attempt UUID even for identical source.

Defaults: five-second wall-clock budget, 64 KiB combined stdout/stderr retention. Configurable ranges: 0 < timeout <= 60 seconds; 1–1048576 output bytes. These are code execution limits, not engineering work-time caps. Use the current Python interpreter with isolated mode, no shell, closed stdin and a minimal environment that does not inherit API keys. Collect binary output through nonblocking POSIX pipes. Keep exactly the capped prefix on overflow and mark output_limited; decoded display replaces invalid UTF-8 while binary evidence preserves retained bytes. Pipe selection does not establish total chronological ordering across stdout and stderr.

On deadline, output overflow, ordinary completion or Ctrl-C, clean up the child process group, then reap the direct child. Children that deliberately escape the process group are outside this boundary. OS process creation/reaping delays can exceed the nominal wall deadline. Memory use, network and filesystem access by learner code are not sandboxed. This runner is for personally authored beginner programs only. Linux tested; macOS implementation uses POSIX facilities but awaits machine acceptance. Windows run is rejected explicitly.

## Evidence and recovery
Migration 2 adds immutable attempt and execution records without replacing v1 sessions/events. An attempt references its session, which pins exercise identity/version. Output hashes, runner/Python versions, limits, duration, process exit code and completion timestamp are retained. Source and output are write-once through the application and chmod read-only; their hashes are verified by result inspection. This detects corruption, not malicious same-user tampering.

Filesystem writes precede their corresponding database transaction. If interrupted between them, unreferenced files may remain; no result is inferred from their existence. Submitted attempts without a committed execution remain pending_or_interrupted. No automatic recovery reruns are performed. A failed result/event transaction commits neither result nor completion event. A later explicit run is a new attempt. Abrupt controller/OS termination may leave a process needing manual cleanup; crash supervision is outside this increment.

Statuses distinguish completed (exit 0), program_error (nonzero process exit), timed_out, output_limited, interrupted and runner_error (infrastructure failure). None means an exercise passed or independent capability was demonstrated. Session phase and progression are untouched. stdin is EOF for D01; interactive input support is deferred until the relevant material needs it.

## Verification
Twenty automated tests pass, including the original eight. Coverage includes success and NameError capture, timeout, shared stdout/stderr cap, closed-pipe timeout, cleanup of a descendant holding pipes, no inherited test secret, spawn failure, invalid limits, three retained outcomes after database reopen and source edits, output corruption detection, failed completion transaction and migration preserving session/events.

`verification.txt` contains the test run. `GURU-002-acceptance.json` records an independent CLI exercise using synthetic fixtures and separate result processes. No real learner data or active-exercise solution is included. Baseline start/resume proof JSON files are likewise synthetic developer smoke tests.
