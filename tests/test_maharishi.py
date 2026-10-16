"""Synthetic trajectory/provider-boundary regressions; never live acceptance."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from test_pedagogy import ROOT, EXERCISE
from test_mixed_intents import proposal, QUESTION
from gurukul.pedagogy import orientation,turn_context
from gurukul.teaching_output import evaluate_output
from gurukul.maharishi import (validate_directive,carried_state,snapshot,triggers,supervise,
    select_state,control_context,apply_control,PROFILES,HARD_INVARIANTS)
from gurukul.anthropic_supervisor import AnthropicSupervisor
from gurukul.hermes_teaching import record_result
from gurukul.hermes_continuation import load_previous,continuation_input,digest
from gurukul.store import Store,canonical

NORMAL={'decision':'NO_CHANGE','profile':'NORMAL','reason_codes':[],'confidence':'high',
        'exit_condition':'TTL','constitutional_change':False}
INTERVENE=dict(NORMAL,decision='INTERVENE',profile='ORIENTATION',reason_codes=['REPETITION_LOOP'])
CONFIG=json.loads((ROOT/'config/maharishi.json').read_text());CONFIG['model']=CONFIG['candidate_model']

class FakeProvider:
    def __init__(self,directive=None,fail=False):self.calls=0;self.directive=directive or INTERVENE;self.fail=fail
    def decide(self,view):
        self.calls+=1
        if self.fail:raise OSError('secret-looking diagnostic must not be persisted')
        return copy.deepcopy(self.directive),{'provider':'synthetic','actual_cost_usd':None}

class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.orientation,_=orientation(ROOT,EXERCISE)
        self.previous={'teaching':{'explanation':'Prior comparison','diagnostic_question':QUESTION,
                                  'pedagogy':{'strategy':'comparison'}}}
        self.state=carried_state(None,'')
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.store=Store(self.root/'gurukul.sqlite3');self.session=self.store.start(EXERCISE)
    def tearDown(self):self.store.close();self.tmp.cleanup()
    def context(self,text,history=None):return turn_context(self.orientation,self.previous,text,history or [])
    def view(self,text,history=None):return snapshot(self.context(text,history),self.state)
    def decide(self,view,provider=None,limit=4):return supervise(view,self.state,provider or FakeProvider(),self.store,self.session['id'],str(uuid4()),limit)

    def test_healthy_and_single_explanation_skip_provider(self):
        provider=FakeProvider()
        for text in ['The latest assigned value.','explain with an analogy']:
            state,audit=self.decide(self.view(text),provider)
            self.assertEqual('NOT_INVOKED',audit['status']);self.assertEqual(self.state,state)
        context=self.context('explain with an analogy');r=proposal(question='explain with an analogy?')
        r['pedagogy']['next_activity']='pause'
        _,audit=self.decide(snapshot(context,self.state,r,{'answer_admitted':False,'conversation_status':'CONTINUE'}),provider)
        self.assertEqual('NOT_INVOKED',audit['status'])
        self.assertEqual(0,provider.calls)

    def test_repeated_loop_and_explicit_complaint_intervene(self):
        history=[{'event_id':str(i),'learner_message':'Please explain.','question':QUESTION,
                  'pedagogy':{'concept':'names_values','judgment':'not_applicable','strategy':'comparison'},
                  'pedagogy_admission':{'answer_admitted':False,'conversation_status':'NEEDS_CLARIFICATION'}} for i in range(3)]
        for view in [self.view('Please explain.',history),self.view('You are moving in loops.')]:
            state,audit=self.decide(view)
            self.assertEqual('APPROVED',audit['status']);self.assertEqual('ORIENTATION',state['profile'])
            self.assertIn('REPETITION_LOOP',audit['trigger'])

    def test_canonical_failure_trajectory_breaks_loop_before_complaint(self):
        history=[];provider=FakeProvider();intervened=False
        messages=['explain with an analogy','explain it more simply','what are you talking about?',
                  'where did that question come from?','you are just moving in loops']
        for i,message in enumerate(messages):
            context=self.context(message,history);before=copy.deepcopy(context)
            state,audit=self.decide(snapshot(context,self.state),provider)
            if audit['status']=='APPROVED':
                intervened=True
                reply=proposal(question=message+'?')
                reply['diagnostic_question']=QUESTION
                a,d=evaluate_output(reply,control_context(context,state))
                a,d,_,proof=apply_control(a,d,state,context)
                self.assertEqual('',d['diagnostic_question']);self.assertFalse(a['answer_admitted'])
                self.assertFalse(a['grants_mastery']);self.assertTrue(a['evidence_requirement_unresolved'])
                self.assertEqual(before,context);self.assertEqual('teaching',self.store.resume()['session']['phase'])
                break
            history.append({'event_id':str(i),'learner_message':message,'question':QUESTION,
                            'explanation':'Different explanation',
                            'pedagogy':{'strategy':['analogy','explanation'][i%2],'next_activity':'clarify'},
                            'pedagogy_admission':{'answer_admitted':False,'conversation_status':'CONTINUE','judgment':'not_applicable'}})
        self.assertTrue(intervened);self.assertLessEqual(i,4);self.assertEqual(1,provider.calls)

    def test_meta_question_addresses_before_checks_resume(self):
        context=self.context('Where did that question come from?');state,audit=self.decide(snapshot(context,self.state))
        updated=control_context(context,state)
        self.assertIn('explain_question_origin_if_asked',updated['pedagogical_control']['controls']['require'])
        r=proposal(question=context['C_turn']['learner_message']);r['pedagogy']['next_activity']='pause'
        admission,display=evaluate_output(r,updated)
        admission,display,state,proof=apply_control(admission,display,state,updated)
        self.assertEqual('',display['diagnostic_question']);self.assertEqual('not_applicable',admission['judgment'])
        self.assertNotIn('CONFUSION',admission['intents']['secondary'])
        self.assertFalse(admission['grants_mastery']);self.assertTrue(admission['evidence_requirement_unresolved'])

    def test_guru_pause_confusion_trigger(self):
        context=self.context('I am confused')
        r=proposal(confusion='I am confused');r['pedagogy']['next_activity']='pause'
        view=snapshot(context,self.state,r,{'conversation_status':'CONTINUE','answer_admitted':False})
        self.assertIn('GURU_PAUSE',triggers(view))
        state,audit=self.decide(view);self.assertEqual('ORIENTATION',state['profile'])

    def test_retiring_question_keeps_curriculum_and_evidence(self):
        context=self.context('You are moving in loops.');original=copy.deepcopy(context)
        state=select_state(self.state,INTERVENE,QUESTION);updated=control_context(context,state)
        self.assertEqual('',updated['C_turn']['previous_teaching']['diagnostic_question'])
        self.assertEqual(original['orientation'],updated['orientation'])
        self.assertEqual(QUESTION,updated['pedagogical_control']['retired_question'])
        self.assertEqual(original,context)

    def test_normal_control_does_not_change_guru_response(self):
        context=self.context('The most recently assigned value.')
        self.assertEqual(context,control_context(context,self.state))
        r=proposal(answer='The most recently assigned value.');admission,display=evaluate_output(r,context)
        a,d,_,_=apply_control(admission,display,self.state,context)
        self.assertEqual(display,d);self.assertEqual(admission['judgment'],a['judgment'])

    def test_mastery_curriculum_evidence_security_and_unknown_controls_denied(self):
        for key in ['grants_mastery','curriculum','learner_input','tools','security','budget','system_prompt','relax']:
            value=dict(INTERVENE,**{key:True})
            with self.subTest(key=key),self.assertRaises(ValueError):validate_directive(value)
        for value in [dict(INTERVENE,constitutional_change=True),dict(INTERVENE,profile='ASSESSMENT'),
                      dict(INTERVENE,reason_codes=['BYPASS']),dict(NORMAL,profile='ORIENTATION')]:
            with self.assertRaises(ValueError):validate_directive(value)

    def test_active_profile_cannot_bypass_guru_authority_or_input_checks(self):
        context=control_context(self.context('I am confused'),select_state(self.state,INTERVENE,QUESTION))
        for field,value in [('grants_mastery',True),('current_location','C9'),('unapproved_tool','shell')]:
            r=proposal(confusion='I am confused');r['pedagogy'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):evaluate_output(r,context)
        r=proposal(confusion='Invented learner words')
        a,display=evaluate_output(r,context)
        self.assertFalse(a['answer_admitted']);self.assertEqual('not_applicable',a['judgment'])
        self.assertEqual({},a['learner_verified_spans'])
        self.assertEqual('NEEDS_CLARIFICATION',a['conversation_status'])

    def test_supervision_during_assessment_fails_hard_before_provider(self):
        self.store.db.execute("UPDATE sessions SET phase='assessment' WHERE id=?",(self.session['id'],))
        self.store.db.commit();provider=FakeProvider()
        with self.assertRaises(ValueError):self.decide(self.view('You are moving in loops.'),provider)
        self.assertEqual(0,provider.calls)

    def test_invalid_model_directive_fails_to_explicit_deterministic_fallback(self):
        history=[{'event_id':str(i),'question':QUESTION,
                  'pedagogy_admission':{'answer_admitted':False,'conversation_status':'CONTINUE'}} for i in range(3)]
        state,audit=self.decide(self.view('You are moving in loops.',history),FakeProvider(dict(INTERVENE,tools=['shell'])))
        self.assertEqual('SUPERVISION_FAILED',audit['status']);self.assertEqual('ORIENTATION',state['profile'])
        self.assertIsNone(audit['directive']);self.assertEqual('DETERMINISTIC_ORIENTATION',audit['fallback'])
        self.assertEqual(['REPETITION_LOOP'],audit['fallback_directive']['reason_codes'])

    def test_provider_failure_and_budget_preserve_session(self):
        provider=FakeProvider(fail=True)
        state,audit=self.decide(self.view('You are moving in loops.'),provider,limit=1)
        self.assertEqual('SUPERVISION_FAILED',audit['status']);self.assertNotIn('secret-looking',canonical(audit))
        _,audit=self.decide(self.view('You are moving in loops.'),provider,limit=1)
        self.assertEqual(1,provider.calls);self.assertEqual(0,audit['provider_calls'])
        self.assertEqual('teaching',self.store.resume()['session']['phase'])
        self.assertEqual(1,self.store.db.execute("SELECT count(*) FROM events WHERE event_type='supervision.call_reserved'").fetchone()[0])
        self.store.close();self.store=Store(self.root/'gurukul.sqlite3')
        _,audit=self.decide(self.view('You are moving in loops.'),provider,limit=1)
        self.assertEqual(1,provider.calls);self.assertEqual('SUPERVISION_FAILED',audit['status'])

    def test_supervisory_result_and_teaching_event_rollback_together(self):
        self.store.db.execute("CREATE TRIGGER fail_teaching BEFORE INSERT ON events WHEN NEW.event_type='teaching.integration_finished' BEGIN SELECT RAISE(ABORT,'test'); END")
        self.store.db.commit();before=self.store.events()
        with self.assertRaises(Exception):
            record_result(self.store,str(uuid4()),self.session['id'],{'supervision':{'status':'APPROVED'},'grants_mastery':False})
        self.assertEqual(before,self.store.events());self.assertEqual('teaching',self.store.resume()['session']['phase'])

    def test_triggered_no_change_is_real_and_does_not_retire_question(self):
        state,audit=self.decide(self.view('Where did the question come from?'),FakeProvider(NORMAL))
        self.assertEqual('APPROVED',audit['status']);self.assertEqual(self.state,state)

    def test_profiles_expire_and_request_check_exits_without_retrigger(self):
        state=select_state(self.state,INTERVENE,QUESTION)
        context=self.context('I see.');r=proposal(question='What is text?');a,d=evaluate_output(r,self.context('What is text?'))
        for _ in range(2):a,d,state,_=apply_control(a,d,state,context)
        carried=carried_state({'supervision_state':state},'')
        self.assertEqual('NORMAL',carried['profile'])
        state=select_state(self.state,INTERVENE,QUESTION)
        self.assertEqual('NORMAL',carried_state({'supervision_state':state},'check my understanding')['profile'])
        self.assertEqual([],triggers(self.view('check my understanding')))

    def test_no_repeat_invocation_while_profile_active(self):
        self.state=select_state(self.state,INTERVENE,QUESTION);provider=FakeProvider()
        _,audit=self.decide(self.view('You are moving in loops.'),provider)
        self.assertEqual(0,provider.calls);self.assertEqual('NOT_INVOKED',audit['status'])

    def test_model_client_is_single_call_tool_free_and_records_cost(self):
        adapter=AnthropicSupervisor(CONFIG,self.root/'unused')
        response={'model':CONFIG['model'],'stop_reason':'end_turn','content':[{'type':'text','text':canonical(NORMAL)}],
                  'usage':{'input_tokens':100,'output_tokens':50}}
        with patch.object(adapter,'_request',return_value=response) as transport:
            directive,meta=adapter.decide(self.view('Where did that question come from?'))
            body=transport.call_args[0][2]
            self.assertNotIn('tools',body);self.assertNotIn('mcp_servers',body)
            self.assertEqual('between_tools',body['thinking']['type'])
            self.assertAlmostEqual(.0007,meta['estimated_cost_usd'])
            with self.assertRaises(ValueError):adapter.decide(self.view('Again?'))
            self.assertEqual(1,transport.call_count)

    def test_provider_tool_request_incomplete_or_wrong_model_rejected(self):
        for response in [{'model':CONFIG['model'],'stop_reason':'tool_use','content':[]},
                         {'model':'different','stop_reason':'end_turn','content':[]},
                         {'model':CONFIG['model'],'stop_reason':'end_turn','content':[{'type':'tool_use'}]}]:
            adapter=AnthropicSupervisor(CONFIG,self.root/'unused')
            with patch.object(adapter,'_request',return_value=response),self.assertRaises(ValueError):adapter.decide(self.view('Why repeat?'))

    def test_account_model_resolution_and_limits_checked_without_generation(self):
        adapter=AnthropicSupervisor(CONFIG,self.root/'unused')
        model={'id':CONFIG['model'],'max_input_tokens':1000000,'max_tokens':128000,'capabilities':{}}
        with patch.object(adapter,'_request',return_value=model) as transport:
            proof=adapter.verify_model()
            self.assertEqual(('GET','/v1/models/'+CONFIG['model']),transport.call_args[0])
            self.assertEqual(0,proof['generation_calls']);self.assertFalse(adapter.used)
        for invalid in [dict(model,id='unknown'),dict(model,max_input_tokens=3276),dict(model,max_tokens=256)]:
            with patch.object(adapter,'_request',return_value=invalid),self.assertRaises(ValueError):adapter.verify_model()

    def test_provider_config_cannot_expand_budget_enable_tools_or_retry(self):
        for key,value in [('max_requests_per_session',5),('max_requests_per_episode',2),
                          ('max_output_tokens',513),('tools',['browser']),('automatic_retry',True)]:
            with self.subTest(key=key),self.assertRaises(ValueError):AnthropicSupervisor(dict(CONFIG,**{key:value}),self.root/'unused')
        adapter=AnthropicSupervisor(CONFIG,self.root/'unused')
        for method,path in [('GET','/v1/files'),('POST','/v1/models/claude-sonnet-5-5'),('POST','https://other.invalid')]:
            with self.assertRaises(ValueError):adapter._request(method,path)

    def test_supervisor_audit_and_state_survive_ledger_reload(self):
        call=str(uuid4());root=self.root/'live';directory=root/call;directory.mkdir(parents=True)
        store=Store(directory/'acceptance.sqlite3');session=store.start(EXERCISE)
        from gurukul.learning_authority import canonical_teaching
        authority=canonical_teaching(self.store.path,self.session['id'])
        store.teaching_authority=authority.__enter__()
        self.addCleanup(authority.__exit__,None,None,None)
        previous=dict(self.previous,excerpt='Synthetic excerpt',parent_call_id='previous',parent_event_id=None,parent_report_sha256='hash')
        message='Why keep repeating the question?';context=self.context(message)
        state,audit=supervise(snapshot(context,self.state),self.state,FakeProvider(),store,session['id'],call)
        context=control_context(context,state)
        r=proposal(question=message);a,d=evaluate_output(r,context)
        a,d,state,proof=apply_control(a,d,state,context);audit['compliance']=proof
        _,continuation=continuation_input(previous,message)
        manifest=json.loads((ROOT/'content/sources.json').read_text());config=json.loads((ROOT/'config/hermes-live.json').read_text())
        excerpt='Synthetic excerpt';final=canonical(r)
        provenance={'source_id':config['source_id'],'source_sha256':config['source_sha256'],
            'sections':['Concepts to own',config['source_section']],'excerpt_sha256':digest(excerpt),
            'manifest_sha256':digest(canonical(manifest)),'exercise_sha256':digest(canonical(EXERCISE))}
        report={'status':'PASS','call_id':call,'teaching':r,'response_sha256':digest(final),'provenance':provenance,
                'display_teaching':d,'pedagogy_admission':a,'supervision':audit,'supervision_state':state,'continuation':continuation,
                'turn_context':context}
        record_result(store,call,session['id'],report)
        self.assertEqual('supervision.decision_recorded',store.events()[-2]['event_type'])
        self.assertEqual(audit,store.events()[-2]['payload']);store.close()
        (directory/'report.json').write_text(canonical(dict(report,parent_ledger_record_verified=True)))
        (directory/'provider-response.json').write_text(canonical({'choices':[{'message':{'content':final}}]}))
        (directory/'teaching-response.json').write_text(final);(directory/'approved-excerpt.txt').write_text(excerpt)
        loaded=load_previous(root,call,manifest,config,EXERCISE)
        self.assertEqual(state,loaded['supervision_state']);self.assertEqual('',loaded['teaching']['diagnostic_question'])
        self.assertFalse(loaded['history'][-1]['pedagogy_admission']['grants_mastery'])

if __name__=='__main__':unittest.main()
