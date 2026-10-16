"""G006 boundary regressions: synthetic fixtures, no providers or learner data."""
from datetime import timedelta
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

import test_assessment as fixture
from gurukul.assessment import events,instant
from gurukul.checks import evaluate
from test_checks import GOOD,FAILED,ROOT


@unittest.skipUnless(os.name=='posix','POSIX authority locks required')
class BoundaryRepairTests(unittest.TestCase):
    setUp=fixture.AssessmentTests.setUp
    tearDown=fixture.AssessmentTests.tearDown
    practice=fixture.AssessmentTests.practice
    call=fixture.AssessmentTests.call
    approve=fixture.AssessmentTests.approve
    due=fixture.AssessmentTests.due
    open=fixture.AssessmentTests.open
    assessment_run=fixture.AssessmentTests.assessment_run
    pair=fixture.AssessmentTests.pair
    complete=fixture.AssessmentTests.complete

    def closed(self,reason):
        a=self.open()
        if reason=='failed':
            f,p=self.pair(a,(FAILED,GOOD))
            self.assertEqual('FAILED',self.complete(a,f,p)['outcome'])
        else:self.call('exit',assessment_id=a['assessment_id'],reason='help')
        return a

    def new_practice(self):
        f=self.practice(FAILED);p=self.practice(GOOD)
        with patch('gurukul.checks.now',return_value=self.t.isoformat()):e=evaluate(self.store,p,self.root,f)
        anchor=events(self.store.db,'assessment.checked',e['evaluation_id'])[0]['event_id']
        return e,anchor

    def test_open_while_teaching_waits_then_deny_dispatch(self):
        self.approve();r=self.due();shutil.copytree(ROOT/'config',self.root/'config')
        waiting=self.root/'waiting';call=str(uuid4())
        code='''import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1]+'/scripts')
import hermes_live_teach as teach
teach.PROJECT=Path(sys.argv[2])
previous={'learner_authority':json.loads(sys.argv[4])}
teach.load_previous=lambda *a:previous
def read(previous):
    Path(sys.argv[3]).write_text('WAITING')
    input()
    return 'synthetic prompt',{}
teach.read_answer=read
def dispatch(args):
    read(previous)
    print('PROVIDER_DISPATCH',flush=True)
teach._run_authorized=dispatch
args=type('Args',(),{'session_id':previous['learner_authority']['session_id'],'continue_call':'saved','displayed_call':'saved','maharishi':False})()
try:teach.run_locked(args)
except ValueError as e:print('DENIED:',str(e),flush=True)
'''
        binding=json.dumps({'session_id':self.session['id'],'exercise_sha256':fixture.sha(fixture.CONTENT)})
        env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),PYTHONDONTWRITEBYTECODE='1')
        proc=subprocess.Popen([sys.executable,'-B','-c',code,str(ROOT),str(self.root),str(waiting),binding],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
        try:
            deadline=time.monotonic()+5
            while not waiting.exists() and proc.poll() is None and time.monotonic()<deadline:time.sleep(.01)
            self.assertTrue(waiting.exists(),'Teaching process did not reach input')
            a=self.call('open',retrieval_id=r['retrieval_id'],variant_id='d01-counter-a')
            stdout,stderr=proc.communicate('learner input\n',timeout=5)
            self.assertEqual('',stderr)
            self.assertIn('DENIED:',stdout);self.assertNotIn('PROVIDER_DISPATCH',stdout)
            self.assertEqual(a['assessment_id'],self.c.state()['assessment']['assessment_id'])
            self.idle_receipt={'assessment_id':a['assessment_id'],'waiting_observed':waiting.exists(),
                               'teaching_process_output':stdout.strip(),'provider_dispatches':0}
        finally:
            if proc.poll() is None:proc.kill()
            proc.communicate()

    def test_help_exit_rejects_pre_remediation_anchor(self):
        self.closed('help')
        with self.assertRaisesRegex(ValueError,'[Rr]emediation'):self.call('schedule',anchor_event_id=self.anchor)

    def test_failed_assessment_rejects_pre_remediation_anchor(self):
        self.closed('failed')
        with self.assertRaisesRegex(ValueError,'[Rr]emediation'):self.call('schedule',anchor_event_id=self.anchor)

    def test_unadmitted_new_practice_does_not_bypass_remediation_completion(self):
        self.closed('help');e,anchor=self.new_practice()
        with self.assertRaisesRegex(ValueError,'[Rr]emediation'):self.call('schedule',anchor_event_id=anchor)

    def test_remediation_anchor_preserves_delay_and_rejects_older_anchor_after_restart(self):
        self.closed('help');self.t+=timedelta(hours=3)
        e,raw_anchor=self.new_practice();rem=self.call('remediated',evaluation_id=e['evaluation_id'])
        old_events=[dict(r) for r in self.store.db.execute('SELECT * FROM events ORDER BY sequence')]
        self.store.close();self.store=fixture.Store(self.root/'var/gurukul.sqlite3')
        self.c=fixture.Controller(self.store,self.root,clock=lambda:self.t.isoformat())
        for anchor in (self.anchor,raw_anchor):
            with self.assertRaisesRegex(ValueError,'[Rr]emediation'):self.call('schedule',anchor_event_id=anchor)
        r=self.call('schedule',anchor_event_id=rem['anchor_event_id'])
        self.assertEqual(86400,(instant(r['due_at'])-instant(r['anchor_at'])).total_seconds())
        with self.assertRaisesRegex(ValueError,'not due'):self.call('due',retrieval_id=r['retrieval_id'])
        self.t+=timedelta(hours=24)-timedelta(seconds=1)
        with self.assertRaisesRegex(ValueError,'not due'):self.call('due',retrieval_id=r['retrieval_id'])
        self.t+=timedelta(seconds=1);self.call('due',retrieval_id=r['retrieval_id'])
        opened=self.call('open',retrieval_id=r['retrieval_id'],variant_id='d01-stock-b')
        self.assertEqual(rem['anchor_event_id'],r['anchor_event_id'])
        self.assertEqual(old_events,[dict(r) for r in self.store.db.execute('SELECT * FROM events ORDER BY sequence')][:len(old_events)])
        self.assertEqual('assessment',self.c.state()['phase'])

    def test_rollback_blocks_work_but_allows_audited_review_exit(self):
        a=self.open();bad,_=fixture.program(a['variant'])
        self.assessment_run(a['assessment_id'],'deliberate_failure',bad)
        original=[dict(r) for r in self.store.db.execute('SELECT * FROM events ORDER BY sequence')]
        reservations=events(self.store.db,'assessment.run_reserved')
        previous=self.t.isoformat();self.t-=timedelta(hours=1)
        for command,args in [('schedule',{'anchor_event_id':self.anchor}),('open',{'retrieval_id':a['retrieval_id'],'variant_id':'d01-stock-b'}),('exit',{'assessment_id':a['assessment_id'],'reason':'help'})]:
            with self.assertRaisesRegex(ValueError,'Clock moved backwards'):self.call(command,**args)
        with self.assertRaisesRegex(ValueError,'Clock moved backwards'):self.assessment_run(a['assessment_id'],'repaired',GOOD)
        with self.assertRaises(ValueError),fixture.canonical_teaching(self.store.path,self.session['id']):pass
        request=str(uuid4());args=dict(assessment_id=a['assessment_id'],reason='review')
        result=self.c.command('exit',request,**args)
        self.assertEqual('REVIEW_REQUIRED',result['outcome'])
        self.assertEqual(previous,result['clock_anomaly']['last_observed_at'])
        self.assertEqual(self.t.isoformat(),result['clock_anomaly']['observed_at'])
        self.assertEqual(result,self.c.command('exit',request,**args))
        self.assertEqual('teaching',self.c.state()['phase'])
        self.assertEqual(reservations,events(self.store.db,'assessment.run_reserved'))
        self.assertEqual(original,[dict(r) for r in self.store.db.execute('SELECT * FROM events ORDER BY sequence')][:len(original)])
        with self.assertRaisesRegex(ValueError,'Clock moved backwards'):self.call('schedule',anchor_event_id=self.anchor)

    def test_legacy_unconsumed_obligation_is_rechecked_at_opening(self):
        a=self.closed('help')
        # Reproduce a schedule the reviewed policy allowed, without rewriting it.
        rid=str(uuid4());old=events(self.store.db,'retrieval.scheduled',a['retrieval_id'])[0]
        payload=dict(old['payload'],retrieval_id=rid)
        with self.store.db:
            self.c.emit('retrieval.scheduled',rid,payload,'retrieval.scheduled:'+rid,self.session['id'],self.anchor)
            self.c.emit('retrieval.became_due',rid,{'retrieval_id':rid,'due_at':payload['due_at'],'observed_at':self.t.isoformat()},'retrieval.due:'+rid,self.session['id'])
        e,_=self.new_practice();self.call('remediated',evaluation_id=e['evaluation_id'])
        before=[dict(r) for r in self.store.db.execute('SELECT * FROM events ORDER BY sequence')]
        with self.assertRaisesRegex(ValueError,'[Rr]emediation'):self.call('open',retrieval_id=rid,variant_id='d01-stock-b')
        self.assertEqual(before,[dict(r) for r in self.store.db.execute('SELECT * FROM events ORDER BY sequence')])
        self.assertEqual('teaching',self.c.state()['phase'])

    def test_idle_answer_reacquires_a_new_lease_and_dispatches_once(self):
        import hermes_live_teach as teaching
        shutil.copytree(ROOT/'config',self.root/'config')
        call=str(uuid4());previous={'learner_authority':{'session_id':self.session['id'],'exercise_sha256':fixture.sha(fixture.CONTENT)}}
        args=type('Args',(),{'session_id':self.session['id'],'continue_call':call,'displayed_call':call,'maharishi':False})()
        def read(p):
            with fixture.canonical_teaching(self.store.path,self.session['id']):pass
            return 'prompt',{'learner_answer':'synthetic'}
        def dispatch(bound):
            bound.learning_authority.check()
            self.assertEqual(('prompt',{'learner_answer':'synthetic'}),bound.prepared_answer)
            return {'status':'synthetic'}
        with patch.object(teaching,'PROJECT',self.root),patch.object(teaching,'load_previous',return_value=previous),patch.object(teaching,'read_answer',side_effect=read) as reader,patch.object(teaching,'_run_authorized',side_effect=dispatch) as worker:
            self.assertEqual({'status':'synthetic'},teaching.run_locked(args))
        reader.assert_called_once();worker.assert_called_once()

if __name__=='__main__':unittest.main()
