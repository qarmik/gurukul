"""Snapshot first, execute once, retain result without granting capability."""
import hashlib
from pathlib import Path
from uuid import UUID, uuid4
from .runner import execute, validate_limits, MAX_SOURCE_BYTES
from .store import now


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save_new(path, data):
    with path.open('xb') as handle:
        handle.write(data)
    path.chmod(0o400)


def submit(store, source_path, timeout=5.0, output_limit=65536):
    validate_limits(timeout, output_limit)
    session = store.resume()['session']
    source_path = Path(source_path)
    if source_path.suffix != '.py' or not source_path.is_file():
        raise ValueError('Submit a regular .py file.')
    with source_path.open('rb') as handle:
        source = handle.read(MAX_SOURCE_BYTES + 1)
    if len(source) > MAX_SOURCE_BYTES:
        raise ValueError('Submission exceeds 256 KiB.')
    attempt_id = str(uuid4())
    folder = store.state_dir / 'evidence' / attempt_id
    folder.mkdir(parents=True)
    save_new(folder / 'submission.py', source)
    store.record_submission(attempt_id, session['id'], digest(source), now())
    # Execute the retained bytes, not the mutable original file.
    snapshot = (folder / 'submission.py').read_bytes()
    if digest(snapshot) != digest(source):
        raise ValueError('Submission snapshot integrity failure; execution refused.')
    result = execute(snapshot, timeout, output_limit)
    save_new(folder / 'stdout.bin', result.pop('stdout'))
    save_new(folder / 'stderr.bin', result.pop('stderr'))
    result['stdout_sha256'] = digest((folder / 'stdout.bin').read_bytes())
    result['stderr_sha256'] = digest((folder / 'stderr.bin').read_bytes())
    store.record_execution(attempt_id, result, now())
    return inspect(store, attempt_id)


def inspect(store, attempt_id):
    # Validate before resolving a filesystem path supplied on the CLI.
    if str(UUID(attempt_id)) != attempt_id:
        raise ValueError('Invalid attempt ID.')
    result = store.attempt(attempt_id)
    folder = store.state_dir / 'evidence' / attempt_id
    for filename, expected in [('submission.py', result['source_sha256'])]:
        if digest((folder / filename).read_bytes()) != expected:
            raise ValueError('Submission snapshot integrity failure.')
    if result['execution'] is not None:
        for name in ('stdout', 'stderr'):
            data = (folder / (name + '.bin')).read_bytes()
            if digest(data) != result['execution'][name + '_sha256']:
                raise ValueError('Execution output integrity failure.')
            result['execution'][name] = data.decode('utf-8', errors='replace')
    return result
