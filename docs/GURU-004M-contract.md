# GURU-004M supervised Guru contract repair

Disposition: **PARTIAL PASS / BLOCKED pending targeted live acceptance**.
Curriculum v0.8.3 governs. GURU-005 remains blocked.

## Exact failure and repair

The user supplied the original Guru message for call
`543dfff7-3f8f-4eb6-a92c-3f3e54c5dd03`. It is preserved in
`tests/fixtures/guru_004m_543dfff7.json`. Against the prior validator it raises
`Pedagogical diagnostics schema mismatch`. The exact difference is:

| Contract field | Raw Guru response | Authority |
| --- | --- | --- |
| `current_location` | Missing | Parent turn's pinned active capability |
| `curriculum_version` | Missing | Parent's verified canonical curriculum |
| Other required fields | Present | Existing structural and semantic checks |
| Extra fields | None | Closed schema |

The response contains the mixed-intent schema, source/provenance diagnostics,
an empty diagnostic question, and `grants_mastery: false`. Supplying only those
two parent identity values reproduces successful ungraded admission offline.
The schema coupled admission to the model repeating identity already owned by
Gurukul. The omission explains this rejection; it does not establish the cause
of any other failed response.

The minimal repair uses one contract for NORMAL, ORIENTATION, REMEDIATION and
PAUSE_EVIDENCE. Gurukul derives `current_location` and `curriculum_version`
from a coherent parent context pinned to C0-B01-D01 and v0.8.3. If Guru supplies
either echo, it must match exactly. A conflicting echo or invalid parent
context still blocks admission. No supervision-dependent validation bypass exists.

The live core still requires intents and intent responses, concept, judgment,
strategy, next activity, evidence need, knowledge classes, claim basis,
source-specific/deferred flags, mastery prohibition and curriculum observation.
Unknown fields remain forbidden. All four model echoes (`current_location`,
`curriculum_version`, `current_purpose`, `final_trajectory`) are optional.
The follow-up mother-thread handoff explicitly supersedes the earlier safe-format
rejection for missing purpose/trajectory acknowledgements: omission is accepted;
any supplied value must match. The prompt and validator agree on this contract.
Absent purpose/trajectory fields are not invented in the derived display.
Source grounding, disclosure, code scope and verified learner spans still run
before admission. Profiles retain the same controls, TTL, triggers and budgets.

## Raw evidence and continuation

Binding returns a separate validated copy. `provider-response.json`, the
saved raw teaching object, and the response hash continue to describe what Guru
actually emitted. The admission records `response_authority_binding`, including
its parent origin, values and omitted model echoes. Derived values are never
represented as model output.

On continuation, the saved report must first match its parent ledger, pinned
exercise and source provenance. Raw provider/teaching evidence is compared before
derivation. The binding is then recomputed from the verified saved turn context.
Legacy successful turns with all required echoes continue to load. Safe-format
recovery remains resumable without admitting an answer or granting mastery.

## Earlier rejected Anthropic directive

The supplied live transcript establishes that call
`e24861e2-f318-416a-9bef-97a8fb0a0049` received HTTP 200 and then rejected a
directive with `ValueError`. Its deterministic ORIENTATION fallback worked.
The existing Anthropic client retained safe metadata, not the rejected directive
body; that body was not supplied and the Mac evidence directory is unavailable
in this workspace. **Its exact rejection cause cannot be reconstructed from the
available evidence.** HTTP 200 alone does not imply a contract-valid directive.
No new call was made to try to reproduce it, and its accepted schema is unchanged.

Tracked observability defect **M-SUPERVISOR-RAW-01**: retain a rejected supervisor's
raw provider response in local parent-owned postmortem evidence, as Guru responses
are retained. This is open and **not an acceptance blocker**: a later real Claude
ORIENTATION directive was approved. This repair records the defect without
expanding supervision or adding another paid call.

Future schema/authority failures now record bounded structural diagnostics:
validation stage, failure code, expected/actual/missing/extra keys, and a distinction
between required and optional fields. Omitted optional echoes are not reported as
missing required fields. Unusual key
names are hashed. Guru diagnostics stay in the local report; supervisor
diagnostics stay in the supervisory audit. Neither contains field values,
provider text, hidden prompts or credentials. Directive semantic failures have
specific static codes; invalid directive JSON has a separate stage. The existing
deterministic fallback and one-request reservation survive unchanged.

## Verification and remaining acceptance

Twelve targeted tests cover the exact failed response after an approved directive
through the actual adapter with mocked HTTP transport, all four profiles,
conflicting/missing identity, missing core fields, malformed intents, unknown
fields, optional purpose/trajectory echoes, provenance/mastery/code guards,
diagnostic privacy, rejected HTTP-200
directives, ledger/context binding, safe-format recovery, and reload followed by
a fresh check and answer admission. No paid generation was performed.

Full suite: 176 tests, 175 passed, one macOS sandbox-exec test skipped on Linux.
These are offline regressions. They do not establish live semantic compliance.

The supplied live run already proves account/model verification, a real approved
Claude ORIENTATION directive, fallback, question retirement and profile carry
without another supervisor call. Full integrated acceptance remains pending at
the repaired Guru boundary. Use the [targeted Mac rerun](GURU-004M-Mac.md) from
`198b081e-17f5-4d71-87e1-5cb1152a5cf0`; begin with
`what are you talking about?`. Review the first successful turn before continuing
to question origin, loop complaint, fresh check and the learner's answer.
