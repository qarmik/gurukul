#!/usr/bin/env python3
"""Explicit one-turn Ask Guru trial in a new disposable Mac workspace."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from threading import Lock
from uuid import uuid4
import webbrowser

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'src'))

from gurukul.hermes_relay import Relay, private_key
from gurukul.hermes_teaching import TeachingPipeline, TeachingTurnError, source_input
from gurukul.pedagogy import orientation
from gurukul.store import Store
from gurukul.workspace import Server
from hermes_import_probe import installed_runtime
from hermes_turn import run_worker

MODEL = 'gpt-6-luna'
OUTPUT_LIMIT = 1024


def checked_config(project):
    config = json.loads((project / 'config/hermes-live.json').read_text())
    policy = json.loads((project / 'config/model-policy.json').read_text())['base']
    if (config['provider'] != 'openai_direct' or config['provider'] != policy['provider'] or
            config['model'] != MODEL or config['model'] != policy['requested_model_id'] or
            type(config['max_output_tokens']) is not int or config['max_output_tokens'] != OUTPUT_LIMIT or
            config['automatic_retry'] is not False or config['automatic_escalation'] is not False):
        raise ValueError('Live Ask Guru requires the pinned OpenAI route and 1024-token limit, with retry and escalation disabled.')
    return config


class OneTurnTransport:
    """One worker attempt per launch; the relay independently caps upstream at one."""

    def __init__(self, runtime, installation, config, key_path, ledger):
        self.runtime, self.installation = runtime, installation
        self.config, self.key_path, self.ledger = config.copy(), key_path, ledger
        self.lock = Lock()
        self.used = False
        self.receipt = {'model': config['model'], 'output_token_limit': config['max_output_tokens'],
                        'provider_request_limit': 1, 'relay_reservations': 0,
                        'transport_status': 'NOT_DISPATCHED'}

    def __call__(self, *, system_prompt, prompt):
        with self.lock:
            if self.used:
                raise TeachingTurnError('This workspace’s one live Ask Guru turn has already been used.')
            self.used = True
        relay = None
        report = {}
        call_id = str(uuid4())
        self.receipt.update(call_id=call_id, transport_status='BLOCKED')
        try:
            baseline = hashlib.sha256(self.ledger.read_bytes()).hexdigest()
            relay = Relay(self.config, self.key_path, prompt, system_prompt=system_prompt)
            with relay:
                result = run_worker(
                    self.runtime, self.installation, self.config, self.key_path,
                    self.ledger.parent, self.ledger, self.ledger.parent / ('worker-canary-' + call_id),
                    relay, call_id, prompt, system_prompt, baseline, report)
            self.receipt['transport_status'] = 'HERMES_RESPONSE_VERIFIED'
            return result
        except Exception as exc:
            self.receipt['failure_type'] = type(exc).__name__
            raise TeachingTurnError('Guru could not answer. This trial will not retry.') from exc
        finally:
            calls = relay.calls if relay is not None else []
            self.receipt.update(
                relay_reservations=len(calls),
                upstream=[{k: call.get(k) for k in ('http_status', 'provider_request_id',
                                                    'resolved_model', 'outcome', 'upstream_request_parameters')}
                          for call in calls],
                relay_rejections=len(relay.rejections) if relay is not None else 0,
                worker_status=report.get('worker', {}).get('status'),
                ledger_unchanged_by_worker=report.get('ledger_unchanged_by_worker'))
            print('ASK_GURU_LIVE_RECEIPT=' + json.dumps(self.receipt), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--live-once', action='store_true', help='Opt in to at most one billed provider request.')
    mode.add_argument('--preflight', action='store_true', help='Check local setup without launching a worker or provider request.')
    parser.add_argument('--runtime-root', type=Path, default=Path.home() / 'GurukulRuntime')
    parser.add_argument('--source', type=Path, required=True, help='The approved local D01 HTML.')
    args = parser.parse_args()
    if sys.platform != 'darwin' or not os.access('/usr/bin/sandbox-exec', os.X_OK):
        parser.error('The live trial requires macOS and executable /usr/bin/sandbox-exec.')
    if sys.version_info < (3, 11):
        parser.error('The workspace host requires Python 3.11 or newer.')
    os.umask(0o077)
    try:
        runtime = args.runtime_root.resolve(strict=True)
        source = args.source.resolve(strict=True)
        hermes = runtime / 'hermes-agent'
        if not hermes.is_dir():
            raise ValueError('Missing dedicated Hermes checkout: ' + str(hermes))
        if os.path.lexists(hermes / '.env'):
            raise ValueError('Runtime checkout contains .env; use the dedicated clean install.')
        config = checked_config(PROJECT)
        key = runtime / 'credentials/openai-api-key'
        private_key(key)
        exercise = json.loads((PROJECT / 'content/c0_b01/d01.json').read_text())
        manifest = json.loads((PROJECT / 'content/sources.json').read_text())
        source_input(source, manifest, config, exercise)
        orientation(PROJECT, exercise)
        installation = installed_runtime(runtime)
        if args.preflight:
            print('ASK_GURU_PREFLIGHT=PASS (local setup only; zero provider requests)')
            return 0
        with tempfile.TemporaryDirectory(prefix='gurukul-ask-guru-live-') as tmp:
            root = Path(tmp).resolve()
            shutil.copytree(PROJECT / 'content', root / 'content')
            (root / 'config').mkdir()
            (root / 'config/hermes-live.json').write_text(json.dumps(config))
            ledger = root / 'var/gurukul.sqlite3'
            store = Store(ledger)
            try:
                session = store.start(exercise)
            finally:
                store.close()
            transport = OneTurnTransport(runtime, installation, config, key, ledger)
            with Server(root, session['id'], teaching_pipeline=TeachingPipeline(source, transport)) as server:
                server.daemon_threads = False  # Finish the bounded request before removing its fixture.
                print('Disposable workspace: one live Ask Guru request available. Press Control+C after the reply.', flush=True)
                if not webbrowser.open(server.origin + '/#' + server.token):
                    raise ValueError('Could not open the local browser; no live turn dispatched.')
                try:
                    server.serve_forever()
                except KeyboardInterrupt:
                    pass
            print('ASK_GURU_LIVE_FINAL=' + json.dumps(transport.receipt), flush=True)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print('STOP:', type(exc).__name__, str(exc)[:500], file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
