# GURU-004 — isolated real-runtime import probe

Setup evidence supplied from the Mac: pinned Hermes cc75e8f4021f7efab99158f57601be4d691a6da9, managed Python 3.14.7, clean checkout, successful pm/httpx imports. The earlier bootstrap solstice/httpx warning is unresolved at full runtime level until this probe runs. The synthetic ledger baseline and sandbox read/write/create denial probe passed.

Run from the Gurukul checkout:

```bash
python3 scripts/hermes_import_probe.py
```

The parent uses the installed PM environment composition helper, not activate or an install command. It checks source revision/cleanliness, obtains managed interpreter/dependency paths and rejects paths outside the dedicated GurukulRuntime root. It creates fresh temporary worker home/cwd and synthetic ledger files under ignored var/. No API credential is forwarded.

The first Mac run stopped with `no dependency environment is committed for this install`.
The original launcher resolved the managed base Python and supplied dependency paths via
PYTHONPATH, then changed HERMES_HOME to a fresh directory without PM facts. At this pin,
`pm.environments._require_own_dependencies` rejects that bare store interpreter. The
corrected parent reads `committed_venv` from the prepared dedicated install and launches
its `bin/python` without resolving away the venv symlink. Resolved targets are still
validated within GurukulRuntime. Upstream bootstrap remains unmodified; its supported
venv branch retains the interpreter's own dependencies. No facts/profile are copied,
and no repair or installation is attempted. The sandbox grants read access to that
dependency venv and managed Python, with the same write, process and network restrictions.
The worker records sys.prefix/base_prefix and refuses a bare interpreter. Bootstrap
SystemExit now produces a BLOCKED report with the completed denial checks.

Development regression tests cover venv-versus-resolved-base launch identity, rejection
of a symlink target outside the dedicated runtime, and missing venv rejection. These
are launcher tests only; the corrected Mac import and live teaching acceptance are pending.

The macOS profile denies network activity, process forking, shell execution, writes outside the temporary worker directory (except /dev/null), and reads under the user's home except the explicit runtime/source/dependency paths. Gurukul var/ is explicitly denied. Baseline filesystem, shell and loopback socket operations run in the parent. The restricted worker repeats the denial probes before importing the actual run_agent.AIAgent, verifies its constructor/turn interface, and checks the real empty tool-definition selection. The parent alone saves diagnostics under var/hermes-probes/.

This source was syntax-checked in the development environment. macOS execution is pending; no Linux simulation counts as boundary evidence. Any launch/import/permission mismatch is BLOCKED or FAIL. Do not loosen the ledger or shell restriction merely to make import pass. The script does not instantiate AIAgent, perform a teaching turn or claim before/after live tool-surface verification. Those remain required live acceptance steps. The probe intentionally denies all network; a later explicitly restricted provider route is still needed for inference.

Expected proof: status PASS; pinned revision; actual run_agent.py import path; Python version; constructor_verified and run_conversation_interface_verified true; empty_selection_tool_count zero; ledger_read/write/create, shell and network DENIED; sentinel_unchanged true. No model response exists yet.

The setup script installed optional browser/driver dependencies as part of upstream PM preparation. Installed binaries do not imply tool authority. This probe blocks shell/process launch and checks the selected tool definitions; live construction and turn-level controls must still be verified. GURU-003 Mac acceptance is already complete.
