"""Admit conversational observations, never mastery; recover semantic ambiguity."""
import re
from copy import deepcopy
from gurukul.learner_input import resolve, digest

INTENTS = {'ANSWER','QUESTION','CLARIFICATION','CONFUSION','META_QUESTION','REQUEST_FOR_EXPLANATION','HYPOTHESIS','ATTEMPT','UNCERTAINTY'}
SPANS = {'answer_span':'ANSWER','question_span':'QUESTION','clarification_span':'CLARIFICATION',
         'confusion_span':'CONFUSION','uncertainty_span':'UNCERTAINTY','meta_span':'META_QUESTION','hypothesis_span':'HYPOTHESIS','explanation_span':'REQUEST_FOR_EXPLANATION'}


def explanation_request(message):
    text=message.lower()
    requested=bool(re.search(r"\b(explain|give me (?:an?|some) (analogy|examples?|small examples?)|show me|simpler|simplify|more simply|walk me through|compare it|don't understand.*explanation|do not understand.*explanation)\b",text))
    if not requested:return None
    for pattern,strategy in [(r'analogy','analogy'),(r'counterexample','counterexample'),
                              (r'compar','comparison'),(r'example','miniature_example'),
                              (r'step.by.step|walk me through','verbal_model'),(r'simpl|again|different|understand','explanation')]:
        if re.search(pattern,text):return strategy
    return 'explanation'


def candidate_answers(message):
    """Conservative surface admission: declarative segments, not semantic correctness."""
    if re.match(r'(?i)^(so )?(you are asking|are you asking|do you mean)\b',message.strip()) and message.rstrip().endswith('?'):
        return []
    segments=re.split(r'(?<=[.!?;])\s+|\n+|\s+(?=(?:why|what|how|can you|could you)\b)',message,flags=re.I)
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
    """Called only AFTER all structural/security/source/scope checks succeed."""
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
    reason=None
    observations=[]
    for field,kind in SPANS.items():
        quote=spans.get(field,'')
        if quote and (quote not in message or kind not in labels):reason='Intent evidence is not bound to the learner message'
    for field,kind in SPANS.items():
        if kind in labels and not spans.get(field,''):reason='Intent label lacks an exact evidence span'
    if '?' in message and not (spans['question_span'] or spans['meta_span']):reason='Learner question must be retained and answered'
    answer=spans['answer_span']
    eligible=bool(active_question and answer and (any(answer in segment for segment in candidate_answers(message)) or (answer == message and candidate_answers(message) and '?' not in message and not explanation_request(message))))
    if 'ANSWER' in labels and not eligible:
        observations.append('Proposed answer intent was not admitted; no independent answer content')
    if answer and 'ANSWER' not in labels:reason='Answer span has no answer intent'
    if p['judgment'] not in {'not_applicable','not_assessed'} and not eligible:reason='No independently admissible answer span'
    if eligible and p['judgment'] in {'not_applicable','not_assessed'}:reason='Answer content requires an explicit conversational judgment'
    hint=intent_hint(message)
    requested=hint['requested_strategy']
    if requested:
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
    if 'CLARIFICATION' in hint['possible_intents'] and not spans['clarification_span']:
        reason='Clarification needs acknowledgment rather than a confusion label'
    for field,reply in [('clarification_span','clarification'),('question_span','question'),('meta_span','question'),('confusion_span','confusion')]:
        if spans[field] and not p['intent_responses'][reply].strip():
            observations.append('Secondary intent may be addressed in the main explanation: '+reply)
    if not eligible and hint['candidate_answer_segments'] and active_question and p['judgment']!='not_applicable':
        reason='Unresolved answer admission'
    if spans['confusion_span'] and result['explanation'].strip()==prior.get('explanation','').strip():
        reason='Repeated explanation did not address confusion'
    count=context['turn_policy']['model_observation_counts_not_mastery'][p['concept']]+(eligible and p['judgment']=='correct')
    if eligible and count>=2 and p['next_activity'] not in {'predict','learner_example','variation'}:
        reason='More demanding representation needed'
    if eligible and p['judgment']=='correct' and prior.get('pedagogy',{}).get('next_activity')=='variation' and p['next_activity']=='variation':
        reason='Successful variation should advance representation, not another synonym variation'
    questions=[x.get('question','').strip().casefold() for x in context['C_turn']['recent_exchanges']]
    if eligible and result['diagnostic_question'].strip() and result['diagnostic_question'].strip().casefold() in questions:
        reason='Equivalent exact question needs replacement'
    evidence={'learner_input_sha256':digest(message),'learner_verified_spans':verified,
              'model_interpretation':deepcopy(original['pedagogy']['intents']),
              'model_judgment_proposal':original['pedagogy']['judgment'],
              'conversation_observations':observations,'admission_policy':'separate-display-evidence-v1'}
    if reference_error:
        reason='Interpretation reference rejected: '+reference_error
    if reason:
        display={'explanation':'The proposed response could not be admitted. Your message and the unresolved learning question are saved, and your answer has not been marked wrong. You can ask for a different explanation or continue when ready.',
                 'diagnostic_question':'','miniature_example':''}
        return {**evidence,'conversation_status':'NEEDS_CLARIFICATION','judgment':'not_applicable','answer_admitted':False,
                'reason':reason,'intents':intents,'unresolved_evidence_question':active_question,'pending_question':active_question,'question_displayed':False,'grants_mastery':False},display
    # Pending evidence is not a command to repeat its question on every turn.
    # Safe ungraded discussion may answer, clarify or pause without a new check.
    display=result
    if p['next_activity']=='pause':
        display=dict(result,diagnostic_question='')
    return {**evidence,'conversation_status':'CONTINUE','judgment':'not_applicable' if not eligible else p['judgment'],
            'answer_admitted':eligible,'reason':'Exact learner span bound to active question; correctness remains a model observation',
            'intents':intents,'pending_question':display['diagnostic_question'] or active_question,
            'question_displayed':bool(display['diagnostic_question']),
            'unresolved_evidence_question':active_question if not eligible else '',
            'requested_strategy':requested,'unmet_evidence_requirement':p['evidence_need'],'grants_mastery':False},display


def runtime_notice(report):
    if report['status']=='PASS':return 'Turn saved; evidence verified.'
    return 'Turn could not be completed safely.'
