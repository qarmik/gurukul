# Upskilling portfolio: preview and publication

The portfolio lists up to three selected work items first, followed by a dated
timeline and the curriculum status. Descriptions (including what was verified),
personal contribution and help used, and evidence links are separately approved.
An item is included only if it appears in all three approved lists. Dates have
their own list; a date on a selected work item means the owner confirmed that it
shipped on that date. Undated work still appears in Selected work. Review
the approved prose and permalink targets for confidentiality before enabling;
the exporter never draws any of that prose from the learner ledger.

The curriculum map is pinned to the committed v0.8.3 map and D01 exercise.
D01 is the only exercise tracked by this slice. Assessment closure for review,
criterion-level evidence review and practice checks **do not grant independent
completion** in Gurukul. An approved, fully demonstrated review appears once as
reviewed evidence, without advancing curriculum progress. This version cannot
report a canonical independent pass because the ledger has no such decision.
There is no overall percentage.

## Reviewable preview

From the repository root, with Python 3.11+:

```sh
stage=$(mktemp -d)
PYTHONPATH=src:scripts:tests python -B tests/test_progress.py demo "$stage/site"
python -m http.server --bind 127.0.0.1 --directory "$stage/site/initial" 8000
```

Open http://127.0.0.1:8000/. The fixture creates two snapshots using disposable
Gurukul records and clearly marks all sample claims and dates. To reproduce the
phone, refresh, text rendering, and missing-snapshot checks, run
`node tests/test_progress_browser.cjs "$stage/site"` with Playwright installed.
Set `PLAYWRIGHT_MODULE` and `CHROME_EXECUTABLE` if the installation is elsewhere.

## Opt-in publication path

No job, credential, Pages setting, or real-data feed is enabled by this branch.
The proposed route is GitHub Pages from a dedicated `gh-pages` branch, with only
the staged files under `/progress/`. GitHub returned 404 without authentication
at the proposed URL during preview verification. Before enabling real data, publish
a sample on that route and check the page, JSON and evidence links in a signed-out
phone browser. The repository README contains a readable fallback and links to the
text summary.

After review, keep the approval files and canonical SQLite database outside the
published tree. The owner can explicitly enable a local watcher:

```sh
python scripts/export_progress.py --ledger /private/ledger.sqlite3 \
  --approval /private/progress-approval.json --portfolio-approval /private/portfolio-approval.json \
  --output /public-only-staging/progress --watch
```

Copy `index.html` there once. The watcher opens the ledger read-only and stages
`progress.json` and `summary.md` every five seconds if approved facts changed.
Configure a separate, explicitly enabled publisher to sync only those three
files to the Pages branch and commit/push only when bytes change. Keep credentials
with that publisher, never in the exporter or snapshot. The browser polls every
two seconds; production delay also includes sync and hosting cache time. The
timestamp denotes when the published snapshot was generated, not when the learner
last worked. Nothing streams from the ledger to the browser.

Learner approval JSON has exactly the boolean fields `share_current`,
`share_review`, `share_retrieval`, `share_practice`, plus the list
`approved_dates`. Keep all flags false and the list empty until approved.
Review, retrieval, and practice require their own opt-in; each displayed date
must be individually listed as a UTC calendar day. An otherwise approved
event can appear without a date. Portfolio approval JSON has four objects
keyed by stable work IDs:

- `descriptions`: `title`, `problem`, `verified`
- `contributions`: `contribution`, `help`
- `links`: explicitly approved public GitHub commit or pinned docs permalinks
- `dates`: explicitly confirmed ship dates as YYYY-MM-DD

No entries are approved in the repository. Production exports contain no learner
identifiers, record IDs, evidence hashes, source text, tutor conversations,
assessment material, credentials, or local paths.

## Public snapshot fields

- Top level: `curriculum_version`, `published_at`, `sample`, `selected_work`,
  `current`, `stages`, `milestones`, `timeline`.
- Selected work: `id`, `title`, `problem`, `contribution`, `help`, `verified`,
  `evidence_url`, and optional `date`.
- Current position (or null): `phase_id`, `milestone_id`, `status`, `summary`,
  `next_action`. Stage and milestone rows: `id`, `title`, `status`.
- Timeline rows: `work_id` or `milestone_id`, `status`, `summary`, and optional
  `date`.
