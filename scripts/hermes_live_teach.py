#!/usr/bin/env python3
"""Interactive, Mac-isolated Hermes D01 teaching. No substitute model calls."""
import argparse
import copy
import shlex
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
from gurukul.intent_admission import runtime_notice
from gurukul.teaching_output import evaluate_output
from gurukul.terminal_text import normalize_input
from gurukul.pedagogy import orientation, turn_context, build_prompt, validate_response
from gurukul.hermes_continuation import load_previous, continuation_input
from gurukul.hermes_teaching import SYSTEM_PROMPT, record_result, source_input, teaching_response
from gurukul.store import Store, canonical, now
from gurukul.anthropic_supervisor import configured_provider
from gurukul.maharishi import carried_state, snapshot, supervise, control_context, apply_control
from gurukul.response_contract import ResponseContractError
from hermes_import_probe import PIN, installed_runtime

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


def run(args):
    if sys.platform != 'darwin':
        raise ValueError('Live isolation acceptance must run on the Mac')
    import fcntl
    os.umask(0o077)
    state = PROJECT / 'var/hermes-live'
    state.mkdir(parents=True, exist_ok=True)
    # Serialise adapter turns so a second worker cannot change the shared ledger
    # while the first worker is proving its denial boundary.
    with (state / 'turn.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another teaching turn is active; wait for it to finish')
        return conversation_loop(args, run_locked)


class TeachingExit(Exception):
    """User ended the answer prompt without submitting a turn."""


def read_answer(previous):
    while True:
        try:
            answer = input('Gurukul — your answer or question (/quit to finish): ')
        except EOFError:
            raise TeachingExit()
        try:
            if normalize_input(answer)[0].strip() == '/quit':
                raise TeachingExit()
            return continuation_input(previous, answer)
        except ValueError as exc:
            print(str(exc) + '; please try again. No request sent.')


def conversation_loop(args, turn):
    current = copy.copy(args)
    latest = args.continue_call
    current.displayed_call = None
    print('Gurukul teaching session. Answer at the Gurukul prompt; /quit or Control-C ends it.')
    if getattr(args,'maharishi',False):
        print('Each message permits one Guru request and, when triggered, one supervisor request. No automatic retries.')
    else:
        print('Each submitted answer makes at most one paid request. No automatic retries.')
    try:
        while True:
            report = turn(current)
            if report['status'] != 'PASS' or not report.get('parent_ledger_record_verified'):
                print('Teaching stopped after a failed turn; no retry was made.')
                return 1
            latest = report['call_id']
            if args.once:
                return 0
            current.continue_call = latest
            current.source = None
            current.choose_source = False
            current.displayed_call = latest
    except TeachingExit:
        return 0
    except KeyboardInterrupt:
        print('Interrupted; no automatic retry. An in-flight request may already have been billed.')
        return 130
    except Exception as exc:
        print('STOP:', type(exc).__name__, str(exc)[:500])
        return 1
    finally:
        print('Gurukul session ended. You are returning to the shell.')
        if latest:
            command = ['python3', 'scripts/hermes_live_teach.py', '--runtime-root',
                       str(args.runtime_root), '--continue', latest]
            if getattr(args,'maharishi',False):command.append('--maharishi')
            print('Resume the last successful question with:\n' + shlex.join(command))


def display_teaching(report):
    """One complete explanation; secondary intent responses stay in audit evidence."""
    shown = report.get('display_teaching', report['teaching'])
    judgment = report.get('pedagogy_admission',{}).get('judgment', 'not_applicable')
    print('Conversational judgment: ' + judgment + '. Mastery: not assessed.')
    print(shown['explanation'])
    if shown.get('recovery_notice'):
        print(shown['recovery_notice'])
    if shown.get('miniature_example'):
        print('Separate miniature example:\n' + shown['miniature_example'])
    if shown['diagnostic_question']:
        print(shown['diagnostic_question'])
    else:
        print('Ask a follow-up, describe your confusion, or type /quit.')


def run_locked(args):
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
    supervisor = configured_provider(runtime) if getattr(args,'maharishi',False) else None
    local_source = args.source
    if args.choose_source:
        selected = subprocess.check_output(['/usr/bin/osascript', '-e',
            'POSIX path of (choose file with prompt "Select approved C0-B01_Values_and_Variables.html")'], text=True)
        local_source = Path(selected.strip())
    exercise = json.loads((PROJECT / 'content/c0_b01/d01.json').read_text())
    manifest = json.loads((PROJECT / 'content/sources.json').read_text())
    previous = None
    continuation = None
    if args.continue_call:
        previous = load_previous(PROJECT / 'var/hermes-live', args.continue_call, manifest, config, exercise)
        if previous.get('supervision_state') and supervisor is None:
            raise ValueError('This continuation has active supervision; resume with --maharishi')
        if getattr(args, 'displayed_call', None) != args.continue_call:
            print('Guru: ' + previous['teaching']['explanation'])
            if previous['teaching']['diagnostic_question']:
                print('Question: ' + previous['teaching']['diagnostic_question'])
            else:
                print('The learning question is saved. Ask a follow-up or continue when ready.')
        prompt, continuation = read_answer(previous)
        excerpt, provenance = previous['excerpt'], previous['provenance']
    else:
        prompt, excerpt, provenance = source_input(local_source, manifest, config, exercise)
    curriculum, curriculum_proof = orientation(PROJECT, exercise)
    context = turn_context(curriculum, previous,
                           continuation['learner_answer'] if continuation else '',
                           previous.get('history', []) if previous else [])
    prompt = build_prompt(context, excerpt)
    state = (PROJECT / 'var').resolve()
    state.mkdir(exist_ok=True)
    subprocess.run(['git', '-C', str(PROJECT), 'check-ignore', '-q', str(state / 'hermes-live/proof.json')], check=True)
    call_id = str(uuid4())
    evidence = state / 'hermes-live' / call_id
    evidence.mkdir(parents=True)
    ledger = previous['ledger'] if previous else evidence / 'acceptance.sqlite3'
    canary = evidence / 'worker-must-not-create'
    store = Store(ledger)
    if previous:
        session = store.resume()['session']
        if session['id'] != previous['session_id'] or session['phase'] not in ('teaching', 'remediation'):
            store.close()
            raise ValueError('Teaching session changed; continuation refused')
    else:
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
              'curriculum_provenance': curriculum_proof,
              'turn_context': context, 'epistemic_status': 'Model teaching judgments are provisional, not mastery evidence',
              'source_scope': 'Approved D01 HTML; book pages are not ingested by this test',
              'model_policy_version': policy['policy_version'], 'escalation_authority': 'gurukul'}
    if previous:
        report.update(root_call_id=previous['root_call_id'], continuation=continuation,
                      scope='live_teaching_continuation_only')
    (evidence / 'approved-excerpt.txt').write_text(excerpt)
    supervisor_state = carried_state(previous, context['C_turn']['learner_message']) if supervisor else None
    supervisor_audit = None
    original_context = context
    try:
        if supervisor:
            view=snapshot(context,supervisor_state)
            supervisor_state,supervisor_audit=supervise(view,supervisor_state,supervisor,store,session['id'],call_id,supervisor.config['max_requests_per_session'])
            supervisor_audit.update(stage='before_guru',snapshot=view)
            context=control_context(context,supervisor_state)
            prompt=build_prompt(context,excerpt)
            report.update(supervision=supervisor_audit,turn_context=context)
            baseline=hashlib.sha256(ledger.read_bytes()).hexdigest()

        with tempfile.TemporaryDirectory(prefix='teaching-worker-', dir=runtime) as tmp, \
             socket.socket() as denied_listener, Relay(config, key_path, prompt) as relay:
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
            shutil.copyfile(PROJECT / 'scripts/hermes_worker.py', script)
            profile = sandbox_profile(work, source, python, venv, base, paths, state, relay.port, Path.home().resolve())
            if supervisor:
                profile += '\n(deny file-read* file-write* (literal '+json.dumps(str(supervisor.key_path))+'))'
            (evidence / 'sandbox.sb').write_text(profile)
            child_config = dict(config, source=str(source), revision=PIN, ledger=str(ledger),
                                canary=str(canary), credential_path=str(key_path), denied_port=denied_port,
                                relay_port=relay.port, relay_token=relay.token, base_url=base_url,
                                call_id=call_id, prompt=prompt, system_prompt=SYSTEM_PROMPT)
            if supervisor:child_config['supervisor_credential_path']=str(supervisor.key_path)
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
                teaching = json.loads(final)
                admission, display = evaluate_output(teaching, context)
                if supervisor:
                    if supervisor_audit['status']=='NOT_INVOKED' and supervisor_state['remaining_turns']==0:
                        view=snapshot(original_context,supervisor_state,teaching,admission)
                        supervisor_state,supervisor_audit=supervise(view,supervisor_state,supervisor,store,session['id'],call_id,supervisor.config['max_requests_per_session'])
                        supervisor_audit.update(stage='after_guru',snapshot=view)
                    admission,display,supervisor_state,compliance=apply_control(admission,display,supervisor_state,context)
                    supervisor_audit.update(compliance=compliance,resulting_evidence_yield=admission['answer_admitted'],
                                           state_after=supervisor_state,mastery_changed=False,curriculum_changed=False,security_changed=False)
                    report.update(supervision=supervisor_audit,supervision_state=supervisor_state)
                report.update(runtime_status='PASS', pedagogy_admission=admission, display_teaching=display)
                report.update(status='PASS', teaching=teaching, response_sha256=hashlib.sha256(final.encode()).hexdigest())
                (evidence / 'teaching-response.json').write_text(json.dumps(teaching, indent=2) + '\n')
            finally:
                report['provider_calls'] = relay.calls
                report['relay_rejections'] = relay.rejections
                report['blocked_startup_probes'] = relay.blocked_startup_probes
                if relay.response is not None:
                    (evidence / 'provider-response.json').write_text(json.dumps(relay.response, indent=2) + '\n')
    except (Exception, SystemExit, KeyboardInterrupt) as exc:
        report.update(status='BLOCKED', error_type=type(exc).__name__, error=str(exc)[:1000])
        if isinstance(exc, ResponseContractError):
            report['validation_diagnostics'] = exc.diagnostics
    finally:
        report['runtime_status'] = report['status']
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
    summary = {'runtime_status': report['status'],
                      'conversation_status': report.get('pedagogy_admission',{}).get('conversation_status'),
                      'conversational_judgment': report.get('pedagogy_admission',{}).get('judgment'),
                      'mastery_granted': False,
                      'pedagogy_admission': report.get('pedagogy_admission'), 'call_id': call_id, 'hermes_revision': PIN,
                      'root_call_id': report.get('root_call_id', call_id),
                      'parent_call_id': (report.get('continuation') or {}).get('parent_call_id'),
                      'curriculum_provenance': report.get('curriculum_provenance'),
                      'supervision': report.get('supervision'),
                      'model_pedagogy_proposal': report.get('teaching', {}).get('pedagogy'),
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
                      'provider_errors': [c.get('provider_error') for c in report.get('provider_calls', [])],
                      'request_parameters': [c.get('request_parameters') for c in report.get('provider_calls', [])],
                      'upstream_request_parameters': [c.get('upstream_request_parameters') for c in report.get('provider_calls', [])],
                      'parent_ledger_record_verified': report.get('parent_ledger_record_verified', False),
                      'error': report.get('error'), 'worker_error': report.get('worker', {}).get('error'),
                      'validation_diagnostics': report.get('validation_diagnostics'),
                      'relay_rejections': report.get('relay_rejections'),
                      'blocked_startup_probes': report.get('blocked_startup_probes'),
                      'evidence_directory': str(evidence)}
    if args.once or args.verbose or report['status'] != 'PASS':
        print(json.dumps(summary, indent=2))
    else:
        print(runtime_notice(report) + ' Call: ' + call_id)
        print('Evidence: ' + str(evidence))
    if report['status'] == 'PASS':
        display_teaching(report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true', help='Run one turn and exit (diagnostic mode)')
    parser.add_argument('--maharishi',action='store_true',help='Enable account-verified, trigger-driven Anthropic supervision')
    parser.add_argument('--verbose', action='store_true', help='Print full verification JSON after each turn')
    parser.add_argument('--runtime-root', type=Path, default=Path.home() / 'GurukulRuntime')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--continue', dest='continue_call', metavar='CALL_UUID',
                       help='Answer the saved question and continue a verified local teaching turn')
    group.add_argument('--source', type=Path, help='Approved local C0-B01 HTML file')
    group.add_argument('--choose-source', action='store_true', help='Choose the approved HTML with the Mac file picker')
    args = parser.parse_args()
    try:
        return run(args)
    except KeyboardInterrupt:
        print('Cancelled; no automatic retry.')
        return 130
    except (Exception, SystemExit) as exc:
        print('STOP:', type(exc).__name__, str(exc)[:500])
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
