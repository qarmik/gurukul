# GURU-004: authoritative learner input

Status: implementation and offline regression verified; live acceptance pending.
GURU-005 remains blocked. No future subsystem is implemented by this remediation.

## Evidence contract

The parent captures submitted text before inference. `continuation.learner_input`
retains raw input, normalized input, separate SHA-256 digests and the normalization
policy in ignored private local state and the append-only event ledger. Raw input
means the string delivered by the terminal input API, excluding its submission
newline; this is not a keystroke recording. Only normalized text reaches Hermes.
Normalization removes terminal controls, preserves meaningful Python punctuation,
Unicode and leading/trailing whitespace, and never invents replacement characters.

The parent supplies bounded reference IDs with code-point ranges in the prompt.
Hermes selects a reference (preferably `{"ref":"s0"}` for a whole answer), or
proposes zero-based Unicode code-point offsets with an exclusive end. Gurukul
constructs the text by slicing its authoritative normalized input. Legacy exact
quotes remain compatible only after verification and parent slicing. A model's
corrected or invented quote cannot become a verified learner span.

Admission stores `learner_verified_spans`, their input hash and ranges separately
from `model_interpretation` and `model_judgment_proposal`. The original provider
response remains model evidence, not learner evidence. Continuation reload checks
input hashes, deterministic normalization and verified span bindings as well as
the existing ledger, source and exercise integrity checks. Legacy events are
readable without retroactively inventing raw input that was not captured.

Invalid references produce an ungraded recoverable turn, preserve the pending
question and original input, and identify an interpretation failure. No model
retry occurs. Security/authority failures still stop. Correctness remains a
provisional model observation; substring verification proves origin, not truth.

Code-like conceptual predictions can be admitted as a whole answer without
executing them or requiring prose. `unmet_evidence_requirement` separately retains
the proposed next need, such as explaining the result verbally. This is a teaching
observation only, not a new mastery or capability scoring subsystem.

## Verification

The full offline suite runs 132 tests: 131 pass on Linux; the native Mac sandbox
test is skipped there. Nine new tests cover raw/normalized integrity, punctuation,
Unicode references, rejection/recovery, code-like answers, pure-question refusal,
security, span tampering and mixed-intent ledger reload. These are synthetic tests,
not live Hermes acceptance. The runtime pin, sandbox, relay budget, model routing,
canonical curriculum, map and orientation content remain unchanged.

## Mac acceptance

At the shell prompt (not the Gurukul input prompt):

```sh
cd /Users/qarmik/Documents/GitHub/gurukul
git pull --ff-only
git rev-parse --short HEAD
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_learner_input.py' -v &&
python3 scripts/hermes_live_teach.py --verbose --continue 1c355a22-9193-484a-b498-9552f46e2eb1
```

This resumes the successful analogy turn. Submit **one line at a time**, waiting
for the next Gurukul prompt:

1. `explain with an analogy`
2. `explain it more simply`
3. `give me a small example`
4. Answer the actual displayed question in your own words or with a meaningful
   code-like prediction. Preserve quotes, semicolons and parentheses as intended.

Do not paste shell commands at the Gurukul prompt. Each submission makes at most
one paid request. The first three turns must be ungraded, preserve the unresolved
concept and switch representation appropriately. The last must retain the exact
normalized input, verified source spans and separate model interpretation, without
mastery or curriculum advancement. Use `/quit` when finished.

Reports, provider responses and exact local input remain under ignored
`var/hermes-live/<call-id>/`; the event chain retains the transcript. Audit the
last answer turn at the shell without another model call (replace the placeholder):

```sh
python3 scripts/verify_learner_input.py LAST_ANSWER_CALL_ID
```

The audit reads the ledger-backed evidence and prints hashes/status, not raw input
or credentials. Share the verbose acceptance output and audit result for review.
A transport PASS alone does not establish pedagogical acceptance. Simpler teaching,
a small example, normal answer admission and the complete live sequence are still
pending; the earlier real analogy response is accepted and must not be relabelled
as completion of the whole sequence.

## Follow-up: explanation routing (policy version 5)

Live Mac evidence verified all nine input-integrity tests and the analogy request's
parent-constructed reference. Two additional response-contract defects prevented
completion: a valid simpler comparison was rejected by exact strategy equality;
a later proposal omitted `current_purpose` and `final_trajectory` and stopped the
session. It also gave another analogy instead of an example.

Simplification now admits explanation/comparison/verbal-model representations,
with a concise (90-word) changed explanation. This is a surface guard, not proof
of pedagogical quality; live review remains required. Explicit analogy requests
still require that representation. Natural phrasing such as “give me some example”
is now routed as an explanation request. A requested miniature example must
actually be supplied and must pass the existing disclosure/AST restrictions.

Omitting either of the two descriptive orientation acknowledgements is a safe
format rejection only after all other checks pass. The response is not displayed,
no fields are invented, no grade is recorded, and the pending question survives.
Unknown fields, missing authority fields, false supplied orientation, unsafe code,
and curriculum/mastery violations still fail hard. The raw proposal remains saved;
no second provider request is spent. Recovery uses the existing saved/reloadable
RESPONSE_REJECTED path.

Five additional offline tests pass. Full regression: 137 run, 136 passed and the
Mac-only sandbox test skipped on Linux. No isolation or model-budget changes.

At the Mac shell, update and resume the saved recoverable turn:

```sh
cd /Users/qarmik/Documents/GitHub/gurukul
git pull --ff-only
git rev-parse --short HEAD
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_response_routing.py' -v &&
python3 scripts/hermes_live_teach.py --verbose --continue f4c74088-f825-41e8-82c5-54fc4b2e0a2a
```

At successive Gurukul prompts, submit “explain it more simply”, then “give me some
example”, then your own answer to the displayed question. Stop and share output
if another rejection occurs. Otherwise `/quit` and use the input-audit command
above for the final answer call. Analogy acceptance already passed; do not repeat
it merely to consume another call. Final GURU-004 live acceptance is still pending,
and GURU-005 remains blocked.
