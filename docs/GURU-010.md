# GURU-010 — Ask Guru teaching pipeline

Base: `a49af696115cac8021616611ca9b1fb3bc8b5bb2`.

Ask Guru can run a single D01 question through Gurukul's approved source
admission, curriculum context and prompt, and teaching output validation and
admission. The workspace displays only the admitted teaching text. The
interactive Hermes runner shares turn preparation and continues to use the
same output evaluator.

The server must explicitly receive a `TeachingPipeline(source, transport)`.
The normal workspace launch does not configure a transport; the GURU-009
sample remains available through its existing opt-in. This branch does not
configure or exercise live provider access, start a Hermes worker from the
workspace, or add conversation history. The test transport returns raw teaching
JSON, so it does not bypass production output validation.

The existing canonical teaching lease covers preparation, transport dispatch
and output validation. An open assessment denies direct requests before
dispatch. The question is the only learner text included in the prompt.
Asking Guru does not save or replace the draft, record learning progress,
reserve an execution, or award credit. The UI shows a failed request beside
the question, and normal draft autosave still works.

## Verification

Disposable loopback HTTP workspace; synthetic approved source and stub
transport. No live provider calls.

| Case | Observed result |
| --- | --- |
| Practice question: “What changes after reassignment?” | HTTP 200, validated: “The name now refers to the newly assigned value.” Draft and progress unchanged. |
| Open assessment, direct teaching request | HTTP 409, tutoring denied; zero additional dispatches. Draft and progress unchanged. |
| Simulated timeout | HTTP 502, “Guru could not answer right now. Please try again.” Draft and progress unchanged. |
| Invalid response contract | HTTP 502, validation error shown; no raw response details exposed. Draft and progress unchanged. |

The practice test also tried to open the assessment from inside the stub and
confirmed that the teaching lock still prevented it.

Linux x86-64, Python 3.12.14, Node 24.22.1:

- `PYTHONPATH=src python -B -m unittest discover -s tests -p test_workspace.py -v`: 29 passed.
- `PYTHONPATH=src python -B -m unittest discover -s tests -p test_hermes_live.py -v`: 21 passed with stubbed transport.
- `node --test tests/test_workspace_drafts.mjs`: 23 passed, including display of a validated reply and autosave after a teaching error.
