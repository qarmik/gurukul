# GURU-011: Reply validation diagnostics

## Preserved live result

Base: `997f39faacae53ff667e1b84207d1fc72a5ddbfa`.
Operator-supplied final receipt, preserved verbatim:

```text
ASK_GURU_LIVE_FINAL={"model": "gpt-6-luna", "output_token_limit": 1024, "provider_request_limit": 1, "relay_reservations": 1, "transport_status": "HERMES_RESPONSE_VERIFIED", "call_id": "c7aa0dda-05e5-4a08-8882-6b4339a05901", "upstream": [{"http_status": 200, "provider_request_id": "req_421757ff125a45b29ec44c0363631bd6", "provider_http_error": false, "upstream_stage": "completed", "outcome": "completed", "upstream_request_parameters": {"model": "gpt-6-luna", "max_completion_tokens": 1024, "reasoning_effort": "none", "stream": false, "store": false}, "resolved_model": "gpt-6-luna"}], "relay_rejections": 0, "relay_rejection_codes": [], "worker_status": "PASS", "ledger_unchanged_by_worker": true}
```

The browser showed “Guru’s reply could not be validated.” No exact reply was
available in the preserved local evidence reviewed. The launcher uses temporary
workspace and worker directories, and this call did not opt into saving worker
output. The original rejection reason remains **unknown**. The browser text
cannot distinguish decoding, validation, or admission.

## Offline prompt comparison

The generated D01 prompt asks for a direct conceptual answer to the reassignment
question. A fake prose-only answer is admitted by the existing policy. The
system prompt permits a miniature example with at most two simple statements
and “at most one assigned name.” Two assignments to the same name satisfy that
wording literally, but the validator counts assignment statements and rejects
the example on its existing cumulative-construction rule. This was reproduced
with a fake answer and does not explain the original live rejection.

Proposed wording-only correction: replace “at most one assigned name” with
“at most one assignment statement” and suggest prose for reassignment if an
example would require two assignments. No prompt or validation rule changes
are included here.

## Receipt field

`ASK_GURU_LIVE_RECEIPT` remains the transport snapshot. After teaching output
processing, `ASK_GURU_LIVE_FINAL` includes the resulting `reply_reason_code`:

| Code | Meaning |
| --- | --- |
| `reply_not_evaluated` | No reply reached decoding and evaluation. |
| `invalid_reply_json` | The reply could not be decoded as JSON. |
| `reply_validation_failed` | Decoded JSON failed an existing output check. |
| `reply_withheld_after_validation` | Evaluation returned an outcome other than `CONTINUE`. |
| `reply_admitted` | The server admitted learner-visible text. This is not a browser display acknowledgment. |

Only the fixed code enters the receipt. No prompts, lesson excerpts, replies,
exception messages, or credentials are recorded by the observer. The learner
still sees the existing error text for a withheld reply. The teaching lock and
provider request budget are unchanged. Offline tests use fake responses; zero
provider requests were made.
