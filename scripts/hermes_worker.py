#!/usr/bin/env python3
"""Copied into a disposable sandbox; never opens the Gurukul ledger to persist."""
import errno
import hashlib
import http.client
import inspect
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

MARKER = 'GURUKUL_LIVE_JSON='


def denied(operation):
    try:
        operation()
    except OSError as exc:
        return 'DENIED' if exc.errno in (errno.EACCES, errno.EPERM) else 'ERROR'
    return 'ALLOWED'


def open_only(path, flags):
    fd = os.open(path, flags)
    os.close(fd)


def connect(address):
    with socket.socket() as connection:
        connection.settimeout(1)
        connection.connect(address)


def boundary(config):
    def bind():
        with socket.socket() as connection:
            connection.bind(('127.0.0.1', 0))
    return {
        'ledger_read': denied(lambda: open_only(config['ledger'], os.O_RDONLY)),
        'ledger_write': denied(lambda: open_only(config['ledger'], os.O_WRONLY)),
        'ledger_create': denied(lambda: open_only(config['canary'], os.O_WRONLY | os.O_CREAT | os.O_EXCL)),
        'credential_read': denied(lambda: open_only(config['credential_path'], os.O_RDONLY)),
        'shell': denied(lambda: subprocess.run(['/bin/sh', '-c', 'exit 0'], check=True)),
        'other_local_network': denied(lambda: connect(('127.0.0.1', config['denied_port']))),
        'external_network': denied(lambda: connect(('192.0.2.1', 443))),
        'network_listen': denied(bind),
    }


def surface(agent, config):
    state = {'tools': agent.tools, 'valid_tool_names': sorted(agent.valid_tool_names),
             'context_engine_tools': sorted(getattr(agent, '_context_engine_tool_names', [])),
             'fallback_count': len(agent._fallback_chain), 'provider': agent.provider,
             'model': agent.model, 'api_mode': agent.api_mode, 'base_url': agent.base_url,
             'memory_enabled': agent._memory_enabled,
             'user_profile_enabled': agent._user_profile_enabled}
    if (state['tools'] or state['valid_tool_names'] or state['context_engine_tools'] or
            state['fallback_count'] or state['memory_enabled'] or state['user_profile_enabled'] or
            state['model'] != config['model'] or state['provider'] != 'openai' or
            state['api_mode'] != 'chat_completions' or state['base_url'] != config['base_url']):
        raise RuntimeError('Agent surface or routing differs from allowed contract')
    return state


def relay_request(config, method, path):
    conn = http.client.HTTPConnection('127.0.0.1', config['relay_port'], timeout=5)
    try:
        conn.request(method, path, headers={'Authorization': 'Bearer ' + config['relay_token']})
        response = conn.getresponse()
        if response.status != 200:
            raise RuntimeError('Local relay unavailable')
        return json.loads(response.read())
    finally:
        conn.close()


def main():
    config = json.load(sys.stdin)
    report = {'status': 'BLOCKED', 'live_turn': False, 'tool_dispatch_attempts': 0,
              'revision': config['revision'], 'run_path': []}
    agent = None
    try:
        if sys.prefix == sys.base_prefix:
            raise RuntimeError('Dependency venv identity lost')
        report['boundary_before'] = boundary(config)
        if set(report['boundary_before'].values()) != {'DENIED'}:
            raise RuntimeError('Worker boundary failed before import')
        relay_request(config, 'GET', '/health')
        report['relay_reachable'] = True
        import run_agent
        from model_tools import get_tool_definitions
        source = Path(config['source']).resolve()
        if Path(run_agent.__file__).resolve() != source / 'run_agent.py':
            raise RuntimeError('Wrong runtime imported')
        report.update(imported_from=str(run_agent.__file__), python=sys.version.split()[0],
                      imported_sha256=hashlib.sha256(Path(run_agent.__file__).read_bytes()).hexdigest())
        if get_tool_definitions(enabled_toolsets=[], quiet_mode=True):
            raise RuntimeError('Import exposed tools')
        agent = run_agent.AIAgent(
            provider='openai', model=config['model'], base_url=config['base_url'],
            api_key=config['relay_token'], api_mode='chat_completions',
            enabled_toolsets=[], quiet_mode=True, skip_context_files=True,
            skip_memory=True, skip_background_review=True, load_soul_identity=False,
            save_trajectories=False, checkpoints_enabled=False, fallback_model=None,
            credential_pool=None, max_iterations=1, max_tokens=config['max_output_tokens'],
            reasoning_config={'enabled': False, 'effort': 'none'},
            request_overrides={'store': False, 'response_format': {'type': 'json_object'},
                               'reasoning_effort': 'none'},
            cwd=str(Path.cwd()), run_budget_seconds=90,
        )
        report['surface_before'] = surface(agent, config)
        def forbid_tools(*args, **kwargs):
            report['tool_dispatch_attempts'] += 1
            raise RuntimeError('Gurukul forbids all tool dispatch')
        agent._execute_tool_calls = forbid_tools
        method = agent.run_conversation
        method_path = Path(inspect.getsourcefile(method)).resolve()
        if method_path != source / 'agent' / 'turn_facade.py':
            raise RuntimeError('run_conversation was replaced')
        def trace(frame, event, arg):
            if event == 'call' and frame.f_code.co_name == 'run_conversation':
                filename = frame.f_code.co_filename
                if filename in (str(method_path), str(source / 'agent' / 'conversation_loop.py')):
                    report['run_path'].append(filename)
        relay_request(config, 'POST', '/ready')
        sys.setprofile(trace)
        try:
            result = method(user_message=config['prompt'], system_message=config['system_prompt'],
                            conversation_history=[], task_id=config['call_id'])
        finally:
            sys.setprofile(None)
        report['surface_after'] = surface(agent, config)
        report['boundary_after'] = boundary(config)
        report['live_turn'] = True
        report['result_flags'] = {k: result.get(k) for k in ('completed', 'partial', 'error', 'api_calls')}
        report['final_response'] = result.get('final_response')
        if (set(report['boundary_after'].values()) != {'DENIED'} or report['tool_dispatch_attempts'] or
                len(set(report['run_path'])) != 2 or result.get('error') or result.get('partial') or
                result.get('completed') is not True or not report['final_response']):
            raise RuntimeError('Turn or post-turn checks failed')
        report['status'] = 'PASS'
    except (Exception, SystemExit) as exc:
        # No provider key exists in this process. Do not expose arbitrary runtime internals.
        report.update(status='BLOCKED', error_type=type(exc).__name__, error=str(exc)[:1000])
    finally:
        if agent is not None:
            try:
                agent.close()
            except Exception:
                report['cleanup_warning'] = True
    print(MARKER + json.dumps(report), flush=True)
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
