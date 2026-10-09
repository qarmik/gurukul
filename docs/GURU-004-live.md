# GURU-004A/B — one real isolated teaching turn

The c83effb Mac diagnostic identified `unsupported_parameter: max_tokens`; OpenAI
explicitly requested `max_completion_tokens`. The relay now validates the original
Hermes request, translates only that token-limit field, revalidates, and forwards
the same model/messages and limit. Both original and upstream parameter summaries
and request hashes are retained. Conflicting limits are rejected before forwarding;
the 1,024-token cap and one-request budget remain unchanged. This is transport
compatibility for the actual AIAgent call, not a replacement agent/model invocation.
21 contract tests pass; successful live teaching still requires the next Mac run.

Latest Mac result at fe3ba36: genuine turn_facade and conversation_loop invocation
verified; pre/post tools empty; all eight pre/post denial checks passed. The single
provider request returned HTTP 400, so teaching acceptance remains BLOCKED. The
original relay discarded the provider error body. The diagnostic correction retains
only bounded type/code/param/message fields, omits credential-related text, and prints
selected request parameters without prompt contents. No request parameter, model,
tool permission, network rule or retry budget is changed by this correction.
19 relay/source/evidence development tests pass, including three diagnostic tests.

Status: 16 relay/source/evidence development tests PASS; Mac live acceptance PENDING.
The native boundary regression passed on the Mac at ed6a8f5. The live worker then
reported all eight pre-import denials and zero provider calls, but construction
stopped because the adapter configured 32,768 context tokens, below Hermes's 64,000
minimum. The adapter now sets a conservative 64,000-token working window (not a
claim about the model's maximum). The output/request limits remain unchanged.

Source inspection of pinned `agent/model_metadata.py:detect_local_server_type`
identified the five-request local-backend detection sequence, consistent with the
five prior generic route denials. Exact authenticated pre-turn GET probes for
`/api/v1/models`, `/api/tags`, `/v1/props`, `/props`, and `/version` remain HTTP 403
and never reach the provider. They are now recorded as `blocked_startup_probes`
rather than fatal `relay_rejections`. No fabricated metadata is returned. Queries,
wrong credentials, different paths/methods and post-admission probes are not covered
by this classification. Any fatal relay rejection prevents turn admission. Three
additional HTTP tests verify these distinctions and zero inference forwarding.
The first Mac live attempt stopped at sandbox profile compilation: its SBPL parser
requires `localhost` (or a wildcard) as the network host, and rejected the numeric
loopback address. The rule now uses `localhost:<relay-port>`; there is no wildcard
host or port. The relay still binds/connects via 127.0.0.1. A new Mac-only test
compiles the actual profile and verifies relay reachability, denial of a second
listening port, and ledger read/write denial. It makes no provider call. Linux
skips this test and cannot provide acceptance evidence for the corrected rule.
The first native regression test then hit Apple's system Python launcher: it tried
to spawn Python.app, which the sandbox correctly disallowed. The test now selects
the same prepared dependency venv and clean environment as the live worker, and
asserts venv identity inside the sandbox. No additional executable is permitted;
the production sandbox policy is unchanged by this test-harness correction.
The earlier isolated import probe passed on the Mac at be913af. The user confirmed
dedicated OpenAI credential storage outside Git. Account/model access remains unverified
until the live inference request succeeds. No recorded live teaching response exists yet.

## Exact Mac commands

Run from Terminal (system Python 3.9 is sufficient for the parent):

```bash
cd /Users/qarmik/Documents/GitHub/gurukul
git pull --ff-only
git rev-parse --short HEAD
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_hermes_live.py' -v
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_hermes_sandbox.py' -v
python3 scripts/hermes_live_teach.py --choose-source
```

In the file picker select the approved `C0-B01_Values_and_Variables.html` downloaded
to the Mac. A filename change is fine; the entire file must match the approved hash
`6d301250bb4d6177f818133baaed8ebd2cd00f114aa8453f375d93e849e38f17`.
Do not select the PDF, tracker, or full curriculum. No file is downloaded or searched
automatically. For a reproducible noninteractive source binding, replace the picker
flag with `--source` followed by the quoted absolute path of that same approved file.
The book PDF is not ingested by this narrow test. Do not rerun GURU-003 verification.

The default key file is `~/GurukulRuntime/credentials/openai-api-key`. The parent
requires an owner-only regular file and refuses a symlink. The key is never printed,
sent to this chat, passed in command arguments, supplied to Hermes, or saved in Git.
No Claude credential is read. One permitted inference request may consume API credit.
The relay allows at most 1,024 output tokens (including reasoning, if any) and a
120,000-byte request; it never retries upstream. These are runtime execution bounds,
not engineering-time limits. A repeated manual invocation creates a new paid test.

## Actual execution and isolation

Runtime: `NousResearch/hermes-agent` at
`cc75e8f4021f7efab99158f57601be4d691a6da9`. Source must be clean and pinned, without a
source `.env`. Installed PM paths are read without repair/install. The selected venv
launcher retains its identity. No dependency environment or personal profile is copied.

The adapter verifies local source provenance and selects the Concepts to own and
C0-B01-D01 sections. It launches an actual `run_agent.AIAgent` with a fresh HOME,
HERMES_HOME, cwd, allowlisted environment, empty toolsets, skip_memory/context/background
review, no trajectories/checkpoints/fallback pool. Source inspection and runtime
snapshots cover tools, valid tool names, context-engine tools, memory and routing.
Tool dispatch is explicitly denied. Python call tracing must witness both the actual
`agent/turn_facade.py` and `agent/conversation_loop.py` run_conversation functions.
The agent/turn implementation and provider client are not replaced or mocked.

The macOS sandbox denies ledger/state reads and writes, credential-file access,
process forking/shell launch, listening sockets, and network destinations except one
exact loopback relay port. The parent proves the canary operations work outside the
sandbox. The worker repeats ledger/key/shell/network denial checks before import and
after the turn. A separate live loopback listener verifies other ports are denied.
The parent checks ledger bytes and a creation canary before recording anything.
This retains the experimental sandbox-exec approach already probed on this Mac;
it is not a claim of portable or long-term supported desktop isolation.

The relay forwards the request constructed by Hermes over verified TLS to OpenAI's
fixed `/v1/chat/completions` endpoint. It has no SDK agent/model substitution. It does
not follow redirects or inherit proxy settings. Only the configured model, exact
approved user prompt, text messages, bounded output, and no-tool request shape pass.
Browser/native tools, function definitions, MCP/connector calls, arbitrary proxy
routes, alternate models, streaming and multiple inference calls are rejected.
The worker receives an ephemeral relay token, never the provider key. The relay
requires completed plain-text output, and the parent compares it to Hermes's final
response before acceptance. Configured provider/model are explicit in
`config/hermes-live.json` and checked against model-policy.json. A different provider
requires an equally restricted transport implementation; unsupported routes stop.

## Evidence and acceptance

Each run is retained only under ignored `var/hermes-live/<call-id>/`:

- `report.json`: runtime/call-path proof, before/after tool and boundary results,
  source/excerpt/manifest/exercise hashes, outcome, model, usage, request ID and timing.
- `approved-excerpt.txt`: the admitted local material; no source is committed to Git.
- `teaching-response.json`: successful explanation and diagnostic question.
- `provider-response.json`: actual response metadata and usage when returned.
- `worker.stdout.txt`, `worker.stderr.txt`, `sandbox.sb`: local diagnostics.
- `acceptance.sqlite3`: a dedicated Gurukul integration session and generic append-only
  `teaching.integration_finished` event. The parent records and reopens it for readback.

PASS requires exactly one successful provider response, traced real runtime invocation,
empty pre/post surfaces, all boundary denials, unchanged ledger before the parent
write, accepted teaching JSON and verified parent event persistence. HTTP errors,
unknown request fields, access failures, timeouts or mismatches are BLOCKED. Do not
loosen restrictions or substitute a generic call to obtain a green result.

This is a standalone live integration session, not a learner assessment and not the
complete interactive tutor loop. The first turn asks a diagnosis question; no learner
misunderstanding is claimed diagnosed until a reply is supplied. No mastery is granted.
The prose-only response contract withholds the exercise solution; structural checks
reject code/solution fields, but these checks do not prove pedagogical correctness.
The saved response remains available for human review. Assessment tutoring stays
disabled during an open reconstruction; remediation can follow a failed attempt.

Gurukul owns model routing. The base route is enforced in this harness; escalation
is unavailable. Usage is taken from the provider response. Cost is null with explicit
`not_available` status, never invented as zero. The larger escalation decision/grant
workflow remains unimplemented. `skip_memory: true` is limited to this isolation
milestone; Gurukul will own and selectively supply learner continuity.

## Verification performed here

13 new unit/HTTP contract tests passed; 60 total development tests passed. These
include synthetic transport failures to test request-budget reservation. They do
not count as real Hermes/model or macOS isolation evidence. The attached approved
HTML passed hash admission and section extraction. Worker syntax was checked;
the live command must still run on the user's Mac with their locally stored key.

Official API references inspected for this implementation:
- https://developers.openai.com/api/docs/models/gpt-6-luna
- https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create

Pinned Hermes interfaces inspected: run_agent.py, agent/agent_init.py,
agent/turn_facade.py, agent/conversation_loop.py, agent/transports/chat_completions.py,
agent/agent_init_fallback.py, agent/system_prompt.py and agent/turn_finalizer.py.
