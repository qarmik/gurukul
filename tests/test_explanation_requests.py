"""Offline explanation routing/output recovery/input hygiene; not live acceptance."""
import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
from test_pedagogy import ROOT, EXERCISE, response
from gurukul.pedagogy import orientation, turn_context, classify, validate_response, PedagogicalFormatError
from gurukul.intent_admission import SPANS, intent_hint, candidate_answers
from gurukul.teaching_output import evaluate_output
from gurukul.terminal_text import normalize_input
from gurukul.hermes_continuation import continuation_input, load_previous, digest
from gurukul.hermes_teaching import record_result
from gurukul.store import Store, canonical

QUESTION='What does a name refer to after assignment?'


def proposal(message,strategy='analogy'):
    r=response();r['explanation']='Imagine a label attached to a value: the label refers to that value.'
    r['miniature_example']=''
    spans=dict.fromkeys(SPANS,'');spans['explanation_span']=message
    r['pedagogy'].update(message_kind='REQUEST_FOR_EXPLANATION',judgment='not_applicable',strategy=strategy,
        routing={'control_action':'REQUEST_EXPLANATION','requested_strategy':intent_hint(message)['requested_strategy'] or 'explanation'},
        intents=dict(primary='REQUEST_FOR_EXPLANATION',secondary=[],**spans),
        intent_responses={'clarification':'','question':'','confusion':''})
    return r


class ExplanationTests(unittest.TestCase):
    def setUp(self):
        self.orientation,_=orientation(ROOT,EXERCISE)
        self.previous={'teaching':{'explanation':'Previous explanation','diagnostic_question':QUESTION,
                       'pedagogy':{'strategy':'comparison','next_activity':'predict'}},
                       'parent_call_id':'parent','parent_event_id':'event','parent_report_sha256':'hash','excerpt':'Synthetic excerpt'}
    def context(self,message):return turn_context(self.orientation,self.previous,message,[])

    def test_requests_are_not_answers(self):
        for text in ['explain with an analogy','explain again','explain differently','give me an analogy',
                     'show me a simpler example','simplify that','walk me through it',"I don't understand that explanation",'can you compare it to something?']:
            with self.subTest(text=text):
                self.assertEqual('REQUEST_FOR_EXPLANATION',classify(text))
                self.assertIn('REQUEST_FOR_EXPLANATION',intent_hint(text)['possible_intents'])
                self.assertEqual([],candidate_answers(text))

    def test_analogy_without_code_preserves_need_without_grade_or_mastery(self):
        text='explain with an analogy';r=proposal(text)
        admission,shown=evaluate_output(r,self.context(text))
        self.assertEqual('CONTINUE',admission['conversation_status'])
        self.assertEqual('not_applicable',admission['judgment'])
        self.assertFalse(admission['grants_mastery'])
        self.assertFalse(admission['answer_admitted'])
        self.assertEqual(QUESTION,admission['unresolved_evidence_question'])
        self.assertEqual('',shown['miniature_example'])
        self.assertEqual('analogy',shown['pedagogy']['strategy'])

    def test_ignored_requested_strategy_recovers(self):
        text='explain with an analogy'
        admission,_=evaluate_output(proposal(text,'comparison'),self.context(text))
        self.assertEqual('NEEDS_CLARIFICATION',admission['conversation_status'])
        self.assertEqual('not_applicable',admission['judgment'])

    def test_simple_and_example_strategy_switches(self):
        for text,strategy in [('explain it more simply','explanation'),('give me a small example','miniature_example'),
                              ('can you compare it to something?','comparison')]:
            r=proposal(text,strategy)
            if '?' in text:
                r['pedagogy']['intents']['secondary']=['QUESTION']
                r['pedagogy']['intents']['question_span']=text
                r['pedagogy']['intent_responses']['question']='The comparison contrasts a name with a literal.'
            if strategy=='miniature_example':r['miniature_example']='label = 4\nlabel'
            self.assertEqual('CONTINUE',evaluate_output(r,self.context(text))[0]['conversation_status'])

    def test_supplied_code_stays_bounded(self):
        text='give me a small example'
        for code in ['import os','print(secret)','a=1\nb=2','x=open("file")']:
            r=proposal(text,'miniature_example');r['miniature_example']=code
            with self.subTest(code=code),self.assertRaises(ValueError):evaluate_output(r,self.context(text))

    def test_safe_misplaced_code_is_rejected_not_displayed(self):
        text='explain with an analogy';r=proposal(text);r['explanation']='A small example is label = 4.'
        with self.assertRaises(PedagogicalFormatError):validate_response(r,self.context(text))
        admission,shown=evaluate_output(r,self.context(text))
        self.assertEqual('RESPONSE_REJECTED',admission['conversation_status'])
        self.assertEqual('not_applicable',admission['judgment'])
        self.assertNotIn('label =',shown['explanation'])
        self.assertEqual('',shown['diagnostic_question'])
        self.assertEqual(QUESTION,admission['unresolved_evidence_question'])
        self.assertFalse(admission['grants_mastery'])

    def test_security_precedes_recoverable_format(self):
        text='explain with an analogy'
        for mutation in ['mastery','scope','unsafe_code','malformed']:
            r=proposal(text);r['explanation']='A small example is label = 4.'
            if mutation=='mastery':r['pedagogy']['grants_mastery']=True
            if mutation=='scope':r['pedagogy']['current_location']='C1'
            if mutation=='unsafe_code':r['explanation']='label = open("secret")'
            if mutation=='malformed':r['pedagogy']['unexpected']='value'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError) as failure:evaluate_output(r,self.context(text))
            self.assertNotIsInstance(failure.exception,PedagogicalFormatError)

    def test_terminal_controls_removed_utf8_and_syntax_preserved(self):
        text='नाम = "Cedar"; path = r"\\x1b[31m"'
        clean,meta=normalize_input('\x1b[31m'+text+'\x1b[0m\x1b[C^[[C\x07')
        self.assertEqual(text,clean)
        self.assertTrue(meta['normalized']);self.assertFalse(meta['raw_retained'])
        clean,_=normalize_input('hello\x1b]0;terminal title\x07 world')
        self.assertEqual('hello world',clean)
        with self.assertRaises(ValueError):normalize_input('x'*16001)

    def test_semantic_evidence_and_hash_use_normalized_text(self):
        _,evidence=continuation_input(self.previous,'the \x1b[Cvalue')
        self.assertEqual('the value',evidence['learner_answer'])
        self.assertEqual(digest('the value'),evidence['answer_sha256'])
        self.assertTrue(evidence['input_hygiene']['normalized'])

    def test_normal_answer_admission_resumes_after_explanation(self):
        from test_mixed_intents import proposal as answer_proposal
        request='explain with an analogy'
        _,shown=evaluate_output(proposal(request),self.context(request))
        message='The name refers to its assigned value.'
        context=turn_context(self.orientation,{'teaching':shown},message,[])
        admission,_=evaluate_output(answer_proposal(answer=message),context)
        self.assertEqual('CONTINUE',admission['conversation_status'])
        self.assertTrue(admission['answer_admitted'])
        self.assertEqual('correct',admission['judgment'])
        self.assertFalse(admission['grants_mastery'])

    def test_rejected_response_reloads_without_credit_or_phase_change(self):
        text='explain with an analogy';r=proposal(text);r['explanation']='A small example is label = 4.'
        context=self.context(text);admission,shown=evaluate_output(r,context)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();call=str(uuid4());directory=root/call;directory.mkdir()
            config=json.loads((ROOT/'config/hermes-live.json').read_text());manifest=json.loads((ROOT/'content/sources.json').read_text())
            final=canonical(r);excerpt='Synthetic excerpt'
            proof={'source_id':config['source_id'],'source_sha256':config['source_sha256'],
                   'sections':['Concepts to own',config['source_section']],'excerpt_sha256':digest(excerpt),
                   'manifest_sha256':digest(canonical(manifest)),'exercise_sha256':digest(canonical(EXERCISE))}
            report={'status':'PASS','runtime_status':'PASS','call_id':call,'teaching':r,'response_sha256':digest(final),
                    'provenance':proof,'display_teaching':shown,'pedagogy_admission':admission,'turn_context':context}
            store=Store(directory/'acceptance.sqlite3');session=store.start(EXERCISE)
            record_result(store,call,session['id'],report)
            self.assertEqual('teaching',store.resume()['session']['phase']);store.close()
            (directory/'report.json').write_text(json.dumps(dict(report,parent_ledger_record_verified=True)))
            (directory/'provider-response.json').write_text(json.dumps({'choices':[{'message':{'content':final}}]}))
            (directory/'teaching-response.json').write_text(final);(directory/'approved-excerpt.txt').write_text(excerpt)
            saved=load_previous(root,call,manifest,config,EXERCISE)
            self.assertEqual('not_applicable',saved['history'][0]['pedagogy']['judgment'])
            self.assertEqual('',saved['teaching']['diagnostic_question'])
            self.assertEqual(QUESTION,saved['unresolved_evidence_question'])

if __name__=='__main__':unittest.main()
