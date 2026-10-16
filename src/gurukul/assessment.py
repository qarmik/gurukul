"""One bounded, event-backed D01 retrieval/assessment lifecycle; no mastery."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid4

from .store import canonical, now
from .learning_authority import learning_lock

POLICY = 'd01-assessment-1'
DELAY_SECONDS = 86400
DURATION_SECONDS = 1200
MAX_RUNS = 4
ROLES = {'deliberate_failure', 'repaired'}
EVENTS = {'retrieval.scheduled','retrieval.became_due','assessment.opened',
          'assessment.run_reserved','assessment.observation_recorded',
          'assessment.interrupted','assessment.resumed','assessment.closed',
          'remediation.completed','learning.command_recorded'}


def sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def instant(value):
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None: raise ValueError()
        return result.astimezone(timezone.utc)
    except (TypeError, ValueError):
        raise ValueError('Expected a timezone-aware timestamp.') from None


def uuid(value):
    try:
        if str(UUID(value)) != value: raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Expected a canonical request UUID.') from None
    return value


def events(db, kind=None, subject=None):
    clauses, args = [], []
    if kind: clauses.append('event_type=?'); args.append(kind)
    if subject: clauses.append('subject_id=?'); args.append(subject)
    query = 'SELECT * FROM events' + (' WHERE '+' AND '.join(clauses) if clauses else '') + ' ORDER BY sequence'
    return [dict(r, payload=json.loads(r['payload_json'])) for r in db.execute(query,args)]


def active_assessment(db, session_id):
    opened = [e for e in events(db,'assessment.opened') if e['session_id']==session_id]
    closed = {e['subject_id'] for e in events(db,'assessment.closed')}
    active = [e for e in opened if e['subject_id'] not in closed]
    if len(active)>1: raise ValueError('Ambiguous active assessment authority.')
    return active[0]['payload'] if active else None


def catalogue(root):
    value = json.loads((Path(root)/'content/assessments/d01-candidates.json').read_text())
    if set(value) != {'catalogue_version','candidates'} or value['catalogue_version'] != 1:
        raise ValueError('Unsupported candidate catalogue.')
    ids = [c['id'] for c in value['candidates']]
    if len(ids)!=len(set(ids)): raise ValueError('Duplicate candidate identities.')
    for c in value['candidates']:
        if sha(c['descriptor']) != c['descriptor_sha256'] or sha(c['rules']) != c['rules_sha256']:
            raise ValueError('Candidate descriptor/rule hash mismatch.')
    return value


def candidate(root, variant_id, exercise_sha):
    matches=[c for c in catalogue(root)['candidates'] if c['id']==variant_id]
    if len(matches)!=1: raise ValueError('Unknown candidate.')
    c=matches[0];a=c['approval']
    import keyword
    d=c['descriptor'];initial=d.get('initial_values');changed=d.get('reassignments')
    if (set(d)!={'base_exercise_sha256','prompt','initial_values','reassignments'} or
            not isinstance(d['prompt'],str) or not 1<=len(d['prompt'])<=2500 or
            not isinstance(initial,dict) or len(initial)!=5 or not isinstance(changed,dict) or len(changed)!=2 or
            not set(changed)<=set(initial) or any(not k.isidentifier() or keyword.iskeyword(k) or k=='print' for k in initial) or
            any(type(v) not in (str,int,float) for v in list(initial.values())+list(changed.values())) or
            not any(type(v) is str for v in initial.values()) or not any(type(v) in (int,float) for v in initial.values()) or
            any(type(v) is type(initial[k]) and v==initial[k] for k,v in changed.items())):
        raise ValueError('Candidate must instantiate only the existing D01 task data.')
    if (a.get('status')!='approved' or not a.get('reference') or
            a.get('descriptor_sha256')!=c['descriptor_sha256'] or a.get('rules_sha256')!=c['rules_sha256']):
        raise ValueError('Candidate is not approved for production assessment.')
    if c['descriptor']['base_exercise_sha256']!=exercise_sha or c['rules']!={'kind':'d01-task-data-1','preserve_base_checker':True}:
        raise ValueError('Candidate differs from pinned D01 scope/rules.')
    return c


def conformity(source, descriptor):
    from .checks import analyse, literal
    import ast
    tree=analyse(source)['tree']
    values, initial, changed, first_printed, changed_printed = {},{},set(),set(),set()
    for stmt in tree.body:
        if isinstance(stmt,ast.Assign):
            value=literal(stmt.value,values)
            for target in stmt.targets:
                if target.id not in initial: initial[target.id]=value
                else: changed.add(target.id)
                values[target.id]=value
        else:
            for arg in stmt.value.args:
                if isinstance(arg,ast.Name):
                    if arg.id not in changed: first_printed.add(arg.id)
                    if arg.id in descriptor['reassignments'] and arg.id in changed and type(values[arg.id]) is type(descriptor['reassignments'][arg.id]) and values[arg.id]==descriptor['reassignments'][arg.id]:
                        changed_printed.add(arg.id)
    wanted=descriptor['initial_values']
    return (all(k in first_printed and type(initial.get(k)) is type(v) and initial.get(k)==v for k,v in wanted.items()) and
            set(descriptor['reassignments'])<=changed_printed)


class SubmissionPermit:
    def __init__(self, reservation): self.reservation,self.active=reservation,True


def submission_permission(store, session, source_sha, permit):
    current=active_assessment(store.db,session['id'])
    if not current and session['phase'] not in ('assessment','reconstruction'):
        if permit is not None: raise ValueError('Unexpected assessment permit.')
        return None
    if not isinstance(permit,SubmissionPermit) or not permit.active or not current or session['phase']!='assessment':
        raise ValueError('Use explicit assessment submission; ordinary run cannot bypass assessment.')
    r=permit.reservation
    stored=store.db.execute('SELECT payload_json FROM events WHERE event_type=? AND subject_id=? AND idempotency_key=?',
        ('assessment.run_reserved',current['assessment_id'],'assessment.run:'+r['request_id'])).fetchone()
    if not stored or json.loads(stored[0])!=r or r['source_sha256']!=source_sha:
        raise ValueError('Assessment reservation differs from submission.')
    return r


class Controller:
    def __init__(self, store, root, clock=None):
        self.store,self.root=store,Path(root)
        self.clock=clock or now  # Injection is for synthetic tests; no CLI clock override.
        if store.path != (self.root/'var/gurukul.sqlite3').resolve():
            raise ValueError('Lifecycle requires the canonical learner ledger.')

    def emit(self, kind, subject, payload, key, session, cause=None):
        if kind not in EVENTS: raise ValueError('Unsupported lifecycle event.')
        old=self.store.db.execute('SELECT * FROM events WHERE idempotency_key=?',(key,)).fetchone()
        if old:
            if old['event_type']!=kind or old['subject_id']!=subject or json.loads(old['payload_json'])!=payload:
                raise ValueError('Conflicting lifecycle identity.')
            return old['event_id']
        stamp=self.timestamp
        event_id=str(uuid4())
        self.store.db.execute('''INSERT INTO events(event_id,event_type,schema_version,occurred_at,recorded_at,source,subject_id,session_id,correlation_id,causation_id,idempotency_key,privacy_class,payload_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (event_id,kind,1,stamp,now(),'gurukul.assessment',subject,session,subject,cause,key,'personal_learning',canonical(payload)))
        return event_id

    def session(self):
        s=self.store.resume()
        self.session_id=s['session']['id']
        return s

    def clock_check(self):
        self.timestamp=instant(self.clock()).isoformat()
        rows=events(self.store.db,'learning.command_recorded')+events(self.store.db,'assessment.run_reserved')
        observed=[instant(e['payload']['observed_at']) for e in rows if 'observed_at' in e['payload']]
        if observed and instant(self.timestamp)<max(observed): raise ValueError('Clock moved backwards; lifecycle held for review.')

    def state(self, assessment_id=None):
        s=self.session();active=active_assessment(self.store.db,self.session_id)
        if (s['session']['phase']=='assessment')!=bool(active): raise ValueError('Session phase and assessment authority disagree.')
        if assessment_id:
            matches=events(self.store.db,'assessment.opened',assessment_id)
            if len(matches)!=1 or matches[0]['session_id']!=self.session_id: raise ValueError('Unknown assessment in current session.')
            active=matches[0]['payload']
        if not active: return {'assessment':None,'phase':s['session']['phase']}
        aid=active['assessment_id'];closed=events(self.store.db,'assessment.closed',aid)
        runs=events(self.store.db,'assessment.run_reserved',aid)
        resumed=events(self.store.db,'assessment.resumed',aid)
        interrupted=events(self.store.db,'assessment.interrupted',aid)
        ack=set(resumed[-1]['payload']['acknowledged_pending']) if resumed else set()
        pending=[r['payload']['attempt_id'] for r in runs if not self.store.db.execute('SELECT 1 FROM executions WHERE attempt_id=?',(r['payload']['attempt_id'],)).fetchone()]
        expired=instant(self.clock())>=instant(active['deadline'])
        is_interrupted=expired or bool(set(pending)-ack) or bool(interrupted and (not resumed or interrupted[-1]['sequence']>resumed[-1]['sequence']))
        return {'assessment':active,'status':'CLOSED' if closed else 'INTERRUPTED' if is_interrupted else 'OPEN',
                'runs':[r['payload'] for r in runs],'pending':pending,'closed':closed[-1]['payload'] if closed else None,
                'phase':s['session']['phase'],'deadline_expired':expired}

    def require_open(self, aid, allow_interrupted=False):
        state=self.state(aid)
        if state['status']=='CLOSED' or (state['status']=='INTERRUPTED' and not allow_interrupted):
            raise ValueError('Assessment is closed/interrupted; explicit recovery or exit required.')
        return state

    def command(self, command, request_id, **args):
        uuid(request_id)
        if command not in {'schedule','due','open','resume','exit','complete','remediated'}: raise ValueError('Unknown lifecycle command.')
        with learning_lock(self.store.state_dir):
            self.clock_check();self.session()
            identity={'command':command,'arguments':args}
            previous=self.store.db.execute('SELECT payload_json FROM events WHERE idempotency_key=?',('learning.command:'+request_id,)).fetchone()
            if previous:
                p=json.loads(previous[0])
                if p['identity']!=identity: raise ValueError('Conflicting lifecycle request UUID.')
                return p['result']
            evaluation=None
            if command=='complete':
                state=self.require_open(args['assessment_id'])
                self.bounds(state)
                roles={r['attempt_id']:r['role'] for r in state['runs']}
                supplied=bool(args.get('failed_attempt_id') and args.get('attempt_id'))
                if supplied and (roles.get(args['failed_attempt_id'])!='deliberate_failure' or roles.get(args['attempt_id'])!='repaired'):
                    raise ValueError('Completion requires this assessment\'s own failed/repaired roles.')
                for attempt in ((args['failed_attempt_id'],args['attempt_id']) if supplied else ()):
                    reservation=next(r for r in state['runs'] if r['attempt_id']==attempt)
                    bound=events(self.store.db,'assessment.submission_bound',attempt)
                    if len(bound)!=1 or bound[0]['payload']!=reservation or self.store.attempt(attempt)['source_sha256']!=reservation['source_sha256']:
                        raise ValueError('Assessment submission binding/integrity mismatch.')
                if supplied:
                    from .checks import evaluate,snapshot
                    statuses={a:snapshot(self.store,a)[0]['status'] for a in (args['failed_attempt_id'],args['attempt_id'])}
                    evaluation=(evaluate(self.store,args['attempt_id'],self.root,args['failed_attempt_id'])
                        if all(v in {'completed','program_error'} for v in statuses.values()) else
                        {'outcome':'EXECUTION_BLOCKED','execution_statuses':statuses})
            with self.store.db:
                self.store.db.execute('BEGIN IMMEDIATE')
                result=getattr(self,'_'+command)(**args, evaluation=evaluation) if command=='complete' else getattr(self,'_'+command)(**args)
                result=dict(result,grants_mastery=False,grants_verified_independence=False,advances_curriculum=False)
                self.emit('learning.command_recorded',request_id,{'identity':identity,'result':result,'observed_at':self.timestamp},'learning.command:'+request_id,self.session_id)
                return result

    def _schedule(self, anchor_event_id):
        if active_assessment(self.store.db,self.session_id): raise ValueError('Exit the assessment before scheduling.')
        anchor=self.store.db.execute('SELECT * FROM events WHERE event_id=?',(anchor_event_id,)).fetchone()
        if not anchor or anchor['session_id']!=self.session_id or anchor['event_type'] not in {'assessment.checked','remediation.completed'}:
            raise ValueError('Schedule needs a local practice evaluation or remediation-completion anchor.')
        p=json.loads(anchor['payload_json'])
        if anchor['event_type']=='assessment.checked' and p.get('outcome')!='CHECKS_PASS': raise ValueError('Practice checks must pass; assistance need not be absent.')
        from .evidence import verified_evaluation
        verified_evaluation(self.store,p['evaluation_id'],self.root)
        outstanding=[e for e in events(self.store.db,'retrieval.scheduled') if e['session_id']==self.session_id and not any(x['payload']['retrieval_id']==e['subject_id'] for x in events(self.store.db,'assessment.opened'))]
        if outstanding: raise ValueError('One unconsumed retrieval obligation already exists.')
        anchor_time=instant(anchor['occurred_at'])
        if anchor_time>instant(self.timestamp):raise ValueError('Anchor is in the future; clock review required.')
        rid=str(uuid4());ex=self.session()['exercise'];exercise_sha=sha(ex)
        data={'retrieval_id':rid,'session_id':self.session_id,'exercise_sha256':exercise_sha,
              'anchor_event_id':anchor_event_id,'scheduled_at':self.timestamp,
              'anchor_at':anchor_time.isoformat(),
              'due_at':(anchor_time+timedelta(seconds=DELAY_SECONDS)).isoformat(),
              'policy':POLICY,'delay_seconds':DELAY_SECONDS,'clock_evidence':'parent_wall_clock_not_remote_attestation'}
        self.emit('retrieval.scheduled',rid,data,'retrieval.scheduled:'+rid,self.session_id,anchor_event_id)
        return data

    def retrieval(self,rid):
        rows=events(self.store.db,'retrieval.scheduled',rid)
        if len(rows)!=1 or rows[0]['session_id']!=self.session_id: raise ValueError('Unknown retrieval obligation.')
        if rows[0]['payload']['exercise_sha256']!=sha(self.session()['exercise']): raise ValueError('Retrieval exercise binding changed.')
        return rows[0]

    def _due(self,retrieval_id):
        r=self.retrieval(retrieval_id)
        if instant(self.timestamp)<instant(r['payload']['due_at']): raise ValueError('Retrieval is not due.')
        old=events(self.store.db,'retrieval.became_due',retrieval_id)
        if old:return old[0]['payload']
        p={'retrieval_id':retrieval_id,'due_at':r['payload']['due_at'],'observed_at':self.timestamp}
        self.emit('retrieval.became_due',retrieval_id,p,'retrieval.due:'+retrieval_id,self.session_id,r['event_id']);return p

    def _open(self,retrieval_id,variant_id):
        if self.state()['assessment']: raise ValueError('Another assessment is active.')
        r=self.retrieval(retrieval_id)
        if not events(self.store.db,'retrieval.became_due',retrieval_id): raise ValueError('Explicit due observation required.')
        if instant(self.timestamp)<instant(r['payload']['due_at']): raise ValueError('Not due.')
        if any(e['payload']['retrieval_id']==retrieval_id for e in events(self.store.db,'assessment.opened')): raise ValueError('Retrieval obligation already consumed.')
        c=candidate(self.root,variant_id,r['payload']['exercise_sha256'])
        if any(e['payload']['variant']['descriptor_sha256']==c['descriptor_sha256'] for e in events(self.store.db,'assessment.opened')):
            raise ValueError('Previously opened variant cannot be called fresh.')
        owned={e['payload']['attempt_id'] for e in events(self.store.db,'assessment.run_reserved')}
        for fact in events(self.store.db,'assistance.recorded'):
            p=fact['payload']
            if p['bindings']['exercise_sha256']==r['payload']['exercise_sha256'] and p['fact']['kind']=='solution_exposure' and p['bindings']['attempt_id'] not in owned:
                raise ValueError('Unscoped historical exposure requires review; new identifiers cannot establish freshness.')
        s=self.session()['session']
        if s['phase'] not in {'teaching','remediation'}: raise ValueError('Invalid opening phase.')
        aid=str(uuid4());p={'assessment_id':aid,'retrieval_id':retrieval_id,'session_id':self.session_id,
            'exercise_sha256':r['payload']['exercise_sha256'],'variant':c,'opened_at':self.timestamp,
            'deadline':(instant(self.timestamp)+timedelta(seconds=DURATION_SECONDS)).isoformat(),
            'max_runs':MAX_RUNS,'policy':POLICY,'previous_phase':s['phase']}
        from .pedagogy import orientation
        p['curriculum_binding']=orientation(self.root,self.session()['exercise'])[1]
        p['checker_binding']=self.checker_binding()
        p['policy_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        self.emit('assessment.opened',aid,p,'assessment.opened:'+aid,self.session_id,r['event_id'])
        self.store.db.execute("UPDATE sessions SET phase='assessment' WHERE id=?",(self.session_id,))
        return p

    def bounds(self,state):
        if instant(self.timestamp)>=instant(state['assessment']['deadline']): raise ValueError('Assessment deadline reached; explicit interruption exit required.')
        from .pedagogy import orientation
        if (state['assessment']['checker_binding']!=self.checker_binding() or
                state['assessment']['curriculum_binding']!=orientation(self.root,self.session()['exercise'])[1] or
                state['assessment']['policy_sha256']!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()):
            raise ValueError('Assessment checker/curriculum/policy changed; explicit review exit required.')

    def checker_binding(self):
        from . import checks
        return {'checker_sha256':hashlib.sha256(Path(checks.__file__).read_bytes()).hexdigest(),
                'spec_sha256':hashlib.sha256((self.root/'content/checks/d01-v1.json').read_bytes()).hexdigest()}

    def _resume(self,assessment_id):
        s=self.require_open(assessment_id,True);self.bounds(s)
        p={'assessment_id':assessment_id,'acknowledged_pending':s['pending'],'observed_at':self.timestamp}
        self.emit('assessment.resumed',assessment_id,p,'assessment.resume:'+str(uuid4()),self.session_id)
        return p

    def close_assessment(self,aid,outcome,phase,extra=None):
        self.require_open(aid,True)
        p=dict(assessment_id=aid,outcome=outcome,closed_at=self.timestamp,**(extra or {}))
        self.emit('assessment.closed',aid,p,'assessment.closed:'+aid,self.session_id)
        self.store.db.execute('UPDATE sessions SET phase=? WHERE id=?',(phase,self.session_id))
        return p

    def _exit(self,assessment_id,reason):
        if reason not in {'help','abandon','interrupted','review'}: raise ValueError('Unsupported explicit assessment exit.')
        return self.close_assessment(assessment_id,{'help':'HELP_REQUESTED','abandon':'ABANDONED','interrupted':'INTERRUPTED','review':'REVIEW_REQUIRED'}[reason], 'remediation' if reason=='help' else 'teaching')

    def _complete(self,assessment_id,attempt_id,failed_attempt_id,evaluation):
        state=self.require_open(assessment_id);self.bounds(state)
        if evaluation is None or evaluation['outcome']=='EXECUTION_BLOCKED':
            p={'assessment_id':assessment_id,**(evaluation or {'outcome':'NEEDS_EVIDENCE','reason':'Supply this assessment\'s failed/repaired attempt IDs.'})}
            self.emit('assessment.observation_recorded',assessment_id,p,'assessment.observation:'+sha(p),self.session_id)
            return p
        from .evidence import verified_evaluation
        verified_evaluation(self.store,evaluation['evaluation_id'],self.root)
        if evaluation['outcome'] in {'BLOCKED','NEEDS_EVIDENCE','NEEDS_REVIEW'}:
            p={'assessment_id':assessment_id,'outcome':evaluation['outcome'],'evaluation_id':evaluation['evaluation_id']}
            self.emit('assessment.observation_recorded',assessment_id,p,'assessment.observation:'+sha(p),self.session_id)
            return p
        if evaluation['outcome']=='FAIL':return self.close_assessment(assessment_id,'FAILED','remediation',{'evaluation_id':evaluation['evaluation_id']})
        from .checks import snapshot
        current=candidate(self.root,state['assessment']['variant']['id'],state['assessment']['exercise_sha256'])
        if current!=state['assessment']['variant']: raise ValueError('Admitted variant changed after opening.')
        good=conformity(snapshot(self.store,attempt_id)[1],current['descriptor'])
        if not good:return self.close_assessment(assessment_id,'FAILED','remediation',{'reason':'Wrong variant task data','evaluation_id':evaluation['evaluation_id']})
        # Ordinary G005 policy is retained, including conservative unresolved exposure.
        from .evidence import prepare_eligibility
        review,_=prepare_eligibility(self.store,evaluation['evaluation_id'],self.root)
        return self.close_assessment(assessment_id,'COMPLETED_FOR_REVIEW','teaching',
            {'evaluation_id':evaluation['evaluation_id'],'variant_descriptor_sha256':current['descriptor_sha256'],
             'variant_rules_sha256':current['rules_sha256'],'review_eligibility':review['eligibility'],
             'independence_status':review['independence_status'],'requires_review':True,'assistance':review['assistance']})

    def _remediated(self,evaluation_id):
        if self.session()['session']['phase']!='remediation': raise ValueError('Not in remediation.')
        from .evidence import verified_evaluation
        r,b,checked,_=verified_evaluation(self.store,evaluation_id,self.root)
        if b['session_id']!=self.session_id or r['outcome']!='CHECKS_PASS': raise ValueError('Bound passing practice evaluation required; assisted practice is permitted.')
        closed=[e for e in events(self.store.db,'assessment.closed') if e['session_id']==self.session_id]
        if not closed or checked['sequence']<=closed[-1]['sequence']:
            raise ValueError('Remediation requires practice evidence after assessment exit.')
        for attempt in (b['attempt_id'],b['failed_attempt_id']):
            submitted=events(self.store.db,'execution.submitted',attempt)
            if len(submitted)!=1 or submitted[0]['sequence']<=closed[-1]['sequence']:
                raise ValueError('Remediation requires newly submitted practice after assessment exit.')
        p={'evaluation_id':evaluation_id,'completed_at':self.timestamp}
        eid=self.emit('remediation.completed',evaluation_id,p,'remediation.completed:'+evaluation_id,self.session_id,checked['event_id'])
        self.store.db.execute("UPDATE sessions SET phase='teaching' WHERE id=?",(self.session_id,))
        return dict(p,anchor_event_id=eid)

    def submit(self,assessment_id,request_id,role,path,timeout=5.0,output_limit=65536):
        uuid(request_id)
        if role not in ROLES: raise ValueError('Unsupported assessment artifact role.')
        from .submissions import digest,inspect,submit
        from .runner import validate_limits,MAX_SOURCE_BYTES
        validate_limits(timeout,output_limit)
        path=Path(path)
        if path.suffix!='.py' or not path.is_file():raise ValueError('Regular Python source required.')
        raw=path.read_bytes()
        if len(raw)>MAX_SOURCE_BYTES:raise ValueError('Submission too large.')
        identity={'assessment_id':assessment_id,'role':role,'source_sha256':digest(raw),'timeout':timeout,'output_limit':output_limit,'request_id':request_id}
        with learning_lock(self.store.state_dir):
            self.clock_check();self.session()
            previous=self.store.db.execute('SELECT payload_json FROM events WHERE idempotency_key=?',('assessment.run:'+request_id,)).fetchone()
            if previous:
                r=json.loads(previous[0])
                if any(r[k]!=v for k,v in identity.items()):raise ValueError('Conflicting assessment submission request.')
                row=self.store.db.execute('SELECT 1 FROM attempts WHERE id=?',(r['attempt_id'],)).fetchone()
                return inspect(self.store,r['attempt_id']) if row else dict(r,status='reserved_pending_or_interrupted')
            s=self.require_open(assessment_id);self.bounds(s)
            if len(s['runs'])>=s['assessment']['max_runs']:raise ValueError('Assessment execution reservations exhausted.')
            finished=[r for r in s['runs'] if r['role']==role and self.store.db.execute('SELECT 1 FROM executions WHERE attempt_id=?',(r['attempt_id'],)).fetchone()]
            if any(self.store.attempt(r['attempt_id'])['status'] in {'completed','program_error'} for r in finished):
                raise ValueError('Completed role already exists; complete or exit this assessment.')
            r=dict(identity,attempt_id=str(uuid4()),ordinal=len(s['runs'])+1,observed_at=self.timestamp)
            with self.store.db:
                self.store.db.execute('BEGIN IMMEDIATE')
                self.emit('assessment.run_reserved',assessment_id,r,'assessment.run:'+request_id,self.session_id)
            permit=SubmissionPermit(r)
            try:
                result=submit(self.store,path,timeout,output_limit,_assessment_permit=permit)
                kind='assessment.interrupted' if result['status'] in {'interrupted','pending_or_interrupted'} else 'assessment.observation_recorded'
                p={'assessment_id':assessment_id,'attempt_id':r['attempt_id'],'execution_status':result['status']}
                with self.store.db:
                    self.emit(kind,assessment_id,p,'assessment.execution:'+r['attempt_id'],self.session_id)
                return result
            except BaseException:
                with self.store.db:
                    self.emit('assessment.interrupted',assessment_id,{'assessment_id':assessment_id,'pending_attempt_id':r['attempt_id']},'assessment.interrupt:'+r['attempt_id'],self.session_id)
                raise
            finally:permit.active=False
