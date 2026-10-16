"""Synthetic D01 evidence only; these fixtures demonstrate no learner capability."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4

from gurukul.evidence import digest, eligibility
from gurukul.hermes_teaching import record_result
from gurukul.store import Store
from gurukul.submissions import submit
from test_checks import GOOD, FAILED

ROOT = Path(__file__).resolve().parents[1]
CONTENT = json.loads((ROOT / 'content/c0_b01/d01.json').read_text())


@unittest.skipUnless(os.name == 'posix', 'POSIX execution fixtures required')
class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        shutil.copytree(ROOT / 'content', self.root / 'content')
        self.path = self.root / 'var/gurukul.sqlite3'
        self.store = Store(self.path)
        self.session = self.store.start(CONTENT)
        self.failed = self.run_code(FAILED)
        self.repaired = self.run_code(GOOD)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def run_code(self, code):
        path = self.root / 'synthetic.py'
        path.write_text(code)
        return submit(self.store, path)['id']

    def fact(self, kind='none_declared', **kwargs):
        return dict(request_id=str(uuid4()), kind=kind,
                    steps=kwargs.pop('steps', ['construction', 'repair']),
                    timing=kwargs.pop('timing', 'during_work'),
                    origin=kwargs.pop('origin', 'learner_declaration'), **kwargs)

    def record(self, fact=None, repaired=None, failed=None):
        return self.store.record_assistance(repaired or self.repaired,
            fact if fact is not None else self.fact(), failed or self.failed)

    def review(self, repaired=None, failed=None):
        return eligibility(self.store, repaired or self.repaired, self.root, failed or self.failed)

    def count(self, kind):
        return self.store.db.execute('SELECT count(*) FROM events WHERE event_type=?', (kind,)).fetchone()[0]

    def test_unknown_assistance_holds_checked_pair(self):
        r = self.review()
        self.assertEqual('CHECKS_PASS', r['checker_outcome'])
        self.assertEqual(('HOLD', 'UNKNOWN'), (r['eligibility'], r['independence_status']))
        self.assertEqual('retained', r['practice_evidence'])

    def test_declaration_only_readiness_never_grants_authority(self):
        before = self.store.resume()
        self.record()
        r = self.review()
        self.assertEqual(('READY_FOR_REVIEW', 'DECLARED_ONLY'), (r['eligibility'], r['independence_status']))
        self.assertTrue(r['requires_review'])
        for key in ('grants_mastery', 'grants_verified_independence', 'changes_session_phase', 'advances_curriculum'):
            self.assertIs(False, r[key])
        self.assertEqual(before, self.store.resume())
        self.assertIn('source_sha256', r['bindings'])
        self.assertIn('canonical_sha256', r['curriculum'])

    def test_partial_declaration_cannot_cover_other_step(self):
        self.record(self.fact(steps=['construction']))
        self.assertEqual('HOLD', self.review()['eligibility'])

    def test_conflicting_declarations_preserve_practice_and_both_facts(self):
        self.record()
        self.record(self.fact('hint', steps=['repair']))
        r = self.review()
        self.assertEqual('HOLD', r['eligibility'])
        self.assertEqual('CONFLICTING', r['assistance_provenance'])
        self.assertEqual(2, len(r['assistance']))
        self.assertEqual('retained', r['practice_evidence'])

    def test_late_fact_invalidates_current_readiness_after_restart_without_rewriting(self):
        self.record()
        old = self.review()
        self.record(self.fact('code_or_repair', steps=['repair'], timing='before_work'))
        self.store.close()
        self.store = Store(self.path)
        current = self.review()
        self.assertEqual('READY_FOR_REVIEW', old['eligibility'])
        self.assertEqual('HOLD', current['eligibility'])
        self.assertNotEqual(old['decision_id'], current['decision_id'])
        row = self.store.db.execute("SELECT payload_json FROM events WHERE subject_id=? AND event_type='evidence.eligibility_recorded'", (old['decision_id'],)).fetchone()
        self.assertEqual(old, json.loads(row[0]))
        self.assertEqual(2, self.count('evidence.eligibility_recorded'))

    def test_concept_support_does_not_blanket_disqualify_work(self):
        self.record(self.fact('concept_support', steps=['concept_practice'], timing='before_work'))
        self.record()
        self.assertEqual('READY_FOR_REVIEW', self.review()['eligibility'])

    def test_post_submission_hint_does_not_rewrite_that_work_as_assisted(self):
        self.record()
        self.record(self.fact('hint', steps=['repair'], timing='after_submission'))
        self.assertEqual('READY_FOR_REVIEW', self.review()['eligibility'])

    def test_completed_pair_post_submission_exposure_preserves_readiness_after_restart(self):
        self.record()
        before = self.review()
        fact = self.fact('solution_exposure', timing='after_submission')
        recorded = self.record(fact)
        self.store.close()
        self.store = Store(self.path)
        current = self.review()
        self.assertEqual(('READY_FOR_REVIEW', 'DECLARED_ONLY'),
                         (current['eligibility'], current['independence_status']))
        self.assertEqual(recorded, self.record(fact))
        historical = self.store.db.execute('SELECT payload_json FROM events WHERE subject_id=?', (before['decision_id'],)).fetchone()
        self.assertEqual(before, json.loads(historical[0]))

    def test_hint_after_later_identical_pair_cannot_retroactively_assist_earlier_pair(self):
        self.record()
        earlier = self.review()
        later_failed, later_repaired = self.run_code(FAILED), self.run_code(GOOD)
        self.record(repaired=later_repaired, failed=later_failed)
        self.record(self.fact('hint', steps=['repair'], timing='after_submission'),
                    repaired=later_repaired, failed=later_failed)
        self.store.close()
        self.store = Store(self.path)
        current = self.review()
        self.assertEqual(('READY_FOR_REVIEW', 'DECLARED_ONLY'),
                         (current['eligibility'], current['independence_status']))
        self.assertEqual('READY_FOR_REVIEW', self.review(later_repaired, later_failed)['eligibility'])
        historical = self.store.db.execute('SELECT payload_json FROM events WHERE subject_id=?', (earlier['decision_id'],)).fetchone()
        self.assertEqual(earlier, json.loads(historical[0]))

    def test_hash_matching_help_for_other_pair_is_unresolved_not_proven_assistance(self):
        self.record(self.fact('hint', steps=['repair']))
        later_failed, later_repaired = self.run_code(FAILED), self.run_code(GOOD)
        self.record(repaired=later_repaired, failed=later_failed)
        current = self.review(later_repaired, later_failed)
        self.assertEqual(('HOLD', 'UNKNOWN'),
                         (current['eligibility'], current['independence_status']))
        carried = next(e for e in current['assistance'] if e['fact']['kind']=='hint')
        self.assertEqual(self.repaired, carried['original_bindings']['attempt_id'])

    def test_late_report_of_during_work_exposure_changes_current_not_historical_decision(self):
        self.record()
        earlier = self.review()
        self.record(self.fact('solution_exposure', timing='during_work'))
        self.store.close()
        self.store = Store(self.path)
        current = self.review()
        self.assertEqual(('HOLD', 'ASSISTED_OR_EXPOSED'),
                         (current['eligibility'], current['independence_status']))
        historical = self.store.db.execute('SELECT payload_json FROM events WHERE subject_id=?', (earlier['decision_id'],)).fetchone()
        self.assertEqual(earlier, json.loads(historical[0]))

    def test_post_submission_exposure_reported_after_other_pair_has_unresolved_timing(self):
        later_failed, later_repaired = self.run_code(FAILED), self.run_code(GOOD)
        self.record(repaired=later_repaired, failed=later_failed)
        self.record(self.fact('solution_exposure', timing='after_submission'))
        r = self.review(later_repaired, later_failed)
        self.assertEqual(('HOLD', 'UNKNOWN'), (r['eligibility'], r['independence_status']))

    def exposure(self, timing):
        self.record()
        self.record(self.fact('solution_exposure', timing=timing))
        r = self.review()
        self.assertEqual(('HOLD', 'ASSISTED_OR_EXPOSED'), (r['eligibility'], r['independence_status']))
        self.assertEqual('CHECKS_PASS', r['checker_outcome'])

    def test_exposure_before_work_holds(self):
        self.exposure('before_work')

    def test_exposure_during_work_holds(self):
        self.exposure('during_work')

    def test_exposure_after_submission_preserves_completed_work(self):
        self.record()
        self.record(self.fact('solution_exposure', timing='after_submission'))
        self.assertEqual('READY_FOR_REVIEW', self.review()['eligibility'])

    def test_unknown_timing_cannot_silently_become_no_help(self):
        self.record()
        self.record(self.fact('hint', steps=['repair'], timing='unknown'))
        self.assertEqual('HOLD', self.review()['eligibility'])
        with self.assertRaises(ValueError):
            self.record(self.fact(timing='unknown'))

    def test_identical_source_attempt_does_not_inherit_positive_declaration(self):
        self.record()
        self.assertEqual('READY_FOR_REVIEW', self.review()['eligibility'])
        failed, repaired = self.run_code(FAILED), self.run_code(GOOD)
        r = self.review(repaired, failed)
        self.assertEqual(('HOLD', 'UNKNOWN'), (r['eligibility'], r['independence_status']))

    def test_identical_source_cannot_wash_recorded_help_with_new_ids(self):
        self.record(self.fact('code_or_repair', steps=['repair']))
        failed, repaired = self.run_code(FAILED), self.run_code(GOOD)
        self.record(repaired=repaired, failed=failed)
        self.assertEqual('HOLD', self.review(repaired, failed)['eligibility'])

    def test_copy_after_hint_does_not_inherit_original_after_submission_exception(self):
        self.record(self.fact('hint', steps=['repair'], timing='after_submission'))
        failed, repaired = self.run_code(FAILED), self.run_code(GOOD)
        self.record(repaired=repaired, failed=failed)
        self.assertEqual('HOLD', self.review(repaired, failed)['eligibility'])

    def test_solution_exposure_is_not_reset_by_different_source_or_session(self):
        self.record(self.fact('solution_exposure', timing='after_submission'))
        with self.store.db:
            self.store.db.execute("UPDATE sessions SET status='closed'")
        self.store.start(CONTENT)
        failed = self.run_code(FAILED.replace('beta', 'other'))
        repaired = self.run_code(GOOD.replace('beta', 'other'))
        self.record(repaired=repaired, failed=failed)
        self.assertEqual('HOLD', self.review(repaired, failed)['eligibility'])

    def test_completed_readiness_and_future_variant_restriction_both_survive_restart(self):
        self.record()
        original_decision = self.review()
        exposure = self.record(self.fact('solution_exposure', timing='after_submission'))
        self.assertEqual('READY_FOR_REVIEW', self.review()['eligibility'])
        with self.store.db:
            self.store.db.execute("UPDATE sessions SET status='closed'")
        self.store.start(CONTENT)
        failed = self.run_code(FAILED.replace('beta', 'new-text'))
        repaired = self.run_code(GOOD.replace('beta', 'new-text'))
        self.record(repaired=repaired, failed=failed)
        self.store.close()
        self.store = Store(self.path)
        past = self.review()
        future = self.review(repaired, failed)
        self.assertEqual(('READY_FOR_REVIEW', 'DECLARED_ONLY'), (past['eligibility'], past['independence_status']))
        self.assertEqual(('HOLD', 'ASSISTED_OR_EXPOSED'), (future['eligibility'], future['independence_status']))
        carried = next(e for e in future['assistance'] if e['fact']['kind']=='solution_exposure')
        self.assertEqual('prior_variant_exposure', carried['relevance'])
        self.assertEqual(exposure['bindings'], carried['original_bindings'])
        historical = self.store.db.execute('SELECT payload_json FROM events WHERE subject_id=?', (original_decision['decision_id'],)).fetchone()
        self.assertEqual(original_decision, json.loads(historical[0]))
        for r in (past, future):
            self.assertFalse(r['grants_verified_independence'])
            self.assertFalse(r['grants_mastery'])

    def test_late_report_of_during_work_exposure_still_excludes_subsequent_work(self):
        later_failed, later_repaired = self.run_code(FAILED), self.run_code(GOOD)
        self.record(repaired=later_repaired, failed=later_failed)
        # Report is later than both pairs, occurrence remains scoped during A.
        self.record(self.fact('solution_exposure', timing='during_work'))
        current = self.review(later_repaired, later_failed)
        self.assertEqual(('HOLD', 'ASSISTED_OR_EXPOSED'), (current['eligibility'], current['independence_status']))
        exposure = next(e for e in current['assistance'] if e['fact']['kind']=='solution_exposure')
        self.assertEqual('prior_variant_exposure', exposure['relevance'])

    def test_identical_replay_and_restart_are_idempotent(self):
        fact = self.fact()
        self.record(fact)
        self.record(fact)
        first = self.review()
        events = self.store.events()
        self.store.close()
        self.store = Store(self.path)
        self.record(fact)
        self.assertEqual(first, self.review())
        self.assertEqual(events, self.store.events())

    def test_request_identity_cannot_be_reused_for_changed_fact_or_attempt(self):
        fact = self.fact()
        self.record(fact)
        before = self.store.events()
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            self.record(dict(fact, kind='hint'))
        clone = self.run_code(GOOD)
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            self.record(fact, repaired=clone)
        self.assertEqual(1, self.count('assistance.recorded'))
        self.assertEqual(before[-1]['payload'], next(e['payload'] for e in self.store.events() if e['event_type']=='assistance.recorded'))

    def test_assistance_event_failure_rolls_back_and_retry_succeeds(self):
        self.store.db.execute("CREATE TRIGGER fail_assist BEFORE INSERT ON events WHEN NEW.event_type='assistance.recorded' BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        fact = self.fact()
        with self.assertRaises(sqlite3.IntegrityError):
            self.record(fact)
        self.assertEqual(0, self.count('assistance.recorded'))
        self.store.db.execute('DROP TRIGGER fail_assist')
        self.record(fact)
        self.assertEqual(1, self.count('assistance.recorded'))

    def test_eligibility_event_failure_has_no_partial_decision(self):
        self.store.db.execute("CREATE TRIGGER fail_eligible BEFORE INSERT ON events WHEN NEW.event_type='evidence.eligibility_recorded' BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.review()
        self.assertEqual(0, self.count('evidence.eligibility_recorded'))
        self.assertEqual(1, self.count('assessment.checked'))
        self.store.db.execute('DROP TRIGGER fail_eligible')
        self.assertEqual('HOLD', self.review()['eligibility'])

    def test_missing_failed_run_is_hold_even_with_declaration(self):
        self.store.record_assistance(self.repaired, self.fact())
        r = eligibility(self.store, self.repaired, self.root)
        self.assertEqual(('NEEDS_EVIDENCE', 'HOLD'), (r['checker_outcome'], r['eligibility']))

    def test_wrong_session_failure_cannot_bind_assistance(self):
        with self.store.db:
            self.store.db.execute("UPDATE sessions SET status='closed'")
        self.store.start(CONTENT)
        repaired = self.run_code(GOOD)
        with self.assertRaisesRegex(ValueError, 'one session'):
            self.record(repaired=repaired)

    def test_source_and_output_integrity_fail_before_new_decision(self):
        self.record()
        self.review()
        source = self.root / 'var/evidence' / self.repaired / 'submission.py'
        source.chmod(0o600)
        source.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'integrity'):
            self.review()
        source.write_text(GOOD)
        stdout = source.parent / 'stdout.bin'
        stdout.chmod(0o600)
        stdout.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'integrity'):
            self.review()
        self.assertEqual(1, self.count('evidence.eligibility_recorded'))

    def test_canonical_curriculum_corruption_refuses_eligibility(self):
        path = self.root / 'content/curriculum/v0.8.3.txt'
        path.write_text('corrupt')
        with self.assertRaisesRegex(ValueError, 'curriculum digest'):
            self.review()
        self.assertEqual(0, self.count('evidence.eligibility_recorded'))

    def test_evaluation_payload_must_match_parent_event(self):
        r = self.review()
        evaluation_id = r['bindings']['evaluation_id']
        row = self.store.db.execute('SELECT result_json FROM evaluations WHERE id=?', (evaluation_id,)).fetchone()
        corrupted = json.loads(row[0]); corrupted['outcome'] = 'FAIL'
        with self.store.db:
            self.store.db.execute('DROP TRIGGER evaluations_no_update')
            self.store.db.execute('UPDATE evaluations SET result_json=? WHERE id=?', (json.dumps(corrupted), evaluation_id))
        with self.assertRaisesRegex(ValueError, 'parent event'):
            self.review()
        self.assertEqual(1, self.count('evidence.eligibility_recorded'))

    def test_spec_revision_creates_new_decision_without_rewriting_old_one(self):
        self.record()
        old = self.review()
        spec = self.root / 'content/checks/d01-v1.json'
        revised = json.loads(spec.read_text()); revised['checker_version'] = 'synthetic-revision'
        spec.write_text(json.dumps(revised))
        current = self.review()
        self.assertNotEqual(old['decision_id'], current['decision_id'])
        self.assertNotEqual(old['bindings']['evaluation_id'], current['bindings']['evaluation_id'])
        self.assertEqual(2, self.count('evidence.eligibility_recorded'))

    def test_no_help_declaration_cannot_override_failed_deterministic_checks(self):
        repaired = self.run_code('print(42)\n')
        self.record(repaired=repaired)
        r = self.review(repaired=repaired)
        self.assertEqual(('FAIL', 'HOLD'), (r['checker_outcome'], r['eligibility']))
        self.assertTrue(any(c['status'] == 'FAIL' for c in r['deterministic_checks']))

    def test_wrong_failure_pair_does_not_inherit_declaration(self):
        self.record()
        another_failure = self.run_code(FAILED)
        r = self.review(failed=another_failure)
        self.assertEqual('HOLD', r['eligibility'])
        self.assertEqual('UNKNOWN', r['independence_status'])

    def test_parent_supported_observation_requires_exact_event_provenance(self):
        from gurukul.evidence import bindings
        bound = bindings(self.store, self.repaired, self.failed)[0]
        payload = {'status':'PASS', 'grants_mastery':False,
                   'provenance':{'exercise_sha256':bound['exercise_sha256']},
                   'teaching':{'explanation':'Synthetic bounded hint, not a learner response.'}}
        record_result(self.store, 'synthetic-teaching', self.session['id'], payload)
        event = self.store.events()[-1]
        fact = self.fact('hint', steps=['repair'], origin='parent_event',
                         support_event_id=event['event_id'], support_payload_sha256=digest(payload))
        self.record(fact)
        r = self.review()
        self.assertEqual('SUPPORTED_OBSERVATIONS', r['assistance_provenance'])
        self.assertEqual('HOLD', r['eligibility'])
        with self.assertRaisesRegex(ValueError, 'provenance mismatch'):
            self.record(dict(fact, request_id=str(uuid4()), support_payload_sha256='0'*64))

    def test_missing_cross_ledger_reference_cannot_be_claimed_as_observed(self):
        with self.assertRaisesRegex(ValueError, 'cross-ledger'):
            self.record(self.fact('hint', origin='parent_event', support_event_id=str(uuid4()), support_payload_sha256='0'*64))
        with self.assertRaises(ValueError):
            self.record(self.fact(origin='parent_event'))

    def test_closed_schema_and_surface_language_cannot_grant_credit(self):
        for fact in (self.fact(kind='independent'), dict(self.fact(), grants_mastery=True),
                     self.fact(steps=['advance']), self.fact(steps=['repair','repair']),
                     self.fact(origin='guru_approved'), self.fact(kind=[])):
            with self.subTest(fact=fact), self.assertRaises(ValueError):
                self.record(fact)
        self.assertEqual(0, self.count('assistance.recorded'))

    def test_recording_observations_does_not_change_assessment_phase(self):
        with self.store.db:
            self.store.db.execute("UPDATE sessions SET phase='reconstruction'")
        self.record()
        self.review()
        self.assertEqual('reconstruction', self.store.resume()['session']['phase'])
        self.assertEqual([1,2,3], [r[0] for r in self.store.db.execute('SELECT version FROM schema_version ORDER BY version')])

    def test_cli_separate_processes_recompute_current_eligibility(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT/'src'), PYTHONDONTWRITEBYTECODE='1')
        def cli(*args):
            return json.loads(subprocess.check_output([sys.executable,'-B','-m','gurukul','--root',str(self.root),*args],env=env,text=True))
        def review(): return cli('eligibility',self.repaired,'--failed-attempt',self.failed)
        def record(fact):
            path=self.root/'assistance.json';path.write_text(json.dumps(fact))
            return cli('assistance',self.repaired,'--failed-attempt',self.failed,'--assistance-file',str(path))
        self.assertEqual('HOLD',review()['eligibility'])
        record(self.fact())
        self.assertEqual('READY_FOR_REVIEW',review()['eligibility'])
        record(self.fact('hint',steps=['repair']))
        self.assertEqual('HOLD',review()['eligibility'])
        self.assertEqual(3,self.count('evidence.eligibility_recorded'))


if __name__ == '__main__':
    unittest.main()
