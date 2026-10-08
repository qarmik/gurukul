# GURU-004A preflight — partial, not live acceptance

Current status (2026-10-08): dedicated Mac setup and isolated import PASS at Gurukul
be913af. See GURU-004-import-probe.md and runtime-lock.json for the reported evidence.
OpenAI direct / gpt-6-luna / dedicated API key are selected; key readiness remains
unconfirmed. The historical preflight below records the original questions, not
outstanding installation requests. No live teaching turn has run. The supplied D01
HTML and book PDF match the approved manifest hashes; Mac file bindings remain to
be supplied or staged outside Git.

GURU-003 Mac acceptance is complete: b6f94e0, 24 new tests passed. Do not repeat that verification.

## Runtime identified and pinned
Actual runtime: NousResearch/hermes-agent. The source-inspected revision is cc75e8f4021f7efab99158f57601be4d691a6da9, pinned in integrations/hermes/runtime-lock.json. This pins our integration target, not an assumed version on the learner's Mac. No installation, upgrade, login or model call has been performed.

Source at that revision exposes run_agent.AIAgent; its constructor delegates initialization to agent/agent_init.py. agent/turn_facade.py provides run_conversation(user_message, system_message, conversation_history, task_id, ...) and chat(message). The intended adapter calls run_conversation and retains final_response plus request metadata through Gurukul. It must import and invoke this runtime, not replace it with an SDK model call.

The pinned pyproject.toml declares >=3.11,<3.15 for upgrade compatibility but explicitly targets 3.14 for the real runtime and dependency lock. Current source-environment documentation uses the checkout's activation/PM workflow. The selected revision's activation scripts and dependencies must be checked before installation. Do not assume Gurukul's existing interpreter is adequate or upgrade it implicitly. Provider, model and auth method are unset pending the user's details.

## Tool restrictions: inspected, not dynamically verified
model_tools.py distinguishes enabled_toolsets=None (all) from an explicit empty list. It also has context-sensitive tool injection (e.g. dispatcher-owned Kanban workers). agent_init.py loads plugins/configuration, can inject memory/context-engine tools, and populates tools/valid_tool_names. run_agent.py loads environment files at import. Thus passing [] alone is insufficient proof for a reused personal Hermes installation.

Required live acceptance: clean dedicated Hermes home and cwd; no inherited personal plugins, MCP definitions, profiles or task environment; explicit empty allowlist; memory/context/background review/trajectory/checkpoint controls; assert no exposed tools after initialization and before/after the turn; fail closed if any appear; reject tool-dispatch attempts. Verify model-provider native tool settings as well after the provider is known. Prompt wording is not an authority boundary.

Direct ledger writes require filesystem isolation: the worker must not receive a Gurukul DB handle or writable ledger mount. A separate same-user process alone does not deny host filesystem access. Container or equivalent worker isolation must be chosen after learning the available Mac setup. Approved local source excerpts enter through the parent adapter; only Gurukul writes returned evidence. Fresh Hermes housekeeping state, if required, lives in its disposable worker location, never in the Gurukul ledger.

Browsing tools and shell tools must be absent/denied. The worker still needs the explicitly chosen model endpoint; network policy must distinguish provider inference traffic from browsing. These controls have not yet been executed or certified on a live runtime.

## Information needed before setup
1. Is Hermes already installed? If yes, installation method, checkout location and revision/version (not config/auth file contents).
2. Which model provider/model and authentication method should be used? Confirm whether access is already configured; never submit credential values in chat.
3. Is Docker Desktop or Colima already available on the Mac? If neither, say so; isolation setup must be resolved before a live test claims ledger denial.

## Remaining acceptance evidence
Pinned revision and clean-checkout verification; actual runtime import/interface check; live tool-surface and denied-operation tests; verified ledger isolation; approved D01 local source provenance; one actual Hermes teaching turn; retained teaching response and integration output under ignored var/; exact Mac commands matched to the confirmed setup. A stub, source inspection or generic model response does not count. No teaching response or integration test output exists yet.

## Inspected upstream sources
- https://github.com/NousResearch/hermes-agent/blob/cc75e8f4021f7efab99158f57601be4d691a6da9/run_agent.py
- https://github.com/NousResearch/hermes-agent/blob/cc75e8f4021f7efab99158f57601be4d691a6da9/agent/agent_init.py
- https://github.com/NousResearch/hermes-agent/blob/cc75e8f4021f7efab99158f57601be4d691a6da9/agent/turn_facade.py
- https://github.com/NousResearch/hermes-agent/blob/cc75e8f4021f7efab99158f57601be4d691a6da9/model_tools.py
- https://github.com/NousResearch/hermes-agent/blob/cc75e8f4021f7efab99158f57601be4d691a6da9/agent/tool_executor.py
- https://github.com/NousResearch/hermes-agent/blob/cc75e8f4021f7efab99158f57601be4d691a6da9/pyproject.toml
- https://hermes-agent.nousresearch.com/docs/guides/python-library/
