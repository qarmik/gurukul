# GURU-004: separate display from pending evidence

## Root cause and correction

The admission layer conflated three different decisions: safe response display,
answer admissibility and presentation of unresolved questions. It forcibly replaced
safe replies' next questions with an old pending question. On rejection it repeated
that same question again. A pause proposed by Hermes could never actually pause
it. Repeated strategy labels and empty supplementary response fields added further
rejections even when the main explanation could address the learner.

Policy version 6 preserves all hard validation before admission. It separates:

- Display: a validated ungraded response can clarify, teach, answer a meta-question
  or pause. An empty diagnostic question is legitimate.
- Evidence: a genuine answer still requires independently admissible, parent-bound
  spans and an explicit provisional judgment. Model labels alone do not grant credit.
- Pending state: the unresolved question remains saved separately from what is
  displayed. A later answer can bind to it after pause, rejection and restart.

A model's ungraded confirmation tagged ANSWER is no longer treated as a failed
answer when there is no admissible answer content. It stays ungraded. A model
proposing a correctness judgment without admissible evidence is still rejected.
A repeated strategy label is not proof of a repeated explanation; exact repeated
explanations during confusion still recover. Main explanation can carry responses
to secondary intents; empty supplementary fields create review observations rather
than proving that the intent was ignored. This is not semantic certification that
every concern was answered well; that remains part of live acceptance.

Recovery suppresses the repeated diagnostic question while preserving it in state.
Resuming old recovery records applies this display rule without rewriting their
ledger events. Explicit pause suppresses a new question too. No automatic retries,
model escalation, mastery transitions, curriculum changes or boundary relaxation.

## Verification and limits

Six new synthetic conversation tests cover confusion with the same strategy label,
confirmation, meta-question plus confusion, invalid references without question
repetition, authority denial, and a ledger-backed rejection → pause → restart →
answer sequence. Existing tests now explicitly distinguish preserved evidence from
forced question display. Full suite: 143 tests, 142 passed, one Mac-only skip on
Linux. These tests cannot certify all future model responses or live pedagogy.
The pinned Hermes runtime, relay budget and sandbox remain unchanged.

## Mac check

If the old process is at the Gurukul prompt, enter `/quit` first. At the shell:

```sh
cd /Users/qarmik/Documents/GitHub/gurukul
git pull --ff-only
git rev-parse --short HEAD
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_conversation_state.py' -v &&
python3 scripts/hermes_live_teach.py --verbose --continue 69b493fc-91b6-4979-9d7b-3d2d82a240ff
```

First ask where the pending question came from and request that it pause while
Guru explains the topic. It must address that concern without grading or forcing
the old question back. Then request a simpler explanation and a small example,
one turn at a time. Answer a subsequent question in your own words/code-like
prediction; verify the saved input with `scripts/verify_learner_input.py CALL_ID`.
Stop after any new rejection rather than spending calls repeating it. The local
reports/provider responses remain the acceptance transcript; do not commit them.

GURU-004 remains pending live acceptance. GURU-005 remains blocked. The earlier
analogy and input-reference live successes are retained, not relabelled as failure.
