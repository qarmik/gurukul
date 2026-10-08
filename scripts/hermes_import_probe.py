#!/usr/bin/env python3
"""Mac-only, credential-free real Hermes import probe. Not live acceptance."""
import argparse
import errno
import inspect
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile

PIN = 'cc75e8f4021f7efab99158f57601be4d691a6da9'
MARKER = 'GURUKUL_PROBE_JSON='


def denied(operation):
    try:
        operation()
    except OSError as exc:
        return 'DENIED' if exc.errno in (errno.EACCES, errno.EPERM) else 'ERROR:' + str(exc.errno)
    return 'ALLOWED'


def worker(source, sentinel):
    sentinel = Path(sentinel)
    report = {'scope': 'import_probe_only', 'revision': PIN, 'live_turn': False}
    report['ledger_read'] = denied(sentinel.read_bytes)
    report['ledger_write'] = denied(lambda: sentinel.write_bytes(b'probe'))
    report['ledger_create'] = denied(lambda: sentinel.with_name('new-file').write_bytes(b'probe'))
    report['shell'] = denied(lambda: subprocess.run(['/bin/sh', '-c', 'exit 0'], check=True))
    def network_probe():
        with socket.socket() as connection:
            connection.bind(('127.0.0.1', 0))
    report['network'] = denied(network_probe)
    if not all(report[k] == 'DENIED' for k in ('ledger_read', 'ledger_write', 'ledger_create', 'shell', 'network')):
        report['status'] = 'FAIL'
        print(MARKER + json.dumps(report))
        return 1
    try:
        import run_agent
        from model_tools import get_tool_definitions
        imported = Path(run_agent.__file__).resolve()
        if imported != Path(source).resolve() / 'run_agent.py':
            raise RuntimeError('Wrong Hermes source imported')
        constructor = inspect.signature(run_agent.AIAgent)
        required = {'enabled_toolsets', 'skip_memory', 'skip_context_files',
                    'skip_background_review', 'quiet_mode', 'provider', 'model'}
        if not required <= set(constructor.parameters):
            raise RuntimeError('Pinned constructor interface differs from inspected contract')
        turn = inspect.signature(run_agent.AIAgent.run_conversation)
        if 'user_message' not in turn.parameters:
            raise RuntimeError('Missing run_conversation user_message interface')
        tools = get_tool_definitions(enabled_toolsets=[], quiet_mode=True)
        if tools:
            raise RuntimeError('Explicit empty tool selection exposed tools')
        report.update(imported_from=str(imported), python=sys.version.split()[0],
                      constructor_verified=True, run_conversation_interface_verified=True,
                      empty_selection_tool_count=len(tools), status='PASS')
    except Exception as exc:
        report.update(status='BLOCKED', error_type=type(exc).__name__, error=str(exc))
    print(MARKER + json.dumps(report))
    return 0 if report['status'] == 'PASS' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, default=Path.home() / 'GurukulRuntime')
    parser.add_argument('--worker', nargs=2, metavar=('SOURCE', 'SENTINEL'))
    args = parser.parse_args()
    if args.worker:
        return worker(*args.worker)
    if sys.platform != 'darwin':
        parser.error('This probe must run on the Mac; no Linux substitute.')
    project = Path(__file__).resolve().parents[1]
    state = project / 'var'
    runtime = args.runtime_root.resolve()
    source = runtime / 'hermes-agent'
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True).strip()
    if revision != PIN or dirty:
        raise SystemExit('STOP: Hermes revision mismatch or dirty checkout.')
    # Compose installed PM paths without activation, installation or app import.
    clean_env = {'HOME': str(Path.home()), 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin',
                 'HERMES_HOME': str(runtime / 'hermes-home'),
                 'HERMES_RUNTIME_DIR': str(runtime / 'hermes-tools')}
    compose = '''set -e
. "$1/scripts/_activation.sh"
composed="$(hermes_compose_env "$1" sh)"
hermes_apply_env "$composed"
python -c 'import json,os,sys; print("GURUKUL_ENV="+json.dumps({"python":sys.executable,"pythonpath":os.environ.get("PYTHONPATH", "")}))'
'''
    result = subprocess.run(['/bin/bash', '--noprofile', '--norc', '-c', compose, 'probe', str(source)],
                            cwd=source, env=clean_env, capture_output=True, text=True, timeout=60)
    lines = [line for line in result.stdout.splitlines() if line.startswith('GURUKUL_ENV=')]
    if result.returncode or len(lines) != 1:
        print(result.stderr[-6000:])
        raise SystemExit('STOP: installed PM environment could not be composed; no install attempted.')
    selected = json.loads(lines[0].split('=', 1)[1])
    python = Path(selected['python']).resolve()
    pythonpaths = [Path(p).resolve() for p in selected['pythonpath'].split(os.pathsep) if p]
    if not python.is_relative_to(runtime) or not pythonpaths or any(not p.is_relative_to(runtime) for p in pythonpaths):
        raise SystemExit('STOP: selected interpreter/dependency paths escape the dedicated runtime.')
    state.mkdir(exist_ok=True)
    reports = state / 'hermes-probes'
    reports.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='import-probe-', dir=runtime) as tmp, \
         tempfile.TemporaryDirectory(prefix='probe-ledger-', dir=state) as ledger_tmp:
        work = Path(tmp).resolve()
        home = work / 'home'
        home.mkdir()
        sentinel = Path(ledger_tmp).resolve() / 'sentinel'
        sentinel.write_bytes(b'probe')
        assert sentinel.read_bytes() == b'probe'
        baseline_new = sentinel.with_name('new-file')
        baseline_new.write_bytes(b'probe'); baseline_new.unlink()
        subprocess.run(['/bin/sh', '-c', 'exit 0'], check=True)
        with socket.socket() as baseline_socket:
            baseline_socket.bind(('127.0.0.1', 0))
        script = work / 'probe.py'
        shutil.copyfile(__file__, script)
        q = lambda p: json.dumps(str(p))
        profile = ['(version 1)', '(allow default)', '(deny network*)',
                   '(deny process-fork)', '(deny process-exec)',
                   '(allow process-exec (literal ' + q(python) + '))',
                   '(deny file-write*)', '(allow file-write* (subpath ' + q(work) + '))',
                   '(allow file-write* (literal "/dev/null"))',
                   '(deny file-read* (subpath ' + q(Path.home().resolve()) + '))']
        for allowed in set(pythonpaths + [python.parent.parent, source, work]):
            profile.append('(allow file-read* (subpath ' + q(allowed) + '))')
        profile.append('(deny file-read* file-write* (subpath ' + q(state.resolve()) + '))')
        child_env = {'HOME': str(Path.home()), 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin',
                     'HERMES_HOME': str(home), 'HERMES_RUNTIME_DIR': str(runtime / 'hermes-tools'),
                     'PYTHONPATH': os.pathsep.join(map(str, pythonpaths)), 'PYTHONNOUSERSITE': '1',
                     'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': str(work), 'LANG': 'en_US.UTF-8'}
        try:
            child = subprocess.run(['/usr/bin/sandbox-exec', '-p', '\n'.join(profile),
                                    str(python), '-s', '-B', '-P', str(script), '--worker', str(source), str(sentinel)],
                                   cwd=work, env=child_env, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            raise SystemExit('STOP: isolated import exceeded 120 seconds; live acceptance remains blocked.')
        (reports / 'latest-import.stdout.txt').write_text(child.stdout)
        (reports / 'latest-import.stderr.txt').write_text(child.stderr)
        payloads = [line[len(MARKER):] for line in child.stdout.splitlines() if line.startswith(MARKER)]
        if len(payloads) != 1:
            print(child.stderr[-6000:])
            raise SystemExit('STOP: no valid isolated report. Logs saved under var/hermes-probes/.')
        report = json.loads(payloads[0])
        report['sentinel_unchanged'] = sentinel.read_bytes() == b'probe' and not baseline_new.exists()
        if not report['sentinel_unchanged'] or child.returncode:
            report['status'] = 'BLOCKED'
        (reports / 'latest-import.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
        print('Proof saved under var/hermes-probes/. No model call was made.')
        return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
