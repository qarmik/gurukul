"""Synthetic checker fixtures, not learner submissions or proof of mastery."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from gurukul.checks import analyse, evaluate
from gurukul.store import Store, canonical
from gurukul.submissions import submit

ROOT = Path(__file__).resolve().parents[1]
CONTENT = json.loads((ROOT / 'content/c0_b01/d01.json').read_text())
# These mechanical test inputs intentionally use generic names and labels.
GOOD = 'a="alpha"\nb="beta"\nc=3\nd=4.5\ne=-6\nprint(a,b,c,d,e)\na="omega"\nc=9\nprint(a,c)\n'
FAILED = GOOD.replace('a="alpha"', 'a=alpha')


@unittest.skipUnless(os.name == 'posix', 'POSIX runner required to produce evidence')
class D01Checks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        shutil.copytree(ROOT / 'content', self.root / 'content')
        self.store = Store(self.root / 'var/gurukul.sqlite3')
        self.store.start(CONTENT)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def run_code(self, code, **kwargs):
        source = self.root / 'fixture.py'
        source.write_text(code)
        return submit(self.store, source, **kwargs)['id']

    def check(self, repaired, failed=None):
        return evaluate(self.store, repaired, self.root, failed)

    def pair(self):
        return self.run_code(FAILED), self.run_code(GOOD)

    def test_full_pair_passes_without_mastery(self):
        failed, repaired = self.pair()
        before = self.store.resume()
        with patch('gurukul.submissions.execute', side_effect=AssertionError('must not rerun')):
            r = self.check(repaired, failed)
        self.assertEqual('CHECKS_PASS', r['outcome'])
        self.assertTrue(all(c['status'] == 'PASS' for c in r['checks']))
        self.assertFalse(r['grants_mastery'])
        self.assertEqual('not_verified', r['independence'])
        self.assertEqual(before, self.store.resume())
        self.assertEqual(CONTENT['version'], r['exercise_version'])
        self.assertEqual(hashlib.sha256(GOOD.encode()).hexdigest(), r['source_sha256'])
        self.assertEqual('1', r['checker_version'])

    def test_successful_execution_alone_fails_requirements(self):
        result = self.check(self.run_code('print(42)\n'))
        self.assertEqual('FAIL', result['outcome'])
        self.assertEqual('FAIL', next(c for c in result['checks'] if c['id'] == 'five_variables')['status'])

    def test_missing_failed_run_is_incomplete(self):
        self.assertEqual('NEEDS_EVIDENCE', self.check(self.run_code(GOOD))['outcome'])

    def test_no_reassignment_or_same_value_fails(self):
        for code in (GOOD.replace('a="omega"\nc=9\n', ''), GOOD.replace('a="omega"\nc=9\n', 'a="alpha"\nc=3\n')):
            r = self.check(self.run_code(code))
            self.assertEqual('FAIL', r['outcome'])

    def test_reassignment_not_printed_and_change_reverted_fail(self):
        for code in (GOOD.replace('print(a,c)\n', ''), GOOD.replace('print(a,c)\n', 'a="alpha"\nc=3\nprint(a,c)\n')):
            r = self.check(self.run_code(code))
            item = next(c for c in r['checks'] if c['id'] == 'reassign_and_reprint')
            self.assertEqual('FAIL', item['status'])

    def test_hardcoded_output_does_not_count_as_variable_print(self):
        r = self.check(self.run_code(GOOD.replace('print(a,b,c,d,e)', 'print("alpha beta 3 4.5 -6")')))
        self.assertEqual('FAIL', r['outcome'])
        self.assertEqual('FAIL', next(c for c in r['checks'] if c['id'] == 'print_initial_values')['status'])

    def test_only_numeric_initial_values_fail(self):
        code = GOOD.replace('"alpha"', '1').replace('"beta"', '2')
        r = self.check(self.run_code(code))
        self.assertEqual('FAIL', next(c for c in r['checks'] if c['id'] == 'text_and_numbers')['status'])

    def test_unused_text_cannot_satisfy_printed_value_mix(self):
        code = GOOD.replace('"alpha"', '1').replace('"beta"', '2') + 'unused="text"\n'
        r = self.check(self.run_code(code))
        self.assertEqual('FAIL', next(c for c in r['checks'] if c['id'] == 'text_and_numbers')['status'])

    def test_unsupported_valid_python_needs_review(self):
        self.assertEqual('NEEDS_REVIEW', self.check(self.run_code('for n in range(5):\n print(n)\n'))['outcome'])

    def test_wrong_error_and_unrelated_repair_fail(self):
        for broken, outcome in [('1/0\n', 'FAIL'), (FAILED + 'print("extra")\n', 'NEEDS_REVIEW')]:
            bad = self.run_code(broken)
            r = self.check(self.run_code(GOOD), bad)
            self.assertEqual(outcome, r['outcome'])

    def test_failure_after_repair_rejected(self):
        repaired = self.run_code(GOOD)
        failed = self.run_code(FAILED)
        self.assertEqual('FAIL', self.check(repaired, failed)['outcome'])

    def test_failure_from_another_session_rejected(self):
        failed = self.run_code(FAILED)
        with self.store.db:
            self.store.db.execute("UPDATE sessions SET status='closed'")
        self.store.start(CONTENT)
        self.assertEqual('FAIL', self.check(self.run_code(GOOD), failed)['outcome'])

    def test_timeout_and_output_limit_are_blocked(self):
        for code, kwargs in [('while True: pass', {'timeout': 0.1}), (GOOD, {'output_limit': 1})]:
            self.assertEqual('BLOCKED', self.check(self.run_code(code, **kwargs))['outcome'])

    def test_failed_program_not_passed(self):
        self.assertEqual('FAIL', self.check(self.run_code(FAILED))['outcome'])

    def test_repeated_check_and_restart_are_idempotent(self):
        failed, repaired = self.pair()
        first = self.check(repaired, failed)
        events = self.store.events()
        self.store.close()
        self.store = Store(self.root / 'var/gurukul.sqlite3')
        self.assertEqual(first, self.check(repaired, failed))
        self.assertEqual(events, self.store.events())
        self.assertEqual(1, self.store.db.execute('SELECT count(*) FROM evaluations').fetchone()[0])

    def test_evaluation_and_event_rollback_together(self):
        failed, repaired = self.pair()
        self.store.db.execute("CREATE TRIGGER fail_check BEFORE INSERT ON events WHEN NEW.event_type='assessment.checked' BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.check(repaired, failed)
        self.assertEqual(0, self.store.db.execute('SELECT count(*) FROM evaluations').fetchone()[0])

    def test_corrupt_source_or_exercise_refused(self):
        repaired = self.run_code(GOOD)
        source = self.root / 'var/evidence' / repaired / 'submission.py'
        source.chmod(0o600)
        source.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'snapshot integrity'):
            self.check(repaired)
        source.write_text(GOOD)
        with self.store.db:
            self.store.db.execute("UPDATE exercises SET content_json='{}'")
        with self.assertRaisesRegex(ValueError, 'exercise integrity'):
            self.check(repaired)

    def test_spec_change_creates_separate_versioned_evaluation(self):
        repaired = self.run_code(GOOD)
        first = self.check(repaired)
        path = self.root / 'content/checks/d01-v1.json'
        spec = json.loads(path.read_text());spec['checker_version'] = 'test-revision'
        path.write_text(json.dumps(spec))
        second = self.check(repaired)
        self.assertNotEqual(first['evaluation_id'], second['evaluation_id'])
        self.assertNotEqual(first['spec_sha256'], second['spec_sha256'])

    def test_unknown_exercise_hash_needs_review(self):
        altered = dict(CONTENT, title='Different task with reused identity')
        packed = canonical(altered)
        with self.store.db:
            self.store.db.execute('UPDATE exercises SET content_json=?, sha256=?', (packed, hashlib.sha256(packed.encode()).hexdigest()))
        self.assertEqual('NEEDS_REVIEW', self.check(self.run_code(GOOD))['outcome'])

    def test_migration_retains_prior_execution_evidence(self):
        failed, repaired = self.pair()
        before = self.store.attempt(repaired)
        events = self.store.events()
        self.store.db.executescript('DROP TABLE evaluations; DELETE FROM schema_version WHERE version=3;')
        self.store.close()
        self.store = Store(self.root / 'var/gurukul.sqlite3')
        self.assertEqual(before, self.store.attempt(repaired))
        self.assertEqual(events, self.store.events())
        self.assertEqual('CHECKS_PASS', self.check(repaired, failed)['outcome'])

    def test_cli_check_uses_saved_evidence_in_separate_process(self):
        failed, repaired = self.pair()
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
        process = subprocess.run([sys.executable, '-m', 'gurukul', '--root', str(self.root),
                                  'check', repaired, '--failed-attempt', failed],
                                 env=env, capture_output=True, text=True, check=True)
        self.assertEqual('CHECKS_PASS', json.loads(process.stdout)['outcome'])

    def test_labels_and_literal_print_formatting_are_supported(self):
        data = analyse('x=-3\nprint("value",x,sep=":",end="!")\n')
        self.assertEqual('value:-3!', data['stdout'])

    def test_saved_output_must_match_independent_prediction(self):
        from gurukul.runner import execute
        def wrong_capture(*args):
            captured = execute(*args)
            captured['stdout'] = b'wrong captured output\n'
            return captured
        with patch('gurukul.submissions.execute', side_effect=wrong_capture):
            repaired = self.run_code(GOOD)
        result = self.check(repaired)
        self.assertEqual('FAIL', next(c for c in result['checks'] if c['id']=='output_matches')['status'])

    def test_evaluations_cannot_be_updated_or_deleted(self):
        self.check(self.run_code(GOOD))
        for sql in ('DELETE FROM evaluations', "UPDATE evaluations SET result_json='{}'"):
            with self.assertRaises(sqlite3.IntegrityError):
                self.store.db.execute(sql)
            self.store.db.rollback()


if __name__ == '__main__':
    unittest.main()
