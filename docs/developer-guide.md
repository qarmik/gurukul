# Gurukul developer guide

Gurukul is a local, single-learner workspace. Python 3.11 or newer is required.
The runner targets macOS and Linux; it is not a sandbox for untrusted code.
For a new disposable checkout, from the repository root:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/gurukul --root "$PWD" start
.venv/bin/gurukul --root "$PWD" resume
.venv/bin/gurukul-workspace --root "$PWD"
```

The workspace needs an existing local session and serves the browser on loopback.
The default launch makes no live model calls. The optional `--sample-guru`
workspace flag enables a fixed sample, not a live tutor. Local state and learner
evidence under `var/` are not part of the public repository.

## Design and verification references

- [First exercise (D01)](../content/c0_b01/d01.json) and [curriculum map](../content/curriculum/map.json).
- [Architecture baseline](architecture-v0.1.md) (historical), [execution capture](GURU-002.md), and [saved-answer checks](GURU-003.md).
- [Retrieval and assessment authority](GURU-006.md) and [workspace setup, storage, and local request boundaries](GURU-007.md).
- [Ask Guru source and admission checks](GURU-010.md), [opt-in live launcher](GURU-011.md), and [live trial closeout](GURU-011-live-closeout.md).

The older notes describe the verification status of their own revisions.
Read the linked verification context before applying a result to a later
revision. A software test or successful execution is not a learner assessment
pass. The live launcher can make a billable request and should not be used
as an ordinary smoke test.
