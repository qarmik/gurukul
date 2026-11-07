"""Local learner workspace. Teaching unavailable; no provider transport here."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
from urllib.parse import urlparse, parse_qs
from uuid import uuid5, NAMESPACE_URL
import webbrowser

from .store import Store,canonical,now
from .assessment import Controller,events,catalogue,candidate,sha,instant
from .learning_authority import learning_lock,canonical_teaching
from .submissions import submit,inspect,save_new,digest
from . import workspace_store as ws
from .checks import evaluate,snapshot,exercise_for_attempt


child_id=ws.child_id


@contextmanager
def operation_lock(directory):
    # Separate short workspace orchestration lock; canonical authority remains in Controller.
    with learning_lock(directory/'workspace'):
        yield


class Workspace:
    def __init__(self,root,session_id,reviewer_id=None):
        self.root=Path(root).resolve();self.path=self.root/'var/gurukul.sqlite3'
        if not self.path.is_file() or self.path.is_symlink():raise ValueError('Existing canonical learner ledger required.')
        self.store=Store(self.path);self.sid=session_id;self.reviewer_id=reviewer_id
        try:
            if self.store.resume()['session']['id']!=session_id:raise ValueError('Canonical active session differs.')
            ws.migrate(self.store)
            (self.store.state_dir/'workspace').mkdir(exist_ok=True,mode=0o700)
        except BaseException:self.store.close();raise
        self.controller=Controller(self.store,self.root)

    def close(self):self.store.close()

    def context(self,context):
        state=self.controller.state()
        if context=='practice':
            if state['assessment']:raise ValueError('Assessment open: practice routes unavailable.')
            if state['phase'] not in {'teaching','remediation'}:raise ValueError('Canonical state cannot authorize practice.')
            return state
        ws.request_uuid(context)
        return self.controller.state(context)

    def mutable(self,context):
        state=self.context(context)
        if context!='practice' and state['status']!='OPEN':raise ValueError('Assessment closed/interrupted; preserve evidence and exit or review.')
        return state

    def state(self,context=None):
        active=self.controller.state()
        context=context or (active['assessment']['assessment_id'] if active['assessment'] else 'practice')
        state=self.context(context);d=ws.draft(self.store,self.sid,context)
        a=state['assessment']
        task=(a['variant']['descriptor'] if a else {'prompt':'D01 practice: construct five text/numeric variables, print their values, reassign two and print them again. Preserve a deliberate unquoted-text failure and its repair.'})
        operations=[]
        for e in events(self.store.db,'workspace.operation_requested'):
            if e['session_id']==self.sid and e['payload']['context']==context:
                operations.append(self.reconcile(e))
        available=[e for e in events(self.store.db,'retrieval.scheduled') if e['session_id']==self.sid and not any(o['payload']['retrieval_id']==e['subject_id'] for o in events(self.store.db,'assessment.opened'))]
        attempt_ids={r['attempt_id'] for r in state.get('runs',[])} | {o['attempt']['id'] for o in operations if o.get('attempt')}
        return {'context':context,'draft':d,'task':task,'lifecycle':state,
                'declarations':[e['payload'] for e in events(self.store.db,'assistance.recorded') if e['payload']['bindings']['attempt_id'] in attempt_ids],
                'reviews':[e['payload'] for e in events(self.store.db,'evidence.review_recorded') if e['payload']['assessment_id']==context],
                'server_time':now(),'deadline':a['deadline'] if a else None,
                'reservations_used':len(state.get('runs',[])),'reservation_limit':a['max_runs'] if a else None,
                'operations':operations,'retrieval_available':bool(available),
                'teaching':'unavailable_in_first_slice','interpreter':sys.version,
                'execution_interpreter':sys.executable,'grants_mastery':False,'advances_curriculum':False}

    def save(self,context,revision,source):
        with operation_lock(self.store.state_dir):
            self.context(context)
            return ws.save(self.store,self.sid,context,revision,source)

    def start(self):
        with operation_lock(self.store.state_dir):
            active=self.controller.state()
            if active['assessment']:return {'context':active['assessment']['assessment_id'],'already_open':True}
            self.context('practice')
            available=[e for e in events(self.store.db,'retrieval.scheduled') if e['session_id']==self.sid and not any(o['payload']['retrieval_id']==e['subject_id'] for o in events(self.store.db,'assessment.opened'))]
            if len(available)!=1:raise ValueError('Exactly one existing unconsumed obligation required. No obligation is created here.')
            rid=available[0]['subject_id'];used={e['payload']['variant']['descriptor_sha256'] for e in events(self.store.db,'assessment.opened')}
            options=[]
            for entry in catalogue(self.root)['candidates']:
                if entry['approval']['status']=='approved' and entry['descriptor_sha256'] not in used:
                    options.append(candidate(self.root,entry['id'],available[0]['payload']['exercise_sha256']))
            if not options:raise ValueError('No approved unused variant; review required.')
            self.controller.command('due',child_id(rid,'due'),retrieval_id=rid)
            opened=self.controller.command('open',child_id(rid,'open'),retrieval_id=rid,variant_id=options[0]['id'])
            return {'context':opened['assessment_id'],'opening':opened}

    def run_attempt(self,context,role):
        state=self.context(context)
        if context=='practice':
            ops=[e for e in events(self.store.db,'workspace.operation_requested') if e['session_id']==self.sid and e['payload']['context']==context and e['payload']['role']==role]
            for e in reversed(ops):
                a=child_id(e['subject_id'],'practice-attempt')
                if self.store.db.execute('SELECT 1 FROM executions WHERE attempt_id=?',(a,)).fetchone():return inspect(self.store,a)
            return None
        for r in reversed(state['runs']):
            if r['role']==role and self.store.db.execute('SELECT 1 FROM executions WHERE attempt_id=?',(r['attempt_id'],)).fetchone():return inspect(self.store,r['attempt_id'])
        return None

    def reconcile(self,requested):
        identity=requested['subject_id'];finished=ws.result(self.store,identity)
        if finished:return finished
        p=requested['payload'];attempt=p.get('existing_attempt_id')
        if p['context']=='practice' and not attempt:attempt=child_id(identity,'practice-attempt')
        elif not attempt:
            reserved=self.store.db.execute('SELECT payload_json FROM events WHERE idempotency_key=?',('assessment.run:'+child_id(identity,'run'),)).fetchone()
            if reserved:attempt=json.loads(reserved[0])['attempt_id']
        if attempt and self.store.db.execute('SELECT 1 FROM attempts WHERE id=?',(attempt,)).fetchone():
            saved=inspect(self.store,attempt)
            if p['action']=='submit' and p['context']!='practice':
                completion=self.store.db.execute('SELECT payload_json FROM events WHERE idempotency_key=?',('learning.command:'+child_id(identity,'complete'),)).fetchone()
                if completion:
                    observation=json.loads(completion[0])['result']
                    return {'operation_id':identity,'status':'COMPLETION_CONFIRMED' if observation.get('outcome') in {'COMPLETED_FOR_REVIEW','FAILED'} else 'COMPLETION_UNRESOLVED','attempt':saved,'observation':observation,'reconciled':True}
            return {'operation_id':identity,'status':'EXECUTION_PRESERVED_COMPLETION_UNRESOLVED' if p['action']=='submit' else 'EXECUTION_PRESERVED','attempt':saved,'requires_reconciliation':True}
        return {'operation_id':identity,'status':'INTERRUPTED_BEFORE_RESULT','requires_reconciliation':True}

    def perform(self,context,revision,role,action):
        if role not in {'deliberate_failure','repaired'} or action not in {'run','submit'}:raise ValueError('Unsupported operation.')
        if action=='submit' and role!='repaired':raise ValueError('Submit requires the repaired evidence stage.')
        identity=child_id(self.sid,canonical([context,revision,role,action]))
        with operation_lock(self.store.state_dir):
            previous=ws.operation(self.store,identity)
            if previous:return self.reconcile(previous)
            self.mutable(context)
            d=ws.draft(self.store,self.sid,context)
            if type(revision) is not int or d['revision']!=revision:raise ValueError('Stale revision; no execution.')
            if not d['source'].strip():raise ValueError('Write your source before Run or Submit.')
            existing=self.run_attempt(context,role)
            if existing and existing['source_sha256']!=d['source_sha256']:
                if context=='practice':existing=None
                else:raise ValueError('Completed role is immutable. Current draft differs; no replacement or execution was made.')
            failed=self.run_attempt(context,'deliberate_failure') if action=='submit' else None
            if action=='submit' and not failed:raise ValueError('Capture the deliberate-failure evidence first.')
            p={'context':context,'revision':revision,'source_sha256':d['source_sha256'],'source':d['source'],
               'action':action,'role':role,'existing_attempt_id':existing['id'] if existing else None,
               'failed_attempt_id':failed['id'] if failed else None}
            with self.store.db:
                ws.event(self.store,'workspace.operation_requested',identity,self.sid,p,'workspace.request:'+identity)
            # Immutable operation input is durable before any worker execution.
            folder=self.store.state_dir/'workspace'/identity;folder.mkdir(mode=0o700)
            source=folder/'source.py';save_new(source,p['source'].encode())
            try:
                if existing:attempt=existing
                elif context=='practice':
                    with learning_lock(self.store.state_dir):
                        self.mutable(context)
                        attempt=submit(self.store,source,_practice_request=identity)
                else:attempt=self.controller.submit(context,child_id(identity,'run'),role,source)
                if action=='run':result={'status':'EXECUTION_RECORDED','attempt':attempt}
                else:
                    try:
                        if context=='practice':
                            with learning_lock(self.store.state_dir):
                                self.mutable(context)
                                observation=evaluate(self.store,attempt['id'],self.root,failed['id'])
                            result={'status':'PRACTICE_REVIEW_NEEDED' if observation['outcome']=='NEEDS_REVIEW' else 'PRACTICE_CHECK_RECORDED','observation':observation,'attempt':attempt}
                        else:
                            observation=self.controller.command('complete',child_id(identity,'complete'),assessment_id=context,attempt_id=attempt['id'],failed_attempt_id=failed['id'])
                            result={'status':'COMPLETION_CONFIRMED' if observation.get('outcome') in {'COMPLETED_FOR_REVIEW','FAILED'} else 'REVIEW_NEEDED' if observation.get('outcome')=='NEEDS_REVIEW' else 'COMPLETION_UNRESOLVED','observation':observation,'attempt':attempt}
                    except (ValueError,OSError) as exc:
                        result={'status':'EXECUTION_PRESERVED_COMPLETION_UNRESOLVED','attempt':attempt,'reason':str(exc)}
                result.update(operation_id=identity,grants_mastery=False,grants_verified_independence=False,advances_curriculum=False)
            except (ValueError,OSError) as exc:
                result={'operation_id':identity,'status':'OPERATION_UNRESOLVED','reason':str(exc),'grants_mastery':False,'advances_curriculum':False}
            with self.store.db:
                ws.event(self.store,'workspace.operation_finished',identity,self.sid,result,'workspace.result:'+identity,
                         ws.operation(self.store,identity)['event_id'])
            return result

    def exit(self,context,reason):
        if context=='practice':raise ValueError('No assessment to exit.')
        if reason not in {'help','interrupted','review','abandon'}:raise ValueError('Invalid exit reason.')
        return self.controller.command('exit',child_id(context,'exit:'+reason),assessment_id=context,reason=reason)

    def declare(self,context,role,text,kind,timing,statement_at=None):
        with operation_lock(self.store.state_dir):
            self.context(context)
            if role not in {'deliberate_failure','repaired'}:raise ValueError('Invalid evidence scope.')
            attempt=self.run_attempt(context,role);failed=self.run_attempt(context,'deliberate_failure') if role=='repaired' else None
            if not attempt:raise ValueError('Run evidence must exist before recording its declaration.')
            data={'kind':kind,'steps':['construction','repair'],'timing':timing,'origin':'learner_declaration',
                  'declaration_text':text,'declaration_source':'workspace','statement_at':statement_at}
            data['request_id']=child_id(attempt['id'],canonical(data))
            return self.store.record_assistance(attempt['id'],data,failed['id'] if failed else None)

    def review(self,context,reviewer,request_id,source_hashes,result_hashes,criteria,rationale):
        ws.request_uuid(request_id)
        if not self.reviewer_id or reviewer!=self.reviewer_id or reviewer.casefold() in {'guru','maharishi'}:raise ValueError('Explicit authorized human reviewer required.')
        state=self.context(context)
        if context=='practice' or state['status']!='CLOSED':raise ValueError('Review requires a closed assessment; it cannot close one.')
        required={'five_variables','text_and_numbers','print_initial_values','reassign_and_reprint','quoted_text_repair','variant_conformity'}
        if not isinstance(criteria,dict) or set(criteria)!=required:raise ValueError('Criterion-level review required.')
        if any(v not in {'demonstrated','not_demonstrated','unresolved'} for v in criteria.values()):raise ValueError('Invalid review finding.')
        if not isinstance(rationale,str) or not 1<=len(rationale)<=8192:raise ValueError('Evidence rationale required.')
        bound={};results={}
        for role in ('deliberate_failure','repaired'):
            attempt=self.run_attempt(context,role)
            if not attempt:raise ValueError('Both assessment-owned roles required.')
            a,_=snapshot(self.store,attempt['id']);exercise_for_attempt(self.store,a)
            raw=json.loads(self.store.db.execute('SELECT result_json FROM executions WHERE attempt_id=?',(a['id'],)).fetchone()[0])
            bound[a['id']]=a['source_sha256'];results[a['id']]=sha(raw)
        if bound!=source_hashes or results!=result_hashes:raise ValueError('Reviewed evidence hashes differ.')
        p={'assessment_id':context,'reviewer_id':reviewer,'source_hashes':bound,'result_hashes':results,
           'criteria':criteria,'rationale':rationale,'historical_outcome':state['closed']['outcome'],
           'grants_mastery':False,'grants_verified_independence':False,'advances_curriculum':False,
           'changes_eligibility':False,'recorded_at':now()}
        with self.store.db:
            self.store.db.execute('BEGIN IMMEDIATE')
            old=self.store.db.execute('SELECT payload_json FROM events WHERE idempotency_key=?',('workspace.review:'+request_id,)).fetchone()
            if old:
                previous=json.loads(old[0]);compare=dict(previous);compare['recorded_at']=p['recorded_at']
                if compare!=p:raise ValueError('Conflicting review identity.')
                return previous
            ws.event(self.store,'evidence.review_recorded',request_id,self.sid,p,'workspace.review:'+request_id)
        return p

    def teach(self):
        with canonical_teaching(self.path,self.sid):
            raise ValueError('Teaching unavailable in this first workspace slice; no provider was called.')


class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,root,session_id,reviewer_id=None,reviewer_token=None):
        self.root=Path(root).resolve();self.session_id=session_id
        self.token=secrets.token_urlsafe(32);self.reviewer_id=reviewer_id;self.reviewer_token=reviewer_token
        super().__init__(('127.0.0.1',0),Handler)
        self.origin='http://127.0.0.1:'+str(self.server_address[1])


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def reply(self,status,payload,content_type='application/json',extra=None):
        data=json.dumps(payload,ensure_ascii=False).encode() if content_type=='application/json' else payload
        self.send_response(status)
        for k,v in {'Content-Type':content_type,'Content-Length':str(len(data)),'Cache-Control':'no-store',
                    'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
                    'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",**(extra or {})}.items():self.send_header(k,v)
        self.end_headers();self.wfile.write(data)

    def transport(self,mutation=False,review=False):
        if self.headers.get('Host')!=urlparse(self.server.origin).netloc:raise PermissionError('Invalid host.')
        origin=self.headers.get('Origin')
        if (mutation and origin!=self.server.origin) or (origin and origin!=self.server.origin):raise PermissionError('Invalid origin.')
        if not urlparse(self.path).path.startswith('/api/'):return
        auth=self.headers.get('Authorization','')
        if review:
            if not self.server.reviewer_token or not secrets.compare_digest(auth,'Bearer '+self.server.reviewer_token):raise PermissionError('Reviewer authorization required.')
            return
        jar=cookies.SimpleCookie();jar.load(self.headers.get('Cookie',''))
        token=jar['gurukul_launch'].value if 'gurukul_launch' in jar else ''
        if not secrets.compare_digest(token,self.server.token) and not secrets.compare_digest(auth,'Bearer '+self.server.token):raise PermissionError('Launch authorization required.')

    def do_GET(self):
        service=None
        try:
            self.transport();url=urlparse(self.path)
            if url.path in {'/','/app.js','/style.css'}:
                name={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}[url.path]
                content={'/':'text/html; charset=utf-8','/app.js':'text/javascript; charset=utf-8','/style.css':'text/css; charset=utf-8'}[url.path]
                self.reply(200,(Path(__file__).parent/'workspace_assets'/name).read_bytes(),content);return
            if url.path!='/api/state':self.reply(404,{'error':'Unknown route.'});return
            query=parse_qs(url.query)
            if set(query)-{'context'}:raise ValueError('Unsupported query.')
            service=Workspace(self.server.root,self.server.session_id)
            self.reply(200,service.state(query.get('context',[None])[0]))
        except PermissionError as exc:self.reply(403,{'error':str(exc)})
        except (ValueError,OSError,sqlite3.Error,cookies.CookieError) as exc:self.reply(409,{'error':str(exc)})
        finally:
            if service:service.close()

    def do_POST(self):
        service=None
        try:
            path=urlparse(self.path).path
            if self.path!=path:raise ValueError('No query parameters for writes.')
            self.transport(True,path=='/api/review')
            if self.headers.get('Content-Type')!='application/json' or self.headers.get('Transfer-Encoding'):raise ValueError('JSON body with explicit length required.')
            length=int(self.headers.get('Content-Length','-1'))
            if not 0<=length<=2097152:raise ValueError('Request body too large.')
            self.connection.settimeout(5)
            body=json.loads(self.rfile.read(length))
            if not isinstance(body,dict):raise ValueError('JSON object required.')
            if path=='/api/bootstrap':
                if body:raise ValueError('Empty bootstrap body required.')
                self.reply(200,{'authorized':True},extra={'Set-Cookie':'gurukul_launch='+self.server.token+'; HttpOnly; SameSite=Strict; Path=/api/'});return
            service=Workspace(self.server.root,self.server.session_id,self.server.reviewer_id)
            if path=='/api/save':result=service.save(**body)
            elif path=='/api/start':
                if body!={'ready':True}:raise ValueError('Explicit ready-to-start confirmation required.')
                result=service.start()
            elif path=='/api/run':result=service.perform(action='run',**body)
            elif path=='/api/submit':result=service.perform(action='submit',**body)
            elif path=='/api/declare':result=service.declare(**body)
            elif path=='/api/exit':result=service.exit(**body)
            elif path=='/api/review':result=service.review(reviewer=self.server.reviewer_id,**body)
            elif path=='/api/teach':
                if body:raise ValueError('Teaching request unavailable.')
                result=service.teach()
            else:self.reply(404,{'error':'Unknown route.'});return
            self.reply(200,result)
        except PermissionError as exc:self.reply(403,{'error':str(exc)})
        except (ValueError,OSError,TypeError,KeyError,sqlite3.Error,cookies.CookieError) as exc:self.reply(409,{'error':str(exc)})
        finally:
            if service:service.close()


def main():
    if sys.version_info<(3,11):raise SystemExit('Workspace requires Python 3.11 or newer. Existing execution records are not changed.')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--reviewer-id')
    parser.add_argument('--reviewer-token-file',type=Path)
    args=parser.parse_args();os.umask(0o077)
    s=Store(args.root/'var/gurukul.sqlite3') if (args.root/'var/gurukul.sqlite3').is_file() else None
    if not s:raise SystemExit('Canonical session setup is required before launch; no learner session was created.')
    try:sid=s.resume()['session']['id']
    finally:s.close()
    reviewer_token=None
    if bool(args.reviewer_id)!=bool(args.reviewer_token_file):parser.error('Reviewer identity and private token file must be supplied together.')
    if args.reviewer_token_file:
        p=args.reviewer_token_file
        if p.is_symlink() or not p.is_file() or p.stat().st_mode&0o077:parser.error('Reviewer token must be a private regular file.')
        reviewer_token=p.read_text().strip()
        if len(reviewer_token)<32:parser.error('Reviewer token must contain at least 32 characters.')
    server=Server(args.root,sid,args.reviewer_id,reviewer_token)
    print('Workspace interpreter:',sys.executable,sys.version.split()[0],flush=True)
    print('Learner execution uses this interpreter; every result records its Python version. Historical records remain unchanged.',flush=True)
    if args.no_browser:print('Open locally:',server.origin+'/#'+server.token,flush=True)
    else:webbrowser.open(server.origin+'/#'+server.token)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
