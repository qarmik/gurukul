"""Synthetic evidence-integrity regressions; no provider calls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
from test_pedagogy import ROOT, EXERCISE
from test_mixed_intents import proposal, QUESTION
from gurukul.learner_input import capture, verify, resolve, references, verify_admission
from gurukul.hermes_continuation import continuation_input, load_previous, digest
from gurukul.hermes_teaching import record_result
from gurukul.pedagogy import orientation, turn_context
from gurukul.teaching_output import evaluate_output
from gurukul.store import Store, canonical


class LearnerInputTests(unittest.TestCase):
    def setUp(self):
        self.orientation,_=orientation(ROOT,EXERCISE)
        self.previous={'teaching':{'explanation':'Prior explanation','diagnostic_question':QUESTION,
                                  'pedagogy':{'strategy':'comparison','next_activity':'predict'}},
                       'parent_call_id':'parent','parent_event_id':'event','parent_report_sha256':'hash','excerpt':'Synthetic'}
    def context(self,message):return turn_context(self.orientation,self.previous,message,[])

    def test_raw_and_normalized_are_separate_and_exact(self):
        raw='  नाम = "Cedar"; x_men = नाम; print(x_men)\t\x1b[C\n'
        _,evidence=continuation_input(self.previous,raw)
        record=evidence['learner_input']
        self.assertEqual(raw,record['raw_input'])
        self.assertEqual(raw.replace('\x1b[C',''),verify(record))
        self.assertEqual(verify(record),evidence['learner_answer'])
        self.assertEqual(record,capture(raw))
        for field in ['raw_input','normalized_input','raw_sha256','normalized_sha256']:
            corrupt=copy.deepcopy(record);corrupt[field]+='x'
            with self.subTest(field=field),self.assertRaises(ValueError):verify(corrupt)

    def test_normalization_only_removes_characters_preserving_python_syntax(self):
        syntax="  café_1 = ['a', \"b\"]; x = (3 + 2) / 4; d = {'q': x}\n\t# comment"
        raw='\x1b[31m'+syntax+'\x1b[0m'
        record=capture(raw)
        self.assertEqual(syntax,record['normalized_input'])
        iterator=iter(raw)
        self.assertTrue(all(any(c==r for r in iterator) for c in record['normalized_input']))

    def test_parent_references_and_unicode_offsets_reconstruct(self):
        text='नाम is text; later value.'
        for ref in references(text):
            value,binding=resolve({'ref':ref['ref']},text)
            self.assertEqual(text[ref['start']:ref['end']],value)
            self.assertEqual(digest(text),binding['input_sha256'])
        self.assertEqual('नाम',resolve({'start':0,'end':3},text)[0])

    def test_invalid_references_recover_without_credit_or_input_mutation(self):
        text='Cedar gives NameError.';context=self.context(text)
        for value in [{'ref':'s999'}, {'start':-1,'end':5}, {'start':0,'end':999},
                      {'start':True,'end':5},{'start':3,'end':3},'Cedar gives a different result.']:
            r=proposal(answer=text);r['pedagogy']['intents']['answer_span']=value
            untouched=copy.deepcopy(r)
            admission,shown=evaluate_output(r,context)
            self.assertEqual(untouched,r)
            self.assertEqual(text,context['C_turn']['learner_message'])
            self.assertEqual('NEEDS_CLARIFICATION',admission['conversation_status'])
            self.assertEqual('not_applicable',admission['judgment'])
            self.assertFalse(admission['answer_admitted']);self.assertFalse(admission['grants_mastery'])
            self.assertEqual('',admission['intents']['answer_span'])
            self.assertNotIn('answer_span',admission['learner_verified_spans'])
            self.assertIn('Interpretation reference rejected',admission['reason'])
            self.assertEqual(QUESTION,shown['diagnostic_question'])

    def test_code_like_prediction_admitted_without_requiring_prose(self):
        text='Birch = 10; alias = Birch; print(alias); alias = "Birch"; print(alias) -- output -- 10; Birch'
        r=proposal(answer=text);r['pedagogy']['intents']['answer_span']={'ref':'s0'}
        r['pedagogy']['evidence_need']='Explain in words why the two values differ.'
        admission,_=evaluate_output(r,self.context(text))
        self.assertTrue(admission['answer_admitted'])
        self.assertEqual('correct',admission['judgment'])
        self.assertEqual(text,admission['learner_verified_spans']['answer_span']['text'])
        self.assertEqual({'ref':'s0'},admission['model_interpretation']['answer_span'])
        self.assertEqual('Explain in words why the two values differ.',admission['unmet_evidence_requirement'])
        self.assertFalse(admission['grants_mastery'])

    def test_model_reference_cannot_make_pure_question_gradeable(self):
        text='What is a literal?';r=proposal(answer=text,question=text)
        r['pedagogy']['intents']['answer_span']={'ref':'s0'}
        self.assertFalse(evaluate_output(r,self.context(text))[0]['answer_admitted'])

    def test_verified_span_tampering_is_refused(self):
        text='Cedar gives NameError.'
        admission,_=evaluate_output(proposal(answer=text),self.context(text))
        verify_admission(admission,text)
        for field in ['text','input_sha256','end']:
            corrupt=copy.deepcopy(admission)
            corrupt['learner_verified_spans']['answer_span'][field]='invented'
            with self.subTest(field=field),self.assertRaises(ValueError):verify_admission(corrupt,text)

    def test_reference_does_not_bypass_security(self):
        r=proposal(answer='Cedar gives NameError.');r['pedagogy']['intents']['answer_span']={'ref':'s0'}
        r['pedagogy']['grants_mastery']=True
        with self.assertRaises(ValueError):evaluate_output(r,self.context('Cedar gives NameError.'))

    def test_mixed_references_survive_ledger_reload_and_raw_tamper_refused(self):
        answer='Cedar gives NameError.';question='Why?';text=answer+' '+question
        r=proposal(answer=answer,question=question)
        for field,value in [('answer_span',answer),('question_span',question)]:
            start=text.index(value);r['pedagogy']['intents'][field]={'start':start,'end':start+len(value)}
        admission,display=evaluate_output(r,self.context(text))
        _,continuation=continuation_input(self.previous,text)
        for corrupt in [False,True]:
            with self.subTest(corrupt=corrupt),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp).resolve();call=str(uuid4());directory=root/call;directory.mkdir()
                config=json.loads((ROOT/'config/hermes-live.json').read_text());manifest=json.loads((ROOT/'content/sources.json').read_text())
                final=canonical(r);excerpt='Synthetic excerpt'
                proof={'source_id':config['source_id'],'source_sha256':config['source_sha256'],
                       'sections':['Concepts to own',config['source_section']],'excerpt_sha256':digest(excerpt),
                       'manifest_sha256':digest(canonical(manifest)),'exercise_sha256':digest(canonical(EXERCISE))}
                stored=copy.deepcopy(continuation)
                stored.pop('parent_event_id')
                if corrupt:stored['learner_input']['raw_input']+='invented'
                report={'status':'PASS','call_id':call,'teaching':r,'response_sha256':digest(final),
                        'provenance':proof,'display_teaching':display,'pedagogy_admission':admission,
                        'continuation':stored}
                store=Store(directory/'acceptance.sqlite3');session=store.start(EXERCISE)
                record_result(store,call,session['id'],report);store.close()
                (directory/'report.json').write_text(json.dumps(dict(report,parent_ledger_record_verified=True)))
                (directory/'provider-response.json').write_text(json.dumps({'choices':[{'message':{'content':final}}]}))
                (directory/'teaching-response.json').write_text(final);(directory/'approved-excerpt.txt').write_text(excerpt)
                if corrupt:
                    with self.assertRaises(ValueError):load_previous(root,call,manifest,config,EXERCISE)
                else:
                    saved=load_previous(root,call,manifest,config,EXERCISE)
                    self.assertEqual(text,saved['history'][0]['learner_message'])
                    bound=saved['history'][0]['pedagogy']['intents']
                    self.assertEqual(answer,bound['answer_span']);self.assertEqual(question,bound['question_span'])
                    self.assertEqual('correct',saved['history'][0]['pedagogy']['judgment'])

if __name__=='__main__':unittest.main()
