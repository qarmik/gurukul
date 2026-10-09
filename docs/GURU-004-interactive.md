# GURU-004-INTERACTIVE

Implemented; live Mac interactive acceptance pending. Existing successful real
continuations remain valid. This increment fixes the observed return-to-shell
confusion; it does not add tools, providers, history access or mastery authority.

## Mac verification

```bash
cd /Users/qarmik/Documents/GitHub/gurukul
git pull --ff-only
git rev-parse --short HEAD
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_hermes_interactive.py' -v
```

After seven tests pass, run the following with the latest successful local call ID:

```bash
python3 scripts/hermes_live_teach.py --continue CALL_UUID
```

Answer two successive questions at the Gurukul prompt without running another
command. Type `/quit` at the next answer prompt. Expected proof: two saved PASS
turns with relevant responses, an answer prompt after each, and a clean exit with
a resume command naming the last successful turn. No GURU-003 recheck is required.

Default output shows teaching, the next question, saved call ID and evidence path.
Full pre/post boundary, tool, model and ledger reports remain in ignored local
state. Use `--verbose` to also print full verification JSON. `--once` performs one
turn and exits for diagnostic workflows. Source-picker starts also enter the loop;
the source is selected once and subsequent turns use verified pinned evidence.

## Lifecycle and limits

Each iteration revalidates saved context and admission, creates a fresh isolated
Hermes worker, performs pre/post checks, and records one linked event. Only a PASS
with verified persistence advances the loop. Failed turns or exceptions exit and
leave the resume pointer on the last successful question; they never retry.
Blank/oversized answers reprompt before inference. `/quit` and end-of-input submit
nothing. Control-C exits; interrupting an in-flight provider request cannot undo a
charge already incurred. A blocked interrupted turn is not used as future context.
The process lock covers the session and releases on exit. An idle prompt makes no
provider calls. There is no automatic Claude escalation.

Gurukul supplies only the previous explanation/question, current answer and pinned
D01 material. This is not full-history memory or a completed mastery/progression
workflow. Answers, responses and raw proof stay outside Git.

## Development evidence

Seven synthetic UI control-flow tests passed: two answers followed by quit,
quit/EOF/Control-C without submission, invalid-input reprompt, failed/unverified
turn stop, exception stop, one-turn compatibility, and source selection only once.
The Hermes-related suite ran 40 tests: 39 passed, one native Mac sandbox test was
skipped on Linux. These tests do not substitute for the real Mac interactive check.
