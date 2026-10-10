# GURU-004M Mac setup and live acceptance

GURU-003's 24 Mac tests already passed; these instructions do not repeat them.
No new setup package or Docker/Colima installation is needed. If an old teaching
process is open, enter `/quit` at its Gurukul prompt first.

## Dedicated Anthropic setup

At the shell:

```sh
cd /Users/qarmik/Documents/GitHub/gurukul
git pull --ff-only
git rev-parse --short HEAD
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_maharishi.py' -v &&
python3 scripts/maharishi_setup.py --model claude-sonnet-5-5
```

Expected: 21 new offline tests pass. Setup prompts privately for the dedicated
Gurukul Anthropic key unless its dedicated local file already exists. Enter it
only in that hidden terminal prompt. It never prints the key and makes no
generation call. Successful setup prints `setup_status: PASS`, the resolved model,
verified limits and `generation_calls: 0`. If it fails, stop and share only the
safe setup status/HTTP code; do not disclose the key.

The default new key file is
`/Users/qarmik/GurukulRuntime/credentials/anthropic-maharishi-api-key`.
If the dedicated Gurukul key was already stored elsewhere, explicitly select that
owner-only file with `--key-file /absolute/path/to/dedicated-key` instead. No
personal key/profile is automatically reused. Settings remain outside the checkout.

## Actual Guru + Maharishi run

After setup passes, resume the previously saved trajectory/source:

```sh
python3 scripts/hermes_live_teach.py --maharishi --verbose --continue 69b493fc-91b6-4979-9d7b-3d2d82a240ff
```

This starts the actual pinned Hermes runtime. A healthy submitted message has one
Guru call. A triggered message can additionally spend one bounded Claude call;
there are no retries, and the integration session has four supervisor calls total.
If that historical call is unavailable, stop; a deliberate fresh test can instead
use `--maharishi --verbose --choose-source` to select the same approved local HTML.

Submit these one at a time at the **Gurukul prompt**, not the shell:

1. `explain with an analogy`
2. `explain it more simply`
3. `what are you talking about?`
4. `where did that question come from?`
5. `you are just moving in loops`

The resumed history may already trigger orientation on the first turn. At or before
the loop complaint, require a real Anthropic decision:

- `supervision.status = APPROVED`, provider `anthropic_direct`, HTTP 200,
  resolved model matching the verified settings, usage and a validated INTERVENE
  directive. `SUPERVISION_FAILED`/deterministic fallback does not count as live
  Maharishi acceptance.
- The stale question is suppressed/retired. Guru addresses the learner concern
  and explains the question's origin when asked. No automatic ghost question is
  appended. Semantic compliance must be read in the actual explanation.
- Provisional judgment is `not_applicable` during suspended evidence collection;
  the canonical evidence requirement remains unresolved, mastery false, phase and
  curriculum unchanged. The process stays at the Gurukul input prompt.
- The real Hermes `run_conversation_path` is recorded, tools remain empty, the
  ledger stays parent-owned, and every before/after denial probe is DENIED,
  including `supervisor_credential_read`. Each Guru turn has one provider call.

Then submit `check my understanding`. Guru should offer a fresh representation
or question, not restore the retired question. Answer it in your own words and
confirm ordinary evidence admission resumes without mastery or progression.
If a security/runtime error occurs, stop; never weaken the sandbox to continue.

Type `/quit`. Keep the final resume call ID. The full linked transcript, supervision
audit/usage and provider responses are automatically saved in the ignored local
`var/hermes-live/` evidence and original session ledger. Do not commit them.
Share the terminal output of this bounded run, with secrets excluded, for final
integrated acceptance. GURU-005 remains blocked until that review passes.
