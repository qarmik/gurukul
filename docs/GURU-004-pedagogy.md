# GURU-004 pedagogical correction — live acceptance pending

GURU-005 is blocked until this correction is tested and demonstrated with the real
pinned Hermes runtime and GPT-6 Luna on the Mac. No live result is claimed here.

## Architecture

The curriculum bounds the Guru's teaching; it does not replace the Guru's intelligence.
The Guru knows the whole journey but teaches the current step. Source material grounds
teaching; it is not the sole knowledge available unless the task is source-specific.
Gurukul owns curriculum state, learner state, evidence and progression. Hermes proposes
pedagogical reasoning within that authority. The destination is the professional
transformation defined in the curriculum, not merely completing exercises.

The approved v0.8.3 text is preserved in content/curriculum/v0.8.3.txt. Its derived
map.json retains all C0–C9 stage requirements, fourteen families, principles, gates,
human checkpoints, field method and graduate standard. scripts/build_curriculum_map.py
reproduces the map. The dispatch supplies the concise professional role label; the
canonical text supplies the graduate outcome. The existing pinned D01 exercise is
unchanged: no new Must item, prerequisite, gate, stage unlock or evidence waiver.

Each turn receives:
- A: compact stage/family map, target, principles, field method and graduate expectations.
- B: exact C0 requirements/gate philosophy, active D01 objectives and evidence, nearby
  future material and explicit premature-depth restrictions.
- C: current message, previous teaching and up to twenty linked ancestor exchanges
  within a 40KB context budget. Full exchanges remain in the original local ledger.

The excerpt remains SHA-bound; the report additionally records canonical/map/orientation
hashes, policy version and exact turn context. Legacy turns remain resumable. Ancestor
selection follows causation links, not unrelated branches or mere timestamp ordering.

## Teaching policy and evidence

Stable D01 fundamentals can use model knowledge. Source-specific answers require the
supplied excerpt or an explicit limitation; requirements use canonical curriculum.
Current/version-sensitive and regulatory questions defer when no verified authoritative
source is supplied. External browsing remains unavailable. The legacy exercise's source
access restriction continues to prohibit unapproved retrieval; the versioned adapter
policy now permits general knowledge for explanations without changing the exercise.

The parent supplies a conservative message-kind hint: ANSWER, QUESTION, CONFUSION,
META_QUESTION, REQUEST_FOR_EXPLANATION, HYPOTHESIS, ATTEMPT, or local QUIT. The model's
classification and its origin are retained. Obvious direct questions/confusion must be
not_assessed rather than graded as answers. Natural-language heuristics are fallible;
ambiguous classifications must be reviewed, not treated as ground truth.

The structured proposal records concept, provisional judgment, strategy, next activity,
missing evidence, claim provenance/basis, future deferral, and internal curriculum
orientation. It may record a curriculum_observation for review but has no mutation path.
Knowledge classes include approved_source, model_general_knowledge, canonical_curriculum,
learner_evidence; verified_external_source and deterministic_result are reserved and
refused when not actually supplied. These are model-reported attributions, not verified
citations or proof of the model's internal knowledge source.

Two provisional correct observations for a concept trigger prediction, learner-generated
example or variation. Exact repeated questions are refused; older questions are visible
to the model to discourage semantic repetition. Confusion requires a different strategy.
This threshold schedules practice, never mastery. Incorrect answers may trigger reteaching;
no assessment phase changes occur. Tutoring is still blocked during reconstruction.

Separate miniature examples may contain at most two literal/name statements and one
assignment, never calls/imports or a multi-variable exercise solution. Prose remains
code-free. This permits useful examples without generating the active five-variable
solution. Checks do not fully detect cumulative/prose disclosure or semantic topic drift;
those remain live-review obligations. A rejected response stops without automatic retry.

The existing worker, sandbox, empty tool surface, provider relay, model routing, 1,024
output-token cap and one-request-per-message budget are unchanged. Reports/transcripts
remain in ignored local state. No credentials, personal answers or raw telemetry enter Git.

## Development tests and limits

15 new offline tests cover map reproducibility, compact global/active context, canonical
requirements, general-knowledge allowance, future-topic guard/deferral, source and claim
class routing, no progression authority, direct-question routing, progression thresholds,
changed strategy, repetition checks, bounded examples, context budgets and saved rich
response reload. Existing Hermes-related tests are also required. These verify contracts
and synthetic fixtures, not actual model reasoning. Keyword/syntax guards cannot certify
semantic correctness or absence of all later-stage leakage.

## Exact Mac commands

```bash
cd /Users/qarmik/Documents/GitHub/gurukul
git pull --ff-only
git rev-parse --short HEAD
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_pedagogy.py' -v
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_hermes*.py' -v
```

Continue the latest successful local turn, with full diagnostic summaries:

```bash
python3 scripts/hermes_live_teach.py --verbose --continue CALL_UUID
```

Use the latest local call ID, not a failed one. No new source selection is required.
This is interactive: enter each message at the Gurukul prompt, never at the shell.

## Live A–E checklist (must remain pending until reviewed)

A. Ask: "If I use a name before assigning a value, does Python create an empty box?"
Expected: an accurate brief Python explanation beyond the excerpt where needed,
model_general_knowledge attribution, D01 scope, and no source-only refusal.

B. Ask: "Does this connect to agent memory later? Can you teach that now?"
Expected: accurate brief acknowledgment and explicit deferral of depth; no architecture
lesson or code. Review future_topic_deferred and strategy as well as actual prose.

C. On every successful response, inspect internal current_location C0-B01-D01,
current_purpose programming independence foundation, final_trajectory regulated-enterprise
AI architecture, and curriculum hashes. The ordinary explanation should stay beginner-level.
An acknowledgment proves context was used, not comprehensive understanding of the curriculum.

D. Ask: "What do you mean by material?"
Expected: META_QUESTION, not_assessed, direct explanation of supplied source material;
no marking it wrong or ignoring it in favour of the previous quiz question.
Also ask "What does the supplied book excerpt say about this?" to review source grounding.

E. Answer the actual D01 questions in your own words. After repeated correct observations,
expect a changed representation (prediction/example/variation), with a concrete evidence_need.
Do not fabricate learner correctness for testing. If confused, describe the confusion:
expect a genuinely different explanation, not merely a different strategy label.

Enter /quit after collecting the needed evidence. Reports retain exact input context,
model response, provenance, linked event and pre/post boundary evidence for each turn.
Review all A–E transcripts for correctness, scope, grounding and disclosure before
recording live acceptance. GURU-005 remains blocked until that review passes.
