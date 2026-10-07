import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
from gurukul.runner import execute
from gurukul.store import Store
from gurukul.submissions import submit, inspect

ROOT = Path(__file__).resolve().parents[1]
CONTENT = json.loads((ROOT / 'content/c0_b01/d01.json').read_text())


@unittest.skipUnless(os.name == 'posix', 'POSIX runner only')
class RunnerTests(unittest.TestCase):
    def test_success_and_program_failure(self):
        ok = execute(b'print(6 * 7)\n')
        self.assertEqual(('completed', 0, b'42\n'), (ok['status'], ok['exit_code'], ok['stdout']))
        bad = execute(b'print(undefined_name)\n')
        self.assertEqual('program_error', bad['status'])
        self.assertNotEqual(0, bad['exit_code'])
        self.assertIn(b'NameError', bad['stderr'])

    def test_timeout(self):
        started = time.monotonic()
        result = execute(b'while True: pass\n', timeout=0.15)
        self.assertEqual('timed_out', result['status'])
        self.assertLess(time.monotonic() - started, 3)

    def test_output_limit_both_streams(self):
        result = execute(b'import os\nwhile True:\n os.write(1,b"x"*4096)\n os.write(2,b"y"*4096)\n', output_limit=10000)
        self.assertEqual('output_limited', result['status'])
        self.assertEqual(10000, len(result['stdout']) + len(result['stderr']))

    def test_closed_pipes_do_not_bypass_timeout(self):
        result = execute(b'import os,time\nos.close(1)\nos.close(2)\ntime.sleep(10)\n', timeout=0.15)
        self.assertEqual('timed_out', result['status'])

    def test_descendant_holding_pipes_is_killed(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'escaped'
            child = 'import time; from pathlib import Path; time.sleep(0.7); Path(' + repr(str(marker)) + ').touch()'
            code = 'import subprocess,sys\nsubprocess.Popen([sys.executable,"-c",' + repr(child) + '])\n'
            result = execute(code.encode(), timeout=0.2)
            self.assertEqual('timed_out', result['status'])
            time.sleep(0.8)
            self.assertFalse(marker.exists())

    def test_credentials_not_inherited_and_no_interactive_stdin(self):
        with patch.dict(os.environ, {'GURUKUL_TEST_SECRET': 'test-only'}):
            result = execute(b'import os,sys\nprint(os.getenv("GURUKUL_TEST_SECRET"))\nprint(repr(sys.stdin.read()))\n')
        self.assertEqual(b"None\n''\n", result['stdout'])

    def test_spawn_failure_is_infrastructure_failure(self):
        with patch('gurukul.runner.subprocess.Popen', side_effect=OSError('synthetic spawn failure')):
            result = execute(b'print(1)')
        self.assertEqual('runner_error', result['status'])
        self.assertIsNone(result['exit_code'])

    def test_invalid_limits(self):
        for limit in (float('nan'), float('inf'), 0, -1, 61):
            with self.assertRaises(ValueError):
                execute(b'', timeout=limit)


@unittest.skipUnless(os.name == 'posix', 'POSIX runner only')
class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / 'var/gurukul.sqlite3')
        self.store.start(CONTENT)
        self.source = self.root / 'learner.py'

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_three_results_survive_restart_and_original_edit(self):
        attempts = []
        for code, status in [(b'print(42)\n', 'completed'), (b'print(missing)\n', 'program_error'), (b'while True: pass\n', 'timed_out')]:
            self.source.write_bytes(code)
            result = submit(self.store, self.source, timeout=0.2)
            self.assertEqual(status, result['status'])
            self.assertEqual(hashlib.sha256(code).hexdigest(), result['source_sha256'])
            attempts.append(result)
        self.source.write_text('changed after submission')
        self.store.close()
        self.store = Store(self.root / 'var/gurukul.sqlite3')
        for result in attempts:
            self.assertEqual(result, inspect(self.store, result['id']))
        self.assertEqual(7, len(self.store.events()))
        self.assertEqual('teaching', self.store.resume()['session']['phase'])

    def test_output_corruption_refused(self):
        self.source.write_text('print(42)')
        result = submit(self.store, self.source)
        file = self.root / 'var/evidence' / result['id'] / 'stdout.bin'
        file.chmod(0o600)
        file.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'output integrity'):
            inspect(self.store, result['id'])

    def test_result_event_failure_keeps_pending_attempt(self):
        self.source.write_text('print(42)')
        self.store.db.execute("CREATE TRIGGER fail_finished BEFORE INSERT ON events WHEN NEW.event_type='execution.finished' BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            submit(self.store, self.source)
        row = self.store.db.execute('SELECT id FROM attempts').fetchone()
        self.assertEqual('pending_or_interrupted', inspect(self.store, row['id'])['status'])
        self.assertEqual(0, self.store.db.execute('SELECT count(*) FROM executions').fetchone()[0])
        self.assertEqual(2, len(self.store.events()))

    def test_v1_migration_retains_session_and_events(self):
        before = self.store.resume()
        events = self.store.events()
        self.store.db.executescript('DROP TABLE executions; DROP TABLE attempts; DELETE FROM schema_version WHERE version=2;')
        self.store.close()
        self.store = Store(self.root / 'var/gurukul.sqlite3')
        self.assertEqual(before, self.store.resume())
        self.assertEqual(events, self.store.events())
        self.assertEqual([1, 2, 3], [r[0] for r in self.store.db.execute('SELECT version FROM schema_version ORDER BY version')])


if __name__ == '__main__':
    unittest.main()
