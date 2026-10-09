"""Actual Mac profile compilation/denial check; no Hermes, key, or inference."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from hermes_live_teach import sandbox_profile
from hermes_import_probe import installed_runtime


@unittest.skipUnless(sys.platform == 'darwin', 'Requires actual macOS sandbox-exec')
class MacSandboxTests(unittest.TestCase):
    def test_compiled_profile_allows_only_relay_port_and_denies_ledger(self):
        runtime = (Path.home() / 'GurukulRuntime').resolve()
        python, venv, base, paths = installed_runtime(runtime)
        with tempfile.TemporaryDirectory(dir=runtime) as tmp, socket.socket() as relay, socket.socket() as other:
            root = Path(tmp).resolve()
            work, state = root / 'work', root / 'state'
            work.mkdir()
            state.mkdir()
            ledger = state / 'ledger'
            ledger.write_text('unchanged')
            for listener in (relay, other):
                listener.bind(('127.0.0.1', 0))
                listener.listen(4)
                with socket.create_connection(listener.getsockname(), timeout=2):
                    pass
            profile = sandbox_profile(work, runtime / 'hermes-agent', python, venv, base,
                                      paths, state, relay.getsockname()[1], Path.home().resolve())
            code = '''
import errno,json,os,socket,sys
def connect(port):
    with socket.socket() as s:
        s.settimeout(2)
        s.connect(('127.0.0.1',int(port)))
def opened(path,flags):
    fd=os.open(path,flags)
    os.close(fd)
def denied(operation):
    try: operation()
    except OSError as e: return e.errno in (errno.EACCES,errno.EPERM)
    return False
connect(sys.argv[1])
print(json.dumps({'relay':True, 'dependency_venv':sys.prefix != sys.base_prefix,
    'other_port_denied':denied(lambda:connect(sys.argv[2])),
    'ledger_read_denied':denied(lambda:opened(sys.argv[3],os.O_RDONLY)),
    'ledger_write_denied':denied(lambda:opened(sys.argv[3],os.O_WRONLY))}))
'''
            result = subprocess.run(['/usr/bin/sandbox-exec', '-p', profile, str(python),
                                     '-s', '-B', '-P', '-c', code, str(relay.getsockname()[1]),
                                     str(other.getsockname()[1]), str(ledger)],
                                    cwd=work, capture_output=True, text=True, timeout=15,
                                    env={'HOME': str(work), 'HERMES_HOME': str(work),
                                         'HERMES_RUNTIME_DIR': str(runtime / 'hermes-tools'),
                                         'PYTHONPATH': os.pathsep.join(map(str, paths)),
                                         'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1',
                                         'TMPDIR': str(work), 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin'})
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual({'relay': True, 'dependency_venv': True, 'other_port_denied': True,
                              'ledger_read_denied': True, 'ledger_write_denied': True},
                             json.loads(result.stdout))
            self.assertEqual('unchanged', ledger.read_text())
