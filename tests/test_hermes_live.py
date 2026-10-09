"""Synthetic unit/HTTP contract tests, NOT live Hermes or macOS acceptance."""
import copy
import hashlib
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from gurukul.hermes_relay import Relay, STARTUP_PROBE_PATHS, private_key, validate_request
from gurukul.hermes_teaching import record_result, source_input, teaching_response
from gurukul.store import Store

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'config/hermes-live.json').read_text())
EXERCISE = json.loads((ROOT / 'content/c0_b01/d01.json').read_text())


class RequestPolicyTests(unittest.TestCase):
    def setUp(self):
        self.body = {'model': CONFIG['model'], 'messages': [{'role': 'user', 'content': 'approved'}],
                     'max_completion_tokens': 512, 'store': False}

    def test_text_request_allowed(self):
        self.assertEqual(self.body, validate_request(self.body, CONFIG['model'], 'approved', 1024))

    def test_text_blocks_allowed(self):
        self.body['messages'][0]['content'] = [{'type': 'text', 'text': 'approved'}]
        validate_request(self.body, CONFIG['model'], 'approved', 1024)

    def test_escalation_tools_native_tools_and_unknown_fields_denied(self):
        changes = [{'model': 'different-model'}, {'tools': [{'type': 'web_search'}]},
                   {'tools': [{'type': 'function', 'function': {'name': 'terminal'}}]},
                   {'web_search_options': {}}, {'functions': [{'name': 'shell'}]},
                   {'tool_choice': 'auto'}, {'parallel_tool_calls': True}, {'store': True},
                   {'n': 2}, {'stream': True}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_request(dict(self.body, **change), CONFIG['model'], 'approved', 1024)

    def test_budget_required_and_cannot_expand(self):
        for limit in (None, 0, 1025, True, '10'):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                validate_request(dict(self.body, max_completion_tokens=limit), CONFIG['model'], 'approved', 1024)

    def test_history_tool_messages_and_external_content_denied(self):
        for msg in ({'role': 'tool', 'content': 'approved'},
                    {'role': 'assistant', 'content': 'approved'},
                    {'role': 'user', 'content': 'different'},
                    {'role': 'user', 'content': [{'type': 'image_url', 'image_url': {'url': 'https://example.com'}}]}):
            with self.subTest(msg=msg), self.assertRaises(ValueError):
                validate_request(dict(self.body, messages=[msg]), CONFIG['model'], 'approved', 1024)

    def test_real_http_relay_blocks_routes_and_requires_turn_admission(self):
        with Relay(CONFIG, Path('/unused'), 'approved') as relay:
            with patch.object(relay, 'forward', side_effect=AssertionError('no inference permitted')):
                conn = http.client.HTTPConnection('127.0.0.1', relay.port)
                for method, path in [('CONNECT', 'example.com:443'), ('POST', '/v1/responses'),
                                     ('POST', '/v1/chat/completions')]:
                    conn.request(method, path, json.dumps(self.body), {'Authorization': 'Bearer ' + relay.token})
                    result = conn.getresponse()
                    self.assertEqual(403, result.status)
                    result.read()
                conn.close()
            self.assertEqual([], relay.calls)

    def test_one_request_reservation_survives_provider_failure(self):
        with Relay(CONFIG, Path('/unused'), 'approved') as relay:
            relay.ready = True
            with patch.object(relay, 'forward', side_effect=OSError('synthetic transport failure')) as forward:
                for expected in (502, 403):
                    conn = http.client.HTTPConnection('127.0.0.1', relay.port)
                    conn.request('POST', '/v1/chat/completions', json.dumps(self.body),
                                 {'Authorization': 'Bearer ' + relay.token})
                    response = conn.getresponse()
                    self.assertEqual(expected, response.status)
                    response.read()
                    conn.close()
                self.assertEqual(1, forward.call_count)
            self.assertEqual(1, len(relay.calls))

    def test_known_startup_probes_stay_denied_without_provider_forwarding(self):
        with Relay(CONFIG, Path('/unused'), 'approved') as relay:
            with patch.object(relay, 'forward', side_effect=AssertionError('must never forward')):
                for path in STARTUP_PROBE_PATHS:
                    conn = http.client.HTTPConnection('127.0.0.1', relay.port)
                    conn.request('GET', path, headers={'Authorization': 'Bearer ' + relay.token})
                    response = conn.getresponse()
                    self.assertEqual(403, response.status)
                    response.read()
                    conn.close()
            self.assertEqual(5, len(relay.blocked_startup_probes))
            self.assertEqual([], relay.rejections)
            self.assertEqual([], relay.calls)

    def test_probe_exceptions_do_not_cover_wrong_auth_queries_or_live_turn(self):
        for path, token_valid, ready in [('/props?upstream=other', True, False),
                                         ('/props', False, False), ('/props', True, True)]:
            with self.subTest(path=path, token_valid=token_valid, ready=ready):
                with Relay(CONFIG, Path('/unused'), 'approved') as relay:
                    relay.ready = ready
                    conn = http.client.HTTPConnection('127.0.0.1', relay.port)
                    conn.request('GET', path, headers={'Authorization': 'Bearer ' + (relay.token if token_valid else 'invalid')})
                    response = conn.getresponse()
                    self.assertEqual(403, response.status)
                    response.read()
                    conn.close()
                    self.assertEqual([], relay.blocked_startup_probes)
                    self.assertEqual(1, len(relay.rejections))

    def test_fatal_rejection_prevents_ready_and_inference(self):
        with Relay(CONFIG, Path('/unused'), 'approved') as relay:
            for method, path in [('GET', '/unexpected'), ('POST', '/ready'), ('POST', '/v1/chat/completions')]:
                conn = http.client.HTTPConnection('127.0.0.1', relay.port)
                conn.request(method, path, headers={'Authorization': 'Bearer ' + relay.token})
                response = conn.getresponse()
                self.assertEqual(403, response.status)
                response.read()
                conn.close()
            self.assertFalse(relay.ready)
            self.assertEqual([], relay.calls)


class SourceAndEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_source_hash_and_section_binding(self):
        # Synthetic fixture deliberately differs from approved production source.
        path = self.root / 'source.html'
        path.write_text('<h2>Concepts to own</h2><div class="card">Quoted text is data.</div>'
                        '<section class="day">C0-B01-D01 Predict reassignment.</section>')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        config = dict(CONFIG, source_sha256=digest)
        manifest = {'sources': {CONFIG['source_id']: {'sha256': digest, 'access': 'approved_local_only'}}}
        prompt, excerpt, proof = source_input(path, manifest, config, EXERCISE)
        self.assertIn('Quoted text is data.', prompt)
        self.assertEqual(hashlib.sha256(excerpt.encode()).hexdigest(), proof['excerpt_sha256'])
        path.write_text(path.read_text() + 'corruption')
        with self.assertRaises(ValueError):
            source_input(path, manifest, config, EXERCISE)

    def test_disclosure_schema_blocks_code_and_solution_fields(self):
        okay = {'explanation': 'A quoted word is a text value.', 'diagnostic_question': 'What changes after reassignment?'}
        self.assertEqual(okay, teaching_response(json.dumps(okay)))
        for response in (dict(okay, solution='answer'), dict(okay, explanation='x = 7'),
                         dict(okay, explanation='print(x)'), dict(okay, explanation='```python'),
                         dict(okay, explanation='')):
            with self.subTest(response=response), self.assertRaises(ValueError):
                teaching_response(json.dumps(response))

    def test_key_permissions_and_symlink_denied(self):
        path = self.root / 'key'
        path.write_text('synthetic-not-a-key')
        path.chmod(0o644)
        with self.assertRaises(ValueError):
            private_key(path)
        path.chmod(0o600)
        self.assertEqual('synthetic-not-a-key', private_key(path))
        link = self.root / 'link'
        link.symlink_to(path)
        with self.assertRaises(OSError):
            private_key(link)

    def test_parent_event_survives_restart_without_mastery_or_phase_change(self):
        path = self.root / 'state.sqlite3'
        store = Store(path)
        session = store.start(EXERCISE)
        result = {'status': 'PASS', 'grants_mastery': False, 'teaching': {'synthetic': True}}
        record_result(store, 'test-call', session['id'], result)
        store.close()
        store = Store(path)
        self.assertEqual('teaching', store.resume()['session']['phase'])
        self.assertEqual(result, store.events()[-1]['payload'])
        with self.assertRaises(sqlite3.IntegrityError):
            store.db.execute("DELETE FROM events WHERE event_type='teaching.integration_finished'")
        store.close()

    def test_reconstruction_blocks_tutoring_then_remediation_allows(self):
        store = Store(self.root / 'state.sqlite3')
        session = store.start(EXERCISE)
        with store.db:
            store.db.execute("UPDATE sessions SET phase='reconstruction'")
        with self.assertRaises(ValueError):
            record_result(store, 'test-call', session['id'], {'status': 'PASS'})
        self.assertEqual(1, len(store.events()))
        with store.db:
            store.db.execute("UPDATE sessions SET phase='remediation'")
        record_result(store, 'test-call', session['id'], {'status': 'PASS'})
        self.assertEqual(2, len(store.events()))
        store.close()

    def test_event_insert_failure_leaves_no_partial_record(self):
        store = Store(self.root / 'state.sqlite3')
        session = store.start(EXERCISE)
        store.db.execute("CREATE TRIGGER reject_teaching BEFORE INSERT ON events WHEN NEW.event_type='teaching.integration_finished' BEGIN SELECT RAISE(ABORT,'test'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            record_result(store, 'test-call', session['id'], {})
        self.assertEqual(1, len(store.events()))
        store.close()
