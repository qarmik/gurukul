"""Workspace-to-relay integration with a simulated sandbox worker and fake upstream."""
import contextlib
import hashlib
import http.client
import io
import json
import subprocess
import unittest
from unittest.mock import Mock, patch

import test_workspace as workspace_tests
from gurukul.hermes_relay import Relay
from gurukul.pedagogy import SYSTEM_PROMPT
from ask_guru_live import OneTurnTransport, checked_config, relay_receipt
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
        self.fixture.server.teaching_pipeline.reply_observer = self.transport.record_reply
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

    def fake_upstream(self, relay, body, *, call):
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
        call.update(http_status=200, provider_request_id='req_fake', provider_http_error=False)
        return 200, {'model': 'gpt-6-luna', 'choices': [
            {'finish_reason': 'stop', 'message': {'content': self.raw}}]}

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
        self.assertEqual('reply_admitted', receipt['reply_reason_code'])
        self.assertEqual(1, receipt['relay_reservations'])
        self.assertEqual(1, receipt['provider_request_limit'])
        self.assertTrue(receipt['ledger_unchanged_by_worker'])
        self.assertEqual('req_fake', receipt['upstream'][0]['provider_request_id'])
        self.assertEqual(before, self.fixture.progress_snapshot())

    def test_assessment_denies_before_worker_and_upstream(self):
        self.assertEqual(200, self.request('/api/start', 'POST', {'ready': True})[0])
        self.assertEqual(409, self.ask()[0])
        self.assertFalse(self.worker.called)
        self.upstream.assert_not_called()
        self.assertFalse(self.transport.used)
        self.assertEqual('reply_not_evaluated', self.transport.receipt['reply_reason_code'])

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
        self.assertEqual('reply_not_evaluated', self.transport.receipt['reply_reason_code'])
        self.assertEqual(before, self.fixture.progress_snapshot())

    def test_invalid_json_is_hidden_and_reported_without_raw_text(self):
        before = self.draft_and_progress()
        self.raw = 'private malformed reply'
        status, raw = self.ask()
        self.assertEqual(502, status)
        self.assertEqual({'error': 'Guru’s reply could not be validated.'}, json.loads(raw))
        self.assertEqual('invalid_reply_json', self.transport.receipt['reply_reason_code'])
        self.assertNotIn(self.raw, json.dumps(self.transport.receipt))
        self.assertNotIn(self.raw, self.output.getvalue())
        self.upstream.assert_called_once()
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
        self.assertEqual('reply_validation_failed', self.transport.receipt['reply_reason_code'])
        self.assertNotIn('private reply', json.dumps(self.transport.receipt))
        self.assertEqual(before, self.fixture.progress_snapshot())

    def test_semantically_unadmitted_reply_does_not_claim_message_was_saved(self):
        before = self.draft_and_progress()
        self.fixture.proposal['pedagogy']['intents']['question_span'] = {'ref': 'unknown'}
        self.raw = json.dumps(self.fixture.proposal)
        status, raw = self.ask()
        self.assertEqual(502, status)
        self.assertNotIn(b'saved', raw)
        self.assertNotIn(self.fixture.explanation.encode(), raw)
        self.assertEqual('reply_withheld_after_validation', self.transport.receipt['reply_reason_code'])
        self.assertEqual(before, self.fixture.progress_snapshot())
        self.upstream.assert_called_once()

    def test_same_name_two_assignment_example_hits_existing_disclosure_limit(self):
        self.assertIn('at most one assigned name', SYSTEM_PROMPT)
        self.raw = json.dumps(self.fixture.proposal | {'miniature_example': 'sample = 2\nsample = 3'})
        status, raw = self.ask()
        self.assertEqual(502, status)
        self.assertNotIn(b'sample = 2', raw)
        self.assertEqual('reply_validation_failed', self.transport.receipt['reply_reason_code'])
        self.upstream.assert_called_once()


class RelayReceiptTests(unittest.TestCase):
    def fixture(self, path, reply, *, send_error=None, headers_error=None, policy_only=False):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            key = Path(tmp) / 'dummy-key'
            key.touch(mode=0o600)
            key.write_text('dummy-credential-value')
            config = checked_config(workspace_tests.ROOT)
            prompt = 'dummy prompt, never in receipt'
            connection = Mock()
            connection.request.side_effect = send_error
            connection.getresponse.side_effect = headers_error
            connection.getresponse.return_value = reply
            with Relay(config, key, prompt) as relay, patch(
                    'gurukul.hermes_relay.http.client.HTTPSConnection',
                    return_value=connection) as fake_connection:
                relay.ready = True
                expected_statuses = []
                for route in ([path] if policy_only else [path, path]):
                    with contextlib.closing(http.client.HTTPConnection('127.0.0.1', relay.port, timeout=5)) as client:
                        client.request('POST', route, json.dumps({
                            'model': config['model'], 'max_completion_tokens': 1024,
                            'messages': [{'role': 'user', 'content': prompt}]}),
                            {'Authorization': 'Bearer ' + relay.token})
                        response = client.getresponse()
                        response.read()
                        expected_statuses.append(response.status)
                receipt = relay_receipt(relay, config['model'])
                self.assertEqual(0 if policy_only else 1, fake_connection.call_count)
                self.assertEqual(0 if policy_only else 1, connection.request.call_count)
            serialized = json.dumps(receipt)
            for forbidden in ('dummy-credential-value', prompt, 'raw exception detail', 'raw provider body'):
                self.assertNotIn(forbidden, serialized)
            return expected_statuses, receipt

    def response(self, status=200, body=b''):
        reply = Mock(status=status)
        reply.getheader.return_value = 'req_fixture123'
        reply.read.return_value = body
        return reply

    def test_body_read_failure_preserves_headers_and_denies_second_forward(self):
        reply = self.response()
        reply.read.side_effect = TimeoutError('raw exception detail')
        statuses, receipt = self.fixture('/v1/chat/completions', reply)
        self.assertEqual([502, 403], statuses)
        self.assertEqual(1, receipt['relay_reservations'])
        self.assertEqual(['request_budget_exhausted'], receipt['relay_rejection_codes'])
        call, = receipt['upstream']
        self.assertEqual('response_body_read', call['upstream_stage'])
        self.assertEqual(200, call['http_status'])
        self.assertEqual('req_fixture123', call['provider_request_id'])

    def test_distinct_connection_headers_decode_and_http_failure_stages(self):
        route = '/v1/chat/completions'
        for kwargs, reply, stage, expected_status in (
                ({'send_error': OSError('raw exception detail')}, None, 'connection_or_send', None),
                ({'headers_error': TimeoutError('raw exception detail')}, None, 'response_headers', None),
                ({}, self.response(body=b'raw provider body'), 'response_body_decode', 200),
                ({}, self.response(429, b'{"error":{"message":"raw provider body"}}'), 'provider_http_error', 429),
                ({}, self.response(429, b'raw provider body'), 'response_body_decode', 429)):
            with self.subTest(stage=stage, status=expected_status):
                statuses, receipt = self.fixture(route, reply, **kwargs)
                self.assertEqual([429 if expected_status == 429 else 502, 403], statuses)
                call, = receipt['upstream']
                self.assertEqual(stage, call['upstream_stage'])
                self.assertEqual(expected_status, call['http_status'])
                self.assertEqual('req_fixture123' if expected_status else None, call['provider_request_id'])
                self.assertEqual(expected_status == 429 if expected_status else None, call['provider_http_error'])

    def test_policy_only_denial_has_no_upstream_record(self):
        statuses, receipt = self.fixture('/private-prompt-or-path', None, policy_only=True)
        self.assertEqual([403], statuses)
        self.assertEqual([], receipt['upstream'])
        self.assertEqual(0, receipt['relay_reservations'])
        self.assertEqual(['route_or_turn_not_authorized'], receipt['relay_rejection_codes'])
        self.assertNotIn('private-prompt-or-path', json.dumps(receipt))

    def test_untrusted_header_and_model_values_are_omitted(self):
        reply = self.response(body=b'{"model":"raw provider body"}')
        reply.getheader.return_value = 'dummy-credential-value'
        statuses, receipt = self.fixture('/v1/chat/completions', reply)
        self.assertEqual([502, 403], statuses)
        call, = receipt['upstream']
        self.assertIsNone(call['provider_request_id'])
        self.assertIsNone(call['resolved_model'])


if __name__ == '__main__':
    unittest.main()
