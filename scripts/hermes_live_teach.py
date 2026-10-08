#!/usr/bin/env python3
"""One real, Mac-isolated Hermes D01 teaching turn. No substitute model calls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
from uuid import uuid4

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'src'))
from gurukul.hermes_relay import Relay, private_key
from gurukul.hermes_teaching import SYSTEM_PROMPT, record_result, source_input, teaching_response
from gurukul.store import Store, canonical, now
from hermes_import_probe import PIN, installed_runtime

MARKER = 'GURUKUL_LIVE_JSON='


def sandbox_profile(work, source, python, venv, base, paths, state, port, actual_home):
    q = lambda value: json.dumps(str(value))
    rules = ['(version 1)', '(allow default)', '(deny network*)',
             '(allow network-outbound (remote ip "127.0.0.1:' + str(port) + '"))',
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


def run(args):
    if sys.platform != 'darwin':
        raise ValueError('Live isolation acceptance must run on the Mac')
    os.umask(0o077)
    runtime = args.runtime_root.resolve()
    source = runtime / 'hermes-agent'
    if (source / '.env').exists():
        raise ValueError('Runtime source .env is not allowed; do not reuse a configured profile')
    config = json.loads((PROJECT / 'config/hermes-live.json').read_text())
    policy = json.loads((PROJECT / 'config/model-policy.json').read_text())
    if (config['provider'] != 'openai_direct' or config['provider'] != policy['base']['provider'] or
            config['model'] != policy['base']['requested_model_id'] or config['automatic_escalation'] or
            config['automatic_retry'] or type(config['max_output_tokens']) is not int or
            not 1 <= config['max_output_tokens'] <= 1024):
        raise ValueError('Live route differs from Gurukul policy or supported isolation contract')
    python, venv, base, paths = installed_runtime(runtime)
    key_path = runtime / 'credentials/openai-api-key'
    private_key(key_path)  # Validate locally; never print or forward this secret to Hermes.
    local_source = args.source
    if args.choose_source:
        selected = subprocess.check_output(['/usr/bin/osascript', '-e',
            'POSIX path of (choose file with prompt "Select approved C0-B01_Values_and_Variables.html")'], text=True)
        local_source = Path(selected.strip())
    exercise = json.loads((PROJECT / 'content/c0_b01/d01.json').read_text())
    manifest = json.loads((PROJECT / 'content/sources.json').read_text())
    prompt, excerpt, provenance = source_input(local_source, manifest, config, exercise)
    state = (PROJECT / 'var').resolve()
    state.mkdir(exist_ok=True)
    subprocess.run(['git', '-C', str(PROJECT), 'check-ignore', '-q', str(state / 'hermes-live/proof.json')], check=True)
    call_id = str(uuid4())
    evidence = state / 'hermes-live' / call_id
    evidence.mkdir(parents=True)
    ledger = evidence / 'acceptance.sqlite3'
    canary = evidence / 'worker-must-not-create'
    store = Store(ledger)
    session = store.start(exercise)
    # This is a dedicated integration session, never a learner assessment attempt.
    baseline = hashlib.sha256(ledger.read_bytes()).hexdigest()
    with ledger.open('r+b'):
        pass
    canary.write_bytes(b'baseline')
    canary.unlink()
    report = {'status': 'BLOCKED', 'call_id': call_id, 'started_at': now(),
              'scope': 'live_teaching_integration_only', 'hermes_revision': PIN,
              'gurukul_revision': subprocess.check_output(['git', '-C', str(PROJECT), 'rev-parse', 'HEAD'], text=True).strip(),
              'provenance': provenance, 'grants_mastery': False,
              'source_scope': 'Approved D01 HTML; book pages are not ingested by this test',
              'model_policy_version': policy['policy_version'], 'escalation_authority': 'gurukul'}
    (evidence / 'approved-excerpt.txt').write_text(excerpt)
    try:
        with tempfile.TemporaryDirectory(prefix='teaching-worker-', dir=runtime) as tmp, \
             socket.socket() as denied_listener, Relay(config, key_path, prompt) as relay:
            work = Path(tmp).resolve()
            home = work / 'home'
            home.mkdir()
            cwd = work / 'cwd'
            cwd.mkdir()
            base_url = 'http://127.0.0.1:' + str(relay.port) + '/v1'
            hermes_config = {'model': {'default': config['model'], 'provider': 'openai',
                                      'base_url': base_url, 'streaming': False, 'context_length': 32768},
                             'compression': {'enabled': False}, 'mcp_servers': {}}
            (home / 'config.yaml').write_text(json.dumps(hermes_config))  # JSON is valid YAML.
            denied_listener.bind(('127.0.0.1', 0))
            denied_listener.listen(4)
            denied_port = denied_listener.getsockname()[1]
            with socket.create_connection(('127.0.0.1', denied_port), timeout=2):
                pass
            subprocess.run(['/bin/sh', '-c', 'exit 0'], check=True)
            script = work / 'worker.py'
            shutil.copyfile(PROJECT / 'scripts/hermes_worker.py', script)
            profile = sandbox_profile(work, source, python, venv, base, paths, state, relay.port, Path.home().resolve())
            (evidence / 'sandbox.sb').write_text(profile)
            child_config = dict(config, source=str(source), revision=PIN, ledger=str(ledger),
                                canary=str(canary), credential_path=str(key_path), denied_port=denied_port,
                                relay_port=relay.port, relay_token=relay.token, base_url=base_url,
                                call_id=call_id, prompt=prompt, system_prompt=SYSTEM_PROMPT)
            env = {'HOME': str(home), 'HERMES_HOME': str(home),
                   'HERMES_RUNTIME_DIR': str(runtime / 'hermes-tools'),
                   'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'PYTHONNOUSERSITE': '1',
                   'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': os.pathsep.join(map(str, paths)),
                   'TMPDIR': str(work), 'LANG': 'en_US.UTF-8'}
            report['clean_worker'] = {'fresh_home': True, 'fresh_cwd': True, 'provider_key_in_worker': False,
                                      'personal_config_inherited': False, 'skip_memory': True}
            try:
                child = subprocess.run(['/usr/bin/sandbox-exec', '-p', profile, str(python),
                                        '-s', '-B', '-P', str(script)], input=json.dumps(child_config),
                                       cwd=cwd, env=env, capture_output=True, text=True, timeout=180)
                # The relay token is ephemeral; redact it too before saving diagnostics.
                stdout = child.stdout.replace(relay.token, '[relay-token]')
                stderr = child.stderr.replace(relay.token, '[relay-token]')
                (evidence / 'worker.stdout.txt').write_text(stdout[:2000000])
                (evidence / 'worker.stderr.txt').write_text(stderr[:2000000])
                payloads = [line[len(MARKER):] for line in stdout.splitlines() if line.startswith(MARKER)]
                if len(payloads) != 1:
                    raise ValueError('Worker did not produce exactly one report; inspect local worker.stderr.txt')
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
                teaching = teaching_response(final)
                report.update(status='PASS', teaching=teaching, response_sha256=hashlib.sha256(final.encode()).hexdigest())
                (evidence / 'teaching-response.json').write_text(json.dumps(teaching, indent=2) + '\n')
            finally:
                report['provider_calls'] = relay.calls
                report['relay_rejections'] = relay.rejections
                if relay.response is not None:
                    (evidence / 'provider-response.json').write_text(json.dumps(relay.response, indent=2) + '\n')
    except (Exception, SystemExit) as exc:
        report.update(status='BLOCKED', error_type=type(exc).__name__, error=str(exc)[:1000])
    finally:
        report['finished_at'] = now()
        try:
            record_result(store, call_id, session['id'], report)
            store.close()
            reopened = Store(ledger)
            events = reopened.events()
            reopened.close()
            if events[-1]['payload'] != json.loads(canonical(report)):
                raise ValueError('Ledger readback mismatch')
            report['parent_ledger_record_verified'] = True
        except Exception as exc:
            report.update(status='BLOCKED', ledger_error_type=type(exc).__name__)
        (evidence / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'call_id': call_id, 'hermes_revision': PIN,
                      'run_conversation_path': report.get('worker', {}).get('run_path'),
                      'boundary_before': report.get('worker', {}).get('boundary_before'),
                      'boundary_after': report.get('worker', {}).get('boundary_after'),
                      'tools_before': report.get('worker', {}).get('surface_before', {}).get('valid_tool_names'),
                      'tools_after': report.get('worker', {}).get('surface_after', {}).get('valid_tool_names'),
                      'source_sha256': provenance['source_sha256'],
                      'requested_model': config['model'],
                      'resolved_model': [c.get('resolved_model') for c in report.get('provider_calls', [])],
                      'provider_calls': len(report.get('provider_calls', [])),
                      'provider_http_status': [c.get('http_status') for c in report.get('provider_calls', [])],
                      'parent_ledger_record_verified': report.get('parent_ledger_record_verified', False),
                      'error': report.get('error'), 'worker_error': report.get('worker', {}).get('error'),
                      'relay_rejections': report.get('relay_rejections'),
                      'evidence_directory': str(evidence)}, indent=2))
    if report['status'] == 'PASS':
        print(report['teaching']['explanation'])
        print(report['teaching']['diagnostic_question'])
    return 0 if report['status'] == 'PASS' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, default=Path.home() / 'GurukulRuntime')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--source', type=Path, help='Approved local C0-B01 HTML file')
    group.add_argument('--choose-source', action='store_true', help='Choose the approved HTML with the Mac file picker')
    args = parser.parse_args()
    try:
        return run(args)
    except (Exception, SystemExit) as exc:
        print('STOP:', type(exc).__name__, str(exc)[:500])
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
