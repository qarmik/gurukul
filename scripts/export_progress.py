"""Project committed Gurukul evidence into an explicitly approved public snapshot."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
MILESTONE = "C0-B01-D01"
MAP_SHA = "3f2a4c93f0fa44a3cb4d46847f526a9f877c5cf632a55bf83a0262fbd2e57910"
EXERCISE_SHA = "f5bc541e6dbca989bb7122b8b855fc9bcda20eb6b2beb0c5bec20d21ea44e5a3"
APPROVALS = {"share_current", "share_review", "share_retrieval", "share_practice"}
CRITERIA = {"five_variables", "text_and_numbers", "print_initial_values",
            "reassign_and_reprint", "quoted_text_repair", "variant_conformity"}
ASSESSMENT_EVENTS = {"retrieval.scheduled", "retrieval.became_due", "assessment.opened",
                     "assessment.closed", "assessment.observation_recorded", "remediation.completed"}
PUBLIC_LINK = re.compile(r"https://github\.com/qarmik/gurukul/(?:commit/[0-9a-f]{40}|blob/[0-9a-f]{40}/docs/[\w./-]+)")


def selected_work(approval):
    """Only the intersection of the three owner-approved lists can appear."""
    if approval is None:
        return []
    keys = {"descriptions", "contributions", "links", "dates"}
    if set(approval) != keys or any(not isinstance(approval[key], dict) for key in keys):
        raise ValueError("Invalid portfolio approvals.")
    descriptions, contributions, links, dates = (approval[key] for key in
                                                   ("descriptions", "contributions", "links", "dates"))
    approved = []
    for key in descriptions:
        if key not in contributions or key not in links:
            continue
        if not re.fullmatch(r"[a-z0-9-]{1,40}", key):
            raise ValueError("Invalid portfolio item ID.")
        description, contribution, link = descriptions[key], contributions[key], links[key]
        if (set(description) != {"title", "problem", "verified"} or
                set(contribution) != {"contribution", "help"} or
                any(not isinstance(v, str) or not 1 <= len(v.strip()) <= 350
                    or re.search(r"://|\bwww\.|@", v, re.I)
                    for v in (*description.values(), *contribution.values())) or
                not PUBLIC_LINK.fullmatch(link) or ".." in link.split("/")):
            raise ValueError("Invalid approved portfolio item.")
        item = {"id": key, **description, **contribution, "evidence_url": link}
        if key in dates:
            item["date"] = approved_date(dates[key])
        approved.append(item)
    if len(approved) > 3:
        raise ValueError("Select at most three portfolio items.")
    return approved


def approved_map(root):
    path = root / "content/curriculum"
    raw = (path / "map.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != MAP_SHA:
        raise ValueError("Curriculum map requires fresh publication approval.")
    mapping = json.loads(raw)
    if hashlib.sha256((path / "v0.8.3.txt").read_bytes()).hexdigest() != mapping["canonical_sha256"]:
        raise ValueError("Curriculum source does not match the approved map.")
    return mapping


def date_only(value):
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise ValueError("A published date must have a time zone.")
    return stamp.astimezone(timezone.utc).date().isoformat()


def approved_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Use an explicitly approved calendar date.")
    datetime.strptime(value, "%Y-%m-%d")
    return value


def project(ledger, approval, root=ROOT, *, portfolio=None, sample=False):
    if (set(approval) != APPROVALS | {"approved_dates"}
            or any(type(approval[key]) is not bool for key in APPROVALS)
            or not isinstance(approval["approved_dates"], list)):
        raise ValueError("Invalid publication approval.")
    approved_dates = {approved_date(value) for value in approval["approved_dates"]}
    mapping = approved_map(root)
    exercise_bytes = (root / "content/c0_b01/d01.json").read_bytes()
    if hashlib.sha256(exercise_bytes).hexdigest() != EXERCISE_SHA:
        raise ValueError("Milestone mapping requires fresh publication approval.")
    exercise = json.loads(exercise_bytes)
    stages = [{"id": key, "title": mapping["stages"][key]["title"], "status": "not_tracked"}
              for key in (f"C{i}" for i in range(10))]
    milestone = {"id": MILESTONE, "title": "Literal or variable?", "status": "not_published"}
    current = None
    timeline = []
    work = selected_work(portfolio)
    if approval["share_current"]:
        with closing(sqlite3.connect(Path(ledger).resolve().as_uri() + "?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            sessions = db.execute("SELECT id, phase, exercise_id, exercise_version FROM sessions "
                                  "WHERE status='active'").fetchall()
            if len(sessions) > 1:
                raise ValueError("Ambiguous active session.")
            if sessions and (sessions[0]["exercise_id"], sessions[0]["exercise_version"]) == (
                    MILESTONE, exercise["version"]):
                stored = db.execute("SELECT content_json, sha256 FROM exercises WHERE id=? AND version=?",
                                    (MILESTONE, exercise["version"])).fetchone()
                if (not stored or hashlib.sha256(stored["content_json"].encode()).hexdigest() != stored["sha256"]
                        or json.loads(stored["content_json"]) != exercise):
                    raise ValueError("Stored exercise is not the approved milestone.")
                current, timeline = session_progress(db, sessions[0], approval, approved_dates)
                milestone["status"] = current["status"]
                # D01 is tracked; there is no stage-level completion authority.
                stages[0]["status"] = "in_progress"
    timeline += [{"work_id": item["id"], "status": "shipped", "summary": item["title"], "date": item["date"]}
                 for item in work if "date" in item]
    timeline.sort(key=lambda row: row.get("date", ""), reverse=True)
    return {"curriculum_version": mapping["curriculum_version"], "current": current,
            "stages": stages, "milestones": [milestone], "timeline": timeline,
            "selected_work": work, "sample": sample}


def session_progress(db, session, approval, approved_dates):
    status = "in_progress"
    summary = "No verified curriculum pass is recorded."
    next_action = "Continue the values and variables exercise."
    rows = db.execute(
        "SELECT event_type, source, subject_id, occurred_at, payload_json FROM events "
        "WHERE session_id=? AND schema_version=1 AND source IN ('gurukul.assessment','gurukul.workspace') "
        "ORDER BY sequence", (session["id"],))
    obligations, opened, closed, reviews = {}, {}, {}, {}
    latest_assessment = None
    observation = None
    remediated = False
    for row in rows:
        kind, source, key, stamp, raw = row
        if kind == "evidence.review_recorded" and source == "gurukul.workspace" and approval["share_review"]:
            p = json.loads(raw)
            aid = p.get("assessment_id")
            if aid in closed and closed[aid]["outcome"] == "COMPLETED_FOR_REVIEW":
                reviews[aid] = (stamp, p)
        elif kind in ASSESSMENT_EVENTS and source == "gurukul.assessment":
            p = json.loads(raw)
            if kind == "retrieval.scheduled":
                obligations[key] = (p["due_at"], False)
            elif kind == "retrieval.became_due" and key in obligations:
                obligations[key] = (obligations[key][0], True)
            elif kind == "assessment.opened":
                obligations.pop(p["retrieval_id"], None)
                opened[key] = True
                latest_assessment, observation, remediated = key, None, False
            elif kind == "assessment.closed" and key in opened:
                closed[key] = p
            elif kind == "assessment.observation_recorded" and key == latest_assessment:
                observation = p.get("outcome")
            elif kind == "remediation.completed":
                remediated = True

    if latest_assessment in closed:
        outcome = closed[latest_assessment]["outcome"]
        if outcome in {"COMPLETED_FOR_REVIEW", "REVIEW_REQUIRED"}:
            status, next_action = "awaiting_review", "Review the assessment evidence before advancing."
        elif outcome in {"FAILED", "HELP_REQUESTED", "ABANDONED", "INTERRUPTED"} and not remediated:
            status, next_action = "blocked", "Reconcile the assessment outcome before continuing."
    elif latest_assessment:
        next_action = "Finish the open assessment."
        if observation == "NEEDS_REVIEW":
            status, next_action = "awaiting_review", "Review the open assessment evidence."
        elif observation in {"BLOCKED", "EXECUTION_BLOCKED", "NEEDS_EVIDENCE"}:
            status, next_action = "blocked", "Resolve the assessment evidence issue."
    if session["phase"] == "remediation":
        status, next_action = "blocked", "Complete the remediation work before the next assessment."
    elif obligations and approval["share_retrieval"] and session["phase"] != "assessment":
        if any(due for _, due in obligations.values()):
            next_action = "Complete the recorded due retrieval."
        elif status == "in_progress":
            next_action = "Return for the scheduled retrieval."

    timeline = []
    reviewed = [(stamp, p) for stamp, p in reviews.values() if
                p.get("historical_outcome") == "COMPLETED_FOR_REVIEW"
                and p.get("criteria") == dict.fromkeys(CRITERIA, "demonstrated")
                and all(p.get(k) is False for k in ("grants_mastery", "grants_verified_independence",
                                                    "advances_curriculum", "changes_eligibility"))]
    if reviewed:
        summary = "A reviewer marked all D01 evidence criteria demonstrated. No curriculum pass was awarded."
        timeline.append({"milestone_id": MILESTONE, "status": "reviewed_evidence", "summary": summary})
        review_date = min(date_only(stamp) for stamp, _ in reviewed)
        if review_date in approved_dates:
            timeline[-1]["date"] = review_date
    if obligations and approval["share_retrieval"]:
        due_at, due = min(obligations.values(), key=lambda pair: (not pair[1], pair[0]))
        timeline.append({"milestone_id": MILESTONE, "status": "due" if due else "scheduled",
                         "summary": "Retrieval is due." if due else "Retrieval is scheduled."})
        if date_only(due_at) in approved_dates:
            timeline[-1]["date"] = date_only(due_at)
    if approval["share_practice"]:
        practice = db.execute(
            """SELECT e.occurred_at FROM events e
               WHERE e.session_id=? AND e.schema_version=1 AND e.event_type='assessment.checked'
                 AND e.source='gurukul.checker' AND json_extract(e.payload_json,'$.outcome')='CHECKS_PASS'
                 AND NOT EXISTS (
                   SELECT 1 FROM events r WHERE r.event_type='assessment.run_reserved'
                     AND r.session_id=e.session_id
                     AND json_extract(r.payload_json,'$.attempt_id')=e.correlation_id)
               ORDER BY e.sequence DESC LIMIT 1""", (session["id"],)).fetchone()
        if practice:
            timeline.append({"milestone_id": MILESTONE, "status": "practised",
                             "summary": "Practice checks were recorded. This is not an independent pass."})
            if date_only(practice["occurred_at"]) in approved_dates:
                timeline[-1]["date"] = date_only(practice["occurred_at"])
    return {"phase_id": "C0", "milestone_id": MILESTONE, "status": status,
            "summary": summary, "next_action": next_action}, timeline


def markdown(snapshot):
    def plain(text):
        return re.sub(r"([\\`*_\[\]<>!|])", r"\\\1", " ".join(text.split()))

    current = snapshot["current"]
    lines = ["# Upskilling portfolio", "", f'Curriculum v{snapshot["curriculum_version"]}',
             f'Published: {snapshot["published_at"]}', ""]
    if snapshot["sample"]:
        lines += ["**Sample preview — not a claim about the learner.**", ""]
    lines += ["## Selected work", ""]
    for item in snapshot["selected_work"]:
        lines += [f'### {plain(item["title"])}', "",
                  *[f'**{label}:** {plain(item[key])}' for label, key in (
                      ("Problem", "problem"), ("My contribution", "contribution"),
                      ("Help used", "help"), ("Verified", "verified"))],
                  f'[Evidence]({item["evidence_url"]})', ""]
    if not snapshot["selected_work"]:
        lines += ["No selected work is approved for display yet.", ""]
    lines += ["## Curriculum progress", ""]
    if current:
        title = snapshot["milestones"][0]["title"]
        phase = snapshot["stages"][0]["title"]
        lines += [f'**Current:** {current["phase_id"]} — {phase} / {current["milestone_id"]} — {title}',
                  "", current["summary"], "", f'**Next:** {current["next_action"]}', ""]
    else:
        lines += ["No approved learner snapshot is available.", ""]
    for item in snapshot["timeline"]:
        lines.append("- " + plain(item["summary"]) + (" (" + item["date"] + ")" if "date" in item else ""))
    lines += ["", "Software releases are separate from learner progress.", ""]
    return "\n".join(lines)


def write_atomic(path, content):
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".progress-", delete=False) as f:
        temp = Path(f.name)
        try:
            f.write(content)
            f.close()
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)


def publish(ledger, approval, output, root=ROOT, *, portfolio=None, sample=False):
    output = Path(output).resolve()
    if output.is_relative_to(Path(ledger).resolve().parent):
        raise ValueError("Output must be outside the learner state directory.")
    snapshot = project(ledger, approval, root, portfolio=portfolio, sample=sample)
    path = output / "progress.json"
    try:
        old = json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        old = {}
    # Repeated exports of the same accepted facts do not create a new update.
    old_stamp = old.pop("published_at", None)
    if old == snapshot and old_stamp:
        snapshot["published_at"] = old_stamp
        if not (output / "summary.md").is_file():
            write_atomic(output / "summary.md", markdown(snapshot))
        return snapshot
    snapshot["published_at"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    write_atomic(output / "summary.md", markdown(snapshot))
    write_atomic(path, json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--approval", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="Existing public-only staging directory")
    parser.add_argument("--portfolio-approval", type=Path, help="Private, owner-approved portfolio selections")
    parser.add_argument("--watch", action="store_true", help="Re-export changed approved facts every five seconds")
    args = parser.parse_args()
    try:
        while True:
            portfolio = json.loads(args.portfolio_approval.read_text()) if args.portfolio_approval else None
            publish(args.ledger, json.loads(args.approval.read_text()), args.output, portfolio=portfolio)
            if not args.watch:
                return
            time.sleep(5)
    except (ValueError, OSError, sqlite3.Error, KeyError, TypeError):
        parser.exit(1, "Progress export stopped. Verify the ledger, approval, and staging directory locally.\n")


if __name__ == "__main__":
    main()
