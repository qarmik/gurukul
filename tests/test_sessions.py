import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from gurukul.store import Store

ROOT = Path(__file__).resolve().parents[1]
CONTENT = json.loads((ROOT / 'content/c0_b01/d01.json').read_text())


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.store = Store(self.path / 'var/gurukul.sqlite3')

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_resume_without_session(self):
        with self.assertRaisesRegex(ValueError, 'No active'):
            self.store.resume()

    def test_restart_and_idempotent_start(self):
        first = self.store.start(CONTENT)
        self.store.close()
        self.store = Store(self.path / 'var/gurukul.sqlite3')
        self.assertEqual(first, self.store.start(CONTENT))
        self.assertEqual(first, self.store.resume()['session'])
        self.assertEqual(1, len(self.store.events()))

    def test_changed_content_rejected(self):
        self.store.start(CONTENT)
        altered = dict(CONTENT, title='changed')
        with self.assertRaisesRegex(ValueError, 'version increment'):
            self.store.start(altered)
        self.assertEqual(CONTENT, self.store.resume()['exercise'])

    def test_events_append_only(self):
        self.store.start(CONTENT)
        for statement in ('DELETE FROM events', "UPDATE events SET source='other'"):
            with self.assertRaises(sqlite3.IntegrityError):
                self.store.db.execute(statement)
            self.store.db.rollback()

    def test_resume_rejects_corrupted_exercise(self):
        self.store.start(CONTENT)
        original_events = self.store.events()
        altered = dict(CONTENT, title='Corrupted exercise')
        self.store.db.execute('UPDATE exercises SET content_json=?', (json.dumps(altered),))
        self.store.db.commit()
        self.store.close()
        self.store = Store(self.path / 'var/gurukul.sqlite3')
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            self.store.resume()
        self.assertEqual(original_events, self.store.events())

    def test_source_references_resolve_in_manifest(self):
        manifest = json.loads((ROOT / 'content/sources.json').read_text())
        self.assertEqual(manifest['version'], CONTENT['source']['manifest_version'])
        for ref in CONTENT['source']['references']:
            source = manifest['sources'][ref['source_id']]
            self.assertIn('title', source)
            self.assertRegex(source['sha256'], r'^[0-9a-f]{64}$')

    def test_event_failure_rolls_back_session_and_content(self):
        self.store.db.execute("CREATE TRIGGER fail_event BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT, 'forced failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.start(CONTENT)
        self.assertEqual(0, self.store.db.execute('SELECT count(*) FROM sessions').fetchone()[0])
        self.assertEqual(0, self.store.db.execute('SELECT count(*) FROM exercises').fetchone()[0])

    def test_separate_process_resume_uses_pinned_content(self):
        folder = self.path / 'content/c0_b01'
        folder.mkdir(parents=True)
        source = folder / 'd01.json'
        source.write_text(json.dumps(CONTENT))
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
        def invoke(command):
            run = subprocess.run([sys.executable, '-m', 'gurukul', '--root', str(self.path), command], env=env, capture_output=True, text=True, check=True)
            return json.loads(run.stdout)
        first = invoke('start')
        source.unlink()
        self.assertEqual(first, invoke('resume'))
        self.assertEqual('not_integrated', first['hermes_status'])


if __name__ == '__main__':
    unittest.main()
