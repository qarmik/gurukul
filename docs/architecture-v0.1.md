# Gurukul v0.1 — corrected architecture

Status: corrections accepted; GURU-001 implemented. Remaining sprint increments are not implemented.

## Authority and processes
One local Python runtime owns SQLite, versioned exercises, evidence and progression. Learner execution will be a child process. Hermes means the actual NousResearch/hermes-agent runtime, never a generic endpoint renamed Hermes. The intended integration is a separate local Hermes worker behind a typed adapter. The worker will embed the upstream AIAgent API in its supported environment; pin and verify an upstream revision at GURU-004 before implementing the binding. Upstream reference: https://hermes-agent.nousresearch.com/docs/guides/python-library/ . No Hermes installation or live call is included in GURU-001.

The adapter passes narrowly scoped local teaching material, learner responses and observed evidence. Hermes proposes teaching, diagnosis and interventions. Gurukul authorizes actions and commits results. Use a dedicated Hermes profile with no general shell, browser, external connectors, autonomous skill modification or direct database access. Tool-disabling settings must be verified against the pinned runtime, not assumed. Only model-provider network access is intended. Isolation is an acceptance requirement for GURU-004, not a claim about this scaffold. Hermes memory is contextual and never the authoritative evidence ledger.

## Teaching and assessment loop
1. Hermes teaches D01 using approved local material and separate miniature examples.
2. Hermes asks a prediction/explanation question and diagnoses the specific misunderstanding from the answer.
3. If necessary, Hermes reteaches from that same local corpus using a different example, then checks again.
4. Learner attempts the exercise; deterministic execution/checks and bounded help record evidence.
5. Later, a fresh reconstruction opens as an assessment attempt. Tutoring is unavailable only while that attempt is open.
6. Failure closes and preserves the attempt, then enters remediation. Hermes diagnoses/reteaches and supports practice.
7. A later fresh reconstruction uses a new variant and a new attempt record. Remediation never overwrites the failure or turns assisted practice into independent success.

Proposed phases: teaching, comprehension_check, practice, feedback, retrieval_due, assessment, remediation. GURU-001 persists only the initial teaching phase. Future transitions must be event-backed and gate-controlled; no command currently grants mastery. Uncertainty in comprehension is not automatically evidence of mastery or failure.

## Local content boundary
The D01 package derives scope and task instructions from the attached C0-B01 book. Approved reading is Python Crash Course, 3rd edition, pp. 16–19. GURU-004 must ingest those approved local pages, retain source/page identifiers and hashes, and use them for teaching/reteaching without external browsing. The copyrighted PDF is not redistributed in this source bundle. No generated teaching notes are represented as approved book text. The initial scaffold can display instructions but cannot yet teach through Hermes.

## Solution disclosure
Separate teaching examples from active assessment solutions. Do not supply the learner's first implementation. Hints require an attempt; debugging hints require a hypothesis. Track cumulative hints to prevent completing the solution line by line. A classification by Hermes alone is insufficient enforcement.

During live assessment, no tutor output reaches the learner. Outside assessment, use reviewed hint levels and constrained diagnostic selections for exercise-specific help. Unrestricted teaching operates on separate examples, without an answer key in context. Treat possible answer-equivalent leakage as exposure, retain it, and retire the affected variant from independent assessment. These controls reduce leakage; free-form generation is not provably solution-free.

An explicit solution request after an attempt closes/retires that variant before disclosure, logs solution exposure and prevents independent credit. A later attempt must use a fresh variant. No automatic disclosure after failure. Teaching, remediation and hint exposure remain separate event types.

## State and evidence
SQLite owns structured state; future submission snapshots and execution output live in the evidence directory. Sessions pin exercise ID, version and content hash. Starting twice returns the existing active session. Changed content under the same version is rejected. Resume uses the stored snapshot even when source content is unavailable.

Future records retain the proposed capability, exercise, session, attempt, execution, assistance, evaluation, capability_state and retrieval design. GURU-001 implements exercises, sessions and events only. Schema migration must be explicit when adding further tables.

## Extensible nervous-system ledger
The event envelope includes: sequence, UUID event_id, namespaced event_type, schema_version, occurred_at, recorded_at, source, subject_id, optional session_id, correlation_id, optional causation_id, unique idempotency_key, privacy_class and typed JSON payload. Producers supply observations; runtime policy authorizes resulting actions. Unknown future event types must not grant authority or alter gates automatically.

Current producer: gurukul.runtime; current event: session.started. Future namespaces can include learning.*, assessment.*, assistance.*, activity.*, presence.*, intervention.* and permission.* without coupling the envelope to a single sensor. Later sensor observations should include provenance/confidence and minimal retention. Observation, proposed intervention, permission decision and executed action are separate events. Telemetry ingestion and schema registries are deferred until needed.

Session creation and its event commit atomically. Database triggers reject event updates/deletes through normal access. This is not tamper-proof storage against the machine owner. Future events require versioned payload validation, deduplication and transactionally updated projections. SQLite and local files remain personal-device evidence, not remotely attested proof of independence.

## Responsibility boundaries
Deterministic code owns execution results, check outcomes, help availability, due dates and gate evaluation. Hermes teaches, diagnoses, proposes bounded hints and evaluates qualitative explanations. It cannot write learner files, execute submitted code, modify ledger rows or grant progression. Local data and synthetic examples only; no bank/customer data. A future subprocess runner is not a hostile-code sandbox. Camera, OS telemetry, blocking, iPhone and HeyClicky are deferred.

## Seven-day vertical slice
Day 1 / GURU-001: package, D01 content, database, start/resume, restart proof.
Day 2 / GURU-002: immutable submissions, bounded execution and captured results.
Day 3 / GURU-003: deterministic D01 checks tied to submission versions.
Day 4 / GURU-004: actual Hermes worker; approved-local teaching/reteaching, prediction-based diagnosis, controlled hints, disclosure enforcement and failure handling.
Day 5 / GURU-005: assistance-aware evidence transitions and gate tests.
Day 6 / GURU-006: due retrieval, bounded assessment, failure-to-remediation transition and later fresh reconstruction.
Day 7 / GURU-007: real end-to-end learner trial, recovery check and release evidence.

These are engineering targets with scope discipline, not a 60-minute build cap. No UI expansion, device enforcement or generic productivity tooling before the core learning loop works. Actual delayed retrieval is reported separately from simulated-clock scheduling tests. If upstream integration consumes more time, report it; never substitute a generic LLM and call the sprint complete.
