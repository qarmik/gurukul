# GURU-004 mixed-intent remediation — live acceptance pending

GURU-005 remains blocked. The user-reported v1 live run established useful curriculum
orientation and teaching progression, but exposed a coarse exclusive routing guard.
This increment preserves the canonical map, scope/provenance guards, runtime pin,
worker restrictions, one-request budget and Gurukul-only progression authority.

## Interpretation, admission and presentation

A learner utterance is not necessarily one thing. Gurukul must preserve the relevant
parts rather than discard valid evidence because another intent is also present.
Runtime success, conversational judgment and mastery are three different states.

Policy d01-pedagogy-2-mixed asks Hermes for primary/secondary intents and exact short
learner spans for answer, question, clarification, confusion, uncertainty, meta-request
and hypothesis. Dedicated response fields acknowledge clarification and answer questions
or confusion. These fields are displayed and pass the same disclosure/scope guards as
ordinary explanation. Wording repair is not automatically conceptual confusion.

Before admitting a conversational judgment, Gurukul requires an active question and
an exact answer span inside a parent-detected declarative segment of the learner's
message. A model label alone cannot confer admission. Pure questions/confusion remain
not_applicable. The surface segmentation is deliberately conservative and cannot prove
semantic relevance or correctness: those judgments remain provisional model observations,
never mastery evidence. Ambiguous segmentation requests clarification instead of inventing
credit. No gate, curriculum, stage or assessment transition can be changed by this path.

A structurally valid response that passes all authority/source/disclosure/scope checks
may still need conversational repair. Gurukul records NEEDS_CLARIFICATION, no admitted
correctness judgment, preserves the unresolved question, and stays at the input prompt.
There is no automatic retry or second inference. Invalid/tampered evidence, security or
scope violations, provider/runtime failures, malformed schema, and assessment-policy
violations still stop fail-closed. These failures cannot be downgraded by intent labels.

Reports preserve the raw provider/model proposal, admitted judgment and separately
displayed response. History uses only admitted judgments for saturation; proposed but
rejected correctness never becomes credit after restart. Secondary intents and the
admission reason survive serialization. The generic ledger remains append-only.

Normal output says "Turn saved; evidence verified." It separately displays conversational
judgment (correct, partial, uncertain, incorrect, not_applicable) and "Mastery: not assessed."
Verbose summaries label runtime_status explicitly. Legacy internal status and old saved
turns remain compatible. Old not_assessed values remain readable; new requests use
not_applicable. Historical PASS messages are not retroactively rewritten.

A successful variation must move to another activity rather than another variation with
synonymous words. Existing saturation/exact-repeat checks remain, now with recoverable
routing. Semantic equivalence and real instructional quality still require live review.

## Development proof

13 new synthetic tests cover all requested mixed-intent combinations, conversational
repair, pure question/confusion handling, fake/unbound answer spans, secondary replies,
recovery without ending the session, persisted intent/admission reload, status wording,
no mastery/curriculum bypass, and progression after successful variation. They do not
claim actual Hermes semantic performance. Existing pedagogy and Hermes checks also run.

## Mac commands and live acceptance

First exit any running teaching session with /quit or Control-C. Only paste these
commands when the ordinary shell prompt ending in % is visible:

```bash
cd /Users/qarmik/Documents/GitHub/gurukul
git pull --ff-only
git rev-parse --short HEAD
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_mixed_intents.py' -v
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_pedagogy.py' -v
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_hermes*.py' -v
```

After all pass, resume the last successful concrete question (not the blocked call):

```bash
python3 scripts/hermes_live_teach.py --verbose --continue CALL_UUID
```

1. Read the actual question. Submit a clarification of prior wording plus your answer.
   Expected: both intents retained, answer evaluated, clarification acknowledged, no
   false confusion, no mastery, and the next prompt remains available.
2. Answer the next actual question and include a genuine follow-up question. Expected:
   the answer is evaluated and the follow-up answered, with both preserved in evidence.
3. Ask a pure question without an answer. Expected: direct response, not_applicable
   judgment, unresolved evidence preserved, and continued session.
4. Enter /quit and retain the transcript plus local evidence directories. Review the
   actual prose, runtime boundaries, intent spans, admission and judgments together.

Each submission uses at most one provider request. No API key is requested in chat.
Live acceptance remains pending until all three semantic cases are reviewed. No claim
of learner mastery follows from a successful integration or conversational judgment.


Explanation-request routing and the narrow safe-format recovery path are extended
by [GURU-004 explanation requests](GURU-004-explanation-requests.md). The mixed-intent
and runtime/conversational/mastery separation remains in force.
