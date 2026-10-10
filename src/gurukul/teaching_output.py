"""Hard validation precedes recoverable output rejection; never retries inference."""
from gurukul.pedagogy import validate_response, PedagogicalFormatError
from gurukul.intent_admission import admit, intent_hint


def evaluate_output(proposal, context):
    try:
        validate_response(proposal,context)
    except PedagogicalFormatError as exc:
        # All authority, source, scope, schema and bounded-example checks already ran.
        if 'intents' not in proposal['pedagogy']:
            raise ValueError('Live response missing mixed-intent schema')
        pending=(context['C_turn'].get('previous_teaching') or {}).get('diagnostic_question','') or context['C_turn'].get('unresolved_evidence_question','')
        reason=str(exc)
        bound,_=admit(proposal,context)
        admission={**bound,'conversation_status':'RESPONSE_REJECTED','judgment':'not_applicable',
                   'answer_admitted':False,'grants_mastery':False,'reason':reason,
                   'intents':bound['intents'],'pending_question':pending,
                   'unresolved_evidence_question':pending,'question_displayed':False,
                   'requested_strategy':intent_hint(context['C_turn']['learner_message'])['requested_strategy']}
        shown={'explanation':'The Guru response did not satisfy the teaching-response policy. Your request has been preserved and was not graded. Please submit it again or ask another question. No automatic retry was made.',
               'diagnostic_question':'','miniature_example':''}
        return admission,shown
    if 'intents' not in proposal['pedagogy']:
        raise ValueError('Live response missing mixed-intent schema')
    return admit(proposal,context)
