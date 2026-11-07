"""Synthetic workspace service/HTTP tests. No real learner ledger or providers."""
from datetime import datetime,timedelta,timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch
from uuid import uuid4

from gurukul.store import Store,canonical
from gurukul.checks import evaluate
from gurukul.submissions import submit
from gurukul.assessment import Controller,events,sha
from gurukul.workspace import Workspace,Server,child_id
from gurukul import workspace_store as ws
from test_checks import ROOT,CONTENT,GOOD,FAILED
from test_assessment import program


@unittest.skipUnless(os.name=='posix','POSIX runner/authority required')
class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='g007-synthetic-');self.root=Path(self.tmp.name)
        shutil.copytree(ROOT/'content',self.root/'content')
        s=Store(self.root/'var/gurukul.sqlite3');self.sid=s.start(CONTENT)['id']
        f=self.seed(s,FAILED);p=self.seed(s,GOOD)
        old=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
        with patch('gurukul.checks.now',return_value=old):e=evaluate(s,p,self.root,f)
        anchor=events(s.db,'assessment.checked',e['evaluation_id'])[0]['event_id']
        self.retrieval=Controller(s,self.root).command('schedule',str(uuid4()),anchor_event_id=anchor)
        s.close();self.w=Workspace(self.root,self.sid)
    def tearDown(self):self.w.close();self.tmp.cleanup()
    def seed(self,s,source):
        path=self.root/'fixture.py';path.write_text(source);return submit(s,path)['id']
    def save(self,source,context='practice'):
        return self.w.save(context,self.w.state(context)['draft']['revision'],source)
    def run(self,*args,**kwargs):return super().run(*args,**kwargs)
    def action(self,source,role,action='run',context='practice'):
        d=self.save(source,context);return self.w.perform(context,d['revision'],role,action)
    def opened(self):
        a=self.w.start();return a['context'],a['opening']
    def failed(self,aid,opened):
        bad,good=program(opened['variant']);f=self.action(bad,'deliberate_failure',context=aid);return f,good

    def test_concurrent_operation_lock_cannot_execute_or_save(self):
        d=self.save(GOOD)
        from gurukul.workspace import operation_lock
        with operation_lock(self.w.store.state_dir),patch('gurukul.submissions.execute',side_effect=AssertionError('no execution')):
            with self.assertRaises(ValueError):self.w.perform('practice',d['revision'],'repaired','run')
            with self.assertRaises(ValueError):self.w.save('practice',d['revision'],'lost')
        self.assertEqual(d['source'],self.w.state()['draft']['source'])

    def test_crash_after_intent_before_snapshot_does_not_execute_on_retry(self):
        d=self.save(GOOD)
        with patch('gurukul.workspace.save_new',side_effect=RuntimeError('snapshot write interrupted')),self.assertRaises(RuntimeError):
            self.w.perform('practice',d['revision'],'repaired','run')
        self.w.close();self.w=Workspace(self.root,self.sid)
        with patch('gurukul.submissions.execute',side_effect=AssertionError('no retry execution')):
            r=self.w.perform('practice',d['revision'],'repaired','run')
        self.assertEqual('INTERRUPTED_BEFORE_RESULT',r['status'])

    def test_interpreter_requirement_precedes_any_state_access(self):
        from gurukul.workspace import main
        with patch('gurukul.workspace.sys.version_info',(3,9)),patch('gurukul.workspace.Store',side_effect=AssertionError('no state access')):
            with self.assertRaisesRegex(SystemExit,'3.11'):main()

    def test_preparation_neutral_no_variant_data_no_opening(self):
        state=self.w.state();self.assertEqual('',state['draft']['source'])
        self.assertNotIn('initial_values',state['task']);self.assertNotIn('cedar',json.dumps(state))
        self.assertEqual([],events(self.w.store.db,'assessment.opened'))
        self.assertIsNone(state['deadline']);self.assertTrue(state['retrieval_available'])

    def test_draft_restart_and_stale_tab_compare_and_swap(self):
        self.w.save('practice',0,'# own draft\n');self.w.close();self.w=Workspace(self.root,self.sid)
        self.assertEqual('# own draft\n',self.w.state()['draft']['source'])
        with self.assertRaisesRegex(ValueError,'Stale draft'):self.w.save('practice',0,'LOST UPDATE')
        self.assertEqual(1,self.w.state()['draft']['revision'])

    def test_practice_double_click_and_restart_never_duplicate_execution(self):
        d=self.save(GOOD);r=self.w.perform('practice',d['revision'],'repaired','run')
        count=self.w.store.db.execute('SELECT count(*) FROM executions').fetchone()[0]
        self.w.close();self.w=Workspace(self.root,self.sid)
        with patch('gurukul.submissions.execute',side_effect=AssertionError('duplicate execution')):
            self.assertEqual(r,self.w.perform('practice',d['revision'],'repaired','run'))
        self.assertEqual(count,self.w.store.db.execute('SELECT count(*) FROM executions').fetchone()[0])

    def test_later_draft_cannot_change_immutable_snapshot(self):
        r=self.action(GOOD,'repaired');a=r['attempt'];self.save('print(999)\n')
        path=self.w.store.state_dir/'evidence'/a['id']/'submission.py'
        self.assertEqual(a['source_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(GOOD,path.read_text())

    def test_practice_run_and_submit_reuse_matching_result_and_check(self):
        self.action(FAILED,'deliberate_failure');r=self.action(GOOD,'repaired')
        d=self.w.state()['draft'];count=self.w.store.db.execute('SELECT count(*) FROM executions').fetchone()[0]
        result=self.w.perform('practice',d['revision'],'repaired','submit')
        self.assertEqual('PRACTICE_CHECK_RECORDED',result['status'])
        self.assertEqual('CHECKS_PASS',result['observation']['outcome'])
        self.assertEqual(r['attempt']['id'],result['attempt']['id'])
        self.assertEqual(count,self.w.store.db.execute('SELECT count(*) FROM executions').fetchone()[0])

    def test_assessment_start_idempotent_blank_draft_pinned_deadline(self):
        self.save('# previous practice')
        aid,a=self.opened();again=self.w.start()
        self.assertEqual(aid,again['context']);self.assertEqual('',self.w.state(aid)['draft']['source'])
        self.assertEqual(1,len(events(self.w.store.db,'assessment.opened')))
        self.assertEqual(a['deadline'],self.w.state(aid)['deadline'])
        self.assertEqual(4,self.w.state(aid)['reservation_limit'])

    def test_full_assessment_submit_captures_and_completes_without_ids(self):
        aid,a=self.opened();f,good=self.failed(aid,a)
        result=self.action(good,'repaired','submit',aid)
        self.assertEqual('COMPLETION_CONFIRMED',result['status'])
        self.assertEqual('COMPLETED_FOR_REVIEW',result['observation']['outcome'])
        self.assertEqual('CLOSED',self.w.state(aid)['lifecycle']['status'])
        self.assertEqual(2,self.w.state(aid)['reservations_used'])
        self.assertEqual('HOLD',result['observation']['review_eligibility'])
        self.assertFalse(result['grants_verified_independence']);self.assertFalse(result['advances_curriculum'])

    def test_assessment_run_then_submit_no_extra_reservation(self):
        aid,a=self.opened();f,good=self.failed(aid,a)
        r=self.action(good,'repaired','run',aid);d=self.w.state(aid)['draft']
        result=self.w.perform(aid,d['revision'],'repaired','submit')
        self.assertEqual(r['attempt']['id'],result['attempt']['id'])
        self.assertEqual(2,self.w.state(aid)['reservations_used'])

    def test_completed_role_cannot_be_replaced_by_new_draft(self):
        aid,a=self.opened();self.failed(aid,a)
        d=self.save(GOOD,aid)
        with self.assertRaisesRegex(ValueError,'immutable'):self.w.perform(aid,d['revision'],'deliberate_failure','run')
        self.assertEqual(1,self.w.state(aid)['reservations_used'])

    def test_crash_before_worker_preserves_intent_and_never_reexecutes(self):
        d=self.save(GOOD)
        with patch('gurukul.submissions.execute',side_effect=RuntimeError('synthetic worker crash')),self.assertRaises(RuntimeError):self.w.perform('practice',d['revision'],'repaired','run')
        self.w.close();self.w=Workspace(self.root,self.sid)
        with patch('gurukul.submissions.execute',side_effect=AssertionError('must not execute twice')):
            result=self.w.perform('practice',d['revision'],'repaired','run')
        self.assertEqual('pending_or_interrupted',result['attempt']['status'])
        self.assertTrue(result['requires_reconciliation'])

    def test_crash_between_execution_and_completion_preserves_both_reservations(self):
        aid,a=self.opened();self.failed(aid,a);_,good=program(a['variant']);d=self.save(good,aid)
        original=self.w.controller.command
        def crash(command,*args,**kwargs):
            if command=='complete':raise RuntimeError('synthetic between-stage crash')
            return original(command,*args,**kwargs)
        with patch.object(self.w.controller,'command',side_effect=crash),self.assertRaises(RuntimeError):self.w.perform(aid,d['revision'],'repaired','submit')
        self.w.close();self.w=Workspace(self.root,self.sid)
        with patch('gurukul.submissions.execute',side_effect=AssertionError('no duplicate')):r=self.w.perform(aid,d['revision'],'repaired','submit')
        self.assertEqual('EXECUTION_PRESERVED_COMPLETION_UNRESOLVED',r['status'])
        self.assertEqual(2,self.w.state(aid)['reservations_used']);self.assertEqual('OPEN',self.w.state(aid)['lifecycle']['status'])

    def test_crash_after_completion_reconciles_authoritative_confirmation(self):
        aid,a=self.opened();self.failed(aid,a);_,good=program(a['variant']);d=self.save(good,aid)
        original=ws.event
        def crash(store,kind,*args,**kwargs):
            if kind=='workspace.operation_finished':raise RuntimeError('response lost after commit')
            return original(store,kind,*args,**kwargs)
        with patch('gurukul.workspace_store.event',side_effect=crash),self.assertRaises(RuntimeError):self.w.perform(aid,d['revision'],'repaired','submit')
        result=self.w.perform(aid,d['revision'],'repaired','submit')
        self.assertEqual('COMPLETION_CONFIRMED',result['status']);self.assertTrue(result['reconciled'])

    def test_expired_completion_is_unresolved_without_extending_deadline(self):
        aid,a=self.opened();self.failed(aid,a);_,good=program(a['variant']);d=self.save(good,aid)
        original=self.w.controller.command
        def late(command,*args,**kwargs):
            if command=='complete':self.w.controller.clock=lambda:(datetime.fromisoformat(a['deadline'])+timedelta(seconds=1)).isoformat()
            return original(command,*args,**kwargs)
        with patch.object(self.w.controller,'command',side_effect=late):r=self.w.perform(aid,d['revision'],'repaired','submit')
        self.assertEqual('EXECUTION_PRESERVED_COMPLETION_UNRESOLVED',r['status'])
        self.assertEqual(a['deadline'],self.w.state(aid)['deadline'])
        self.assertEqual('INTERRUPTED',self.w.exit(aid,'interrupted')['outcome'])

    def test_unsupported_syntax_review_not_cheating_or_success(self):
        aid,a=self.opened();self.failed(aid,a);_,good=program(a['variant'])
        good=good.replace('print(', 'print(',1)+'print(f"{count}")\n'
        result=self.action(good,'repaired','submit',aid)
        self.assertEqual('REVIEW_NEEDED',result['status'])
        self.assertEqual('NEEDS_REVIEW',result['observation']['outcome'])
        self.assertEqual('OPEN',self.w.state(aid)['lifecycle']['status'])
        self.assertEqual('REVIEW_REQUIRED',self.w.exit(aid,'review')['outcome'])

    def test_declaration_exact_text_timing_restart_and_no_independence(self):
        self.action(FAILED,'deliberate_failure');r=self.action(GOOD,'repaired')
        text='I did not use any sources. I just used what I have already learned.'
        fact=self.w.declare('practice','repaired',text,'none_declared','during_work')
        self.assertEqual(text,fact['fact']['declaration_text'])
        self.assertEqual('declared_only',fact['provenance']['status'])
        self.assertIsNone(fact['fact']['statement_at'])
        self.w.close();self.w=Workspace(self.root,self.sid)
        self.assertEqual(fact,self.w.declare('practice','repaired',text,'none_declared','during_work'))
        self.assertEqual(text,self.w.state()['declarations'][0]['fact']['declaration_text'])

    def test_human_review_requires_separate_identity_and_never_changes_outcome(self):
        aid,a=self.opened();self.failed(aid,a);_,good=program(a['variant']);self.action(good,'repaired',context=aid)
        self.w.exit(aid,'interrupted');source={};result={}
        for run in self.w.state(aid)['lifecycle']['runs']:
            attempt=self.w.store.attempt(run['attempt_id']);source[attempt['id']]=attempt['source_sha256'];result[attempt['id']]=sha(attempt['execution'])
        criteria={k:'demonstrated' for k in ('five_variables','text_and_numbers','print_initial_values','reassign_and_reprint','quoted_text_repair','variant_conformity')}
        args=(aid,'architect',str(uuid4()),source,result,criteria,'Sources and saved results reviewed against each criterion.')
        with self.assertRaisesRegex(ValueError,'authorized'):self.w.review(*args)
        self.w.reviewer_id='architect';review=self.w.review(*args)
        self.assertEqual(review,self.w.review(*args))
        self.assertFalse(review['changes_eligibility']);self.assertEqual('INTERRUPTED',self.w.state(aid)['lifecycle']['closed']['outcome'])
        self.assertEqual([],events(self.w.store.db,'evidence.eligibility_recorded'))
        bad=dict(source);bad[next(iter(bad))]='0'*64
        with self.assertRaisesRegex(ValueError,'hashes differ'):self.w.review(aid,'architect',str(uuid4()),bad,result,criteria,'Mismatch')

    def test_practice_and_teaching_direct_calls_cannot_bypass_assessment(self):
        aid,a=self.opened()
        for call in (lambda:self.w.perform('practice',0,'repaired','run'),self.w.teach):
            with self.assertRaises(ValueError):call()
        self.w.exit(aid,'help')
        with self.assertRaisesRegex(ValueError,'unavailable'):self.w.teach()
        self.assertEqual('remediation',self.w.state()['lifecycle']['phase'])

    def test_submission_input_does_not_execute_unbound_private_practice_request(self):
        p=self.root/'bad.py';p.write_text(GOOD)
        with patch('gurukul.submissions.execute') as execute,self.assertRaises(ValueError):submit(self.w.store,p,_practice_request=str(uuid4()))
        execute.assert_not_called()

class HTTPTests(unittest.TestCase):
    seed=WorkspaceTests.seed
    def setUp(self):
        WorkspaceTests.setUp(self)
        self.server=Server(self.root,self.sid,'architect','R'*40)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.port=self.server.server_address[1]
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();WorkspaceTests.tearDown(self)
    def request(self,path='/api/state',method='GET',body=None,auth=True,origin=None,host=None):
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=10)
        headers={'Host':host or '127.0.0.1:'+str(self.port)}
        if auth:headers['Authorization']='Bearer '+(auth if isinstance(auth,str) else self.server.token)
        if method=='POST':headers.update({'Origin':origin or self.server.origin,'Content-Type':'application/json'})
        c.request(method,path,json.dumps(body or {}) if method=='POST' else None,headers)
        response=c.getresponse();data=response.read();status=response.status;c.close()
        return status,data
    def test_launch_auth_host_origin_and_no_arbitrary_paths(self):
        self.assertEqual(403,self.request(auth=False)[0])
        self.assertEqual(403,self.request(host='attacker.example')[0])
        self.assertEqual(403,self.request('/api/save','POST',{},origin='http://attacker.example')[0])
        self.assertEqual(200,self.request()[0])
        self.assertEqual(404,self.request('/../pyproject.toml')[0])
        self.assertEqual(404,self.request('/api/files?path=/etc/passwd')[0])
        status,raw=self.request('/api/save','POST',{'context':'practice','revision':0,'source':'# draft','path':'/etc/passwd'})
        self.assertEqual(409,status)
    def test_http_edit_run_submit_and_review_authorization(self):
        rev=0
        for role,source,action in [('deliberate_failure',FAILED,'run'),('repaired',GOOD,'submit')]:
            status,data=self.request('/api/save','POST',{'context':'practice','revision':rev,'source':source});self.assertEqual(200,status);rev=json.loads(data)['revision']
            body={'context':'practice','revision':rev,'role':role}
            status,data=self.request('/api/'+action,'POST',body);self.assertEqual(200,status)
        self.assertEqual('PRACTICE_CHECK_RECORDED',json.loads(data)['status'])
        self.assertEqual(403,self.request('/api/review','POST',{})[0])
        self.assertEqual(409,self.request('/api/review','POST',{},auth='R'*40)[0])
    def test_start_requires_explicit_ready_and_direct_teaching_denied(self):
        self.assertEqual(409,self.request('/api/start','POST',{})[0])
        status,raw=self.request('/api/start','POST',{'ready':True});self.assertEqual(200,status)
        aid=json.loads(raw)['context']
        status,raw=self.request('/api/teach','POST',{});self.assertEqual(409,status)
        self.assertIn('Tutoring denied',raw.decode())
        self.assertEqual(409,self.request('/api/run','POST',{'context':'practice','revision':0,'role':'repaired'})[0])
        self.assertEqual(200,self.request('/api/exit','POST',{'context':aid,'reason':'help'})[0])
        self.assertIn('unavailable',self.request('/api/teach','POST',{})[1].decode())
    def test_sample_guru_preserves_draft_and_cannot_dispatch_during_assessment(self):
        from gurukul.workspace import sample_guru
        self.server.responder=Mock(wraps=sample_guru)
        question={'question':'What changes after reassignment?'}
        draft={'context':'practice','revision':0,'source':'# untouched learner draft'}
        self.assertEqual(200,self.request('/api/save','POST',draft)[0])
        _,before=self.request()
        for invalid in ({}, {'question':' '}, {'question':'a'*1001}, {'question':5}):
            self.assertEqual(409,self.request('/api/teach','POST',invalid)[0])
        self.assertEqual(403,self.request('/api/teach','POST',question,auth=False)[0])
        self.assertEqual(403,self.request('/api/teach','POST',question,origin='http://wrong.example')[0])
        self.server.responder.assert_not_called()
        before_events=events(self.w.store.db)
        status,raw=self.request('/api/teach','POST',question)
        self.assertEqual(200,status)
        self.assertEqual({'kind':'sample','reply':sample_guru(question['question']),
                          'grants_assessment_credit':False,'grants_mastery':False,
                          'advances_curriculum':False},json.loads(raw))
        self.server.responder.assert_called_once_with(question['question'])
        _,after=self.request()
        for key in ('draft','operations','lifecycle'):
            self.assertEqual(json.loads(before)[key],json.loads(after)[key])
        self.assertEqual(before_events,events(self.w.store.db))
        self.assertEqual(200,self.request('/api/start','POST',{'ready':True})[0])
        _,active=self.request()
        self.assertEqual('unavailable',json.loads(active)['teaching'])
        before_events=events(self.w.store.db)
        status,raw=self.request('/api/teach','POST',question)
        self.assertEqual(409,status)
        self.assertIn('Tutoring denied',json.loads(raw)['error'])
        self.server.responder.assert_called_once()
        self.assertEqual(before_events,events(self.w.store.db))

    def test_assets_packaged_csp_and_no_token_or_provider_secrets(self):
        status,html=self.request('/',auth=False);self.assertEqual(200,status)
        self.assertIn(b'id="editor"',html);self.assertNotIn(self.server.token.encode(),html)
        self.assertEqual(200,self.request('/app.js',auth=False)[0])
        self.assertEqual(200,self.request('/style.css',auth=False)[0])


if __name__=='__main__':unittest.main()
