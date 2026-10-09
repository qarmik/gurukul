# GURU-004-CONTINUE — answer and receive a follow-up

Implementation complete; live Mac continuation acceptance pending. The earlier
one-turn acceptance remains valid. No new runtime, model, tools or permissions.

From the Mac repository, pull and run only the new continuation tests:

```bash
cd /Users/qarmik/Documents/GitHub/gurukul
git pull --ff-only
git rev-parse --short HEAD
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_hermes_continuation.py' -v
```

Then continue a successful saved turn (replace CALL_UUID with its printed call_id):

```bash
python3 scripts/hermes_live_teach.py --continue CALL_UUID
```

The command displays the saved explanation and question. Type your answer on one
line and press Return. The answer is read interactively, not put in shell history.
Blank or oversized answers are refused; Ctrl-C cancels without automatic retry.
The approved excerpt is restored from local evidence, so no source picker is needed.
Do not remove the previous turn's evidence directory or original acceptance ledger.

Expected proof: status PASS, matching parent_call_id, one provider call with HTTP
200, empty tools before/after, all boundary probes DENIED, verified parent ledger
record, and explanation/next question that respond to your answer. Each continuation
is one paid request. A failed call does not retry or escalate automatically.
To answer the next question, use the new successful call_id with --continue.
Reusing an older call_id deliberately branches from that older question.

## Continuity and admission

Gurukul verifies the saved report against its original append-only ledger event,
checks the stored exercise, source provenance and excerpt digest, and checks the
saved teaching response against its provider response/hash. This detects accidental
corruption; it is not authentication against an owner rewriting the whole database.
Only successful persisted turns in active teaching/remediation sessions are admitted.
Reconstruction is denied before inference; returning to remediation permits tutoring.
This command does not itself transition phases or grant mastery.

The parent supplies only the previous explanation/question, current learner answer
and pinned local excerpt. Learner text is quoted as data, not new instructions or
approved material. Hermes diagnoses that answer, clarifies uncertainty or reteaches
one concept, and asks one next conceptual question. It has no complete-history
memory and must not claim otherwise. Output retains the existing code/solution
schema filter; the filter does not prove pedagogical quality or block every possible
prose solution. Review the actual live response for relevance and disclosure.

All turns in a chain use the original integration session/ledger. Generic events
link to their parent event via causation_id and the original call via correlation_id.
The report stores the learner answer and its digest, the exact question answered,
and the parent evidence digest. These remain under ignored var/hermes-live/.
Adapter invocations are serialized with a local process lock so their ledger denial
checks cannot race each other. Worker restrictions, pinned Hermes, relay request
policy, output budget and Gurukul-only escalation authority remain unchanged.
The ordinary gurukul session CLI is still separate from this integration session.

## Development verification

Eight new offline continuation tests passed. The Hermes-related suite ran 33 tests:
32 passed, one actual-Mac-only sandbox test skipped on Linux. These tests include
synthetic fixtures and do not substitute for a real Hermes diagnosis. No new live
model call was made in the development environment. GURU-003 was not reverified.
