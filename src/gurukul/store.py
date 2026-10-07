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
