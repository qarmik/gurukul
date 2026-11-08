# GURU-009 — Ask Guru sample

Base: `34c483a144e7808a90e6916cf9e4ed1578fac3d7`.
Enable explicitly with `gurukul-workspace --root <disposable-root> --sample-guru`.
The exercise has one question field and one labelled sample reply. The reply is
a fixed D01 practice prompt. The question is not sent to a provider, written to
the ledger, or used to read or change the editor. No assessment credit, mastery
or curriculum advancement is granted.

The authenticated `POST /api/teach` uses the canonical session and holds
`canonical_teaching` through responder dispatch. An open assessment denies even
a direct request; the browser also disables the question and clears the practice
reply on context change. The opt-in sample is confined to the practice editor.
There are no provider credentials, relay calls or new ledger events.

## Verification

Linux x86_64, Python 3.12.14, Node 24.22.1:

- `PYTHONPATH=src python -B -m unittest discover -s tests -p test_workspace.py -v`:
  **26 passed**. Includes authenticated sample response, unchanged draft and
  session events, and direct denial with the responder call count unchanged.
- `node --test tests/test_workspace_drafts.mjs`: **21 passed**. Includes a
  labelled reply with an unsaved draft and disabled controls in assessment.
- Disposable HTTP demonstration: practice returned 200 with a sample reply
  and unchanged draft; assessment opened and the same question returned 409.
  Total responder calls: 1. Executions: 2 seed runs before and after.
  Assessment reservations: 0. Provider calls: 0.

Actual browser verification is pending. No usable Chromium executable was
present on Linux; the Playwright download failed with an invalid ZIP.
Run the browser check with an existing Playwright and Chrome installation:

```sh
PLAYWRIGHT_MODULE=/absolute/path/to/node_modules/playwright-core \
CHROME_EXECUTABLE="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
PYTHON=/absolute/path/to/python3 \
node tests/test_ask_guru_browser.cjs
```

The check creates a temporary synthetic ledger and fresh browser context,
exercises both cases against the real workspace HTTP routes, and closes both
processes. It never reads a learner ledger or uses a personal Chrome profile.
