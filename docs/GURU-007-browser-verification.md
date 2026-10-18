# G007-BROWSER-VERIFY — partial execution receipt

Disposition: **PARTIAL**. Draft-saving defects reproduced and repaired with deterministic JavaScript unit evidence. Actual Mac browser workflow and Finder launch are **BLOCKED: this execution host is Linux, with no Mac/Finder or learner-Mac connection available**. No actual browser interaction, screenshot, double-click, packaged browser bootstrap or target-machine interpreter verification is claimed in this receipt. Implementation acceptance and merge remain pending.

Starting remote branch/commit: `guru-007-local-workspace`, `b4fe4a84f22487d9662f93ebfcaaf14b0585fc5c` (tree `94ab888111bdb8b15662e67d68fbc8fc743a6fd9`, matched to the starting staged tree). Changes remain on that branch; main is unchanged. The supplied learner-specific reconciliation is excluded from this work and publication.

## Reproduction and repair

Actual application JavaScript is executed in Node's built-in `vm`, with minimal DOM nodes, controlled timers and deferred fetch responses. These tests deliberately control request ordering; they are **not a browser implementation or end-to-end browser proof**. No third-party UI framework or test dependency was introduced.

The original six-case test run against the starting JavaScript produced **5 failures, 1 pass**. [Original failure capture](GURU-007-draft-races-before.txt). Demonstrated failures:

| Race | Original observation | Repair |
| --- | --- | --- |
| Last autosave timer fires during a slow Run | Final edit never reaches the server without another action | Requeue a dirty draft when the busy action finishes. |
| Typing during a pending save | First revision persisted; final edit stranded | Compare the acknowledged bytes with current editor contents and queue remaining edits. |
| Periodic read returns after newer save | False draft conflict | Reject responses invalidated by later edits/saves or a newer read. |
| Previous-context read returns late | Context switches backward and latest editor text is replaced | Bind read response to requested context and editor generation. |
| Typing while explicit reload waits | New text is replaced and shown as saved | Cancel stale reload application; retain unsaved indicator and truthful message. |
| Another tab saves a newer revision | Existing conflict protection works | Retain conservative revision conflict; never silently overwrite server or editor. |

The repair is confined to `workspace_assets/app.js`. Start/preparation temporarily freeze editing while the saved draft/context is being switched, including Tab insertion. A failed context load leaves a neutral blank editor and disables execution until confirmed reload. Normal Run still permits editing while waiting. Dirty drafts warn on navigation; an online event retries saving after a disconnect. Failed saves remain explicitly unsaved rather than being labelled saved. Actual browser delivery of online/beforeunload events remains unverified.

No source snapshot, reservation, lifecycle, deadline, assistance policy, review authority, authentication or loopback binding is changed. Action replays continue to use the existing backend's durable operations; autosave does not dispatch execution. Ask Guru remains unavailable.

## Completed checks

[Environment](GURU-007-browser-environment.txt): Linux x86_64, Python 3.12.14, Node v24.19.0. Workspace/service tests and learner subprocesses use the recorded Python executable; these are Linux synthetic executions, not the Mac's interpreter.

```text
node --check src/gurukul/workspace_assets/app.js
# exit 0

node --test tests/test_workspace_drafts.mjs
# tests 10; pass 10; fail 0

PYTHONPATH=src python3 -B -m unittest discover -s tests -p test_workspace.py -v
Ran 25 tests in 4.104s
OK
```

[Final JavaScript capture](GURU-007-draft-races-after.txt) includes the original six cases and added disconnect/reconnect, frozen Tab, out-of-order same-context reads and failed-context-load recovery cases. [Affected service capture](GURU-007-browser-service-verification.txt) rechecks synthetic lifecycle, draft restart/CAS, duplicate dispatch, immutable evidence, crash recovery, declarations, review isolation and direct request guards. All ledgers are disposable fixtures; no real learner ledger or real variant was accessed or consumed. Guru/Maharishi calls: **0/0**.

The service capture preceded the final JavaScript-only reload-message refinement; the final ten-case JavaScript run covers that refinement. There are no Python/backend changes. No new full-suite run was necessary; the earlier 340-test full-suite capture remains evidence for its original revision only.

## Acceptance evidence still missing

| Required claim | Result |
| --- | --- |
| Reproduced races in actual app.js and focused regression repair | Proven in deterministic unit harness. |
| Synthetic service persistence, authority and duplicate-operation protections | 25 affected tests pass. |
| Mac isolated checkout/root/interpreters, safe Finder binding | BLOCKED: Mac unavailable. |
| Real browser editor/Run/Submit and source/result/lifecycle inspection | NOT VERIFIED in this dispatch. |
| Actual browser refresh/reconnect, stale tabs, preparation, timer, declarations, Help/Exit and unsupported-syntax review | NOT VERIFIED; unit/service coverage is not a substitute. |
| Finder double-click, authenticated bootstrap, packaged assets and restart | NOT VERIFIED on Mac. |

**Next micro-task — G007-MAC-SYNTHETIC-VERIFY (30 minutes, Mac access required):** use a separate checkout and disposable synthetic root/session, verify the launcher's resolved root excludes the real ledger, record both interpreters, perform the authorized browser/Finder cases, and retain screenshots plus linked synthetic ledger receipts. No real learner assessment or provider call is needed. Done means target-browser and Finder receipts cover the outstanding rows above; otherwise return the first exact blocker. Do not merge before architect review.
