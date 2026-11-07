# GURU-011: Ask Guru live trial closeout

**Result: PASS** at tested revision `75f6b7635128f8a67fbe9e1069b168e0b118a36f`.
The operator ran the documented `--live-once` launcher in a fresh disposable
Mac practice workspace and submitted “What changes after reassignment?” once.

The shutdown receipt recorded `reply_admitted`. Separately, the operator's
browser screenshots showed a visible Guru answer: an explanation of what
reassignment changes, followed by a practice question using the values 3 and 8.
Both criteria were met. The initial transport receipt's
`reply_not_evaluated` was emitted before validation; the final receipt below
records the decision.

The screenshots show the draft still blank at saved revision `0`, practice
mode, no execution, and no assessment started. No learner progression
occurred. The final receipt reports that the worker left the ledger unchanged.
The operator pressed Control+C; the launcher emitted the final receipt and
returned to the shell. No retry, relaunch, or fallback was used.

## Sanitized final receipt

```text
ASK_GURU_LIVE_FINAL={"model": "gpt-6-luna", "output_token_limit": 1024, "provider_request_limit": 1, "relay_reservations": 1, "transport_status": "HERMES_RESPONSE_VERIFIED", "reply_reason_code": "reply_admitted", "call_id": "2ede7edf-069f-4a61-bf0d-e6780d027985", "upstream": [{"http_status": 200, "provider_request_id": "req_9be13c1bd0394ac2809011443dbf4316", "provider_http_error": false, "upstream_stage": "completed", "outcome": "completed", "upstream_request_parameters": {"model": "gpt-6-luna", "max_completion_tokens": 1024, "reasoning_effort": "none", "stream": false, "store": false}, "resolved_model": "gpt-6-luna"}], "relay_rejections": 0, "relay_rejection_codes": [], "worker_status": "PASS", "ledger_unchanged_by_worker": true}
```

## Earlier attempts

- [Initial live attempt and transport diagnostics](GURU-011-live-diagnostics.md):
  the transport was blocked; provider delivery was not established.
- [Live reply rejection and validation diagnostics](GURU-011-reply-diagnostics.md):
  provider transport completed, but the browser withheld the reply. The
  specific rejection reason remains unknown.

These historical records are unchanged. This closeout records the operator's
evidence; it does not add another trial or rerun tests.
