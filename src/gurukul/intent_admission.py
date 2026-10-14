"""Admit conversational observations, never mastery; recover semantic ambiguity."""
import re
from copy import deepcopy
from gurukul.learner_input import resolve, digest
from gurukul.semantic_routing import exact_control, route_proposal, route_concerns

INTENTS = {'ANSWER','QUESTION','CLARIFICATION','CONFUSION','META_QUESTION','REQUEST_FOR_EXPLANATION','HYPOTHESIS','ATTEMPT','UNCERTAINTY','PEDAGOGICAL_CONTROL'}
SPANS = {'answer_span':'ANSWER','question_span':'QUESTION','clarification_span':'CLARIFICATION',
         'confusion_span':'CONFUSION','uncertainty_span':'UNCERTAINTY','meta_span':'META_QUESTION','hypothesis_span':'HYPOTHESIS','explanation_span':'REQUEST_FOR_EXPLANATION','control_span':'PEDAGOGICAL_CONTROL'}


def explanation_request(message):
    """A strategy hint only; admission never consumes this guess as a requirement."""
    text=message.lower()
    requested=bool(re.search(r"\b(explain|give me (?:an?|some) (analogy|examples?|small examples?)|show me|simplify|more simply|walk me through|compare it|don't understand.*explanation|do not understand.*explanation)\b",text))
    if not requested:return None
    for pattern,strategy in [(r'analogy','analogy'),(r'counterexample','counterexample'),
                              (r'compar','comparison'),(r'example','miniature_example'),
                              (r'step.by.step|walk me through','verbal_model'),(r'simpl|again|different|understand','explanation')]:
        if re.search(pattern,text):return strategy
    return 'explanation'


def candidate_answers(message):
    """Legacy advisory segments; never used to admit or reject learner evidence."""
    if exact_control(message):return []
    if re.match(r'(?i)^(so )?(you are asking|are you asking|do you mean)\b',message.strip()) and message.rstrip().endswith('?'):
        return []
    segments=re.split(r'(?<=[.!?;])\s+|\n+|\s+but\s+|\s+(?=(?:why|what|how|can you|could you)\b)',message,flags=re.I)
    result=[]
    for segment in segments:
        text=segment.strip()
        if not text or '?' in text:continue
        if explanation_request(text):continue
        if re.match(r"^(what|why|how|when|where|can|could|is|does|do|explain|please explain|show me|teach me)\b",text,re.I):continue
        if re.match(r"^(i am confused|i'm confused|i don't understand|i do not understand|i meant|when i said|to clarify|let me clarify)\b",text,re.I):continue
        if re.fullmatch(r"(?i)(i am |i'm )?(confused|unsure|uncertain|not sure)[.!]?",text):continue
        if re.match(r'^(cd |git |PYTHONPATH=|python3? |brew |sudo )',text):continue
        result.append(text)
    return result


def intent_hint(message):
    kinds=[]
    if exact_control(message):kinds.append('PEDAGOGICAL_CONTROL')
    if candidate_answers(message):kinds.append('ANSWER')
    if explanation_request(message):kinds.append('REQUEST_FOR_EXPLANATION')
    for pattern,kind in [(r'\?|\b(what|why|how)\b','QUESTION'),
                          (r'\b(i meant|when i said|to clarify|did not mean|didn.t mean|not literally)\b','CLARIFICATION'),
                          (r"\b(confused|don't understand|do not understand)\b",'CONFUSION'),
                          (r'\b(unsure|uncertain|not sure|maybe)\b','UNCERTAINTY'),
                          (r'\b(i think|hypothesis)\b','HYPOTHESIS')]:
        if re.search(pattern,message,re.I):kinds.append(kind)
    return {'possible_intents':kinds,'origin':'parent_surface_heuristic_not_semantic_truth',
            'candidate_answer_segments':candidate_answers(message),'requested_strategy':explanation_request(message)}


def validate_intents(p):
    value=p['intents']
    expected={'primary','secondary',*SPANS}
    if isinstance(value,dict) and 'explanation_span' not in value:expected.remove('explanation_span')
    if isinstance(value,dict) and 'control_span' not in value:expected.remove('control_span')
    if not isinstance(value,dict) or set(value)!=expected:
        raise ValueError('Mixed-intent schema mismatch')
    if value['primary'] not in INTENTS or not isinstance(value['secondary'],list) or any(not isinstance(x,str) or x not in INTENTS for x in value['secondary']):
        raise ValueError('Invalid intent labels')
    if len(set(value['secondary']))!=len(value['secondary']) or value['primary'] in value['secondary']:
        raise ValueError('Duplicate intents')
    for field in SPANS:
        item=value.get(field,'')
        if not ((isinstance(item,str) and len(item)<=4000) or (isinstance(item,dict) and set(item) in ({'ref'},{'start','end'}))):
            raise ValueError('Invalid intent evidence span')
    responses=p['intent_responses']
    if not isinstance(responses,dict) or set(responses)!={'clarification','question','confusion'}:
        raise ValueError('Intent response schema mismatch')
    if any(not isinstance(x,str) or len(x)>1000 for x in responses.values()):raise ValueError('Invalid intent response text')


def admit(result, context):
    """Bind source spans, then review semantic proposals; never certify correctness."""
    original=result
    result=deepcopy(result)
    p=result['pedagogy']; intents=p['intents']; message=context['C_turn']['learner_message']
    verified={}; reference_error=None
    for field in SPANS:
        try:
            intents[field], binding=resolve(intents.get(field,''),message)
            if binding: verified[field]=dict(binding,text=intents[field])
        except ValueError as exc:
            intents[field]=''
            reference_error=str(exc)
    labels={intents['primary'],*intents['secondary']}; spans=intents
    prior=context['C_turn'].get('previous_teaching') or {}
    active_question=prior.get('diagnostic_question','') or context['C_turn'].get('unresolved_evidence_question','')
    controls=context.get('pedagogical_control',{}).get('controls',{})
    reason=None
    observations=[]
    command=exact_control(message)
    if command and not reference_error:
        # Parent-derived command interpretation is separate from raw model interpretation.
        intents=dict(primary='PEDAGOGICAL_CONTROL',secondary=[],**dict.fromkeys(SPANS,''))
        intents['control_span'],binding=resolve({'ref':'s0'},message)
        verified={'control_span':dict(binding,text=message)}
        p['intents']=intents
        labels={'PEDAGOGICAL_CONTROL'};spans=intents
        p.update(message_kind='PEDAGOGICAL_CONTROL',judgment='not_applicable')
        observations.append('Exact learner command interpreted by the parent; no answer evidence')
    if ('PEDAGOGICAL_CONTROL' in intents['secondary'] and not spans.get('control_span')
            and p.get('routing', {}).get('control_action', 'NONE') == 'NONE'):
        # An unsupported secondary label has no action/evidence authority. Keep the
        # source proposal in the audit; do not invent a control span to satisfy it.
        intents['secondary'] = [x for x in intents['secondary'] if x != 'PEDAGOGICAL_CONTROL']
        labels.discard('PEDAGOGICAL_CONTROL')
        observations.append('Unbound secondary control label not admitted; raw model proposal retained')
    for field,kind in SPANS.items():
        quote=spans.get(field,'')
        if quote and (quote not in message or kind not in labels):reason='Intent evidence is not bound to the learner message'
    for field,kind in SPANS.items():
        if kind in labels and not spans.get(field,''):reason='Intent label lacks an exact evidence span'
    answer=spans['answer_span']
    nonanswer_overlap=bool(answer and any(answer in spans.get(field,'') for field in
                          ('question_span','meta_span','explanation_span','control_span',
                           'confusion_span','clarification_span') if spans.get(field)))
    eligible=bool(active_question and answer and 'ANSWER' in labels and not nonanswer_overlap and not command and not reference_error)
    completed_requested_check=bool(eligible and p['judgment']=='correct' and
                                   context['turn_policy'].get('requested_check_active'))
    if 'ANSWER' in labels and not eligible:
        observations.append('Proposed answer intent was not admitted; no independent answer content')
    if answer and 'ANSWER' not in labels:reason='Answer span has no answer intent'
    if p['judgment'] not in {'not_applicable','not_assessed'} and not eligible:reason='No independently admissible answer span'
    if eligible and not controls.get('suppress_grading') and p['judgment'] in {'not_applicable','not_assessed'}:reason='Answer content requires an explicit conversational judgment'
    route=route_proposal(p,context,spans)
    concerns=route_concerns(route,result)
    if concerns:reason=concerns[0]
    requested=route['requested_strategy']
    if requested and not controls.get('strategy_flexible'):
        if 'REQUEST_FOR_EXPLANATION' not in labels or not spans.get('explanation_span'):
            reason='Explanation request needs explicit routing'
        compatible={requested}
        if requested=='explanation':compatible={'explanation','comparison','verbal_model'}
        if p['strategy'] not in compatible:
            reason='Requested explanation strategy was not supplied'
        if requested=='explanation' and (len(result['explanation'].split())>90 or result['explanation'].strip()==prior.get('explanation','').strip()):
            reason='Simplification needs a concise changed explanation'
        if requested=='miniature_example' and not result['miniature_example'].strip():
            reason='Requested example was not supplied'
    for field,reply in [('clarification_span','clarification'),('question_span','question'),('meta_span','question'),('confusion_span','confusion')]:
        if spans[field] and not p['intent_responses'][reply].strip():
            observations.append('Secondary intent may be addressed in the main explanation: '+reply)
    if spans['confusion_span'] and result['explanation'].strip()==prior.get('explanation','').strip():
        reason='Repeated explanation did not address confusion'
    count=context['turn_policy']['model_observation_counts_not_mastery'][p['concept']]+(eligible and p['judgment']=='correct')
    if eligible and not completed_requested_check and count>=2 and p['next_activity'] not in {'predict','learner_example','variation'}:
        reason='More demanding representation needed'
    if eligible and not completed_requested_check and p['judgment']=='correct' and prior.get('pedagogy',{}).get('next_activity')=='variation' and p['next_activity']=='variation':
        reason='Successful variation should advance representation, not another synonym variation'
    questions=[digest(x.get('question','')) for x in context['C_turn']['recent_exchanges'] if x.get('question')]
    if eligible and not completed_requested_check and result['diagnostic_question'] and digest(result['diagnostic_question']) in questions:
        reason='Equivalent exact question needs replacement'
    evidence={'learner_input_sha256':digest(message),'learner_verified_spans':verified,
              'model_interpretation':deepcopy(original['pedagogy']['intents']),
              'model_judgment_proposal':original['pedagogy']['judgment'],
              'conversation_observations':observations,'admission_policy':'bound-semantic-proposals-v2',
              'semantic_route':route,
              'learner_control':{'kind':'PEDAGOGICAL_CONTROL','action':route['control_action'],
                                 'origin':route['control_origin'],'bound':route['control_bound']} if route['control_action']!='NONE' else None}
    if reference_error:
        reason='Interpretation reference rejected: '+reference_error
    if reason:
        if reason == 'A requested fresh check needs a new diagnostic question' and not reference_error and concerns == [reason]:
            display=dict(result,diagnostic_question='',recovery_notice='Your check request is saved, but Guru did not supply a new question. This turn stays ungraded.')
        else:
            display={'explanation':'The proposed response could not be admitted. Your message and the unresolved learning question are saved, and your answer has not been marked wrong. You can ask for a different explanation or continue when ready.',
                     'diagnostic_question':'','miniature_example':''}
        return {**evidence,'conversation_status':'NEEDS_CLARIFICATION','judgment':'not_applicable','answer_admitted':False,
                'reason':reason,'failure_class':'SEMANTIC_UNCERTAINTY','validation_stage':'semantic_admission',
                'intents':intents,'unresolved_evidence_question':active_question,'pending_question':active_question,'question_displayed':False,'grants_mastery':False},display
    # Pending evidence is not a command to repeat its question on every turn.
    # Safe ungraded discussion may answer, clarify or pause without a new check.
    display=result
    if completed_requested_check:
        observations.append('Requested check answered; further unsolicited question suppressed, independent evidence still unresolved')
        display=deepcopy(result);display['diagnostic_question']='';display['pedagogy']['next_activity']='pause'
    elif p['next_activity']=='pause':
        display=dict(result,diagnostic_question='')
    return {**evidence,'conversation_status':'CONTINUE','judgment':'not_applicable' if not eligible else p['judgment'],
            'answer_admitted':eligible,'reason':'Exact learner span bound to active question; correctness remains a model observation' if eligible else 'No conceptual answer admitted; unresolved evidence retained',
            'intents':intents,'pending_question':'' if completed_requested_check else display['diagnostic_question'] or active_question,
            'question_displayed':bool(display['diagnostic_question']),
            'unresolved_evidence_question':active_question if not eligible else '',
            'requested_check_completed':completed_requested_check,
            'requested_strategy':requested,'unmet_evidence_requirement':
                'Independent exercise evidence still required: '+', '.join(context['orientation']['B_active']['required_evidence'])
                if completed_requested_check else p['evidence_need'],'grants_mastery':False},display


def runtime_notice(report):
    if report['status']=='PASS':return 'Turn saved; evidence verified.'
    return 'Turn could not be completed safely.'
