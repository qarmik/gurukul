"""GURU-004H: exact live content and bounded offline authority regressions."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from uuid import uuid4

from test_pedagogy import ROOT, EXERCISE
from test_mixed_intents import proposal, QUESTION
from test_maharishi import FakeProvider, NORMAL, INTERVENE
from gurukul.pedagogy import orientation, turn_context, classify, build_prompt
from gurukul.intent_admission import candidate_answers, intent_hint
from gurukul.teaching_output import evaluate_output
from gurukul.learner_input import verify_admission
from gurukul.maharishi import (carried_state, snapshot, trigger_evidence, supervise,
                               select_state, control_context, apply_control, hashed)
from gurukul.hermes_teaching import record_result
from gurukul.hermes_continuation import load_previous, continuation_input, digest
from gurukul.store import Store, canonical

sys.path.insert(0, str(ROOT / 'scripts'))
from hermes_live_teach import display_teaching

FIXTURE = ROOT / 'tests/fixtures/guru_004h_b81269bd.json'
PROVENANCE = json.loads((ROOT / 'tests/fixtures/guru_004h_b81269bd-provenance.json').read_text())


class SemanticAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.orientation, _ = orientation(ROOT, EXERCISE)
        self.previous = {'teaching': {'explanation': 'Prior explanation.',
                                     'diagnostic_question': QUESTION,
                                     'pedagogy': {'strategy': 'comparison', 'next_activity': 'predict'}}}
        self.state = carried_state(None, '')
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.store = Store(self.root / 'state.sqlite3')
        self.session = self.store.start(EXERCISE)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def context(self, message, history=None):
        return turn_context(self.orientation, self.previous, message, history or [])

    def view(self, message, history=None):
        return snapshot(self.context(message, history), self.state)

    def supervise(self, view, provider):
        return supervise(view, self.state, provider, self.store, self.session['id'], str(uuid4()))

    def assert_recovery(self, admission, shown):
        self.assertEqual('NEEDS_CLARIFICATION', admission['conversation_status'])
        self.assertEqual('not_applicable', admission['judgment'])
        self.assertFalse(admission['answer_admitted'])
        self.assertFalse(admission['grants_mastery'])
        self.assertEqual(QUESTION, admission['unresolved_evidence_question'])
        self.assertEqual('', shown['diagnostic_question'])
        self.assertEqual('teaching', self.store.resume()['session']['phase'])

    def repeated_history(self):
        return [{'event_id': str(i), 'question': QUESTION,
                 'pedagogy': {'strategy': 'comparison', 'next_activity': 'predict'},
                 'pedagogy_admission': {'conversation_status': 'CONTINUE', 'answer_admitted': False}}
                for i in range(3)]

    def test_latest_assigned_value_is_stable_answer_evidence(self):
        message = 'The name refers to its latest assigned value.'
        context = self.context(message)
        admission, _ = evaluate_output(proposal(answer=message), context)
        self.assertEqual('CONTINUE', admission['conversation_status'])
        self.assertTrue(admission['answer_admitted'])
        self.assertEqual('stable_fundamentals', admission['semantic_route']['knowledge_task'])
        self.assertIn('version_sensitive', context['turn_policy']['surface_signals']['candidates'])
        self.assertFalse(admission['semantic_route']['surface_hints_used_as_authority'])

    def test_exact_b81269bd_response_retains_partial_judgment_and_input(self):
        raw = FIXTURE.read_bytes()
        result = json.loads(raw)
        original = copy.deepcopy(result)
        message = PROVENANCE['learner_message']
        self.previous['teaching']['diagnostic_question'] = PROVENANCE['active_question']
        context = self.context(message)
        saved_context = copy.deepcopy(context)
        admission, shown = evaluate_output(result, context)
        self.assertIn('?', message)
        self.assertEqual('CONTINUE', admission['conversation_status'])
        self.assertTrue(admission['answer_admitted'])
        self.assertEqual('partial', admission['judgment'])
        self.assertEqual(message, admission['learner_verified_spans']['answer_span']['text'])
        self.assertEqual(original['pedagogy']['intents'], admission['model_interpretation'])
        self.assertEqual(original['explanation'], shown['explanation'])
        self.assertEqual(original['diagnostic_question'], shown['diagnostic_question'])
        self.assertFalse(admission['grants_mastery'])
        self.assertEqual('C0-B01-D01', shown['pedagogy']['current_location'])
        self.assertEqual('0.8.3', shown['pedagogy']['curriculum_version'])
        self.assertEqual(original, result)
        self.assertEqual(saved_context, context)
        self.assertEqual(raw, FIXTURE.read_bytes())
        self.assertEqual('529b98d3926d27366e37b20d47d07dfee7616e6ffbbeb466fd17b60d6382c863',
                         PROVENANCE['reported_provider_response_sha256'])
        verify_admission(admission, message)

    def test_latest_python_version_requires_defer_or_recoverable_clarification(self):
        message = 'What is the latest Python version?'
        result = proposal(question=message)
        result['pedagogy']['routing'] = {'knowledge_task': 'version_sensitive'}
        admission, shown = evaluate_output(result, self.context(message))
        self.assert_recovery(admission, shown)
        self.assertEqual('version_sensitive', admission['semantic_route']['knowledge_task'])
        self.assertEqual('model_semantic_proposal', admission['semantic_route']['knowledge_origin'])
        result['pedagogy']['strategy'] = 'defer'
        result['explanation'] = 'The latest Python release needs a current authoritative source that is not supplied here.'
        result['diagnostic_question'] = ''
        admission, shown = evaluate_output(result, self.context(message))
        self.assertEqual('CONTINUE', admission['conversation_status'])
        self.assertEqual('defer', shown['pedagogy']['strategy'])
        self.assertEqual('not_applicable', admission['judgment'])
        self.assertFalse(admission['answer_admitted'])

    def test_legal_variable_name_does_not_require_regulatory_source(self):
        message = 'foo_bar is a legal variable name'
        admission, _ = evaluate_output(proposal(answer=message), self.context(message))
        self.assertEqual('CONTINUE', admission['conversation_status'])
        self.assertTrue(admission['answer_admitted'])
        self.assertEqual('stable_fundamentals', admission['semantic_route']['knowledge_task'])

    def test_code_assignment_words_do_not_create_source_requests(self):
        for message in ['book = "Python"', 'source = "hello"', 'page = 3', 'material = "wood"']:
            with self.subTest(message=message):
                admission, _ = evaluate_output(proposal(answer=message), self.context(message))
                self.assertEqual('CONTINUE', admission['conversation_status'])
                self.assertTrue(admission['answer_admitted'])
                self.assertEqual('stable_fundamentals', admission['semantic_route']['knowledge_task'])
                self.assertEqual(message, admission['intents']['answer_span'])

    def test_agent_name_and_python_ast_vocabulary_do_not_force_deferral(self):
        for message in ['agent = "Rohit"', 'AST is a name here.', 'The last assigned value is 7.']:
            with self.subTest(message=message):
                result = proposal(answer=message)
                result['explanation'] = 'The name agent can refer to a text value.'
                admission, shown = evaluate_output(result, self.context(message))
                self.assertEqual('CONTINUE', admission['conversation_status'])
                self.assertTrue(admission['answer_admitted'])
                self.assertEqual('current_capability', admission['semantic_route']['teaching_scope'])
                self.assertFalse(shown['pedagogy']['future_topic_deferred'])

    def test_poisoned_surface_hints_cannot_change_admission(self):
        message = 'The latest assigned value is 7.'
        result = proposal(answer=message)
        context = self.context(message)
        before = evaluate_output(result, context)
        context['turn_policy'].update(knowledge_task_hint='regulatory', message_kind_hint='CONFUSION',
                                     mixed_intent_hint={'possible_intents': ['QUESTION'],
                                                       'candidate_answer_segments': [], 'requested_strategy': 'analogy'},
                                     surface_signals={'candidates': ['future_topic'], 'authority': 'none'})
        self.assertEqual(before, evaluate_output(result, context))

    def test_explanation_word_in_answer_does_not_create_strategy_requirement(self):
        message = 'Quotes make it simpler for Python to use text directly.'
        admission, _ = evaluate_output(proposal(answer=message), self.context(message))
        self.assertEqual('CONTINUE', admission['conversation_status'])
        self.assertTrue(admission['answer_admitted'])

    def test_mixed_confusion_hypothesis_preserves_answer_evidence(self):
        confusion = "I don't understand"
        answer = 'I think quotes make Rohit text.'
        message = confusion + ', but ' + answer
        result = proposal(answer=answer, confusion=confusion, hypothesis=answer)
        admission, _ = evaluate_output(result, self.context(message))
        self.assertEqual('CONTINUE', admission['conversation_status'])
        self.assertTrue(admission['answer_admitted'])
        self.assertIn('CONFUSION', admission['intents']['secondary'])
        self.assertIn('HYPOTHESIS', admission['intents']['secondary'])
        self.assertEqual(confusion, admission['learner_verified_spans']['confusion_span']['text'])
        self.assertEqual(answer, admission['learner_verified_spans']['answer_span']['text'])
        self.assertIn('ANSWER', intent_hint(message)['possible_intents'])
        verify_admission(admission, message)

    def test_mixed_answer_and_question_preserves_both_spans(self):
        answer = 'Quoted Rohit is text.'
        question = 'Why does Python do that?'
        message = answer + ' ' + question
        admission, _ = evaluate_output(proposal(answer=answer, question=question), self.context(message))
        self.assertEqual('CONTINUE', admission['conversation_status'])
        self.assertTrue(admission['answer_admitted'])
        self.assertIn('QUESTION', admission['intents']['secondary'])
        self.assertEqual(question, admission['intents']['question_span'])
        verify_admission(admission, message)

    def test_question_mark_in_answer_is_not_a_punctuation_veto(self):
        message = 'Quotes give the text itself, right? The unquoted name uses its assigned value.'
        result = proposal(answer=message)
        admission, _ = evaluate_output(result, self.context(message))
        self.assertEqual('CONTINUE', admission['conversation_status'])
        self.assertTrue(admission['answer_admitted'])
        self.assertEqual(message, admission['intents']['answer_span'])

    def test_pure_question_and_confusion_overlap_cannot_supply_answer_evidence(self):
        for message, field in [('What is Rohit?', 'question'), ("I don't understand", 'confusion')]:
            with self.subTest(message=message):
                result = proposal(answer=message, **{field: message})
                admission, shown = evaluate_output(result, self.context(message))
                self.assert_recovery(admission, shown)

    def test_check_my_understanding_is_parent_control_even_if_model_says_answer(self):
        message = 'check my understanding'
        self.assertEqual('PEDAGOGICAL_CONTROL', classify(message))
        self.assertEqual([], candidate_answers(message))
        self.assertEqual(['PEDAGOGICAL_CONTROL'], intent_hint(message)['possible_intents'])
        result = proposal(answer=message)
        original = copy.deepcopy(result)
        admission, shown = evaluate_output(result, self.context(message))
        self.assertEqual('CONTINUE', admission['conversation_status'])
        self.assertEqual('PEDAGOGICAL_CONTROL', admission['intents']['primary'])
        self.assertEqual('REQUEST_FRESH_CHECK', admission['learner_control']['action'])
        self.assertEqual('exact_command', admission['learner_control']['origin'])
        self.assertNotIn('answer_span', admission['learner_verified_spans'])
        self.assertEqual('not_applicable', admission['judgment'])
        self.assertFalse(admission['answer_admitted'])
        self.assertEqual('not_applicable', shown['pedagogy']['judgment'])
        self.assertEqual(original['pedagogy']['intents'], admission['model_interpretation'])
        self.assertEqual(original, result)
        verify_admission(admission, message)

    def test_embedded_check_phrase_does_not_override_genuine_answer(self):
        message = 'Quoted Rohit is text; please check my understanding.'
        answer = 'Quoted Rohit is text'
        admission, _ = evaluate_output(proposal(answer=answer), self.context(message))
        self.assertTrue(admission['answer_admitted'])
        self.assertIsNone(admission['learner_control'])

    def test_fresh_check_exits_profile_without_reviving_retired_question(self):
        state = select_state(self.state, INTERVENE, QUESTION)
        state = carried_state({'supervision_state': state}, 'check my understanding')
        self.assertEqual('NORMAL', state['profile'])
        self.assertIn(hashed(QUESTION), state['retired_questions'])
        context = control_context(self.context('check my understanding'), state)
        result = proposal(question='check my understanding')
        fresh = 'Describe a new name and the value it refers to.'
        result['diagnostic_question'] = fresh
        admission, shown = evaluate_output(result, context)
        admission, shown, state, _ = apply_control(admission, shown, state, context)
        self.assertEqual('CONTINUE', admission['conversation_status'])
        self.assertEqual(fresh, shown['diagnostic_question'])
        self.assertEqual('not_applicable', admission['judgment'])
        self.assertFalse(admission['answer_admitted'])
        self.assertTrue(admission['evidence_requirement_unresolved'])
        next_context = turn_context(self.orientation, {'teaching': shown}, 'The name refers to its latest assigned value.', [])
        admission, _ = evaluate_output(proposal(answer=next_context['C_turn']['learner_message']), next_context)
        self.assertTrue(admission['answer_admitted'])
        self.assertFalse(admission['grants_mastery'])

    def test_parent_task_requirement_cannot_be_overridden_by_model_route(self):
        message = 'What is the current release?'
        context = self.context(message)
        context['task_metadata']['required_knowledge_task'] = 'version_sensitive'
        result = proposal(question=message)
        result['pedagogy']['routing'] = {'knowledge_task': 'stable_fundamentals'}
        admission, shown = evaluate_output(result, context)
        self.assert_recovery(admission, shown)
        self.assertEqual('parent_task_metadata', admission['semantic_route']['knowledge_origin'])
        self.assertEqual('version_sensitive', admission['semantic_route']['knowledge_task'])

    def test_invalid_parent_task_metadata_still_fails_hard(self):
        for field, value in [('unlocked_capability', 'C7'), ('required_knowledge_task', 'unlock'),
                             ('default_knowledge_task', 'anything')]:
            context = self.context('The value is 7.')
            context['task_metadata'][field] = value
            result = proposal(answer='The value is 7.')
            result['pedagogy']['routing'] = {'knowledge_task': 'stable_fundamentals'}
            with self.subTest(field=field), self.assertRaises(ValueError):
                evaluate_output(result, context)

    def test_source_curriculum_and_future_semantics_recover_without_disclosure(self):
        cases = [('What does the book say?', {'knowledge_task': 'source_specific'}),
                 ('What does the curriculum require?', {'knowledge_task': 'curriculum_requirement'}),
                 ('What does the regulation require?', {'knowledge_task': 'regulatory'}),
                 ('Teach agent design now.', {'teaching_scope': 'future_depth'}),
                 ('I meant something else.', {'knowledge_task': 'uncertain'})]
        for message, routing in cases:
            with self.subTest(message=message):
                result = proposal(question=message)
                result['pedagogy']['routing'] = routing
                admission, shown = evaluate_output(result, self.context(message))
                self.assert_recovery(admission, shown)
                self.assertNotEqual(result['explanation'], shown['explanation'])
                self.assertEqual('SEMANTIC_UNCERTAINTY', admission['failure_class'])

    def test_malformed_routing_and_hard_authority_still_fail_closed(self):
        message = 'The latest assigned value is 7.'
        for routing in [{'knowledge_task': 'unlock_stage'}, {'tools': 'shell'}, [], {'teaching_scope': 7}]:
            result = proposal(answer=message)
            result['pedagogy']['routing'] = routing
            with self.subTest(routing=routing), self.assertRaises(ValueError):
                evaluate_output(result, self.context(message))
        for mutation in [{'grants_mastery': True}, {'current_location': 'C7'}, {'curriculum_version': '0.9'},
                         {'knowledge_classes': ['verified_external_source']}, {'tools': ['shell']}]:
            result = proposal(answer=message)
            result['pedagogy'].update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                evaluate_output(result, self.context(message))

    def test_python_for_loop_does_not_trigger_supervision_or_fallback(self):
        for message in ['What is a for loop?', 'What are Python loops?', 'Explain the last assigned value.']:
            with self.subTest(message=message):
                provider = FakeProvider(fail=True)
                state, audit = self.supervise(self.view(message), provider)
                self.assertEqual('NOT_INVOKED', audit['status'])
                self.assertEqual(self.state, state)
                self.assertEqual(0, provider.calls)
                self.assertFalse(audit['trigger_evidence']['fallback_eligible'])

    def test_loop_complaint_with_context_can_receive_model_review(self):
        provider = FakeProvider()
        state, audit = self.supervise(self.view('you are just moving in loops'), provider)
        self.assertEqual('APPROVED', audit['status'])
        self.assertIn('REPETITION_LOOP', audit['trigger'])
        self.assertEqual('ORIENTATION', state['profile'])
        self.assertEqual(1, provider.calls)
        self.assertFalse(audit['trigger_evidence']['fallback_eligible'])
        self.assertFalse(audit['trigger_evidence']['structural'])

    def test_failed_review_of_lexical_complaint_cannot_change_supervisor_state(self):
        for provider in [FakeProvider(fail=True), FakeProvider(dict(INTERVENE, tools=['shell']))]:
            with self.subTest(provider=provider):
                state, audit = self.supervise(self.view('you are just moving in loops'), provider)
                self.assertEqual('SUPERVISION_FAILED', audit['status'])
                self.assertEqual(self.state, state)
                self.assertNotIn('fallback', audit)
                self.assertFalse(audit['trigger_evidence']['fallback_eligible'])

    def test_structural_repetition_allows_explicit_fallback(self):
        view = self.view('Please explain.', self.repeated_history())
        self.assertEqual(2, view['exact_question_repetitions'])
        state, audit = self.supervise(view, FakeProvider(fail=True))
        self.assertEqual('SUPERVISION_FAILED', audit['status'])
        self.assertTrue(audit['trigger_evidence']['fallback_eligible'])
        self.assertEqual('DETERMINISTIC_ORIENTATION', audit['fallback'])
        self.assertEqual('ORIENTATION', state['profile'])
        self.assertEqual(['REPETITION_LOOP'], audit['fallback_directive']['reason_codes'])
        self.assertEqual(1, audit['request_reservations'])

    def test_supervisor_no_change_preserves_state_despite_lexical_complaint(self):
        state, audit = self.supervise(self.view('you are just moving in loops'), FakeProvider(NORMAL))
        self.assertEqual('APPROVED', audit['status'])
        self.assertEqual(self.state, state)
        self.assertNotIn('fallback', audit)

    def test_prior_intervention_resets_structural_fallback_window(self):
        history = self.repeated_history()
        history[-1]['supervision'] = {'directive': INTERVENE}
        evidence = trigger_evidence(self.view('you are just moving in loops', history))
        self.assertIn('REPETITION_LOOP', evidence['candidates'])
        self.assertFalse(evidence['fallback_eligible'])

    def test_shared_truncated_question_prefix_is_not_structural_repetition(self):
        history = self.repeated_history()
        for index, item in enumerate(history):
            item['question'] = 'A long distinct understanding check. ' * 20 + str(index)
        view = self.view('Please explain.', history)
        self.assertEqual(0, view['exact_question_repetitions'])
        self.assertEqual(view['recent'][0]['question'], view['recent'][1]['question'])
        self.assertFalse(trigger_evidence(view)['fallback_eligible'])

    def test_requested_check_without_question_recovers_and_preserves_evidence(self):
        result = proposal(question='check my understanding')
        result['diagnostic_question'] = ''
        admission, shown = evaluate_output(result, self.context('check my understanding'))
        self.assert_recovery(admission, shown)

    def test_display_uses_one_explanation_without_duplicate_intent_responses(self):
        main = 'I understand the confusion. Quoted Rohit is text.'
        result = proposal(confusion='I am confused')
        result['explanation'] = main
        result['miniature_example'] = 'label = 7\nlabel'
        result['pedagogy']['intent_responses'] = {'clarification': main, 'question': main,
                                                'confusion': 'I understand the confusion.'}
        report = {'teaching': result, 'display_teaching': result,
                  'pedagogy_admission': {'judgment': 'not_applicable'}}
        original = copy.deepcopy(report)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            display_teaching(report)
        printed = output.getvalue()
        self.assertEqual(1, printed.count(main))
        self.assertEqual(1, printed.count('I understand the confusion.'))
        self.assertEqual(1, printed.count(result['miniature_example']))
        self.assertEqual(1, printed.count(result['diagnostic_question']))
        self.assertEqual(original, report)
        self.assertIn('intent_responses', result['pedagogy'])

    def test_exact_response_and_semantic_route_survive_saved_ledger_reload(self):
        raw = FIXTURE.read_bytes()
        result = json.loads(raw)
        message = PROVENANCE['learner_message']
        context = self.context(message)
        admission, shown = evaluate_output(result, context)
        config = json.loads((ROOT / 'config/hermes-live.json').read_text())
        manifest = json.loads((ROOT / 'content/sources.json').read_text())
        call = str(uuid4())
        directory = self.root / call
        directory.mkdir()
        excerpt = 'Synthetic approved excerpt for persistence regression.'
        previous = dict(self.previous, excerpt=excerpt, parent_call_id='synthetic-parent',
                        parent_event_id=None, parent_report_sha256='synthetic-hash')
        _, continuation = continuation_input(previous, message)
        final = raw.decode().rstrip('\n')
        report = {'status': 'PASS', 'call_id': call, 'teaching': result,
                  'response_sha256': digest(final), 'display_teaching': shown,
                  'pedagogy_admission': admission, 'turn_context': context, 'continuation': continuation,
                  'provenance': {'source_id': config['source_id'], 'source_sha256': config['source_sha256'],
                                 'sections': ['Concepts to own', config['source_section']],
                                 'excerpt_sha256': digest(excerpt), 'manifest_sha256': digest(canonical(manifest)),
                                 'exercise_sha256': digest(canonical(EXERCISE))}}
        store = Store(directory / 'acceptance.sqlite3')
        session = store.start(EXERCISE)
        record_result(store, call, session['id'], report)
        self.assertEqual('teaching', store.resume()['session']['phase'])
        store.close()
        (directory / 'report.json').write_text(canonical(dict(report, parent_ledger_record_verified=True)))
        (directory / 'provider-response.json').write_text(canonical({'choices': [{'message': {'content': final}}]}))
        (directory / 'teaching-response.json').write_bytes(raw)
        (directory / 'approved-excerpt.txt').write_text(excerpt)
        loaded = load_previous(self.root, call, manifest, config, EXERCISE)
        self.assertEqual('partial', loaded['history'][-1]['pedagogy_admission']['judgment'])
        self.assertEqual(admission['semantic_route'], loaded['history'][-1]['pedagogy_admission']['semantic_route'])
        self.assertEqual(message, loaded['history'][-1]['learner_message'])
        self.assertNotIn('current_location', json.loads((directory / 'teaching-response.json').read_text())['pedagogy'])
        self.assertEqual(raw, (directory / 'teaching-response.json').read_bytes())
        self.assertFalse(loaded['history'][-1]['pedagogy_admission']['grants_mastery'])

    def test_prompt_marks_optional_semantics_and_audit_only_intent_responses(self):
        prompt = build_prompt(self.context('check my understanding'), 'Synthetic approved excerpt.')
        from gurukul.pedagogy import SYSTEM_PROMPT
        self.assertIn('optional_proposal_fields', prompt)
        self.assertIn('PEDAGOGICAL_CONTROL', prompt)
        self.assertIn('surface hints have no authority', SYSTEM_PROMPT)
        self.assertIn('audit fields, not automatically displayed', SYSTEM_PROMPT)


if __name__ == '__main__':
    unittest.main()
