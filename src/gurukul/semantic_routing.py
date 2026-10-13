"""Surface clues are advisory. Bound proposals never own curriculum or mastery."""
import re
from gurukul.response_contract import schema_error

KNOWLEDGE_TASKS = {'stable_fundamentals', 'source_specific', 'curriculum_requirement',
                   'version_sensitive', 'regulatory', 'uncertain'}
SCOPES = {'current_capability', 'future_acknowledgement', 'future_depth', 'uncertain'}
ACTIONS = {'NONE', 'REQUEST_FRESH_CHECK', 'REQUEST_EXPLANATION'}
REQUESTED_STRATEGIES = {'explanation', 'analogy', 'miniature_example', 'comparison',
                        'counterexample', 'verbal_model'}
# A deliberately small command protocol, not a natural-language classifier.
COMMANDS = {'check my understanding': 'REQUEST_FRESH_CHECK',
            'ask me a new question': 'REQUEST_FRESH_CHECK',
            'resume the check': 'REQUEST_FRESH_CHECK'}
ROUTING_FIELDS = {'knowledge_task': KNOWLEDGE_TASKS, 'teaching_scope': SCOPES,
                  'control_action': ACTIONS, 'requested_strategy': REQUESTED_STRATEGIES}


def exact_control(message):
    return COMMANDS.get(message.strip().casefold().rstrip('.!').rstrip())


def surface_signals(message):
    """Candidates may inform the existing inference; no consumer may enforce them."""
    patterns = {'source_specific': r'\b(book|source|excerpt|page)\b',
                'curriculum_requirement': r'\b(curriculum|requirement|gate)\b',
                'version_sensitive': r'\b(latest|current version|python 3\.\d+)\b',
                'regulatory': r'\b(regulation|regulatory|law|legal|rbi)\b',
                'future_topic': r'\b(agent|governance|formal method|inference economic|LEGB|AST|enterprise architect)'}
    return {'candidates': [name for name, pattern in patterns.items() if re.search(pattern, message, re.I)],
            'authority': 'none', 'origin': 'parent_surface_hint'}


def validate_routing(value):
    if not isinstance(value, dict) or set(value) - set(ROUTING_FIELDS):
        raise schema_error('Invalid semantic routing proposal', 'guru.routing.schema', set(), value,
                           optional=set(ROUTING_FIELDS))
    for key, allowed in ROUTING_FIELDS.items():
        if key in value and (not isinstance(value[key], str) or value[key] not in allowed):
            raise ValueError('Invalid semantic routing ' + key)


def route_proposal(p, context, intents):
    """Derive a reviewable route from parent metadata and exact-bound interpretation."""
    proposed = p.get('routing', {})
    metadata = context.get('task_metadata', {})
    if not isinstance(metadata, dict):raise ValueError('Invalid authoritative task metadata')
    if metadata.get('unlocked_capability', context['C_turn']['location']) != context['C_turn']['location']:
        raise ValueError('Authoritative task capability conflicts with parent location')
    required = metadata.get('required_knowledge_task')
    if required is not None and required not in KNOWLEDGE_TASKS - {'uncertain'}:
        raise ValueError('Invalid authoritative knowledge task')
    default = metadata.get('default_knowledge_task', 'stable_fundamentals')
    if default not in KNOWLEDGE_TASKS:raise ValueError('Invalid authoritative default knowledge task')
    task = required or proposed.get('knowledge_task') or default
    command = exact_control(context['C_turn']['learner_message'])
    action = command or proposed.get('control_action', 'NONE')
    if action == 'NONE' and intents.get('explanation_span'):
        action = 'REQUEST_EXPLANATION'
    # Natural controls need a bound control/explanation span. A keyword cannot supply it.
    control_bound = bool(command or intents.get('control_span') or
                         action == 'REQUEST_EXPLANATION' and intents.get('explanation_span'))
    return {'knowledge_task': task,
            'knowledge_origin': 'parent_task_metadata' if required else 'model_semantic_proposal' if
                'knowledge_task' in proposed else 'parent_current_task_default',
            'claim_source_specific': p['source_specific'],
            'claim_knowledge_classes': list(p['knowledge_classes']),
            'bound_interpretation_spans': [key for key, value in intents.items() if key.endswith('_span') and value],
            'teaching_scope': proposed.get('teaching_scope',
                'future_acknowledgement' if p['future_topic_deferred'] else 'current_capability'),
            'control_action': action, 'control_bound': control_bound,
            'control_origin': 'exact_command' if command else 'model_semantic_proposal',
            'requested_strategy': None if command else proposed.get('requested_strategy'),
            'surface_hints_used_as_authority': False}


def route_concerns(route, result):
    """Semantic contradictions yield clarification, never a runtime BLOCKED verdict."""
    p = result['pedagogy']; concerns = []
    task = route['knowledge_task']; scope = route['teaching_scope']
    if task == 'uncertain' or scope == 'uncertain':
        concerns.append('Semantic route requires clarification')
    if task == 'source_specific' and p['strategy'] != 'defer' and (
            not p['source_specific'] or 'approved_source' not in p['knowledge_classes']):
        concerns.append('Source-specific claim needs supplied source grounding')
    if task == 'curriculum_requirement' and p['strategy'] != 'defer' and 'canonical_curriculum' not in p['knowledge_classes']:
        concerns.append('Curriculum requirements need canonical grounding')
    if task in {'version_sensitive', 'regulatory'} and p['strategy'] != 'defer':
        concerns.append('Authoritative current source unavailable; clarify or defer claim')
    if scope == 'future_depth':
        concerns.append('Teaching depth exceeds the unlocked capability')
    if scope == 'future_acknowledgement' and (
            not p['future_topic_deferred'] or p['strategy'] != 'defer' or
            result['miniature_example'] or len(result['explanation'].split()) > 100):
        concerns.append('Future acknowledgement must remain brief and defer depth')
    if route['control_action'] != 'NONE' and not route['control_bound']:
        concerns.append('Pedagogical control lacks a bound learner span')
    if route['control_action'] == 'REQUEST_FRESH_CHECK' and not result['diagnostic_question'].strip():
        concerns.append('A requested fresh check needs a new diagnostic question')
    return concerns
