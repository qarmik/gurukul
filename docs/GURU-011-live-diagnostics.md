# GURU-011 live trial and offline receipt diagnostics

The original Mac trial used Gurukul
`2d1787194c288718b54b973139145e747bfb366f`. The following is the operator-supplied
final receipt, preserved verbatim. The preceding receipt had the same fields.

```text
ASK_GURU_LIVE_FINAL={"model": "gpt-6-luna", "output_token_limit": 1024, "provider_request_limit": 1, "relay_reservations": 1, "transport_status": "BLOCKED", "call_id": "9f3d742f-a09f-42b3-955c-b0cff28c02f9", "failure_type": "ValueError", "upstream": [{"http_status": null, "provider_request_id": null, "resolved_model": null, "outcome": "blocked", "upstream_request_parameters": {"model": "gpt-6-luna", "max_completion_tokens": 1024, "reasoning_effort": "none", "stream": false, "store": false}}], "relay_rejections": 1, "worker_status": "BLOCKED", "ledger_unchanged_by_worker": true}
```

Browser: “Guru could not answer. This trial will not retry.” Blank draft at
revision 0, practice mode, no execution and no assessment started. The final
receipt followed Control+C. No teaching reply was displayed.

The receipt establishes a reservation and a blocked transport before teaching
reply validation. It does not establish provider delivery or the underlying
failure stage. The original relay recorded response status and request ID only
after its forwarding function returned, so null fields do not establish that
response headers never arrived. The single relay rejection has no reason code in
this receipt and cannot be causally assigned to the blocked upstream attempt.
The Ask Guru launcher did not request preservation of raw worker output or a raw
relay response; no such original diagnostics were available for this review.
The original live allowance remains spent.

The new receipt records status and a safely formatted provider request ID
before reading the body. A fixed upstream-stage label distinguishes local
credential handling, connection/send, waiting for headers, body read, body
decode, confirmed HTTP error, and reply validation. A 4xx/5xx status is also
marked independently, even if the body cannot be read or decoded. Separate
relay reason codes describe local policy denials without including request
paths, keys, prompts, bodies, or raw exception text.

Offline verification used dummy credentials, real loopback relay requests and
injected fake HTTPS connections. A body timeout after HTTP 200 retained the
status and `req_fixture123`; the second relay request returned 403 with
`request_budget_exhausted` and made no second forward. A standalone policy
denial had zero reservations and no upstream entry. Existing workspace tests
also exercised the teaching lock, reply validation and unchanged learner state.
Zero real provider requests. No further live attempt is authorized here.
