#!/usr/bin/env python3
"""Shared isolated Hermes turn runner for the terminal and workspace hosts."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile

from hermes_import_probe import PIN


MARKER = 'GURUKUL_LIVE_JSON='


def sandbox_profile(work, source, python, venv, base, paths, state, port, actual_home):
    q = lambda value: json.dumps(str(value))
    rules = ['(version 1)', '(allow default)', '(deny network*)',
             '(allow network-outbound (remote ip "localhost:' + str(port) + '"))',
             '(deny process-fork)', '(deny process-exec)',
             '(allow process-exec (literal ' + q(python) + '))',
             '(allow process-exec (literal ' + q(base) + '))',
             '(deny file-write*)', '(allow file-write* (subpath ' + q(work) + '))',
             '(allow file-write* (literal "/dev/null"))',
             '(deny file-read* (subpath ' + q(actual_home) + '))']
    for allowed in sorted(set(paths + [venv, base.parent.parent, source, work])):
        rules.append('(allow file-read* (subpath ' + q(allowed) + '))')
    rules.append('(deny file-read* file-write* (subpath ' + q(state) + '))')
    return '\n'.join(rules)


def run_worker(runtime, installation, config, key_path, state, ledger, canary,
               relay, call_id, prompt, system_prompt, baseline, report, *,
               evidence=None, supervisor_key=None):
    python, venv, base, paths = installation
    source = runtime / 'hermes-agent'
    with tempfile.TemporaryDirectory(prefix='teaching-worker-', dir=runtime) as tmp, socket.socket() as denied_listener:
        work = Path(tmp).resolve()
        home = work / 'home'
        home.mkdir()
        cwd = work / 'cwd'
        cwd.mkdir()
        base_url = 'http://127.0.0.1:' + str(relay.port) + '/v1'
        hermes_config = {'model': {'default': config['model'], 'provider': 'openai',
                                  'base_url': base_url, 'streaming': False, 'context_length': 64000},
                         'compression': {'enabled': False}, 'mcp_servers': {}}
        (home / 'config.yaml').write_text(json.dumps(hermes_config))  # JSON is valid YAML.
        denied_listener.bind(('127.0.0.1', 0))
        denied_listener.listen(4)
        denied_port = denied_listener.getsockname()[1]
        with socket.create_connection(('127.0.0.1', denied_port), timeout=2):
            pass
        subprocess.run(['/bin/sh', '-c', 'exit 0'], check=True)
        script = work / 'worker.py'
        shutil.copyfile(Path(__file__).with_name('hermes_worker.py'), script)
        profile = sandbox_profile(work, source, python, venv, base, paths, state, relay.port, Path.home().resolve())
        for credential in (key_path, supervisor_key):
            if credential is not None:
                profile += '\n(deny file-read* file-write* (literal '+json.dumps(str(credential))+'))'
        if evidence is not None:
            (evidence / 'sandbox.sb').write_text(profile)
        child_config = dict(config, source=str(source), revision=PIN, ledger=str(ledger),
                            canary=str(canary), credential_path=str(key_path), denied_port=denied_port,
                            relay_port=relay.port, relay_token=relay.token, base_url=base_url,
                            call_id=call_id, prompt=prompt, system_prompt=system_prompt)
        if supervisor_key is not None:child_config['supervisor_credential_path']=str(supervisor_key)
        env = {'HOME': str(home), 'HERMES_HOME': str(home),
               'HERMES_RUNTIME_DIR': str(runtime / 'hermes-tools'),
               'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'PYTHONNOUSERSITE': '1',
               'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': os.pathsep.join(map(str, paths)),
               'TMPDIR': str(work), 'LANG': 'en_US.UTF-8'}
        report['clean_worker'] = {'fresh_home': True, 'fresh_cwd': True, 'provider_key_in_worker': False,
                                  'personal_config_inherited': False, 'skip_memory': True}
        child = subprocess.run(['/usr/bin/sandbox-exec', '-p', profile, str(python),
                                '-s', '-B', '-P', str(script)], input=json.dumps(child_config),
                               cwd=cwd, env=env, capture_output=True, text=True, timeout=180)
        # The relay token is ephemeral; redact it too before saving diagnostics.
        stdout = child.stdout.replace(relay.token, '[relay-token]')
        stderr = child.stderr.replace(relay.token, '[relay-token]')
        if evidence is not None:
            (evidence / 'worker.stdout.txt').write_text(stdout[:2000000])
            (evidence / 'worker.stderr.txt').write_text(stderr[:2000000])
        payloads = [line[len(MARKER):] for line in stdout.splitlines() if line.startswith(MARKER)]
        if len(payloads) != 1:
            raise ValueError('Worker did not produce exactly one report')
        worker = json.loads(payloads[0])
        report['worker'] = worker
        expected_import_hash = hashlib.sha256((source / 'run_agent.py').read_bytes()).hexdigest()
        if worker.get('status') == 'PASS' and worker.get('imported_sha256') != expected_import_hash:
            raise ValueError('Imported runtime bytes differ from verified checkout')
        report['ledger_unchanged_by_worker'] = hashlib.sha256(ledger.read_bytes()).hexdigest() == baseline and not canary.exists()
        if child.returncode or worker['status'] != 'PASS' or not report['ledger_unchanged_by_worker']:
            raise ValueError('Worker boundary/runtime checks failed')
        if relay.rejections or len(relay.calls) != 1 or relay.response is None:
            raise ValueError('Relay did not verify exactly one policy-compliant provider response')
        wire = relay.response['choices'][0]
        final = worker['final_response']
        if wire.get('finish_reason') != 'stop' or wire['message'].get('content') != final:
            raise ValueError('Hermes final response differs from completed provider response')
        return final
