"""Exact GURU-004M response regression; mocked transport is not live acceptance."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from gurukul.anthropic_supervisor import AnthropicSupervisor
from gurukul.hermes_continuation import continuation_input, digest, load_previous
from gurukul.hermes_teaching import record_result
from gurukul.maharishi import (PROFILES, apply_control, carried_state, control_context,
                              hashed, snapshot, supervise, validate_directive)
from gurukul.pedagogy import (DIAGNOSTIC_KEYS, DESCRIPTIVE_KEYS, DESCRIPTIVE_ECHO_VALUES, PARENT_ECHO_KEYS,
                             build_prompt, orientation, turn_context, validate_response)
from gurukul.response_contract import ResponseContractError
from gurukul.store import Store, canonical
from gurukul.teaching_output import evaluate_output
from test_mixed_intents import QUESTION, proposal
from test_pedagogy import EXERCISE, ROOT

RAW = (ROOT / 'tests/fixtures/guru_004m_543dfff7.json').read_text().strip()
FAILED = json.loads(RAW)
MESSAGE = 'what are you talking about?'
DIRECTIVE = {'decision': 'INTERVENE', 'profile': 'ORIENTATION',
             'reason_codes': ['LEARNER_CONFUSION', 'META_QUESTION', 'REPETITION_LOOP'],
             'confidence': 'high', 'exit_condition': 'TTL', 'constitutional_change': False}


class SupervisedContractTests(unittest.TestCase):
    def setUp(self):
        self.orientation, _ = orientation(ROOT, EXERCISE)
        self.previous = {'teaching': {'explanation': 'Earlier explanation',
                                     'diagnostic_question': QUESTION,
                                     'pedagogy': {'strategy': 'comparison'}},
                         'parent_call_id': 'synthetic', 'parent_event_id': None,
                         'parent_report_sha256': 'synthetic', 'excerpt': 'Synthetic approved excerpt.'}
        self.context = turn_context(self.orientation, self.previous, MESSAGE, [])
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.root_call = str(uuid4())
        (self.root / self.root_call).mkdir()
        self.store = Store(self.root / self.root_call / 'acceptance.sqlite3')
        self.session = self.store.start(EXERCISE)
        self.config = json.loads((ROOT / 'config/maharishi.json').read_text())
        self.config['model'] = self.config['candidate_model']
        self.manifest = json.loads((ROOT / 'content/sources.json').read_text())
        self.guru_config = json.loads((ROOT / 'config/hermes-live.json').read_text())

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def supervise(self, directive=DIRECTIVE, text=None, history=None):
        adapter = AnthropicSupervisor(self.config, self.root / 'unused-key')
        context = self.context if text is None else turn_context(self.orientation, self.previous, text, history or [])
        state = carried_state(None, '')
        def transport(method, path, body):
            self.assertEqual(('POST', '/v1/messages'), (method, path))
            self.assertNotIn('tools', body)
            adapter.metadata.update(http_status=200, generation_requests=1)
            return {'model': self.config['model'], 'stop_reason': 'end_turn',
                    'content': [{'type': 'text', 'text': canonical(directive)}],
                    'usage': {'input_tokens': 100, 'output_tokens': 50}}
        with patch.object(adapter, '_request', side_effect=transport) as request:
            state, audit = supervise(snapshot(context, state), state, adapter, self.store,
                                     self.session['id'], str(uuid4()))
            self.assertEqual(1, request.call_count)
        return state, audit

    def save(self, result, admission, display, context, state, audit, previous=None, call=None):
        call = call or self.root_call
        directory = self.root / call
        directory.mkdir(exist_ok=True)
        final = RAW if result == FAILED else canonical(result)
        excerpt = 'Synthetic approved excerpt.'
        config = self.guru_config
        proof = {'source_id': config['source_id'], 'source_sha256': config['source_sha256'],
                 'sections': ['Concepts to own', config['source_section']],
                 'excerpt_sha256': digest(excerpt),
                 'manifest_sha256': digest(canonical(self.manifest)),
                 'exercise_sha256': digest(canonical(EXERCISE))}
        _, continuation = continuation_input(previous or self.previous, context['C_turn']['learner_message'])
        report = {'status': 'PASS', 'call_id': call, 'root_call_id': self.root_call,
                  'teaching': result, 'response_sha256': digest(final), 'provenance': proof,
                  'turn_context': context, 'display_teaching': display,
                  'pedagogy_admission': admission, 'supervision': audit,
                  'supervision_state': state, 'continuation': continuation}
        record_result(self.store, call, self.session['id'], report)
        (directory / 'report.json').write_text(canonical(dict(report, parent_ledger_record_verified=True)))
        (directory / 'provider-response.json').write_text(canonical({'choices': [{'message': {'content': final}}]}))
        (directory / 'teaching-response.json').write_text(final)
        (directory / 'approved-excerpt.txt').write_text(excerpt)
        return directory, report

    def test_exact_failed_response_after_approved_orientation(self):
        self.assertEqual(['current_location', 'curriculum_version'],
                         sorted(DIAGNOSTIC_KEYS - set(FAILED['pedagogy'])))
        with self.assertRaises(ResponseContractError) as error:
            validate_response(copy.deepcopy(FAILED))
        self.assertEqual(['current_location', 'curriculum_version'], error.exception.diagnostics['missing_keys'])
        state, audit = self.supervise()
        self.assertEqual('APPROVED', audit['status'])
        self.assertEqual(200, audit['provider']['http_status'])
        self.assertEqual(DIRECTIVE, audit['directive'])
        controlled = control_context(self.context, state)
        result = copy.deepcopy(FAILED)
        admission, display = evaluate_output(result, controlled)
        admission, display, state, compliance = apply_control(admission, display, state, controlled)
        self.assertEqual(FAILED, result)  # Original provider output is immutable.
        self.assertEqual('CONTINUE', admission['conversation_status'])
        self.assertEqual('META_QUESTION', display['pedagogy']['message_kind'])
        self.assertEqual('META_QUESTION', admission['intents']['primary'])
        self.assertEqual(['CONFUSION'], admission['intents']['secondary'])
        self.assertEqual(MESSAGE, admission['intents']['meta_span'])
        self.assertEqual(MESSAGE, admission['intents']['confusion_span'])
        self.assertEqual('not_applicable', admission['judgment'])
        self.assertFalse(admission['answer_admitted'])
        self.assertFalse(admission['grants_mastery'])
        self.assertTrue(admission['evidence_requirement_unresolved'])
        self.assertTrue(compliance['grading_suppressed'])
        self.assertEqual('', display['diagnostic_question'])
        self.assertEqual(FAILED['explanation'], display['explanation'])
        self.assertNotIn(QUESTION, canonical(display))
        self.assertIn(hashed(QUESTION), state['retired_questions'])
        self.assertEqual('C0-B01-D01', display['pedagogy']['current_location'])
        self.assertEqual('0.8.3', display['pedagogy']['curriculum_version'])
        self.assertEqual(self.context['orientation'], controlled['orientation'])
        self.assertEqual(self.context['turn_policy'], controlled['turn_policy'])
        self.assertEqual(['current_location', 'curriculum_version'],
                         admission['response_authority_binding']['omitted_model_echoes'])
        self.assertEqual('teaching', self.store.resume()['session']['phase'])

    def test_every_profile_uses_the_same_closed_contract(self):
        for profile in PROFILES:
            directive = dict(DIRECTIVE, profile=profile)
            if profile == 'NORMAL':
                directive.update(decision='NO_CHANGE', reason_codes=[])
            with self.subTest(profile=profile):
                state, audit = self.supervise(directive)
                self.assertEqual('APPROVED', audit['status'])
                context = control_context(self.context, state)
                prompt = build_prompt(context, 'Synthetic excerpt')
                contract = json.loads(prompt.split('GURU RESPONSE CONTRACT JSON:\n')[1].split('\nAPPROVED SOURCE EXCERPT')[0])
                self.assertTrue(contract['profiles_share_contract'])
                self.assertEqual({'current_location': 'C0-B01-D01', 'curriculum_version': '0.8.3'},
                                 contract['optional_parent_echoes'])
                self.assertEqual(DESCRIPTIVE_ECHO_VALUES, contract['optional_descriptive_echoes'])
                admission, display = evaluate_output(copy.deepcopy(FAILED), context)
                self.assertEqual('CONTINUE', admission['conversation_status'])
                invalid = copy.deepcopy(FAILED)
                invalid['pedagogy']['unlock_stage'] = 'C1'
                with self.assertRaises(ResponseContractError):
                    evaluate_output(invalid, context)

    def test_present_echoes_must_match_and_never_repair_corrupt_parent(self):
        for field, value, wrong in [('current_location', 'C0-B01-D01', 'C7'), ('curriculum_version', '0.8.3', '0.9')]:
            valid = copy.deepcopy(FAILED)
            valid['pedagogy'][field] = value
            self.assertEqual(value, validate_response(valid, self.context)['pedagogy'][field])
            valid['pedagogy'][field] = wrong
            with self.subTest(field=field), self.assertRaises(ResponseContractError) as error:
                evaluate_output(valid, self.context)
            self.assertEqual('conflicting_' + field, error.exception.diagnostics['failure_code'])
        for corrupt in [None, {}, {'C_turn': {'location': 'C1'}},
                        dict(self.context, orientation={**self.orientation,
                             'A_global': {**self.orientation['A_global'], 'curriculum_version': 'new'}})]:
            with self.subTest(parent=corrupt), self.assertRaises(ValueError):
                evaluate_output(copy.deepcopy(FAILED), corrupt)

    def test_core_fields_and_hard_boundaries_are_not_optional(self):
        for field in (DIAGNOSTIC_KEYS - PARENT_ECHO_KEYS - DESCRIPTIVE_KEYS) | {'intents', 'intent_responses'}:
            result = copy.deepcopy(FAILED)
            result['pedagogy'].pop(field)
            with self.subTest(missing=field), self.assertRaises(ValueError):
                evaluate_output(result, self.context)
        mutations = [lambda p: p.update(grants_mastery=True),
                     lambda p: p.update(source_specific=True, knowledge_classes=['learner_evidence']),
                     lambda p: p.update(knowledge_classes=['verified_external_source']),
                     lambda p: p.update(intents=[]),
                     lambda p: p.update(intent_responses={'confusion': 'Only one field'}),
                     lambda p: p.update(judgment='invented')]
        for mutate in mutations:
            result = copy.deepcopy(FAILED)
            mutate(result['pedagogy'])
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                evaluate_output(result, self.context)
        result = copy.deepcopy(FAILED)
        result['miniature_example'] = 'import os'
        with self.assertRaises(ValueError):
            evaluate_output(result, self.context)

    def test_structural_diagnostics_never_record_field_values_or_unsafe_keys(self):
        result = copy.deepcopy(FAILED)
        result['pedagogy'].pop('evidence_need')
        result['pedagogy']['secret-looking-token!'] = 'private provider text'
        with self.assertRaises(ResponseContractError) as error:
            evaluate_output(result, self.context)
        info = error.exception.diagnostics
        self.assertEqual('guru.pedagogy.schema', info['validation_stage'])
        self.assertEqual(['evidence_need'], info['missing_keys'])
        self.assertEqual(sorted(PARENT_ECHO_KEYS | DESCRIPTIVE_KEYS | {'routing'}), info['optional_keys'])
        self.assertEqual(1, len(info['extra_keys']))
        self.assertTrue(info['extra_keys'][0].startswith('<key-sha256:'))
        self.assertNotIn('secret-looking-token!', canonical(info))
        self.assertNotIn('private provider text', canonical(info))
        self.assertNotIn(FAILED['explanation'], canonical(info))

    def test_rejected_http_200_directive_has_safe_diagnostics_and_same_fallback(self):
        invalid = dict(DIRECTIVE, tools=['private tool text'])
        history=[{'event_id':str(i),'question':QUESTION,
                  'pedagogy_admission':{'answer_admitted':False,'conversation_status':'CONTINUE'}} for i in range(3)]
        state, audit = self.supervise(invalid, 'you are just moving in loops', history)
        self.assertEqual('SUPERVISION_FAILED', audit['status'])
        self.assertEqual('DETERMINISTIC_ORIENTATION', audit['fallback'])
        self.assertEqual('ORIENTATION', state['profile'])
        self.assertEqual(1, audit['provider_calls'])
        self.assertEqual(1, audit['request_reservations'])
        self.assertEqual(['tools'], audit['validation_diagnostics']['extra_keys'])
        self.assertNotIn('private tool text', canonical(audit))
        with self.assertRaises(ResponseContractError) as error:
            validate_directive(dict(DIRECTIVE, reason_codes=['REPETITION_LOOP'] * 2))
        self.assertEqual('duplicate_reason_code', error.exception.diagnostics['failure_code'])

    def test_exact_raw_output_reloads_then_fresh_check_and_answer_resume(self):
        state, audit = self.supervise()
        context = control_context(self.context, state)
        admission, display = evaluate_output(copy.deepcopy(FAILED), context)
        admission, display, state, _ = apply_control(admission, display, state, context)
        directory, report = self.save(FAILED, admission, display, context, state, audit)
        loaded = load_previous(self.root, self.root_call, self.manifest, self.guru_config, EXERCISE)
        self.assertEqual(RAW, (directory / 'teaching-response.json').read_text())
        self.assertNotIn('current_location', report['teaching']['pedagogy'])
        self.assertEqual('C0-B01-D01', loaded['teaching']['pedagogy']['current_location'])
        self.assertEqual('', loaded['teaching']['diagnostic_question'])
        self.assertFalse(loaded['history'][-1]['pedagogy_admission']['grants_mastery'])
        state = carried_state(loaded, 'check my understanding')
        self.assertEqual('NORMAL', state['profile'])
        fresh = 'Invent a different name and describe how quoted text differs from it.'
        request = proposal(question='check my understanding')
        request['diagnostic_question'] = fresh
        context = control_context(turn_context(self.orientation, loaded, 'check my understanding', loaded['history']), state)
        admission, display = evaluate_output(request, context)
        admission, display, state, _ = apply_control(admission, display, state, context)
        self.assertEqual(fresh, display['diagnostic_question'])
        self.assertNotIn(hashed(fresh), state['retired_questions'])
        next_call = str(uuid4())
        self.save(request, admission, display, context, state, {}, loaded, next_call)
        loaded = load_previous(self.root, next_call, self.manifest, self.guru_config, EXERCISE)
        answer = 'Birch is an undefined name and raises NameError; quoted Birch gives text.'
        context = control_context(turn_context(self.orientation, loaded, answer, loaded['history']), state)
        admission, display = evaluate_output(proposal(answer=answer), context)
        admission, display, _, _ = apply_control(admission, display, state, context)
        self.assertTrue(admission['answer_admitted'])
        self.assertEqual('correct', admission['judgment'])
        self.assertFalse(admission['grants_mastery'])
        self.assertTrue(admission['evidence_requirement_unresolved'])
        self.assertEqual('teaching', self.store.resume()['session']['phase'])

    def test_saved_parent_context_cannot_be_changed_before_derivation(self):
        state, audit = self.supervise()
        context = control_context(self.context, state)
        admission, display = evaluate_output(copy.deepcopy(FAILED), context)
        admission, display, state, _ = apply_control(admission, display, state, context)
        directory, report = self.save(FAILED, admission, display, context, state, audit)
        report['turn_context']['orientation']['A_global']['curriculum_version'] = 'new'
        (directory / 'report.json').write_text(canonical(dict(report, parent_ledger_record_verified=True)))
        with self.assertRaisesRegex(ValueError, 'differs from ledger'):
            load_previous(self.root, self.root_call, self.manifest, self.guru_config, EXERCISE)

    def test_safe_format_recovery_keeps_parent_binding_and_raw_response(self):
        state, audit = self.supervise()
        context = control_context(self.context, state)
        result = copy.deepcopy(FAILED)
        result['pedagogy'].pop('current_purpose')
        result['explanation'] = ' '.join(['text'] * 181)  # Genuine concise-output violation.
        admission, display = evaluate_output(result, context)
        self.assertEqual('RESPONSE_REJECTED', admission['conversation_status'])
        admission, display, state, _ = apply_control(admission, display, state, context)
        self.save(result, admission, display, context, state, audit)
        loaded = load_previous(self.root, self.root_call, self.manifest, self.guru_config, EXERCISE)
        self.assertEqual('', loaded['teaching']['diagnostic_question'])
        self.assertEqual('C0-B01-D01', loaded['teaching']['pedagogy']['current_location'])
        self.assertFalse(admission['answer_admitted'])
        self.assertFalse(admission['grants_mastery'])

    def test_all_four_echoes_can_be_omitted_and_reload_without_rejection(self):
        state, audit = self.supervise()
        context = control_context(self.context, state)
        result = copy.deepcopy(FAILED)
        for field in DESCRIPTIVE_KEYS:
            result['pedagogy'].pop(field)
        original = copy.deepcopy(result)
        admission, display = evaluate_output(result, context)
        admission, display, state, _ = apply_control(admission, display, state, context)
        self.assertEqual('CONTINUE', admission['conversation_status'])
        self.assertEqual(original, result)
        directory, report = self.save(result, admission, display, context, state, audit)
        loaded = load_previous(self.root, self.root_call, self.manifest, self.guru_config, EXERCISE)
        self.assertEqual(original, json.loads((directory / 'teaching-response.json').read_text()))
        self.assertEqual(original, report['teaching'])
        for field in DESCRIPTIVE_KEYS:
            self.assertNotIn(field, loaded['teaching']['pedagogy'])
        self.assertEqual('C0-B01-D01', loaded['teaching']['pedagogy']['current_location'])
        self.assertEqual('0.8.3', loaded['teaching']['pedagogy']['curriculum_version'])
        self.assertEqual('', loaded['teaching']['diagnostic_question'])
        self.assertFalse(admission['grants_mastery'])
        self.assertTrue(admission['evidence_requirement_unresolved'])

    def test_optional_descriptive_echoes_must_match_when_present(self):
        for field, value in DESCRIPTIVE_ECHO_VALUES.items():
            result = copy.deepcopy(FAILED)
            self.assertEqual(value, validate_response(result, self.context)['pedagogy'][field])
            result['pedagogy'][field] = 'different'
            with self.subTest(field=field), self.assertRaises(ResponseContractError) as error:
                evaluate_output(result, self.context)
            self.assertEqual('conflicting_' + field, error.exception.diagnostics['failure_code'])

    def test_binding_is_rechecked_even_when_report_matches_ledger(self):
        state, audit = self.supervise()
        context = control_context(self.context, state)
        admission, display = evaluate_output(copy.deepcopy(FAILED), context)
        admission, display, state, _ = apply_control(admission, display, state, context)
        admission['response_authority_binding']['values']['curriculum_version'] = 'new'
        self.save(FAILED, admission, display, context, state, audit)
        with self.assertRaisesRegex(ValueError, 'authority binding changed'):
            load_previous(self.root, self.root_call, self.manifest, self.guru_config, EXERCISE)


if __name__ == '__main__':
    unittest.main()
