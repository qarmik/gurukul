"""Admit conversational observations, never mastery; recover semantic ambiguity."""
import re

INTENTS = {'ANSWER','QUESTION','CLARIFICATION','CONFUSION','META_QUESTION','REQUEST_FOR_EXPLANATION','HYPOTHESIS','ATTEMPT','UNCERTAINTY'}
SPANS = {'answer_span':'ANSWER','question_span':'QUESTION','clarification_span':'CLARIFICATION',
         'confusion_span':'CONFUSION','uncertainty_span':'UNCERTAINTY','meta_span':'META_QUESTION','hypothesis_span':'HYPOTHESIS'}


def candidate_answers(message):
    """Conservative surface admission: declarative segments, not semantic correctness."""
    segments=re.split(r'(?<=[.!?;])\s+|\n+|\s+(?=(?:why|what|how|can you|could you)\b)',message,flags=re.I)
    result=[]
    for segment in segments:
        text=segment.strip()
        if not text or '?' in text:continue
        if re.match(r"^(what|why|how|when|where|can|could|is|does|do|explain|please explain|show me|teach me)\b",text,re.I):continue
        if re.match(r"^(i am confused|i'm confused|i don't understand|i do not understand|i meant|when i said|to clarify|let me clarify)\b",text,re.I):continue
        if re.fullmatch(r"(?i)(i am |i'm )?(confused|unsure|uncertain|not sure)[.!]?",text):continue
        if re.match(r'^(cd |git |PYTHONPATH=|python3? |brew |sudo )',text):continue
        result.append(text)
    return result


def intent_hint(message):
    kinds=[]
    if candidate_answers(message):kinds.append('ANSWER')
    for pattern,kind in [(r'\?|\b(what|why|how)\b','QUESTION'),
                          (r'\b(i meant|when i said|to clarify|did not mean|didn.t mean|not literally)\b','CLARIFICATION'),
                          (r"\b(confused|don't understand|do not understand)\b",'CONFUSION'),
                          (r'\b(unsure|uncertain|not sure|maybe)\b','UNCERTAINTY'),
                          (r'\b(i think|hypothesis)\b','HYPOTHESIS')]:
        if re.search(pattern,message,re.I):kinds.append(kind)
    return {'possible_intents':kinds,'origin':'parent_surface_heuristic_not_semantic_truth',
            'candidate_answer_segments':candidate_answers(message)}


def validate_intents(p):
    value=p['intents']
    if not isinstance(value,dict) or set(value)!={'primary','secondary',*SPANS}:
        raise ValueError('Mixed-intent schema mismatch')
    if value['primary'] not in INTENTS or not isinstance(value['secondary'],list) or any(not isinstance(x,str) or x not in INTENTS for x in value['secondary']):
        raise ValueError('Invalid intent labels')
    if len(set(value['secondary']))!=len(value['secondary']) or value['primary'] in value['secondary']:
        raise ValueError('Duplicate intents')
    for field in SPANS:
        if not isinstance(value[field],str) or len(value[field])>800:raise ValueError('Invalid intent evidence span')
    responses=p['intent_responses']
    if not isinstance(responses,dict) or set(responses)!={'clarification','question','confusion'}:
        raise ValueError('Intent response schema mismatch')
    if any(not isinstance(x,str) or len(x)>1000 for x in responses.values()):raise ValueError('Invalid intent response text')


def admit(result, context):
    """Called only AFTER all structural/security/source/scope checks succeed."""
    p=result['pedagogy']; intents=p['intents']; message=context['C_turn']['learner_message']
    labels={intents['primary'],*intents['secondary']}; spans=intents
    prior=context['C_turn'].get('previous_teaching') or {}
    active_question=prior.get('diagnostic_question','')
    reason=None
    for field,kind in SPANS.items():
        quote=spans[field]
        if quote and (quote not in message or kind not in labels):reason='Intent evidence is not bound to the learner message'
    for field,kind in SPANS.items():
        if kind in labels and not spans[field]:reason='Intent label lacks an exact evidence span'
    if '?' in message and not (spans['question_span'] or spans['meta_span']):reason='Learner question must be retained and answered'
    answer=spans['answer_span']
    eligible=bool(active_question and answer and any(answer in segment for segment in candidate_answers(message)))
    if 'ANSWER' in labels and not eligible:reason='Answer content is ambiguous or no active question exists'
    if answer and 'ANSWER' not in labels:reason='Answer span has no answer intent'
    if p['judgment'] not in {'not_applicable','not_assessed'} and not eligible:reason='No independently admissible answer span'
    if eligible and p['judgment'] in {'not_applicable','not_assessed'}:reason='Answer content requires an explicit conversational judgment'
    hint=intent_hint(message)
    if 'CLARIFICATION' in hint['possible_intents'] and not spans['clarification_span']:
        reason='Clarification needs acknowledgment rather than a confusion label'
    for field,reply in [('clarification_span','clarification'),('question_span','question'),('meta_span','question'),('confusion_span','confusion')]:
        if spans[field] and not p['intent_responses'][reply].strip():reason='Secondary intent needs a direct response'
    if not eligible and hint['candidate_answer_segments'] and active_question and p['judgment']!='not_applicable':
        reason='Unresolved answer admission'
    if spans['confusion_span'] and p['strategy']==context['turn_policy']['previous_strategy']:
        reason='A different explanation is needed for confusion'
    count=context['turn_policy']['model_observation_counts_not_mastery'][p['concept']]+(eligible and p['judgment']=='correct')
    if eligible and count>=2 and p['next_activity'] not in {'predict','learner_example','variation'}:
        reason='More demanding representation needed'
    if eligible and p['judgment']=='correct' and prior.get('pedagogy',{}).get('next_activity')=='variation' and p['next_activity']=='variation':
        reason='Successful variation should advance representation, not another synonym variation'
    questions=[x.get('question','').strip().casefold() for x in context['C_turn']['recent_exchanges']]
    if eligible and result['diagnostic_question'].strip() and result['diagnostic_question'].strip().casefold() in questions:
        reason='Equivalent exact question needs replacement'
    if reason:
        display={'explanation':'I could not reliably separate or route that message. No correctness judgment was recorded. Please restate your answer and any follow-up separately, or ask your question directly.',
                 'diagnostic_question':active_question,'miniature_example':''}
        return {'conversation_status':'NEEDS_CLARIFICATION','judgment':'not_applicable','answer_admitted':False,
                'reason':reason,'intents':intents,'pending_question':active_question,'grants_mastery':False},display
    display=result if eligible else dict(result,diagnostic_question=active_question or result['diagnostic_question'])
    return {'conversation_status':'CONTINUE','judgment':'not_applicable' if not eligible else p['judgment'],
            'answer_admitted':eligible,'reason':'Exact learner span bound to active question; correctness remains a model observation',
            'intents':intents,'pending_question':display['diagnostic_question'],'grants_mastery':False},display


def runtime_notice(report):
    if report['status']=='PASS':return 'Turn saved; evidence verified.'
    return 'Turn could not be completed safely.'
