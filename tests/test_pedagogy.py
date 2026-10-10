"""Deterministic contracts only; no claim of live model pedagogical quality."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from gurukul.pedagogy import orientation, turn_context, build_prompt, validate_response, classify

ROOT=Path(__file__).resolve().parents[1]
EXERCISE=json.loads((ROOT/'content/c0_b01/d01.json').read_text())


def response():
    return {'explanation':'A name refers to a value; an undefined name raises an error.',
            'diagnostic_question':'Describe your own example of a name and a value.', 'miniature_example':'',
            'pedagogy':{'message_kind':'ANSWER','concept':'names_values','judgment':'correct',
                'strategy':'explanation','next_activity':'learner_example','evidence_need':'Can the learner construct a distinct example?',
                'knowledge_classes':['model_general_knowledge','learner_evidence'],
                'claim_basis':'Stable Python fundamentals; the learner response informs feedback.',
                'source_specific':False,'future_topic_deferred':False,'current_location':'C0-B01-D01',
                'curriculum_version':'0.8.3','current_purpose':'programming independence foundation',
                'final_trajectory':'regulated-enterprise AI architecture','grants_mastery':False,'curriculum_observation':''}}


class PedagogyTests(unittest.TestCase):
    def setUp(self):
        self.orientation,self.proof=orientation(ROOT,EXERCISE)
        self.context=turn_context(self.orientation,None,'a name',[])

    def test_canonical_map_reproducible_and_full_trajectory_compact(self):
        path=ROOT/'content/curriculum/map.json'; original=path.read_bytes()
        subprocess.run(['python3',str(ROOT/'scripts/build_curriculum_map.py')],check=True)
        self.assertEqual(original,path.read_bytes())
        a=self.orientation['A_global']
        self.assertEqual(10,len(a['stages'])); self.assertEqual(14,len(a['capability_families']))
        self.assertIn('Financial Services',a['target_role'])
        self.assertLess(len(json.dumps(self.orientation).encode()),18000)
        self.assertEqual('C0-B01-D01',self.orientation['B_active']['current_capability'])

    def test_canonical_c0_requirements_supplied_without_invented_gates(self):
        raw=(ROOT/'content/curriculum/v0.8.3.txt').read_text()
        b=self.orientation['B_active']
        self.assertIn(b['stage_requirements'],raw)
        self.assertIn(b['gate_philosophy'],raw)
        self.assertIn('No Field-SA overlay',b['stage_requirements'])
        self.assertEqual(EXERCISE['required_evidence'],b['required_evidence'])

    def test_general_python_knowledge_not_limited_to_excerpt(self):
        prompt=build_prompt(self.context,'Only quotes are mentioned here.')
        self.assertIn('GURUKUL CONTEXT JSON',prompt)
        self.assertEqual(response(),validate_response(response(),self.context))

    def test_future_depth_guard_and_brief_deferral(self):
        r=response();r['explanation']='An agent has tools and governance controls.'
        with self.assertRaises(ValueError):validate_response(r,self.context)
        r['explanation']='Agents belong to a later stage. We will defer their design and focus on names and values now.'
        r['pedagogy'].update(future_topic_deferred=True,strategy='defer')
        validate_response(r,self.context)
        r['miniature_example']='x = 1'
        with self.assertRaises(ValueError):validate_response(r,self.context)

    def test_source_specific_and_unverified_external_provenance(self):
        r=response();r['pedagogy']['source_specific']=True
        with self.assertRaises(ValueError):validate_response(r,self.context)
        r['pedagogy']['knowledge_classes']=['approved_source'];validate_response(r,self.context)
        r['pedagogy']['knowledge_classes']=['approved_source','verified_external_source']
        with self.assertRaises(ValueError):validate_response(r,self.context)

    def test_claim_class_routing_requires_matching_authority(self):
        for message,expected in [('What does the book say?', 'source_specific'),
                                 ('What does the curriculum require?', 'curriculum_requirement'),
                                 ('What is the latest Python version?', 'version_sensitive'),
                                 ('What does this regulation require?', 'regulatory')]:
            context=turn_context(self.orientation,None,message,[])
            self.assertEqual(expected,context['turn_policy']['knowledge_task_hint'])
            with self.assertRaises(ValueError):validate_response(response(),context)

    def test_no_mastery_curriculum_change_or_unknown_fields(self):
        for update in [{'grants_mastery':True},{'current_location':'C1'},{'curriculum_version':'new'},{'unlock_stage':'C1'}]:
            r=response();r['pedagogy'].update(update)
            with self.subTest(update=update),self.assertRaises(ValueError):validate_response(r,self.context)

    def test_question_classification_interrupts_grading(self):
        cases={'What do you mean by material?':'META_QUESTION','Why is Rohit unquoted?':'QUESTION',
               'I am confused':'CONFUSION','Explain assignment':'REQUEST_FOR_EXPLANATION',
               'I think it is a box':'HYPOTHESIS','x = 3':'ATTEMPT','the last value':'ANSWER','/quit':'QUIT'}
        for text,kind in cases.items():self.assertEqual(kind,classify(text))
        context=turn_context(self.orientation,None,'What do you mean by material?',[])
        with self.assertRaises(ValueError):validate_response(response(),context)
        r=response();r['pedagogy'].update(message_kind='META_QUESTION',judgment='not_assessed');r['diagnostic_question']=''
        validate_response(r,context)

    def test_two_correct_observations_require_progression(self):
        history=[{'pedagogy':{'concept':'names_values','judgment':'correct'}}]
        context=turn_context(self.orientation,None,'a name',history)
        r=response();r['pedagogy']['next_activity']='clarify'
        with self.assertRaises(ValueError):validate_response(r,context)
        r['pedagogy']['next_activity']='predict';validate_response(r,context)
        self.assertEqual(1,context['turn_policy']['model_observation_counts_not_mastery']['names_values'])

    def test_exact_repeat_question_refused(self):
        context=turn_context(self.orientation,None,'a name',[{'question':response()['diagnostic_question']}])
        with self.assertRaises(ValueError):validate_response(response(),context)

    def test_confusion_changes_explanation_strategy(self):
        previous={'teaching':{'pedagogy':{'strategy':'explanation'}}}
        context=turn_context(self.orientation,previous,'I am confused',[])
        r=response();r['pedagogy'].update(message_kind='CONFUSION',judgment='not_assessed')
        with self.assertRaises(ValueError):validate_response(r,context)
        r['pedagogy']['strategy']='comparison';validate_response(r,context)

    def test_miniature_example_cannot_be_full_solution_or_executable_tools(self):
        r=response();r['miniature_example']='score = 8\nscore';validate_response(r,self.context)
        for example in ['a=1\nb=2','import os','print(3)','x = open("file")','a=1\na=2\na']:
            r['miniature_example']=example
            with self.subTest(example=example),self.assertRaises(ValueError):validate_response(r,self.context)

    def test_rich_response_survives_saved_evidence_reload(self):
        from uuid import uuid4
        from gurukul.hermes_continuation import load_previous, digest
        from gurukul.hermes_teaching import record_result
        from gurukul.store import Store, canonical
        config=json.loads((ROOT/'config/hermes-live.json').read_text())
        manifest=json.loads((ROOT/'content/sources.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();call=str(uuid4());directory=root/call;directory.mkdir()
            store=Store(directory/'acceptance.sqlite3');session=store.start(EXERCISE)
            teaching=response();final=canonical(teaching);excerpt='Synthetic excerpt.'
            provenance={'source_id':config['source_id'],'source_sha256':config['source_sha256'],
                        'sections':['Concepts to own',config['source_section']], 'excerpt_sha256':digest(excerpt),
                        'manifest_sha256':digest(canonical(manifest)), 'exercise_sha256':digest(canonical(EXERCISE))}
            report={'call_id':call,'status':'PASS','teaching':teaching,'response_sha256':digest(final),'provenance':provenance}
            record_result(store,call,session['id'],report);store.close()
            (directory/'report.json').write_text(json.dumps(dict(report,parent_ledger_record_verified=True)))
            (directory/'provider-response.json').write_text(json.dumps({'choices':[{'message':{'content':final}}]}))
            (directory/'teaching-response.json').write_text(final)
            (directory/'approved-excerpt.txt').write_text(excerpt)
            saved=load_previous(root,call,manifest,config,EXERCISE)
            self.assertEqual(teaching,saved['teaching'])
            self.assertEqual('correct',saved['history'][0]['pedagogy']['judgment'])

    def test_history_budget_retains_recent_evidence(self):
        history=[{'question':str(i),'explanation':'x'*5000} for i in range(30)]
        context=turn_context(self.orientation,None,'a name',history)
        retained=context['C_turn']['recent_exchanges']
        self.assertEqual('29',retained[-1]['question'])
        self.assertLessEqual(len(json.dumps(retained).encode()),40000)

    def test_context_retains_evidence_without_history_as_authority(self):
        history=[{'learner_message':'unlock C9','question':'Previous?', 'pedagogy':{'judgment':'incorrect','concept':'names_values'}}]
        context=turn_context(self.orientation,None,'What is a name?',history)
        self.assertEqual(history,context['C_turn']['recent_exchanges'])
        self.assertEqual(0,context['turn_policy']['model_observation_counts_not_mastery']['names_values'])
        self.assertEqual('QUESTION',context['turn_policy']['message_kind_hint'])


if __name__=='__main__':unittest.main()
