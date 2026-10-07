"""Bounded POSIX execution of personally authored Python, not a sandbox."""
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import time

RUNNER_VERSION = '1'
MAX_SOURCE_BYTES = 262144


def validate_limits(timeout, output_limit):
    if not math.isfinite(timeout) or not 0 < timeout <= 60:
        raise ValueError('Timeout must be finite and between 0 and 60 seconds.')
    if not isinstance(output_limit, int) or not 1 <= output_limit <= 1048576:
        raise ValueError('Output limit must be between 1 and 1048576 bytes.')
    if os.name != 'posix':
        raise ValueError('This runner requires macOS or Linux (POSIX).')


def execute(source, timeout=5.0, output_limit=65536):
    validate_limits(timeout, output_limit)
    if len(source) > MAX_SOURCE_BYTES:
        raise ValueError('Submission exceeds 256 KiB.')
    start = time.monotonic()
    result = {'status': 'runner_error', 'exit_code': None, 'stdout': b'', 'stderr': b'',
              'runner_error': None, 'duration_seconds': 0.0, 'runner_version': RUNNER_VERSION,
              'python_version': sys.version, 'timeout_seconds': timeout,
              'output_limit_bytes': output_limit}
    proc = None
    streams = {'stdout': bytearray(), 'stderr': bytearray()}
    try:
        with tempfile.TemporaryDirectory(prefix='gurukul-run-') as work:
            script = Path(work) / 'submission.py'
            script.write_bytes(source)
            # No inherited credentials, PYTHONPATH, user site packages or shell.
            proc = subprocess.Popen([sys.executable, '-I', '-B', '-u', str(script)],
                                    cwd=work, env={'PATH': os.defpath, 'HOME': work,
                                                   'TMPDIR': work, 'LANG': 'C.UTF-8'},
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, start_new_session=True)
            try:
                with selectors.DefaultSelector() as selector:
                    for name in streams:
                        pipe = getattr(proc, name)
                        os.set_blocking(pipe.fileno(), False)
                        selector.register(pipe, selectors.EVENT_READ, name)
                    status = None
                    total = 0
                    while selector.get_map() or proc.poll() is None:
                        remaining = timeout - (time.monotonic() - start)
                        if remaining <= 0:
                            status = 'timed_out'
                            break
                        for key, _ in selector.select(min(remaining, 0.05)):
                            data = os.read(key.fileobj.fileno(), 8192)
                            if not data:
                                selector.unregister(key.fileobj)
                                continue
                            room = output_limit - total
                            kept = data[:room]
                            streams[key.data].extend(kept)
                            total += len(kept)
                            if len(data) > room:
                                status = 'output_limited'
                                break
                        if status:
                            break
                    result['status'] = status or ('completed' if proc.wait() == 0 else 'program_error')
            finally:
                # Kill the whole process group, including children retaining pipes.
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
                proc.stdout.close()
                proc.stderr.close()
            result['exit_code'] = proc.returncode
    except KeyboardInterrupt:
        result['status'] = 'interrupted'
    except OSError as exc:
        result['status'] = 'runner_error'
        result['runner_error'] = str(exc)
    finally:
        result['stdout'] = bytes(streams['stdout'])
        result['stderr'] = bytes(streams['stderr'])
        result['duration_seconds'] = time.monotonic() - start
    return result
