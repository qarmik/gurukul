"""Parent-owned canonical learner authority and shared assessment/teaching lock."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import fcntl


@contextmanager
def learning_lock(state_dir):
    path = Path(state_dir) / 'learning.lock'
    if path.is_symlink():
        raise ValueError('Learning lock must not be a symlink.')
    with path.open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another assessment or teaching operation holds learner authority.') from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


class TeachingLease:
    def __init__(self, path, session_id):
        self.path, self.session_id, self.active = Path(path), session_id, True
        self.exercise_sha256 = None

    def check(self):
        if not self.active or self.path.name != 'gurukul.sqlite3' or self.path.is_symlink() or not self.path.is_file():
            raise ValueError('Missing or expired canonical tutoring authority.')
        db = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True)
        db.row_factory = sqlite3.Row
        try:
            from .assessment import active_assessment
            session = db.execute('SELECT * FROM sessions WHERE id=?', (self.session_id,)).fetchone()
            if not session or session['status'] != 'active' or session['phase'] not in ('teaching','remediation') or active_assessment(db, self.session_id):
                raise ValueError('Tutoring denied: assessment open or canonical session unavailable.')
            exercise = db.execute('SELECT * FROM exercises WHERE id=? AND version=?', (session['exercise_id'], session['exercise_version'])).fetchone()
            from .submissions import digest
            if not exercise or digest(exercise['content_json'].encode()) != exercise['sha256']:
                raise ValueError('Canonical exercise integrity failure.')
            if self.exercise_sha256 and self.exercise_sha256 != exercise['sha256']:
                raise ValueError('Canonical exercise changed during tutoring.')
            self.exercise_sha256 = exercise['sha256']
        finally:
            db.close()
        return self

    def binding(self):
        self.check()
        return {'session_id': self.session_id, 'exercise_sha256': self.exercise_sha256}


@contextmanager
def canonical_teaching(path, session_id):
    path = Path(path).resolve() if not Path(path).is_symlink() else Path(path)
    if not session_id or path.is_symlink() or not path.is_file():
        raise ValueError('Explicit canonical learner session is required before tutoring.')
    with learning_lock(path.parent):
        lease = TeachingLease(path, session_id)
        try:
            lease.check()
            yield lease
        finally:
            lease.active = False


@contextmanager
def store_teaching(store, session_id):
    lease = getattr(store, 'teaching_authority', None)
    if lease is not None:
        if not isinstance(lease, TeachingLease):
            raise ValueError('Invalid canonical tutoring authority.')
        lease.check()
        row = store.db.execute('SELECT s.*,e.sha256 FROM sessions s JOIN exercises e ON e.id=s.exercise_id AND e.version=s.exercise_version WHERE s.id=?', (session_id,)).fetchone()
        if not row or row['status'] != 'active' or row['phase'] not in ('teaching','remediation') or row['sha256'] != lease.exercise_sha256:
            raise ValueError('Teaching integration differs from canonical learner authority.')
        yield lease
    else:
        if store.path.name != 'gurukul.sqlite3':
            raise ValueError('Missing canonical session binding for tutoring.')
        with canonical_teaching(store.path, session_id) as lease:
            store.teaching_authority = lease
            try:
                yield lease
            finally:
                del store.teaching_authority
