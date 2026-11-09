"""Exercise the projection against real, disposable Gurukul writer paths."""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from uuid import uuid4

import test_workspace as workspace_tests
from gurukul.assessment import sha
from export_progress import APPROVALS, CRITERIA, project, publish

ROOT = Path(__file__).resolve().parents[1]
TODAY = datetime.now(timezone.utc).date()
DATES = [(TODAY - timedelta(days=days)).isoformat() for days in range(3)]
APPROVED = dict.fromkeys(APPROVALS, True) | {"share_practice": False, "approved_dates": DATES}
SECRET = "PRIVATE_TEST_SENTINEL"
PUBLIC_EVIDENCE = "https://github.com/qarmik/gurukul/commit/b38422a85f36dc23507ca6100560d100dd6d580a"
SAMPLE = {
    "descriptions": {"ask-guru": {
        "title": "Ask Guru: keep help inside practice",
        "problem": "Provide learner help without exposing it during an assessment.",
        "verified": "The linked revision shipped practice help with an assessment boundary.",
    }},
    "contributions": {"ask-guru": {
        "contribution": "Illustrative example: I defined when the tutor must be unavailable and how to verify that boundary.",
        "help": "Illustrative example: AI assisted with implementation and test scaffolding.",
    }},
    "links": {"ask-guru": PUBLIC_EVIDENCE},
    "dates": {"ask-guru": "2026-01-15"},
}


def accept_review(fixture):
    aid, opened = fixture.opened()
    _, good = fixture.failed(aid, opened)
    result = fixture.action(good, "repaired", "submit", aid)
    assert result["observation"]["outcome"] == "COMPLETED_FOR_REVIEW"
    source, executions = {}, {}
    for run in fixture.w.state(aid)["lifecycle"]["runs"]:
        attempt = fixture.w.store.attempt(run["attempt_id"])
        source[attempt["id"]] = attempt["source_sha256"]
        executions[attempt["id"]] = sha(attempt["execution"])
    fixture.w.reviewer_id = SECRET
    args = (aid, SECRET, str(uuid4()), source, executions,
            dict.fromkeys(CRITERIA, "demonstrated"), SECRET + " <img src=x>")
    fixture.w.review(*args)
    return args


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.fixture = workspace_tests.WorkspaceTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.ledger = self.fixture.w.path
        self.out = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.root = self.fixture.root

    def export(self, approval=APPROVED):
        before = hashlib.sha256(self.ledger.read_bytes()).digest()
        snapshot = publish(self.ledger, approval, self.out, self.root)
        self.assertEqual(before, hashlib.sha256(self.ledger.read_bytes()).digest())
        return snapshot

    def test_disabled_approval_never_needs_a_ledger(self):
        snapshot = project(self.out / "absent.sqlite3",
                           dict.fromkeys(APPROVALS, False) | {"approved_dates": []}, self.root)
        self.assertIsNone(snapshot["current"])
        self.assertEqual([], snapshot["timeline"])

    def test_practice_run_does_not_change_snapshot_and_due_is_not_a_pass(self):
        f = self.fixture
        before = self.export()
        self.assertEqual("scheduled", before["timeline"][0]["status"])
        f.action("print(1) # " + SECRET, "repaired")
        self.assertEqual(before, self.export())
        f.w.controller.command("due", str(uuid4()), retrieval_id=f.retrieval["retrieval_id"])
        due = self.export()
        self.assertEqual(["due"], [row["status"] for row in due["timeline"]])
        self.assertEqual("in_progress", due["current"]["status"])
        self.assertNotIn("verified_complete", json.dumps(due))

    def test_committed_review_appears_once_without_inventing_completion(self):
        args = accept_review(self.fixture)
        result = self.export()
        self.assertEqual(["reviewed_evidence"], [row["status"] for row in result["timeline"]])
        self.assertEqual("awaiting_review", result["current"]["status"])
        self.assertEqual("in_progress", result["stages"][0]["status"])
        self.assertNotIn("verified_complete", json.dumps(result))
        self.fixture.w.review(*args)
        self.assertEqual(result, self.export())
        for file in ("progress.json", "summary.md"):
            content = (self.out / file).read_text()
            for private in (SECRET, self.fixture.sid, args[0], str(self.root), "assessment_id", "<img"):
                self.assertNotIn(private, content)
        self.assertEqual(TODAY.isoformat(), result["timeline"][0]["date"])
        private_dates = self.export(APPROVED | {"approved_dates": []})
        self.assertNotIn("date", private_dates["timeline"][0])
        self.assertEqual([], self.export(APPROVED | {"share_review": False})["timeline"])

    def test_reject_unknown_approval_fields_and_output_in_learner_state(self):
        with self.assertRaises(ValueError):
            self.export(APPROVED | {"private": SECRET})
        with self.assertRaises(ValueError):
            publish(self.ledger, APPROVED, self.ledger.parent, self.root)

    def test_only_fully_approved_work_and_confirmed_dates_are_exported(self):
        portfolio = SAMPLE | {"descriptions": SAMPLE["descriptions"] | {
            "private": {"title": SECRET}}, "dates": {}}
        result = publish(self.ledger, APPROVED, self.out, self.root, portfolio=portfolio, sample=True)
        self.assertEqual(1, len(result["selected_work"]))
        self.assertNotIn("date", result["selected_work"][0])
        for file in ("progress.json", "summary.md"):
            public = (self.out / file).read_text()
            self.assertNotIn(SECRET, public)
            self.assertIn(PUBLIC_EVIDENCE, public)
        with self.assertRaises(ValueError):
            publish(self.ledger, APPROVED, self.out, self.root,
                    portfolio=SAMPLE | {"links": {"ask-guru": "javascript:alert(1)"}})


def build_demo(output):
    """Stage two genuine exports from a temporary ledger; never use a real learner DB."""
    fixture = workspace_tests.WorkspaceTests()
    fixture.setUp()
    try:
        output.mkdir()
        for name in ("initial", "updated"):
            (output / name).mkdir()
            shutil.copyfile(ROOT / "docs/progress/index.html", output / name / "index.html")
        fixture.w.controller.command("due", str(uuid4()), retrieval_id=fixture.retrieval["retrieval_id"])
        settings = APPROVED | {"share_practice": True}
        publish(fixture.w.path, settings, output / "initial", fixture.root, portfolio=SAMPLE, sample=True)
        accept_review(fixture)
        publish(fixture.w.path, settings, output / "updated", fixture.root, portfolio=SAMPLE, sample=True)
    finally:
        fixture.tearDown()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "demo":
        build_demo(Path(sys.argv[2]))
    else:
        unittest.main()
