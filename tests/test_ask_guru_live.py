"""Workspace-to-relay integration with a simulated sandbox worker and fake upstream."""
import contextlib
import hashlib
import io
import json
import subprocess
import unittest
from unittest.mock import patch

import test_workspace as workspace_tests
from gurukul.hermes_relay import Relay
from gurukul.pedagogy import SYSTEM_PROMPT
from ask_guru_live import OneTurnTransport, checked_config
from hermes_turn import MARKER


class AskGuruRelayTests(unittest.TestCase):
    def setUp(self):
        self.fixture = workspace_tests.HTTPTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.fixture.enable_teaching_pipeline()
        root = self.fixture.root
        runtime = root / 'runtime'
        source = runtime / 'hermes-agent'
        source.mkdir(parents=True)
        (source / 'run_agent.py').write_text('# fake import identity')
        self.import_hash = hashlib.sha256((source / 'run_agent.py').read_bytes()).hexdigest()
        self.key = runtime / 'credentials/openai-api-key'  # Never create a provider credential.
        self.ledger = root / 'var/gurukul.sqlite3'
        self.transport = OneTurnTransport(runtime, (runtime/'python', runtime/'venv',
                                                    runtime/'base/bin/python', [source]),
                                          checked_config(workspace_tests.ROOT), self.key, self.ledger)
        self.fixture.server.teaching_pipeline.transport = self.transport
        self.request = self.fixture.request
        self.ask = lambda: self.request('/api/teach', 'POST', self.fixture.question)
        self.original_run = subprocess.run
        self.raw = json.dumps(self.fixture.proposal)
        self.output = io.StringIO()
        self.enterContext(contextlib.redirect_stdout(self.output))
        self.worker = self.enterContext(patch('hermes_turn.subprocess.run', side_effect=self.fake_worker))
        self.upstream = self.enterContext(patch.object(Relay, 'forward', autospec=True, side_effect=self.fake_upstream))

    def fake_worker(self, argv, *args, **kwargs):
        if argv[0] != '/usr/bin/sandbox-exec':
            return self.original_run(argv, *args, **kwargs)
        import http.client

        config = json.loads(kwargs['input'])
        profile = argv[2]
        self.assertIn('(deny network*)', profile)
        self.assertIn('(deny file-read* file-write* (literal ' + json.dumps(str(self.key)), profile)
        self.assertIn('(deny file-read* file-write* (subpath ' + json.dumps(str(self.ledger.parent)), profile)
        self.assertNotIn('OPENAI_API_KEY', kwargs['env'])
        self.assertNotIn('# untouched draft', config['prompt'])
        headers = {'Authorization': 'Bearer ' + config['relay_token']}
        conn = http.client.HTTPConnection('127.0.0.1', config['relay_port'], timeout=5)
        try:
            conn.request('POST', '/ready', headers=headers)
            ready = conn.getresponse()
            self.assertEqual(200, ready.status)
            ready.read()
            payload = {
                'model': config['model'], 'max_tokens': config['max_output_tokens'],
                'messages': [{'role': 'system', 'content': 'unapproved worker-added text'},
                             {'role': 'user', 'content': config['prompt']}],
                'prompt_cache_key': 'unapproved worker metadata',
            }
            conn.request('POST', '/v1/chat/completions', json.dumps(payload), headers)
            response = conn.getresponse()
            data = json.loads(response.read())
        finally:
            conn.close()
        ok = response.status == 200
        report = {'status': 'PASS' if ok else 'BLOCKED', 'imported_sha256': self.import_hash,
                  'final_response': data['choices'][0]['message']['content'] if ok else None}
        return subprocess.CompletedProcess(argv, 0 if ok else 1, MARKER + json.dumps(report), '')

    def fake_upstream(self, relay, body):
        self.assertEqual([{'role': 'system', 'content': SYSTEM_PROMPT},
                          {'role': 'user', 'content': relay.prompt}], body['messages'])
        self.assertIn(self.fixture.question['question'], relay.prompt)
        self.assertIn('A name can be reassigned.', relay.prompt)
        self.assertNotIn('prompt_cache_key', body)
        self.assertFalse(body['store'])
        self.assertEqual(1024, body['max_completion_tokens'])
        self.assertEqual('gpt-6-luna', body['model'])
        # Confirm the canonical teaching lock is still held at upstream dispatch.
        self.assertEqual(409, self.request('/api/start', 'POST', {'ready': True})[0])
        return 200, {'model': 'gpt-6-luna', 'choices': [
            {'finish_reason': 'stop', 'message': {'content': self.raw}}]}, 'fake-request-id'

    def draft_and_progress(self):
        status, _ = self.request('/api/save', 'POST', {
            'context': 'practice', 'revision': 0, 'source': '# untouched draft'})
        self.assertEqual(200, status)
        return self.fixture.progress_snapshot()

    def test_validated_reply_and_single_request_budget(self):
        before = self.draft_and_progress()
        status, raw = self.ask()
        self.assertEqual(200, status, raw)
        self.assertEqual('validated', json.loads(raw)['kind'])
        self.assertEqual(self.fixture.explanation, json.loads(raw)['reply'])
        self.assertEqual(502, self.ask()[0])
        self.upstream.assert_called_once()
        receipt = self.transport.receipt
        self.assertEqual(1, receipt['relay_reservations'])
        self.assertEqual(1, receipt['provider_request_limit'])
        self.assertTrue(receipt['ledger_unchanged_by_worker'])
        self.assertEqual('fake-request-id', receipt['upstream'][0]['provider_request_id'])
        self.assertEqual(before, self.fixture.progress_snapshot())

    def test_assessment_denies_before_worker_and_upstream(self):
        self.assertEqual(200, self.request('/api/start', 'POST', {'ready': True})[0])
        self.assertEqual(409, self.ask()[0])
        self.assertFalse(self.worker.called)
        self.upstream.assert_not_called()
        self.assertFalse(self.transport.used)

    def test_timeout_consumes_budget_without_changing_progress(self):
        before = self.draft_and_progress()
        self.upstream.side_effect = TimeoutError('private timeout detail')
        status, raw = self.ask()
        self.assertEqual(502, status)
        self.assertIn(b'This trial will not retry', raw)
        self.assertNotIn(b'private timeout', raw)
        self.assertEqual(502, self.ask()[0])
        self.upstream.assert_called_once()
        self.assertEqual(1, self.transport.receipt['relay_reservations'])
        self.assertEqual(before, self.fixture.progress_snapshot())

    def test_rejected_teaching_reply_leaves_progress_and_draft_unchanged(self):
        before = self.draft_and_progress()
        self.raw = json.dumps(self.fixture.proposal | {'unexpected': 'private reply'})
        status, raw = self.ask()
        self.assertEqual(502, status)
        self.assertIn(b'could not be validated', raw)
        self.assertNotIn(b'private reply', raw)
        self.assertEqual(502, self.ask()[0])
        self.upstream.assert_called_once()
        self.assertEqual(1, self.transport.receipt['relay_reservations'])
        self.assertEqual(before, self.fixture.progress_snapshot())

    def test_semantically_unadmitted_reply_does_not_claim_message_was_saved(self):
        self.fixture.proposal['pedagogy']['intents']['question_span'] = {'ref': 'unknown'}
        self.raw = json.dumps(self.fixture.proposal)
        status, raw = self.ask()
        self.assertEqual(502, status)
        self.assertNotIn(b'saved', raw)
        self.upstream.assert_called_once()


if __name__ == '__main__':
    unittest.main()
