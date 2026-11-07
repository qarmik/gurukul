# G007 recovery message repair

Starting revision: `8bd2a28b0cd468c47c5c0ca4578a2420a8fc369e`.
Branch: `guru-007-local-workspace`. Acceptance and merge remain pending.

The learner-supplied Mac browser captures demonstrated an acknowledged save of
draft revision 14 after reconnecting, while the earlier `Failed to fetch` banner
remained until refresh. The synthetic read-only receipt reported five executions,
zero assessment reservations and the matching revision-14 source hash. These
were supplied Mac observations, not direct access by the build environment.

## Correction

Track transport errors separately from other messages. An acknowledged save
clears the transport error only when the current editor is fully saved and has
no conflict. A successful state read may clear a transport error for an already
clean draft; it cannot mark dirty text saved. A newer edit made during a save
keeps the connection error until its own save succeeds. HTTP rejection and other
errors are not classified as transport failures. Other messages remain present
during connection failures and after recovery, including unresolved completion
and integrity warnings. No lifecycle, execution, timer or budget policy changes.

## Focused verification

Platform: Linux 6.18.55 x86_64; Node v24.22.1.
Command: `node --test tests/test_workspace_drafts.mjs`.

The same final 19 tests against the original app.js at the starting revision:

```text
ℹ tests 19
ℹ suites 0
ℹ pass 14
ℹ fail 5
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 122.298976
```

After repair:

```text
ℹ tests 19
ℹ suites 0
ℹ pass 19
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 114.779388
```

Nine added regressions cover acknowledged recovery without refresh; failed
reconnect; successful state reads with dirty text; read recovery for a clean
draft; preservation of unresolved completion warnings; newer-draft conflicts;
edits during save acknowledgement; HTTP permission rejection; and preserving
unrelated errors beneath transport errors. All ten existing draft-race tests
remain passing. No full-suite rerun or provider calls were performed.

## Remaining browser proof

Status: PARTIAL pending actual browser verification of the repaired asset.
No repaired browser outcome or Mac process shutdown is claimed by this commit.
The build environment cannot inspect or stop the learner's Mac process.

Before verification, identify any workspace process by its exact synthetic root
and preserve the existing revision-14 fixture. Use a new disposable practice root
with no assessment or obligation. In Chrome, verify Offline makes local state
and save requests fail, edits stay unsaved, and reconnect produces an acknowledged
save with no stale connection banner before any refresh. Refresh only after
confirmation and reconcile draft/hash and unchanged execution/reservation counts.
Stop the identified synthetic server and retain its shutdown receipt.

Pending-action editing, Help/Exit, unsupported-syntax review and Finder launch
with the rebuilt environment retain their prior verification status. This repair
does not establish those claims. Earlier accepted increments remain closed;
book companion PR #1 stays draft. No real learner evidence or state is included.
