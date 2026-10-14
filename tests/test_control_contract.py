"""Exact GURU-004H failures; offline regressions do not prove live model compliance."""
import contextlib
import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from test_pedagogy import ROOT, EXERCISE
from test_mixed_intents import proposal, QUESTION
from test_semantic_authority import display_teaching
from gurukul.pedagogy import (orientation, turn_context, build_prompt, SYSTEM_PROMPT,
                             normalize_response_layout, response_layout_binding, validate_response)
from gurukul.teaching_output import evaluate_output
from gurukul.learner_input import verify_admission
from gurukul.hermes_continuation import continuation_input, load_previous, digest
from gurukul.hermes_teaching import record_result
from gurukul.maharishi import carried_state, select_state, control_context, apply_control, PROFILES
from gurukul.store import Store, canonical

FIXTURES=ROOT/'tests/fixtures'
RECORDS={x['call_id'][:8]:x for x in json.loads((FIXTURES/'guru_004h_control_failures-provenance.json').read_text())}


class ControlContractTests(unittest.TestCase):
    def setUp(self):
        self.orientation,_=orientation(ROOT,EXERCISE)
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.root_call=str(uuid4());(self.root/self.root_call).mkdir()
        self.store=Store(self.root/self.root_call/'acceptance.sqlite3');self.session=self.store.start(EXERCISE)
        self.config=json.loads((ROOT/'config/hermes-live.json').read_text())
        self.manifest=json.loads((ROOT/'content/sources.json').read_text())
        self.previous={'teaching':{'explanation':'Prior explanation','diagnostic_question':QUESTION,
                                  'pedagogy':{'strategy':'comparison','next_activity':'predict'}},
                       'excerpt':'Synthetic approved excerpt','parent_call_id':'synthetic',
                       'parent_event_id':None,'parent_report_sha256':'synthetic'}

    def tearDown(self):self.store.close();self.tmp.cleanup()

    def fixture(self,short):return json.loads((FIXTURES/RECORDS[short]['fixture']).read_text())

    def context(self,short):
        entry=RECORDS[short];previous=copy.deepcopy(self.previous)
        previous['teaching']['diagnostic_question']=entry['active_question']
        return turn_context(self.orientation,previous,entry['learner_message'],[])

    def save(self,result,admission,shown,context,previous=None,call=None):
        call=call or self.root_call;directory=self.root/call;directory.mkdir(exist_ok=True)
        _,continuation=continuation_input(previous or self.previous,context['C_turn']['learner_message'])
        final=canonical(result)
        for entry in RECORDS.values():
            raw=(FIXTURES/entry['fixture']).read_text().rstrip('\n')
            if result==json.loads(raw):
                final=raw
                break
        excerpt=self.previous['excerpt']
        proof={'source_id':self.config['source_id'],'source_sha256':self.config['source_sha256'],
               'sections':['Concepts to own',self.config['source_section']],'excerpt_sha256':digest(excerpt),
               'manifest_sha256':digest(canonical(self.manifest)),'exercise_sha256':digest(canonical(EXERCISE))}
        report={'status':'PASS','runtime_status':'PASS','call_id':call,'root_call_id':self.root_call,
                'teaching':result,'response_sha256':digest(final),'provenance':proof,
                'display_teaching':shown,'pedagogy_admission':admission,'turn_context':context,
                'continuation':continuation}
        record_result(self.store,call,self.session['id'],report)
        (directory/'report.json').write_text(canonical(dict(report,parent_ledger_record_verified=True)))
        (directory/'provider-response.json').write_text(canonical({'choices':[{'message':{'content':final}}]}))
        (directory/'teaching-response.json').write_text(final);(directory/'approved-excerpt.txt').write_text(excerpt)
        return directory,report

    def test_exact_nested_ba8_response_recovers_without_inventing_question_or_fields(self):
        r=self.fixture('ba8b8c0b');original=copy.deepcopy(r)
        normalized,moves=normalize_response_layout(r)
        missing=RECORDS['ba8b8c0b']['reported_validation_diagnostics']['missing_keys']
        for field in missing:self.assertEqual(r['pedagogy']['intent_responses'][field],normalized['pedagogy'][field])
        self.assertEqual(13,len(moves));self.assertEqual(original,r)
        a,shown=evaluate_output(r,self.context('ba8b8c0b'))
        self.assertEqual('NEEDS_CLARIFICATION',a['conversation_status'])
        self.assertEqual(original['explanation'],shown['explanation'])
        self.assertEqual('',shown['diagnostic_question']);self.assertIn('recovery_notice',shown)
        self.assertEqual('REQUEST_FRESH_CHECK',a['learner_control']['action'])
        self.assertFalse(a['answer_admitted']);self.assertFalse(a['grants_mastery'])
        self.assertEqual(original['pedagogy']['intents'],a['model_interpretation'])
        self.assertEqual(response_layout_binding(original),a['response_layout_binding'])
        verify_admission(a,RECORDS['ba8b8c0b']['learner_message'])

    def test_exact_fixture_hashes_and_saved_provider_content_match_supplied_bodies(self):
        for short,entry in RECORDS.items():
            with self.subTest(short=short):
                raw=(FIXTURES/entry['fixture']).read_text().rstrip('\n')
                self.assertEqual(entry['message_content_sha256'],hashlib.sha256(raw.encode()).hexdigest())
                r=json.loads(raw);context=self.context(short);a,shown=evaluate_output(r,context)
                directory,_=self.save(r,a,shown,context,call=str(uuid4()))
                wire=json.loads((directory/'provider-response.json').read_text())
                self.assertEqual(raw,wire['choices'][0]['message']['content'])
                self.assertEqual(raw,(directory/'teaching-response.json').read_text())

    def test_exact_ignored_check_preserves_feedback_and_identifies_missing_question(self):
        r=self.fixture('e34db245');a,shown=evaluate_output(r,self.context('e34db245'))
        self.assertEqual('NEEDS_CLARIFICATION',a['conversation_status'])
        self.assertEqual('A requested fresh check needs a new diagnostic question',a['reason'])
        self.assertEqual(r['explanation'],shown['explanation'])
        self.assertIn('did not supply a new question',shown['recovery_notice'])
        self.assertEqual('not_applicable',a['judgment']);self.assertFalse(a['answer_admitted'])

    def test_exact_three_clarifications_display_without_strategy_echo_burden(self):
        for short in ['2392e6af','d7aba191','780ff6d4']:
            with self.subTest(short=short):
                r=self.fixture(short);original=copy.deepcopy(r);a,shown=evaluate_output(r,self.context(short))
                self.assertEqual('CONTINUE',a['conversation_status'])
                self.assertEqual(original['explanation'],shown['explanation'])
                self.assertEqual('clarification',shown['pedagogy']['strategy'])
                self.assertEqual('META_QUESTION',a['intents']['primary'])
                self.assertEqual('not_applicable',a['judgment']);self.assertFalse(a['answer_admitted'])
                self.assertFalse(a['grants_mastery']);self.assertEqual('',shown['diagnostic_question'])
                self.assertEqual(original,r)
                verify_admission(a,RECORDS[short]['learner_message'])

    def test_unbound_secondary_control_has_no_action_and_remains_in_raw_proposal(self):
        r=self.fixture('780ff6d4');a,_=evaluate_output(r,self.context('780ff6d4'))
        self.assertIn('PEDAGOGICAL_CONTROL',a['model_interpretation']['secondary'])
        self.assertNotIn('PEDAGOGICAL_CONTROL',a['intents']['secondary'])
        self.assertEqual('',a['intents']['control_span']);self.assertIsNone(a['learner_control'])
        self.assertTrue(any('Unbound secondary control' in x for x in a['conversation_observations']))

    def test_explicit_control_action_still_requires_bound_span(self):
        r=self.fixture('780ff6d4');r['pedagogy']['routing']={'control_action':'REQUEST_FRESH_CHECK'}
        r['diagnostic_question']='Describe a new name.'
        a,_=evaluate_output(r,self.context('780ff6d4'))
        self.assertEqual('NEEDS_CLARIFICATION',a['conversation_status'])
        self.assertFalse(a['answer_admitted'])

    def test_bad_control_reference_cannot_be_dropped_as_an_optional_label(self):
        r=self.fixture('780ff6d4');r['pedagogy']['intents']['control_span']={'ref':'s999'}
        a,shown=evaluate_output(r,self.context('780ff6d4'))
        self.assertEqual('NEEDS_CLARIFICATION',a['conversation_status'])
        self.assertIn('Interpretation reference rejected',a['reason'])
        self.assertNotEqual(r['explanation'],shown['explanation'])

    def test_future_deferral_flag_does_not_classify_entire_reply_as_future_lesson(self):
        r=self.fixture('780ff6d4');a,_=evaluate_output(r,self.context('780ff6d4'))
        self.assertTrue(r['pedagogy']['future_topic_deferred'])
        self.assertEqual('current_capability',a['semantic_route']['teaching_scope'])
        self.assertGreater(len(r['explanation'].split()),100)
        self.assertLess(len(r['explanation'].split()),180)

    def test_actual_future_depth_and_unsafe_claims_remain_suppressed(self):
        for routing in [{'teaching_scope':'future_depth'}, {'knowledge_task':'version_sensitive'},
                        {'knowledge_task':'regulatory'}]:
            r=self.fixture('d7aba191');r['pedagogy']['routing']=routing
            a,shown=evaluate_output(r,self.context('d7aba191'))
            self.assertEqual('NEEDS_CLARIFICATION',a['conversation_status'])
            self.assertNotEqual(r['explanation'],shown['explanation'])

    def test_fresh_check_failure_cannot_display_unsafe_future_or_current_source_claim(self):
        for routing in [{'teaching_scope':'future_depth'}, {'knowledge_task':'version_sensitive'}]:
            r=self.fixture('e34db245');r['pedagogy']['routing']=routing
            a,shown=evaluate_output(r,self.context('e34db245'))
            self.assertEqual('NEEDS_CLARIFICATION',a['conversation_status'])
            self.assertNotEqual(r['explanation'],shown['explanation'])
            self.assertNotIn('recovery_notice',shown)

    def test_layout_repair_never_invents_genuinely_missing_core(self):
        r=self.fixture('ba8b8c0b');del r['pedagogy']['intent_responses']['grants_mastery']
        with self.assertRaises(ValueError):evaluate_output(r,self.context('ba8b8c0b'))

    def test_layout_repair_cannot_hide_mastery_curriculum_provenance_or_code_violation(self):
        for field,value in [('grants_mastery',True),('current_location','C7'),('curriculum_version','0.9'),
                            ('knowledge_classes',['verified_external_source']),('strategy','unlock')]:
            r=self.fixture('ba8b8c0b');r['pedagogy']['intent_responses'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):evaluate_output(r,self.context('ba8b8c0b'))
        r=self.fixture('ba8b8c0b');r['miniature_example']='import os'
        with self.assertRaises(ValueError):evaluate_output(r,self.context('ba8b8c0b'))

    def test_unknown_or_duplicate_nested_fields_fail_closed(self):
        for change in ['unknown','duplicate','control_duplicate']:
            r=self.fixture('ba8b8c0b')
            if change=='unknown':r['pedagogy']['intent_responses']['tools']=['shell']
            if change=='duplicate':r['pedagogy']['concept']='names_values'
            if change=='control_duplicate':r['pedagogy']['intents']['control_span']={'ref':'s0'}
            with self.subTest(change=change),self.assertRaises(ValueError):evaluate_output(r,self.context('ba8b8c0b'))

    def test_relocated_correct_authority_echo_is_not_reported_as_omitted(self):
        r=self.fixture('ba8b8c0b')
        r['pedagogy']['intent_responses'].update(current_location='C0-B01-D01',curriculum_version='0.8.3')
        a,_=evaluate_output(r,self.context('ba8b8c0b'))
        self.assertEqual([],a['response_authority_binding']['omitted_model_echoes'])

    def test_prompt_exposes_parent_control_and_unambiguous_nested_structure(self):
        context=self.context('e34db245');control=context['learner_control']
        self.assertEqual('REQUEST_FRESH_CHECK',control['action'])
        self.assertEqual('parent_exact_command',control['origin']);self.assertTrue(control['requires_new_question'])
        self.assertFalse(control['answer_evidence']);self.assertFalse(control['grants_mastery'])
        prompt=build_prompt(context,'Synthetic approved excerpt')
        contract=json.loads(prompt.split('GURU RESPONSE CONTRACT JSON:\n')[1].split('\nAPPROVED SOURCE EXCERPT')[0])
        self.assertIn('control_span',contract['nested_keys']['pedagogy.intents'])
        self.assertEqual(['clarification','question','confusion'],contract['nested_keys']['pedagogy.intent_responses'])
        self.assertIn('overrides an earlier pause',SYSTEM_PROMPT)
        self.assertIn('direct pedagogy',SYSTEM_PROMPT)

    def test_embedded_check_phrase_is_still_not_an_exact_parent_command(self):
        c=turn_context(self.orientation,self.previous,'Quoted Rohit is text; please check my understanding.',[])
        self.assertNotIn('learner_control',c)

    def test_all_profiles_keep_layout_repair_ungraded_and_authority_pinned(self):
        directive={'decision':'INTERVENE','profile':'ORIENTATION','reason_codes':['HARNESS_CONFLICT'],
                   'confidence':'low','exit_condition':'TTL','constitutional_change':False}
        for profile in PROFILES:
            with self.subTest(profile=profile):
                r=self.fixture('780ff6d4');context=self.context('780ff6d4');state=carried_state(None,'')
                if profile!='NORMAL':state=select_state(state,dict(directive,profile=profile),QUESTION)
                context=control_context(context,state);a,shown=evaluate_output(r,context)
                a,shown,_,_=apply_control(a,shown,state,context)
                self.assertEqual('CONTINUE',a['conversation_status'])
                self.assertEqual(r['explanation'],shown['explanation'])
                self.assertFalse(a['answer_admitted']);self.assertFalse(a['grants_mastery'])
                self.assertEqual('C0-B01-D01',shown['pedagogy']['current_location'])
                self.assertEqual('teaching',self.store.resume()['session']['phase'])

    def test_nested_layout_survives_reload_with_raw_bytes_and_derived_history_separate(self):
        r=self.fixture('ba8b8c0b');context=self.context('ba8b8c0b');a,shown=evaluate_output(r,context)
        directory,report=self.save(r,a,shown,context)
        raw=(directory/'teaching-response.json').read_bytes()
        loaded=load_previous(self.root,self.root_call,self.manifest,self.config,EXERCISE)
        self.assertEqual(raw,(directory/'teaching-response.json').read_bytes())
        self.assertEqual(r,report['teaching']);self.assertNotIn('concept',report['teaching']['pedagogy'])
        self.assertEqual('names_values',loaded['history'][-1]['pedagogy']['concept'])
        self.assertEqual('not_applicable',loaded['history'][-1]['pedagogy']['judgment'])
        self.assertEqual(r['explanation'],loaded['teaching']['explanation'])

    def test_layout_binding_is_recomputed_even_if_report_matches_ledger(self):
        r=self.fixture('ba8b8c0b');context=self.context('ba8b8c0b');a,shown=evaluate_output(r,context)
        a['response_layout_binding']['moves'][0]['to']='pedagogy.grants_mastery'
        self.save(r,a,shown,context)
        with self.assertRaisesRegex(ValueError,'layout binding changed'):
            load_previous(self.root,self.root_call,self.manifest,self.config,EXERCISE)

    def test_requested_check_answer_stops_unsolicited_recall_and_retains_artifact_evidence(self):
        request='check my understanding';r=proposal(question=request)
        fresh='Which value does a name refer to after reassignment?';r['diagnostic_question']=fresh
        context=turn_context(self.orientation,self.previous,request,[]);a,shown=evaluate_output(r,context)
        self.save(r,a,shown,context)
        previous=load_previous(self.root,self.root_call,self.manifest,self.config,EXERCISE)
        answer='The value assigned later.'
        context=turn_context(self.orientation,previous,answer,previous['history'])
        self.assertTrue(context['turn_policy']['requested_check_active'])
        reply=proposal(answer=answer);reply['diagnostic_question']=QUESTION
        a,shown=evaluate_output(reply,context)
        self.assertEqual('CONTINUE',a['conversation_status']);self.assertTrue(a['answer_admitted'])
        self.assertEqual('correct',a['judgment']);self.assertTrue(a['requested_check_completed'])
        self.assertEqual('',shown['diagnostic_question']);self.assertEqual('pause',shown['pedagogy']['next_activity'])
        self.assertEqual('',a['pending_question']);self.assertEqual('',a['unresolved_evidence_question'])
        self.assertIn('source file',a['unmet_evidence_requirement']);self.assertFalse(a['grants_mastery'])
        call=str(uuid4());self.save(reply,a,shown,context,previous,call)
        loaded=load_previous(self.root,call,self.manifest,self.config,EXERCISE)
        self.assertEqual('',loaded['teaching']['diagnostic_question']);self.assertEqual('',loaded['unresolved_evidence_question'])
        self.assertEqual('pause',loaded['teaching']['pedagogy']['next_activity'])
        self.assertEqual('teaching',self.store.resume()['session']['phase'])

    def test_partial_requested_check_answer_can_still_request_missing_evidence(self):
        history=[{'question':QUESTION,'pedagogy_admission':{'conversation_status':'CONTINUE',
                 'question_displayed':True,'learner_control':{'action':'REQUEST_FRESH_CHECK','bound':True}}}]
        context=turn_context(self.orientation,self.previous,'I think the earlier value.',history)
        self.assertTrue(context['turn_policy']['requested_check_active'])
        r=proposal(answer='I think the earlier value.');r['pedagogy']['judgment']='partial'
        a,shown=evaluate_output(r,context)
        self.assertTrue(a['answer_admitted']);self.assertFalse(a['requested_check_completed'])
        self.assertTrue(shown['diagnostic_question'])

    def start_requested_check(self):
        request='check my understanding';r=proposal(question=request)
        r['diagnostic_question']='Predict: if a name refers to 4, then is reassigned to 9, what value will printing that name show afterward, and why?'
        r['pedagogy'].update(concept='reassignment',strategy='prediction',next_activity='predict')
        context=turn_context(self.orientation,self.previous,request,[])
        a,shown=evaluate_output(r,context);self.save(r,a,shown,context)
        return load_previous(self.root,self.root_call,self.manifest,self.config,EXERCISE)

    def save_partial_check_answer(self,previous):
        answer='9 because it is the first value the variable will look for on running the code'
        r=proposal(answer=answer);r['pedagogy']['intents']['answer_span']={'ref':'s0'}
        r['diagnostic_question']='Now suppose the name is reassigned from 9 to 4 before it is printed. What will printing it show, and what changed?'
        r['pedagogy'].update(concept='reassignment',judgment='partial',strategy='variation',next_activity='variation')
        context=turn_context(self.orientation,previous,answer,previous['history'])
        a,shown=evaluate_output(r,context)
        self.assertEqual('CONTINUE',a['conversation_status']);self.assertTrue(a['answer_admitted'])
        self.assertFalse(a['requested_check_completed']);self.assertTrue(shown['diagnostic_question'])
        call=str(uuid4());self.save(r,a,shown,context,previous,call)
        return load_previous(self.root,call,self.manifest,self.config,EXERCISE)

    def test_requested_check_survives_partial_followup_and_closes_after_correct_answer(self):
        previous=self.save_partial_check_answer(self.start_requested_check())
        answer='the value would change to 4 because it has been reassigned'
        context=turn_context(self.orientation,previous,answer,previous['history'])
        self.assertTrue(context['turn_policy']['requested_check_active'])
        r=proposal(answer=answer);r['pedagogy'].update(concept='reassignment',strategy='variation',next_activity='variation')
        r['diagnostic_question']='Explain quoted and unquoted text again.';original=copy.deepcopy(r)
        a,shown=evaluate_output(r,context)
        self.assertEqual('CONTINUE',a['conversation_status']);self.assertTrue(a['answer_admitted'])
        self.assertTrue(a['requested_check_completed']);self.assertEqual('',a['pending_question'])
        self.assertEqual('',a['unresolved_evidence_question']);self.assertEqual('',shown['diagnostic_question'])
        self.assertEqual('pause',shown['pedagogy']['next_activity']);self.assertEqual(original,r)
        verify_admission(a,answer);self.assertFalse(a['grants_mastery']);self.assertIn('source file',a['unmet_evidence_requirement'])
        call=str(uuid4());self.save(r,a,shown,context,previous,call)
        loaded=load_previous(self.root,call,self.manifest,self.config,EXERCISE)
        self.assertEqual('',loaded['teaching']['diagnostic_question']);self.assertEqual('',loaded['unresolved_evidence_question'])
        self.assertEqual('pause',loaded['history'][-1]['pedagogy']['next_activity'])
        self.assertFalse(turn_context(self.orientation,loaded,'What evidence is required?',loaded['history'])['turn_policy']['requested_check_active'])
        self.assertEqual('teaching',self.store.resume()['session']['phase'])

    def test_correct_followup_pause_clears_the_answered_pending_question(self):
        previous=self.save_partial_check_answer(self.start_requested_check())
        answer='the value would change to 4 because it has been reassigned'
        context=turn_context(self.orientation,previous,answer,previous['history'])
        r=proposal(answer=answer);r['diagnostic_question']=''
        r['pedagogy'].update(concept='reassignment',strategy='clarification',next_activity='pause')
        a,shown=evaluate_output(r,context)
        self.assertEqual('CONTINUE',a['conversation_status']);self.assertTrue(a['requested_check_completed'])
        self.assertEqual('',a['pending_question']);self.assertEqual('',a['unresolved_evidence_question'])
        self.assertEqual('',shown['diagnostic_question']);self.assertFalse(a['grants_mastery'])

    def test_requested_check_survives_ungraded_clarification_without_a_new_question(self):
        previous=self.start_requested_check();question='What changed when it was reassigned?'
        r=proposal(question=question);r['diagnostic_question']='';r['pedagogy'].update(strategy='clarification',next_activity='pause')
        context=turn_context(self.orientation,previous,question,previous['history']);a,shown=evaluate_output(r,context)
        self.assertFalse(a['answer_admitted']);self.assertEqual('CONTINUE',a['conversation_status'])
        call=str(uuid4());self.save(r,a,shown,context,previous,call)
        loaded=load_previous(self.root,call,self.manifest,self.config,EXERCISE)
        answer='The name now refers to 9.';context=turn_context(self.orientation,loaded,answer,loaded['history'])
        self.assertTrue(context['turn_policy']['requested_check_active'])
        a,shown=evaluate_output(proposal(answer=answer),context)
        self.assertTrue(a['requested_check_completed']);self.assertEqual('',shown['diagnostic_question'])

    def test_requested_check_survives_reference_recovery_without_false_completion(self):
        previous=self.start_requested_check();answer='The name refers to 9.'
        r=proposal(answer=answer);r['pedagogy']['intents']['answer_span']={'ref':'missing'}
        context=turn_context(self.orientation,previous,answer,previous['history']);a,shown=evaluate_output(r,context)
        self.assertEqual('NEEDS_CLARIFICATION',a['conversation_status']);self.assertFalse(a['answer_admitted'])
        call=str(uuid4());self.save(r,a,shown,context,previous,call)
        loaded=load_previous(self.root,call,self.manifest,self.config,EXERCISE)
        context=turn_context(self.orientation,loaded,answer,loaded['history'])
        self.assertTrue(context['turn_policy']['requested_check_active'])
        a,shown=evaluate_output(proposal(answer=answer),context)
        self.assertTrue(a['requested_check_completed']);self.assertEqual('',shown['diagnostic_question'])

    def test_requested_check_does_not_attach_to_an_unlinked_followup(self):
        previous=self.save_partial_check_answer(self.start_requested_check())
        for changed in ['question_answered','active_question','missing_origin']:
            with self.subTest(changed=changed):
                prior=copy.deepcopy(previous);history=prior['history']
                if changed=='question_answered':history[-1]['question_answered']='Unrelated question.'
                if changed=='active_question':prior['teaching']['diagnostic_question']='Unrelated question.'
                if changed=='missing_origin':history.pop(0)
                context=turn_context(self.orientation,prior,'It refers to 4.',history)
                self.assertFalse(context['turn_policy']['requested_check_active'])

    def test_unbound_or_rejected_control_cannot_start_a_requested_check_trajectory(self):
        previous=self.start_requested_check()
        for changed in ['unbound','rejected','not_displayed']:
            with self.subTest(changed=changed):
                history=copy.deepcopy(previous['history']);admission=history[-1]['pedagogy_admission']
                if changed=='unbound':admission['learner_control']['bound']=False
                if changed=='rejected':admission['conversation_status']='NEEDS_CLARIFICATION'
                if changed=='not_displayed':admission['question_displayed']=False
                context=turn_context(self.orientation,previous,'It refers to 9.',history)
                self.assertFalse(context['turn_policy']['requested_check_active'])

    def test_recovery_display_shows_feedback_and_one_notice_without_duplicate_replies(self):
        r=self.fixture('e34db245');a,shown=evaluate_output(r,self.context('e34db245'))
        report={'teaching':r,'display_teaching':shown,'pedagogy_admission':a};output=io.StringIO()
        with contextlib.redirect_stdout(output):display_teaching(report)
        self.assertEqual(1,output.getvalue().count(r['explanation']))
        self.assertEqual(1,output.getvalue().count(shown['recovery_notice']))

    def test_exact_five_response_sequence_saves_and_resumes_without_generic_reply_loop(self):
        previous=self.previous
        for index,short in enumerate(['ba8b8c0b','e34db245','2392e6af','d7aba191','780ff6d4']):
            r=self.fixture(short);message=RECORDS[short]['learner_message']
            context=turn_context(self.orientation,previous,message,previous.get('history',[]))
            a,shown=evaluate_output(r,context)
            self.assertEqual('NEEDS_CLARIFICATION' if index<2 else 'CONTINUE',a['conversation_status'])
            self.assertEqual(r['explanation'],shown['explanation'])
            self.assertFalse(a['answer_admitted']);self.assertFalse(a['grants_mastery'])
            call=self.root_call if index==0 else str(uuid4())
            self.save(r,a,shown,context,previous,call)
            previous=load_previous(self.root,call,self.manifest,self.config,EXERCISE)
            self.assertEqual(r['explanation'],previous['teaching']['explanation'])
            self.assertEqual('teaching',self.store.resume()['session']['phase'])


if __name__=='__main__':unittest.main()
