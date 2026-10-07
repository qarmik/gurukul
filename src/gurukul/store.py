"""Single-writer authority with atomic session/event persistence."""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class Store:
    def __init__(self, path):
        self.state_dir = Path(path).resolve().parent
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
            INSERT OR IGNORE INTO schema_version VALUES(1);
            CREATE TABLE IF NOT EXISTS exercises(
                id TEXT, version INTEGER, sha256 TEXT NOT NULL,
                content_json TEXT NOT NULL, PRIMARY KEY(id, version));
            CREATE TABLE IF NOT EXISTS sessions(
                id TEXT PRIMARY KEY, exercise_id TEXT NOT NULL,
                exercise_version INTEGER NOT NULL, phase TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('active','closed')),
                created_at TEXT NOT NULL,
                FOREIGN KEY(exercise_id, exercise_version) REFERENCES exercises(id, version));
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_session
                ON sessions(status) WHERE status='active';
            CREATE TABLE IF NOT EXISTS events(
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL, event_type TEXT NOT NULL,
                schema_version INTEGER NOT NULL, occurred_at TEXT NOT NULL,
                recorded_at TEXT NOT NULL, source TEXT NOT NULL,
                subject_id TEXT NOT NULL, session_id TEXT,
                correlation_id TEXT NOT NULL, causation_id TEXT,
                idempotency_key TEXT UNIQUE NOT NULL,
                privacy_class TEXT NOT NULL, payload_json TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id));
            CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
                BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
                BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
        ''')
        self._migrate_execution()

    def _migrate_execution(self):
        # Schema versions are an applied-migration ledger; v1 records are retained.
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            if self.db.execute('SELECT 1 FROM schema_version WHERE version=2').fetchone():
                return
            self.db.execute('''CREATE TABLE attempts(
                id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
                source_sha256 TEXT NOT NULL, submitted_at TEXT NOT NULL)''')
            self.db.execute('''CREATE TABLE executions(
                attempt_id TEXT PRIMARY KEY REFERENCES attempts(id),
                result_json TEXT NOT NULL, finished_at TEXT NOT NULL)''')
            for table in ('attempts', 'executions'):
                for action in ('UPDATE', 'DELETE'):
                    self.db.execute(f'''CREATE TRIGGER {table}_no_{action.lower()}
                        BEFORE {action} ON {table}
                        BEGIN SELECT RAISE(ABORT, 'evidence is append-only'); END''')
            self.db.execute('INSERT INTO schema_version VALUES(2)')

    def _execution_event(self, kind, attempt_id, session_id, timestamp, payload):
        self.db.execute('''INSERT INTO events(event_id,event_type,schema_version,
            occurred_at,recorded_at,source,subject_id,session_id,correlation_id,
            causation_id,idempotency_key,privacy_class,payload_json)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (str(uuid4()), kind, 1, timestamp, now(), 'gurukul.runner', attempt_id,
             session_id, attempt_id, None, kind + ':' + attempt_id,
             'personal_learning', canonical(payload)))

    def record_submission(self, attempt_id, session_id, source_sha256, timestamp):
        with self.db:
            self.db.execute('INSERT INTO attempts VALUES(?,?,?,?)',
                            (attempt_id, session_id, source_sha256, timestamp))
            self._execution_event('execution.submitted', attempt_id, session_id,
                                  timestamp, {'source_sha256': source_sha256})

    def record_execution(self, attempt_id, result, timestamp):
        attempt = self.attempt(attempt_id)
        with self.db:
            self.db.execute('INSERT INTO executions VALUES(?,?,?)',
                            (attempt_id, canonical(result), timestamp))
            self._execution_event('execution.finished', attempt_id, attempt['session_id'],
                                  timestamp, result)

    def attempt(self, attempt_id):
        row = self.db.execute('SELECT * FROM attempts WHERE id=?', (attempt_id,)).fetchone()
        if row is None:
            raise ValueError('Unknown attempt ID.')
        result = dict(row)
        execution = self.db.execute('SELECT * FROM executions WHERE attempt_id=?', (attempt_id,)).fetchone()
        result['execution'] = json.loads(execution['result_json']) if execution else None
        result['status'] = result['execution']['status'] if execution else 'pending_or_interrupted'
        return result

    def close(self):
        self.db.close()

    def start(self, content):
        packed = canonical(content)
        digest = hashlib.sha256(packed.encode()).hexdigest()
        try:
            self.db.execute("BEGIN IMMEDIATE")
            active = self.db.execute("SELECT * FROM sessions WHERE status='active'").fetchone()
            if active:
                if (active['exercise_id'], active['exercise_version']) != (content['id'], content['version']):
                    raise ValueError('Another exercise is active; resume it first.')
            existing = self.db.execute(
                "SELECT sha256 FROM exercises WHERE id=? AND version=?",
                (content['id'], content['version'])).fetchone()
            if existing and existing['sha256'] != digest:
                raise ValueError('Exercise content changed without a version increment.')
            if active:
                self.db.commit()
                return dict(active)
            self.db.execute("INSERT OR IGNORE INTO exercises VALUES(?,?,?,?)",
                            (content['id'], content['version'], digest, packed))
            session_id, timestamp = str(uuid4()), now()
            self.db.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?)",
                            (session_id, content['id'], content['version'], 'teaching', 'active', timestamp))
            self.db.execute("INSERT INTO events(event_id,event_type,schema_version,occurred_at,recorded_at,source,subject_id,session_id,correlation_id,causation_id,idempotency_key,privacy_class,payload_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (str(uuid4()), 'session.started', 1, timestamp, timestamp,
                             'gurukul.runtime', content['id'], session_id, session_id, None,
                             'session.started:' + session_id, 'personal_learning',
                             canonical({'exercise_version': content['version'], 'content_sha256': digest, 'phase': 'teaching'})))
            self.db.commit()
            return self.resume()['session']
        except Exception:
            self.db.rollback()
            raise

    def resume(self):
        session = self.db.execute("SELECT * FROM sessions WHERE status='active'").fetchone()
        if not session:
            raise ValueError('No active session. Run start first.')
        exercise = self.db.execute("SELECT content_json, sha256 FROM exercises WHERE id=? AND version=?",
                                   (session['exercise_id'], session['exercise_version'])).fetchone()
        if exercise is None:
            raise ValueError('Stored exercise is missing; resume refused.')
        digest = hashlib.sha256(exercise['content_json'].encode('utf-8')).hexdigest()
        if digest != exercise['sha256']:
            raise ValueError('Stored exercise SHA-256 mismatch; resume refused.')
        return {'session': dict(session), 'exercise': json.loads(exercise['content_json']),
                'hermes_status': 'not_integrated',
                'next_action': 'Read approved local material. Live Hermes teaching is scheduled for GURU-004.'}

    def events(self):
        result = []
        for row in self.db.execute('SELECT * FROM events ORDER BY sequence'):
            item = dict(row)
            item['payload'] = json.loads(item.pop('payload_json'))
            result.append(item)
        return result
