"""Multi-turn synthetic regressions: display, answer admission and pending evidence."""
import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from test_pedagogy import ROOT, EXERCISE
from test_mixed_intents import proposal, QUESTION
from gurukul.pedagogy import orientation, turn_context
from gurukul.teaching_output import evaluate_output
from gurukul.hermes_continuation import continuation_input, load_previous, digest
from gurukul.hermes_teaching import record_result
from gurukul.store import Store, canonical

class ConversationStateTests(unittest.TestCase):
    def setUp(self):
        self.orientation,_=orientation(ROOT,EXERCISE)
        self.previous={'teaching':{'explanation':'Prior comparison','diagnostic_question':QUESTION,
                       'pedagogy':{'strategy':'comparison'}},'excerpt':'Synthetic excerpt',
                       'parent_call_id':'prior','parent_event_id':None,'parent_report_sha256':'hash'}
    def context(self,text,previous=None):return turn_context(self.orientation,previous or self.previous,text,[])

    def test_same_strategy_different_explanation_is_not_rejected(self):
        text='What are you talking about?'
        r=proposal(question=text,confusion=text)
        r['pedagogy']['strategy']='comparison'
        r['explanation']='The check compares a name lookup with text written directly.'
        r['diagnostic_question']=''
        admission,shown=evaluate_output(r,self.context(text))
        self.assertEqual('CONTINUE',admission['conversation_status'])
        self.assertEqual(r['explanation'],shown['explanation'])
        self.assertEqual('',shown['diagnostic_question'])
        self.assertEqual(QUESTION,admission['unresolved_evidence_question'])

    def test_confirming_question_is_not_answer_even_if_model_labels_it(self):
        text='So you are asking what each assignment means, correct?'
        r=proposal(answer=text,question=text)
        r['pedagogy']['judgment']='not_applicable'
        r['explanation']='Yes. The check asks you to distinguish a name lookup from literal text.'
        r['diagnostic_question']=''
        admission,shown=evaluate_output(r,self.context(text))
        self.assertEqual('CONTINUE',admission['conversation_status'])
        self.assertFalse(admission['answer_admitted'])
        self.assertEqual('not_applicable',admission['judgment'])
        self.assertEqual('',shown['diagnostic_question'])

    def test_main_response_can_address_meta_and_confusion_without_duplicate_fields(self):
        text='Why do you keep repeating the question?'
        r=proposal(question=text,confusion=text)
        p=r['pedagogy'];p['intents']['primary']='META_QUESTION'
        p['intents']['meta_span']=p['intents']['question_span'];p['intents']['question_span']=''
        p['intent_responses']['question']=''
        p['strategy']='clarification';p['next_activity']='pause'
        r['explanation']='That was my earlier understanding check. We can pause it and clarify the distinction first.'
        admission,shown=evaluate_output(r,self.context(text))
        self.assertEqual('CONTINUE',admission['conversation_status'])
        self.assertEqual('',shown['diagnostic_question'])
        self.assertFalse(admission['grants_mastery'])
        self.assertEqual(QUESTION,admission['pending_question'])
        self.assertTrue(admission['conversation_observations'])

    def test_invalid_reference_recovery_does_not_repeat_question(self):
        text='The value changes.';r=proposal(answer='invented text')
        admission,shown=evaluate_output(r,self.context(text))
        self.assertEqual('NEEDS_CLARIFICATION',admission['conversation_status'])
        self.assertEqual('',shown['diagnostic_question'])
        self.assertEqual(QUESTION,admission['pending_question'])
        self.assertFalse(admission['answer_admitted'])

    def test_pause_does_not_waive_security(self):
        r=proposal(question='Why?');r['pedagogy']['next_activity']='pause'
        r['pedagogy']['grants_mastery']=True
        with self.assertRaises(ValueError):evaluate_output(r,self.context('Why?'))

    def test_recovery_pause_reload_answer_chain_preserves_pending_evidence(self):
        config=json.loads((ROOT/'config/hermes-live.json').read_text());manifest=json.loads((ROOT/'content/sources.json').read_text())
        excerpt='Synthetic excerpt'
        proof={'source_id':config['source_id'],'source_sha256':config['source_sha256'],
               'sections':['Concepts to own',config['source_section']],'excerpt_sha256':digest(excerpt),
               'manifest_sha256':digest(canonical(manifest)),'exercise_sha256':digest(canonical(EXERCISE))}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();root_call=str(uuid4());directory=root/root_call;directory.mkdir()
            store=Store(directory/'acceptance.sqlite3');session=store.start(EXERCISE)
            previous=self.previous
            sequence=[('The value changes.',proposal(answer='invented')),
                      ('Why repeat that?',proposal(question='Why repeat that?')),
                      ('Cedar gives NameError and quoted Cedar is text.',proposal(answer='Cedar gives NameError and quoted Cedar is text.'))]
            for index,(text,r) in enumerate(sequence):
                call=root_call if index==0 else str(uuid4());directory=root/call;directory.mkdir(exist_ok=True)
                if index==1:
                    r['pedagogy']['next_activity']='pause';r['diagnostic_question']=''
                context=self.context(text,previous);admission,display=evaluate_output(r,context)
                _,continuation=continuation_input(previous,text)
                final=canonical(r)
                report={'status':'PASS','call_id':call,'root_call_id':root_call,'teaching':r,
                        'response_sha256':digest(final),'provenance':proof,'display_teaching':display,
                        'pedagogy_admission':admission,'continuation':continuation,'turn_context':context}
                record_result(store,call,session['id'],report)
                (directory/'report.json').write_text(json.dumps(dict(report,parent_ledger_record_verified=True)))
                (directory/'provider-response.json').write_text(json.dumps({'choices':[{'message':{'content':final}}]}))
                (directory/'teaching-response.json').write_text(final);(directory/'approved-excerpt.txt').write_text(excerpt)
                previous=load_previous(root,call,manifest,config,EXERCISE)
                if index<2:
                    self.assertEqual('',previous['teaching']['diagnostic_question'])
                    self.assertEqual(QUESTION,previous['unresolved_evidence_question'])
                    self.assertEqual('not_applicable',admission['judgment'])
                else:
                    self.assertTrue(admission['answer_admitted'])
                    self.assertEqual('correct',admission['judgment'])
                    self.assertEqual(QUESTION,continuation['question_answered'])
                self.assertFalse(admission['grants_mastery'])
            self.assertEqual('teaching',store.resume()['session']['phase']);store.close()

if __name__=='__main__':unittest.main()
