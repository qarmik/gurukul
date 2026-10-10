"""Regression shapes from live failures; synthetic text, no provider call."""
import copy
import unittest
from test_explanation_requests import proposal, QUESTION
from test_pedagogy import ROOT, EXERCISE
from gurukul.pedagogy import orientation, turn_context, validate_response, PedagogicalFormatError
from gurukul.teaching_output import evaluate_output
from gurukul.intent_admission import intent_hint, candidate_answers

class ResponseRoutingTests(unittest.TestCase):
    def setUp(self):
        self.orientation,_=orientation(ROOT,EXERCISE)
        self.previous={'teaching':{'explanation':'Imagine a labeled container; using the label retrieves its contents.',
            'diagnostic_question':QUESTION,'pedagogy':{'strategy':'analogy'}}}
    def context(self,text):return turn_context(self.orientation,self.previous,text,[])

    def test_simpler_comparison_admitted_without_relabelling_or_grading(self):
        text='explain it more simply';r=proposal(text,'comparison')
        r['explanation']='An unquoted name refers to its assigned value. Quoted text is the text itself.'
        r['pedagogy']['intents']['explanation_span']={'ref':'s0'}
        admission,shown=evaluate_output(r,self.context(text))
        self.assertEqual('CONTINUE',admission['conversation_status'])
        self.assertEqual('comparison',shown['pedagogy']['strategy'])
        self.assertEqual('not_applicable',admission['judgment'])
        self.assertEqual(QUESTION,admission['unresolved_evidence_question'])
        self.assertFalse(admission['grants_mastery'])

    def test_simplification_repetition_still_recovers(self):
        text='explain it more simply';r=proposal(text,'comparison')
        r['explanation']=self.previous['teaching']['explanation']
        self.assertEqual('NEEDS_CLARIFICATION',evaluate_output(r,self.context(text))[0]['conversation_status'])

    def test_some_example_is_request_and_must_supply_example(self):
        for text in ['give me some example','give me some examples','give me a small example']:
            self.assertEqual('miniature_example',intent_hint(text)['requested_strategy'])
            self.assertEqual([],candidate_answers(text))
            r=proposal(text,'miniature_example')
            self.assertEqual('NEEDS_CLARIFICATION',evaluate_output(r,self.context(text))[0]['conversation_status'])
            r['miniature_example']='label = 7\nlabel'
            self.assertEqual('CONTINUE',evaluate_output(r,self.context(text))[0]['conversation_status'])

    def test_missing_descriptive_echoes_recovers_without_inventing_fields(self):
        text='give me some example';r=proposal(text)
        del r['pedagogy']['current_purpose'];del r['pedagogy']['final_trajectory']
        original=copy.deepcopy(r)
        admission,shown=evaluate_output(r,self.context(text))
        self.assertEqual(original,r)
        self.assertEqual('RESPONSE_REJECTED',admission['conversation_status'])
        self.assertEqual('not_applicable',admission['judgment'])
        self.assertFalse(admission['grants_mastery'])
        self.assertEqual(QUESTION,shown['diagnostic_question'])
        # Same path used when a safe rejection is loaded after restart.
        self.assertEqual(r,validate_response(r,self.context(text),allow_safe_format=True))

    def test_missing_echoes_never_hide_authority_or_schema_violation(self):
        for mutation in ['mastery','location','unknown','missing_authority','false_echo','code']:
            text='give me some example';r=proposal(text)
            del r['pedagogy']['current_purpose'];del r['pedagogy']['final_trajectory']
            if mutation=='mastery':r['pedagogy']['grants_mastery']=True
            if mutation=='location':r['pedagogy']['current_location']='C1'
            if mutation=='unknown':r['pedagogy']['extra']='value'
            if mutation=='missing_authority':del r['pedagogy']['grants_mastery']
            if mutation=='false_echo':r['pedagogy']['current_purpose']='replace curriculum'
            if mutation=='code':r['miniature_example']='import os'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError) as error:
                evaluate_output(r,self.context(text))
            self.assertNotIsInstance(error.exception,PedagogicalFormatError)

if __name__=='__main__':unittest.main()
