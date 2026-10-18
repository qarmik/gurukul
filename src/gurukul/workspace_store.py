"""Mutable drafts and narrow append-only workspace records; no gate authority."""
import json
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL
from .store import canonical, now
from .submissions import digest

KINDS={'workspace.operation_requested','workspace.operation_finished','evidence.review_recorded'}

def child_id(parent,label):return str(uuid5(NAMESPACE_URL,'gurukul-workspace:'+parent+':'+label))

def request_uuid(value):
    if not isinstance(value,str) or str(UUID(value))!=value:raise ValueError('Invalid request identity.')
    return value


def migrate(store):
    with store.db:
        store.db.execute('''CREATE TABLE IF NOT EXISTS workspace_drafts(
            session_id TEXT NOT NULL REFERENCES sessions(id), context TEXT NOT NULL,
            revision INTEGER NOT NULL, source TEXT NOT NULL, source_sha256 TEXT NOT NULL,
            updated_at TEXT NOT NULL, PRIMARY KEY(session_id,context))''')
        store.db.execute('INSERT OR IGNORE INTO schema_version VALUES(4)')


def event(store,kind,subject,session,payload,key,cause=None):
    if kind not in KINDS:raise ValueError('Unsupported workspace event.')
    old=store.db.execute('SELECT * FROM events WHERE idempotency_key=?',(key,)).fetchone()
    if old:
        if (old['event_type'],old['subject_id'],old['session_id'],old['payload_json'],old['causation_id'])!=(kind,subject,session,canonical(payload),cause):
            raise ValueError('Conflicting workspace request.')
        return old['event_id']
    eid=str(uuid4());stamp=now()
    store.db.execute('''INSERT INTO events(event_id,event_type,schema_version,occurred_at,recorded_at,
        source,subject_id,session_id,correlation_id,causation_id,idempotency_key,privacy_class,payload_json)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(eid,kind,1,stamp,stamp,'gurukul.workspace',subject,session,subject,cause,key,'personal_learning',canonical(payload)))
    return eid


def operation(store,identity):
    row=store.db.execute('SELECT * FROM events WHERE idempotency_key=?',('workspace.request:'+identity,)).fetchone()
    return dict(row,payload=json.loads(row['payload_json'])) if row else None


def result(store,identity):
    row=store.db.execute('SELECT payload_json FROM events WHERE idempotency_key=?',('workspace.result:'+identity,)).fetchone()
    return json.loads(row[0]) if row else None


def draft(store,sid,context):
    row=store.db.execute('SELECT * FROM workspace_drafts WHERE session_id=? AND context=?',(sid,context)).fetchone()
    if row:return dict(row)
    return dict(session_id=sid,context=context,revision=0,source='',source_sha256=digest(b''),updated_at=None)


def save(store,sid,context,revision,source):
    if type(revision) is not int or not isinstance(source,str) or len(source.encode())>262144:
        raise ValueError('Invalid draft revision or source size.')
    with store.db:
        store.db.execute('BEGIN IMMEDIATE')
        old=draft(store,sid,context)
        if old['revision']!=revision:raise ValueError('Stale draft: reload before editing. Newer work is preserved.')
        store.db.execute('INSERT OR REPLACE INTO workspace_drafts VALUES(?,?,?,?,?,?)',
            (sid,context,revision+1,source,digest(source.encode()),now()))
    return draft(store,sid,context)
