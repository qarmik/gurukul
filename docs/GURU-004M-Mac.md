# GURU-004M Mac setup and live acceptance

Current status: **PASS — GURU-004M scoped integrated acceptance**, recorded by
G004M-CLOSE on 2026-10-16. See the
[learner-supplied Mac ledger verification and architect decision](GURU-004M-ledger-verification.md).
The procedures, commands and pending-review statements below are historical and
preserved unchanged. They do not authorize a rerun. The verified original session
has consumed all 4/4 supervisor reservations; failures, branching and restarting
do not reset that budget. No test reruns or provider calls are required for closure.
GURU-004H remains closed. GURU-005 remains **BLOCKED pending a separate authorized
dispatch**, including after this GURU-004M acceptance.

## Targeted rerun after the supervised Guru contract repair

Account/model setup and a real approved Claude ORIENTATION intervention have
already passed in the supplied live run. Full acceptance is blocked at the Guru
contract boundary. The [exact mismatch and repair](GURU-004M-contract.md) are
offline verified. Do not repeat setup or the original failure trajectory.

The corrected patch must be present in the Mac checkout before this test. A
pull alone does not install unpublished local commits. Once the patch has been
published or applied locally, verify the revision and run the twelve regressions.

1. At the shell, synchronize the repair and run the targeted regressions:

   ```sh
   cd /Users/qarmik/Documents/GitHub/gurukul
   git pull --ff-only
   git rev-parse --short HEAD
   PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_supervised_contract.py' -v &&
   python3 scripts/hermes_live_teach.py \
     --runtime-root /Users/qarmik/GurukulRuntime \
     --continue 198b081e-17f5-4d71-87e1-5cb1152a5cf0 \
     --maharishi --verbose
   ```

2. At the Gurukul prompt, submit only `what are you talking about?` first.
   Require a saved runtime PASS, direct handling of the confusion/meta-question,
   no ghost question, ungraded admission, evidence still unresolved, mastery
   false and an open input prompt. Require a real `APPROVED` Anthropic directive
   with HTTP 200 selecting ORIENTATION, with no automatic retry. A deterministic
   fallback alone does not satisfy this targeted live expectation. If BLOCKED, stop and
   retain this new call ID; its local report now includes structural diagnostics
   for schema/authority failures. Do not repeat the failed turn automatically.

3. Only after that turn succeeds, submit `where did that question come from?`,
   then `you are just moving in loops`, then `check my understanding`, one at a
   time. Answer the fresh check in your own words. Require the retired question
   to remain absent, profile expiry/explicit-check exit, ordinary evidence
   admission resuming and no mastery, progression, curriculum or security drift.
   Quit with `/quit` and share the terminal output plus final call ID. Keep the
   linked raw evidence locally for review.

Done proof is the actual integrated transcript and parent-ledger evidence across
those turns, including the existing isolation probes and provider budgets.
Offline fixtures do not complete GURU-004M. GURU-005 remains blocked until review
of this targeted run passes.

## Original setup procedure (already completed in the supplied run)

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
