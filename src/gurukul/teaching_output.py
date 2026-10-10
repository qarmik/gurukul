"""Hard validation precedes recoverable output rejection; never retries inference."""
from gurukul.pedagogy import validate_response, PedagogicalFormatError, response_authority_binding
from gurukul.intent_admission import admit, intent_hint


def evaluate_output(proposal, context):
    try:
        validated = validate_response(proposal,context,require_intents=True)
    except PedagogicalFormatError as exc:
        # All authority, source, scope, schema and bounded-example checks already ran.
        if 'intents' not in proposal['pedagogy']:
            raise ValueError('Live response missing mixed-intent schema')
        pending=(context['C_turn'].get('previous_teaching') or {}).get('diagnostic_question','') or context['C_turn'].get('unresolved_evidence_question','')
        reason=str(exc)
        validated = validate_response(proposal,context,allow_safe_format=True,require_intents=True)
        bound,_=admit(validated,context)
        admission={**bound,'conversation_status':'RESPONSE_REJECTED','judgment':'not_applicable',
                   'answer_admitted':False,'grants_mastery':False,'reason':reason,
                   'intents':bound['intents'],'pending_question':pending,
                   'unresolved_evidence_question':pending,'question_displayed':False,
                   'requested_strategy':intent_hint(context['C_turn']['learner_message'])['requested_strategy'],
                   'response_authority_binding':response_authority_binding(proposal,context)}
        shown={'explanation':'The Guru response did not satisfy the teaching-response policy. Your request has been preserved and was not graded. Please submit it again or ask another question. No automatic retry was made.',
               'diagnostic_question':'','miniature_example':''}
        return admission,shown
    if 'intents' not in proposal['pedagogy']:
        raise ValueError('Live response missing mixed-intent schema')
    admission,display = admit(validated,context)
    admission['response_authority_binding'] = response_authority_binding(proposal,context)
    return admission,display
