"""Synthetic contract/serialization tests, not live pedagogical acceptance."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from uuid import uuid4

from gurukul.intent_admission import admit, candidate_answers, intent_hint, runtime_notice, SPANS
from gurukul.pedagogy import orientation, turn_context, validate_response
from gurukul.hermes_continuation import load_previous, digest
from gurukul.hermes_teaching import record_result
from gurukul.store import Store, canonical
from test_pedagogy import response, ROOT, EXERCISE
sys.path.insert(0,str(ROOT/'scripts'))
from hermes_live_teach import conversation_loop, TeachingExit

QUESTION='Assume Cedar is undefined. What happens with Cedar versus quoted Cedar?'


def proposal(answer='', clarification='', question='', confusion='', uncertainty='', hypothesis=''):
    r=response();p=r['pedagogy']
    spans=dict.fromkeys(SPANS,'')
    spans.update(answer_span=answer,clarification_span=clarification,question_span=question,
                 confusion_span=confusion,uncertainty_span=uncertainty,hypothesis_span=hypothesis)
    labels=[kind for name,kind in SPANS.items() if spans[name]]
    p.update(intents=dict(primary=labels[0],secondary=labels[1:],**spans),
             intent_responses={'clarification':'Understood: you meant the same rule, not identical outcomes.' if clarification else '',
                               'question':'Python uses a name to look up its associated value.' if question else '',
                               'confusion':'Think of a name as a label referring to a value.' if confusion else ''},
             message_kind=labels[0],judgment='correct' if answer else 'not_applicable',next_activity='learner_example')
    return r


class MixedTests(unittest.TestCase):
    def setUp(self):
        self.orientation,_=orientation(ROOT,EXERCISE)
        self.previous={'teaching':{'explanation':'Prior explanation','diagnostic_question':QUESTION,
                                  'pedagogy':{'strategy':'comparison','next_activity':'variation'}}}

    def context(self,message):return turn_context(self.orientation,self.previous,message,[])

    def checked(self,result,message):
        context=self.context(message)
        validate_response(result,context)
        return admit(result,context)

    def test_answer_clarification_preserves_both_and_acknowledges(self):
        clarification='When I said same result, I meant the same rule.'
        answer='Cedar gives NameError and quoted Cedar is text.'
        admission,shown=self.checked(proposal(answer,clarification),clarification+' '+answer)
        self.assertEqual('correct',admission['judgment'])
        self.assertIn('CLARIFICATION',admission['intents']['secondary'])
        self.assertTrue(shown['pedagogy']['intent_responses']['clarification'])
        self.assertEqual('CONTINUE',admission['conversation_status'])

    def test_dispatch_style_clarification_not_false_confusion(self):
        message='when I said matching results, I did not mean identical values. I meant another name e.g. Birch: the result would be NameError and the text Birch'
        answer='the result would be NameError and the text Birch'
        clarification='when I said matching results, I did not mean identical values.'
        admission,_=self.checked(proposal(answer,clarification),message)
        self.assertEqual('correct',admission['judgment'])
        self.assertNotIn('CONFUSION',intent_hint(message)['possible_intents'])

    def test_answer_question_answers_both(self):
        answer='Cedar gives NameError and quoted Cedar is text.';question='Why does Python call it a name?'
        admission,shown=self.checked(proposal(answer,question=question),answer+' '+question)
        self.assertEqual('correct',admission['judgment'])
        self.assertTrue(shown['pedagogy']['intent_responses']['question'])

    def test_pure_question_not_graded_and_evidence_need_preserved(self):
        question='What do you mean by literal?'
        admission,shown=self.checked(proposal(question=question),question)
        self.assertEqual('not_applicable',admission['judgment'])
        self.assertFalse(admission['answer_admitted'])
        self.assertEqual(QUESTION,shown['diagnostic_question'])

    def test_pure_confusion_not_graded(self):
        message='I am confused'
        admission,_=self.checked(proposal(confusion=message),message)
        self.assertEqual('not_applicable',admission['judgment'])

    def test_uncertainty_and_hypothesis_question(self):
        answer='Cedar gives NameError.';uncertainty='I am unsure'
        admission,_=self.checked(proposal(answer,uncertainty=uncertainty),answer+' '+uncertainty)
        self.assertTrue(admission['answer_admitted'])
        question='Why does that happen?';hypothesis='I think Cedar gives NameError.'
        r=proposal(answer=hypothesis,question=question,hypothesis=hypothesis)
        self.assertEqual('CONTINUE',self.checked(r,hypothesis+' '+question)[0]['conversation_status'])

    def test_model_label_cannot_make_question_an_answer(self):
        question='What is Cedar?'
        r=proposal(answer='Cedar',question=question)
        admission,_=self.checked(r,question)
        self.assertEqual('NEEDS_CLARIFICATION',admission['conversation_status'])
        self.assertEqual('not_applicable',admission['judgment'])

    def test_unbound_or_missing_secondary_response_recovers(self):
        answer='Cedar gives NameError.';question='Why?'
        for change in ('unbound','missing_reply'):
            r=proposal(answer,question=question)
            if change=='unbound':r['pedagogy']['intents']['answer_span']='Invented answer'
            else:r['pedagogy']['intent_responses']['question']=''
            admission,_=self.checked(r,answer+' '+question)
            self.assertEqual('NEEDS_CLARIFICATION',admission['conversation_status'])

    def test_recovery_keeps_session_open_and_waits_for_next_input(self):
        args=argparse.Namespace(continue_call='prior',runtime_root=Path('/tmp/runtime'),once=False,source=None,choose_source=False)
        seen=[]
        def turn(current):
            seen.append(current.continue_call)
            if len(seen)==1:return {'status':'PASS','parent_ledger_record_verified':True,'call_id':'recovery',
                                    'pedagogy_admission':{'conversation_status':'NEEDS_CLARIFICATION','judgment':'not_applicable'}}
            raise TeachingExit()
        with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(0,conversation_loop(args,turn))
        self.assertEqual(['prior','recovery'],seen)

    def test_runtime_status_never_says_answer_passed(self):
        for judgment in ['correct','partial','uncertain','incorrect','not_applicable']:
            text=runtime_notice({'status':'PASS','pedagogy_admission':{'judgment':judgment}})
            self.assertEqual('Turn saved; evidence verified.',text)
            self.assertNotIn('PASS',text)

    def test_authority_and_disclosure_fail_hard_even_if_intent_ambiguous(self):
        for mutation in ['mastery','curriculum','code']:
            r=proposal(answer='invented',question='What is Cedar?')
            if mutation=='mastery':r['pedagogy']['grants_mastery']=True
            if mutation=='curriculum':r['pedagogy']['current_location']='C1'
            if mutation=='code':r['pedagogy']['intent_responses']['question']='print(secret)'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.checked(r,'What is Cedar?')

    def test_successful_variation_moves_representation(self):
        r=proposal(answer='Cedar gives NameError.')
        r['pedagogy']['next_activity']='variation'
        admission,_=self.checked(r,'Cedar gives NameError.')
        self.assertEqual('NEEDS_CLARIFICATION',admission['conversation_status'])
        r['pedagogy']['next_activity']='learner_example'
        self.assertEqual('CONTINUE',self.checked(r,'Cedar gives NameError.')[0]['conversation_status'])

    def test_secondary_intents_and_recovery_survive_reload_without_false_credit(self):
        for recover in [False,True]:
            with self.subTest(recover=recover),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp).resolve();call=str(uuid4());directory=root/call;directory.mkdir()
                message='Cedar gives NameError. Why?'
                r=proposal(answer='Cedar gives NameError.',question='Why?')
                if recover:r['pedagogy']['intents']['answer_span']='Invented'
                admission,display=self.checked(r,message)
                config=json.loads((ROOT/'config/hermes-live.json').read_text());manifest=json.loads((ROOT/'content/sources.json').read_text())
                final=canonical(r);excerpt='Synthetic approved excerpt.'
                proof={'source_id':config['source_id'],'source_sha256':config['source_sha256'],
                       'sections':['Concepts to own',config['source_section']],'excerpt_sha256':digest(excerpt),
                       'manifest_sha256':digest(canonical(manifest)),'exercise_sha256':digest(canonical(EXERCISE))}
                report={'status':'PASS','call_id':call,'teaching':r,'response_sha256':digest(final),
                        'provenance':proof,'display_teaching':display,'pedagogy_admission':admission}
                store=Store(directory/'acceptance.sqlite3');session=store.start(EXERCISE)
                record_result(store,call,session['id'],report);store.close()
                (directory/'report.json').write_text(json.dumps(dict(report,parent_ledger_record_verified=True)))
                (directory/'provider-response.json').write_text(json.dumps({'choices':[{'message':{'content':final}}]}))
                (directory/'teaching-response.json').write_text(final)
                (directory/'approved-excerpt.txt').write_text(excerpt)
                loaded=load_previous(root,call,manifest,config,EXERCISE)
                self.assertIn('QUESTION',loaded['history'][0]['pedagogy_admission']['intents']['secondary'])
                self.assertEqual('not_applicable' if recover else 'correct',loaded['history'][0]['pedagogy']['judgment'])

if __name__=='__main__':unittest.main()
