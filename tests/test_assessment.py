"""Synthetic clocks, fixtures and mocked providers: not delayed learner retrieval."""
import contextlib
from datetime import datetime,timedelta,timezone
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from gurukul.assessment import Controller,catalogue,candidate,events,sha
from gurukul.checks import evaluate
from gurukul.store import Store
from gurukul.submissions import submit,inspect
from gurukul.learning_authority import canonical_teaching
from test_checks import GOOD,FAILED,CONTENT,ROOT

sys.path.insert(0,str(ROOT/'scripts'))
import hermes_live_teach as teaching


def program(c):
    d=c['descriptor'];initial=d['initial_values'];change=d['reassignments']
    code=''.join(k+'='+repr(v)+'\n' for k,v in initial.items())
    code+='print('+','.join(initial)+')\n'
    code+=''.join(k+'='+repr(v)+'\n' for k,v in change.items())
    code+='print('+','.join(change)+')\n'
    first=next(k for k,v in initial.items() if type(v) is str)
    broken=code.replace(first+'='+repr(initial[first]),first+'='+initial[first],1)
    return broken,code


@unittest.skipUnless(os.name=='posix','POSIX runner and file locks required')
class AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='g006-synthetic-')
        self.root=Path(self.tmp.name);shutil.copytree(ROOT/'content',self.root/'content')
        self.store=Store(self.root/'var/gurukul.sqlite3');self.session=self.store.start(CONTENT)
        self.t=datetime.now(timezone.utc)+timedelta(seconds=1)
        self.c=Controller(self.store,self.root,clock=lambda:self.t.isoformat())
        self.f=self.practice(FAILED);self.p=self.practice(GOOD)
        with patch('gurukul.checks.now',return_value=self.t.isoformat()):
            self.eval=evaluate(self.store,self.p,self.root,self.f)
        self.anchor=events(self.store.db,'assessment.checked',self.eval['evaluation_id'])[0]['event_id']

    def tearDown(self):self.store.close();self.tmp.cleanup()
    def practice(self,code):
        path=self.root/'synthetic.py';path.write_text(code);return submit(self.store,path)['id']
    def call(self,cmd,**args):return self.c.command(cmd,str(uuid4()),**args)
    def approve(self):
        path=self.root/'content/assessments/d01-candidates.json';data=json.loads(path.read_text())
        for c in data['candidates']:
            c['approval']={'status':'approved','reference':'SYNTHETIC-TEST-ONLY','descriptor_sha256':c['descriptor_sha256'],'rules_sha256':c['rules_sha256']}
        path.write_text(json.dumps(data))
    def due(self):
        r=self.call('schedule',anchor_event_id=self.anchor)
        self.t+=timedelta(days=1)
        self.call('due',retrieval_id=r['retrieval_id']);return r
    def open(self):
        self.approve();r=self.due();return self.call('open',retrieval_id=r['retrieval_id'],variant_id='d01-counter-a')
    def assessment_run(self,aid,role,code,request=None):
        path=self.root/'assessment.py';path.write_text(code)
        return self.c.submit(aid,request or str(uuid4()),role,path)
    def pair(self,opened,codepair=None):
        bad,good=codepair or program(opened['variant'])
        f=self.assessment_run(opened['assessment_id'],'deliberate_failure',bad)
        p=self.assessment_run(opened['assessment_id'],'repaired',good);return f,p
    def complete(self,a,f,p):return self.call('complete',assessment_id=a['assessment_id'],attempt_id=p['id'],failed_attempt_id=f['id'])
    def declare(self,f,p,kind='none_declared'):
        return self.store.record_assistance(p['id'],{'request_id':str(uuid4()),'kind':kind,'steps':['construction','repair'],'timing':'during_work','origin':'learner_declaration'},f['id'])

    def test_production_catalogue_approved_with_exact_reviewed_bindings(self):
        data=catalogue(ROOT)
        expected={'d01-counter-a':'c86dabca70790a631150cb0ecac3ddf126b4d1279ba6bc6826657fe0bfcf33dd',
                  'd01-stock-b':'8185f84147c0c5f6ba737f609618c309f543db891ea1b8d12423e572a292ee53'}
        self.assertEqual(set(expected),{c['id'] for c in data['candidates']})
        for c in data['candidates']:
            self.assertEqual(expected[c['id']],c['descriptor_sha256'])
            self.assertEqual('c8b8bc914b99843047c860a8a66fc761cd2bdd8ede783e50ffe324ebe51d59f6',c['rules_sha256'])
            self.assertEqual({'status':'approved','reference':'G006-CATALOGUE-RECORD',
                              'descriptor_sha256':expected[c['id']],'rules_sha256':c['rules_sha256']},c['approval'])
            self.assertEqual(c,candidate(ROOT,c['id'],sha(CONTENT)))
        r=self.due()
        opened=self.call('open',retrieval_id=r['retrieval_id'],variant_id='d01-counter-a')
        self.assertEqual('G006-CATALOGUE-RECORD',opened['variant']['approval']['reference'])

    def test_unapproved_temporary_candidates_remain_unavailable(self):
        path=self.root/'content/assessments/d01-candidates.json';data=json.loads(path.read_text())
        for c in data['candidates']:
            c['approval']={'status':'unapproved','reference':None,'descriptor_sha256':None,'rules_sha256':None}
        path.write_text(json.dumps(data))
        r=self.due()
        for c in data['candidates']:
            with self.assertRaisesRegex(ValueError,'not approved'):
                self.call('open',retrieval_id=r['retrieval_id'],variant_id=c['id'])
        self.assertEqual('teaching',self.store.resume()['session']['phase'])
        self.assertEqual([],events(self.store.db,'assessment.opened'))

    def test_schedule_due_does_not_open_or_grant_authority(self):
        r=self.call('schedule',anchor_event_id=self.anchor)
        with self.assertRaisesRegex(ValueError,'not due'):self.call('due',retrieval_id=r['retrieval_id'])
        self.t+=timedelta(days=1)
        result=self.call('due',retrieval_id=r['retrieval_id'])
        self.assertFalse(result['grants_mastery']);self.assertEqual('teaching',self.c.state()['phase'])
        with canonical_teaching(self.store.path,self.session['id']):pass

    def test_lifecycle_duplicate_and_conflicting_request(self):
        request=str(uuid4())
        a=self.c.command('schedule',request,anchor_event_id=self.anchor)
        self.assertEqual(a,self.c.command('schedule',request,anchor_event_id=self.anchor))
        with self.assertRaisesRegex(ValueError,'Conflicting'):self.c.command('due',request,retrieval_id=a['retrieval_id'])
        self.assertEqual(1,len(events(self.store.db,'retrieval.scheduled')))

    def test_only_one_obligation_and_explicit_due_required(self):
        r=self.call('schedule',anchor_event_id=self.anchor);self.approve()
        with self.assertRaisesRegex(ValueError,'already exists'):self.call('schedule',anchor_event_id=self.anchor)
        self.t+=timedelta(days=1)
        with self.assertRaisesRegex(ValueError,'due observation'):self.call('open',retrieval_id=r['retrieval_id'],variant_id='d01-counter-a')

    def test_pass_complete_for_review_preserves_base_and_no_mastery(self):
        a=self.open();f,p=self.pair(a)
        self.assertEqual('program_error',f['status'])
        self.assertEqual('assessment',self.c.state()['phase'])
        self.declare(f,p)
        result=self.complete(a,f,p)
        self.assertEqual('COMPLETED_FOR_REVIEW',result['outcome'])
        self.assertEqual('DECLARED_ONLY',result['independence_status'])
        self.assertEqual('READY_FOR_REVIEW',result['review_eligibility'])
        for k in ('grants_mastery','grants_verified_independence','advances_curriculum'):self.assertFalse(result[k])
        self.assertEqual('teaching',self.c.state()['phase'])
        self.assertEqual(CONTENT,self.store.resume()['exercise'])

    def test_missing_declaration_is_preserved_as_unknown_review_only(self):
        a=self.open();f,p=self.pair(a);r=self.complete(a,f,p)
        self.assertEqual('COMPLETED_FOR_REVIEW',r['outcome'])
        self.assertEqual(('HOLD','UNKNOWN'),(r['review_eligibility'],r['independence_status']))

    def test_final_program_failure_enters_remediation(self):
        a=self.open();bad,good=program(a['variant'])
        f=self.assessment_run(a['assessment_id'],'deliberate_failure',bad)
        p=self.assessment_run(a['assessment_id'],'repaired','print(42)\n')
        self.assertEqual('FAILED',self.complete(a,f,p)['outcome'])
        self.assertEqual('remediation',self.c.state()['phase'])
        with canonical_teaching(self.store.path,self.session['id']):pass

    def test_wrong_variant_cannot_hide_behind_base_checks_pass(self):
        a=self.open();f,p=self.pair(a,(FAILED,GOOD))
        r=self.complete(a,f,p)
        self.assertEqual('FAILED',r['outcome']);self.assertEqual('Wrong variant task data',r['reason'])

    def test_borrowed_practice_pair_cannot_complete_assessment(self):
        a=self.open()
        with self.assertRaisesRegex(ValueError,'own failed/repaired'):
            self.call('complete',assessment_id=a['assessment_id'],attempt_id=self.p,failed_attempt_id=self.f)

    def test_ordinary_run_cannot_bypass_open_assessment(self):
        self.open()
        with patch('gurukul.submissions.execute') as execute,self.assertRaises(ValueError):self.practice(GOOD)
        execute.assert_not_called()

    def test_submission_replay_never_executes_twice(self):
        a=self.open();bad,_=program(a['variant']);request=str(uuid4())
        first=self.assessment_run(a['assessment_id'],'deliberate_failure',bad,request)
        with patch('gurukul.submissions.execute',side_effect=AssertionError('must not rerun')):
            self.assertEqual(first,self.assessment_run(a['assessment_id'],'deliberate_failure',bad,request))
        with self.assertRaisesRegex(ValueError,'Conflicting'):self.assessment_run(a['assessment_id'],'deliberate_failure',GOOD,request)
        self.assertEqual(1,len(self.c.state()['runs']))

    def test_interrupted_snapshot_reservation_restart_and_explicit_recovery(self):
        a=self.open();bad,_=program(a['variant']);request=str(uuid4())
        with patch('gurukul.submissions.execute',side_effect=RuntimeError('synthetic worker interruption')),self.assertRaises(RuntimeError):
            self.assessment_run(a['assessment_id'],'deliberate_failure',bad,request)
        state=self.c.state();old=state['pending'][0]
        self.assertEqual('INTERRUPTED',state['status'])
        self.assertEqual(bad,(self.store.state_dir/'evidence'/old/'submission.py').read_text())
        self.store.close();self.store=Store(self.root/'var/gurukul.sqlite3');self.c=Controller(self.store,self.root,clock=lambda:self.t.isoformat())
        with patch('gurukul.submissions.execute',side_effect=AssertionError('no duplicate execution')):
            self.assertEqual('pending_or_interrupted',self.assessment_run(a['assessment_id'],'deliberate_failure',bad,request)['status'])
        with self.assertRaises(ValueError):self.assessment_run(a['assessment_id'],'deliberate_failure',bad)
        self.call('resume',assessment_id=a['assessment_id'])
        self.assertEqual('program_error',self.assessment_run(a['assessment_id'],'deliberate_failure',bad)['status'])
        self.assertEqual('pending_or_interrupted',inspect(self.store,old)['status'])
        self.assertEqual(2,len(self.c.state()['runs']))

    def test_execution_limits_and_reservations_survive_failures(self):
        a=self.open();bad,_=program(a['variant'])
        for _ in range(4):
            with patch('gurukul.submissions.execute',side_effect=RuntimeError('synthetic')),self.assertRaises(RuntimeError):self.assessment_run(a['assessment_id'],'deliberate_failure',bad)
            self.call('resume',assessment_id=a['assessment_id'])
        with self.assertRaisesRegex(ValueError,'exhausted'):self.assessment_run(a['assessment_id'],'deliberate_failure',bad)
        self.assertEqual(4,len(self.c.state()['runs']))

    def test_infrastructure_and_interruption_are_not_program_failure(self):
        a=self.open()
        from gurukul.runner import execute
        def infrastructure(*args):
            value=execute(b'print(1)\n');value.update(status='runner_error',runner_error='synthetic infrastructure');return value
        with patch('gurukul.submissions.execute',side_effect=infrastructure):r=self.assessment_run(a['assessment_id'],'deliberate_failure',FAILED)
        self.assertEqual('runner_error',r['status']);self.assertEqual('OPEN',self.c.state()['status'])
        self.assertEqual([],events(self.store.db,'assessment.closed'))

    def test_deadline_requires_exit_and_never_silently_enables_tutor(self):
        a=self.open();self.t+=timedelta(minutes=21)
        self.assertEqual('INTERRUPTED',self.c.state()['status'])
        with self.assertRaises(ValueError):self.call('resume',assessment_id=a['assessment_id'])
        with self.assertRaises(ValueError),canonical_teaching(self.store.path,self.session['id']):pass
        r=self.call('exit',assessment_id=a['assessment_id'],reason='interrupted')
        self.assertEqual('INTERRUPTED',r['outcome']);self.assertEqual('teaching',self.c.state()['phase'])

    def test_help_exit_is_explicit_before_tutoring(self):
        a=self.open()
        with self.assertRaises(ValueError),canonical_teaching(self.store.path,self.session['id']):pass
        r=self.call('exit',assessment_id=a['assessment_id'],reason='help')
        self.assertEqual('HELP_REQUESTED',r['outcome'])
        with canonical_teaching(self.store.path,self.session['id']):pass
        self.assertEqual([],events(self.store.db,'assistance.recorded'))

    def test_phase_and_event_roll_back_together(self):
        self.approve();r=self.due()
        self.store.db.execute("CREATE TRIGGER reject_open BEFORE INSERT ON events WHEN NEW.event_type='assessment.opened' BEGIN SELECT RAISE(ABORT,'synthetic'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.call('open',retrieval_id=r['retrieval_id'],variant_id='d01-counter-a')
        self.assertEqual('teaching',self.store.resume()['session']['phase'])
        self.assertEqual([],events(self.store.db,'assessment.opened'))

    def test_mismatched_phase_fails_closed(self):
        self.open()
        with self.store.db:self.store.db.execute("UPDATE sessions SET phase='teaching'")
        with self.assertRaises(ValueError):self.c.state()
        with self.assertRaises(ValueError),canonical_teaching(self.store.path,self.session['id']):pass

    def test_shared_lock_excludes_opening_and_concurrent_process(self):
        self.approve();r=self.due()
        with canonical_teaching(self.store.path,self.session['id']):
            with self.assertRaisesRegex(ValueError,'holds learner authority'):self.call('open',retrieval_id=r['retrieval_id'],variant_id='d01-counter-a')
            env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),PYTHONDONTWRITEBYTECODE='1')
            p=subprocess.run([sys.executable,'-B','-m','gurukul','--root',str(self.root),'assessment-open',r['retrieval_id'],'--variant-id','d01-counter-a','--request-id',str(uuid4())],capture_output=True,text=True,env=env)
            self.assertNotEqual(0,p.returncode);self.assertIn('holds learner authority',p.stderr)
        self.call('open',retrieval_id=r['retrieval_id'],variant_id='d01-counter-a')

    def test_missing_authority_and_cached_display_are_denied(self):
        report={'teaching':{'explanation':'MUST NOT DISPLAY','diagnostic_question':''}}
        out=io.StringIO()
        with contextlib.redirect_stdout(out),self.assertRaises(ValueError):teaching.display_teaching(report)
        self.assertNotIn('MUST NOT DISPLAY',out.getvalue())
        with patch.object(teaching,'_run_authorized') as dispatch,self.assertRaises(ValueError):
            teaching.run_locked(type('Args',(),{'session_id':None})())
        dispatch.assert_not_called()

    def test_active_assessment_blocks_new_continuation_cached_and_supervisor_predispatch(self):
        self.open()
        args=type('Args',(),{'session_id':self.session['id'],'continue_call':'saved-call'})()
        with patch.object(teaching,'PROJECT',self.root),patch.object(teaching,'_run_authorized') as dispatch,self.assertRaises(ValueError):teaching.run_locked(args)
        dispatch.assert_not_called()
        from gurukul.maharishi import supervise,carried_state
        provider=type('Provider',(),{'decide':lambda *a:(_ for _ in ()).throw(AssertionError('no dispatch'))})()
        with self.assertRaises(ValueError):supervise({},carried_state(None,''),provider,self.store,self.session['id'],str(uuid4()))

    def test_expired_and_inconsistent_leases_cannot_display(self):
        with canonical_teaching(self.store.path,self.session['id']) as lease:pass
        with self.assertRaises(ValueError):teaching.display_teaching({'teaching':{}},lease)
        from gurukul.learning_authority import store_teaching
        other=Store(self.root/'integration/acceptance.sqlite3');s=other.start(CONTENT)
        try:
            with self.assertRaisesRegex(ValueError,'Missing canonical'):
                with store_teaching(other,s['id']):pass
        finally:other.close()

    def test_used_variant_and_unscoped_exposure_cannot_be_reset(self):
        a=self.open();self.call('exit',assessment_id=a['assessment_id'],reason='abandon')
        r=self.call('schedule',anchor_event_id=self.anchor);self.t+=timedelta(days=1);self.call('due',retrieval_id=r['retrieval_id'])
        with self.assertRaisesRegex(ValueError,'Previously opened'):self.call('open',retrieval_id=r['retrieval_id'],variant_id='d01-counter-a')
        self.declare({'id':self.f},{'id':self.p},'solution_exposure')
        with self.assertRaisesRegex(ValueError,'Unscoped historical'):self.call('open',retrieval_id=r['retrieval_id'],variant_id='d01-stock-b')

    def test_remediation_requires_new_practice_then_later_new_variant(self):
        a=self.open();self.call('exit',assessment_id=a['assessment_id'],reason='help')
        with self.assertRaisesRegex(ValueError,'after assessment exit'):self.call('remediated',evaluation_id=self.eval['evaluation_id'])
        f=self.practice(FAILED);p=self.practice(GOOD)
        with patch('gurukul.checks.now',return_value=self.t.isoformat()):e=evaluate(self.store,p,self.root,f)
        rem=self.call('remediated',evaluation_id=e['evaluation_id'])
        r=self.call('schedule',anchor_event_id=rem['anchor_event_id']);self.t+=timedelta(days=1)
        self.call('due',retrieval_id=r['retrieval_id'])
        b=self.call('open',retrieval_id=r['retrieval_id'],variant_id='d01-stock-b')
        self.assertNotEqual(a['assessment_id'],b['assessment_id']);self.assertEqual(1,len(events(self.store.db,'assessment.closed')))

    def test_changed_descriptor_hash_and_mid_attempt_rules_refused(self):
        a=self.open();f,p=self.pair(a)
        path=self.root/'content/assessments/d01-candidates.json';data=json.loads(path.read_text());data['candidates'][0]['descriptor']['initial_values']['count']=999;path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'hash mismatch'):self.complete(a,f,p)
        self.assertEqual('assessment',self.store.resume()['session']['phase'])

    def test_clock_rollback_is_not_due_evidence(self):
        self.call('schedule',anchor_event_id=self.anchor);self.t-=timedelta(seconds=1)
        with self.assertRaisesRegex(ValueError,'Clock moved backwards'):self.call('schedule',anchor_event_id=self.anchor)

    def test_missing_pair_is_recorded_without_closing(self):
        a=self.open()
        r=self.call('complete',assessment_id=a['assessment_id'],attempt_id=None,failed_attempt_id=None)
        self.assertEqual('NEEDS_EVIDENCE',r['outcome'])
        self.assertEqual('OPEN',self.c.state()['status'])
        self.assertEqual('NEEDS_EVIDENCE',events(self.store.db,'assessment.observation_recorded')[-1]['payload']['outcome'])

    def test_infrastructure_in_failed_role_cannot_become_learner_failure(self):
        a=self.open();bad,good=program(a['variant'])
        from gurukul.runner import execute
        def infrastructure(*args):
            value=execute(b'print(1)\n');value.update(status='runner_error',runner_error='synthetic infrastructure');return value
        with patch('gurukul.submissions.execute',side_effect=infrastructure):f=self.assessment_run(a['assessment_id'],'deliberate_failure',bad)
        p=self.assessment_run(a['assessment_id'],'repaired',good)
        self.assertEqual('EXECUTION_BLOCKED',self.complete(a,f,p)['outcome'])
        self.assertEqual('OPEN',self.c.state()['status'])

    def test_checker_spec_pin_prevents_completion_under_changed_rules(self):
        a=self.open();f,p=self.pair(a)
        path=self.root/'content/checks/d01-v1.json';path.write_text(path.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'checker/curriculum/policy changed'):self.complete(a,f,p)
        self.assertEqual('OPEN',self.c.state()['status'])

    def test_old_submissions_checked_after_exit_are_not_new_remediation(self):
        f=self.practice(FAILED);p=self.practice(GOOD)
        a=self.open();self.call('exit',assessment_id=a['assessment_id'],reason='help')
        with patch('gurukul.checks.now',return_value=self.t.isoformat()):e=evaluate(self.store,p,self.root,f)
        with self.assertRaisesRegex(ValueError,'newly submitted practice'):self.call('remediated',evaluation_id=e['evaluation_id'])

    def test_closing_phase_rolls_back_when_command_receipt_fails(self):
        a=self.open()
        self.store.db.execute("CREATE TRIGGER reject_receipt BEFORE INSERT ON events WHEN NEW.event_type='learning.command_recorded' BEGIN SELECT RAISE(ABORT,'synthetic'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.call('exit',assessment_id=a['assessment_id'],reason='help')
        self.assertEqual('OPEN',self.c.state()['status'])
        self.assertEqual([],events(self.store.db,'assessment.closed'))

    def test_local_teaching_exercise_must_match_canonical_before_dispatch(self):
        path=self.root/'content/c0_b01/d01.json'
        data=json.loads(path.read_text());data['version']=999;path.write_text(json.dumps(data))
        args=type('Args',(),{'session_id':self.session['id']})()
        with patch.object(teaching,'PROJECT',self.root),patch.object(teaching,'_run_authorized') as dispatch,self.assertRaisesRegex(ValueError,'exercise differs'):
            teaching.run_locked(args)
        dispatch.assert_not_called()


if __name__=='__main__':unittest.main()
