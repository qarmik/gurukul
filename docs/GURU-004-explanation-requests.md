# GURU-004 explanation requests and safe output rejection

Implemented; live explanation-strategy acceptance pending. GURU-005 remains blocked.
The reported failed turn reached the real provider with intact isolation, but the
prose code detector rejected the teaching response. Its raw body was not in the
submitted transcript, so no claim is made about the exact matched characters.
The old validator permitted an empty example: it rejected code-like prose, not
absence of code. This increment makes the distinction explicit and recoverable.

## Request handling

Policy d01-pedagogy-3-explanations includes an exact explanation_span and parent
requested_strategy hint. Explanation requests are not answer candidates. Analogy,
simpler explanation, example, comparison, counterexample and step-by-step requests
map to allowed representations. The model generates the actual teaching content;
no analogy is hard-coded. An ignored strategy request reprompts with no correctness
credit. Confusion and mixed-intent handling remain available.

No answer means not_applicable, not incorrect. The original unanswered evidence
question is retained separately while Hermes may simplify the displayed check.
Normal answer admission resumes on the next actual answer. This never grants mastery
or changes phase/gates/curriculum. Code is optional. Any supplied miniature code
still has the existing AST/size restrictions; calls/imports and active multi-variable
solutions are not admitted.

## Rejected output versus hard failure

All structural, authority, provenance, scope and disclosure checks run before safe
format rejection can be classified as recoverable. The narrow recoverable cases are
an otherwise valid overlong explanation within the total text bound, or bounded
literal/name snippets misplaced in prose. Arbitrary/unsafe code, malformed schema,
invalid authority, changed evidence, sandbox/provider/assessment failure remain hard
failures. The validator does not silently accept misplaced code or display it.

RESPONSE_REJECTED records runtime success, no admitted correctness, the original
request/pending question, raw proposal, admission reason and deterministic fallback.
The fallback asks the learner to resubmit; there is no second model call or auto-retry.
The session remains open. Reload revalidates the raw rejected proposal under the same
hard checks; only the safe format exception is allowed, and history excludes false
credit. Runtime success, conversation status, judgment and mastery stay separate.

## Input hygiene

Before semantic recording, bounded normalization removes terminal CSI/OSC/escape
sequences, the visible caret CSI form produced by arrow keys, and non-text control
characters. Ordinary UTF-8, punctuation, quotes, operators and literal backslash
escapes remain unchanged. Semantic text and its hash use normalized input. The record
contains normalization metadata but no raw terminal input. This is not a terminal
emulator and does not execute or rewrite program syntax. The existing multiline
shell-paste hardening gap is separate; exit Gurukul before pasting shell commands.

## Verification

11 new offline tests cover explanation variants, no fabricated judgment/mastery,
pending need retention, strategy selection, code-free analogy, bounded supplied
code, safe rejected output, hard-failure precedence, normalization, recovery reload,
and subsequent answer admission. Synthetic tests establish contracts, not actual
model teaching quality. Prior mixed-intent/pedagogy/Hermes suites must also pass.

At the shell prompt ending in %, after exiting Gurukul, run:

```bash
cd /Users/qarmik/Documents/GitHub/gurukul
git pull --ff-only
git rev-parse --short HEAD
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_explanation_requests.py' -v &&
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_mixed_intents.py' -v &&
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_pedagogy.py' -v &&
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_hermes*.py' -v
```

After they pass, resume the last successful turn:

```bash
python3 scripts/hermes_live_teach.py --verbose --continue CALL_UUID
```

At the Gurukul prompt, submit in order, waiting for each response:
1. explain with an analogy
2. explain it more simply
3. give me a small example
4. Your own answer to the displayed pending question.

Expected live evidence: distinct useful representations, runtime success, no answer
judgment for explanation requests, no mastery, preserved pending concept, normal
answer admission afterward, and intact pre/post isolation checks. A deterministic
fallback proves recovery, not successful explanation-strategy acceptance. Preserve
local reports/transcript, exit with /quit, and review actual prose plus diagnostics.
