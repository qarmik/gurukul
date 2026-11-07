"""D01 practice eligibility, never verified independence or progression."""
import hashlib
import json
from pathlib import Path
from uuid import UUID

from . import checks
from .pedagogy import orientation
from .store import canonical

POLICY_VERSION = 'd01-evidence-eligibility-2-timing'
KINDS = {'none_declared', 'concept_support', 'hint', 'code_or_repair',
         'solution_exposure', 'unknown'}
STEPS = {'construction', 'repair', 'concept_practice'}
TIMINGS = {'before_work', 'during_work', 'after_submission', 'unknown'}
ORIGINS = {'learner_declaration', 'parent_event'}
CONTEXT_KEYS = ('attempt_id', 'source_sha256', 'exercise_id', 'exercise_version',
                'exercise_sha256', 'checker_id', 'checker_version', 'checker_sha256',
                'spec_sha256', 'execution_sha256', 'failed_attempt_id',
                'failed_source_sha256', 'failed_execution_sha256')


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def event_for(store, kind, subject):
    rows = store.db.execute('SELECT * FROM events WHERE event_type=? AND subject_id=?',
                            (kind, subject)).fetchall()
    if len(rows) != 1:
        raise ValueError('Required parent event is missing or ambiguous: ' + kind)
    return rows[0]


def bindings(store, attempt_id, failed_attempt_id=None):
    attempt, _ = checks.snapshot(store, attempt_id)
    exercise = checks.exercise_for_attempt(store, attempt)
    if exercise['id'] != 'C0-B01-D01':
        raise ValueError('Eligibility is limited to D01.')
    failed = checks.snapshot(store, failed_attempt_id)[0] if failed_attempt_id else None
    if failed and (failed['id'] == attempt_id or failed['session_id'] != attempt['session_id']):
        raise ValueError('Failed/repaired evidence must be distinct attempts in one session.')
    result = {'session_id': attempt['session_id'], 'attempt_id': attempt_id,
              'source_sha256': attempt['source_sha256'],
              'exercise_id': exercise['id'], 'exercise_version': exercise['version'],
              'exercise_sha256': exercise['sha256'], 'failed_attempt_id': failed_attempt_id,
              'failed_source_sha256': failed['source_sha256'] if failed else None}
    submitted = event_for(store, 'execution.submitted', attempt_id)
    if (submitted['session_id'] != attempt['session_id'] or
            json.loads(submitted['payload_json']) != {'source_sha256': attempt['source_sha256']}):
        raise ValueError('Submission event does not match artifact bindings.')
    return result, submitted, exercise


def prepare_assistance(store, attempt_id, declaration, failed_attempt_id=None):
    if not isinstance(declaration, dict):
        raise ValueError('Assistance declaration must be an object.')
    required = {'request_id', 'kind', 'steps', 'timing', 'origin'}
    optional = {'support_event_id', 'support_payload_sha256', 'declaration_text', 'declaration_source', 'statement_at'}
    if not required <= declaration.keys() or declaration.keys() - required - optional:
        raise ValueError('Assistance declaration schema mismatch.')
    if 'declaration_text' in declaration:
        if (not isinstance(declaration['declaration_text'], str) or not 1 <= len(declaration['declaration_text']) <= 4096
                or declaration.get('declaration_source') not in {'workspace', 'learner_supplied_transcript'}):
            raise ValueError('Exact declaration text and source are required together.')
    elif 'declaration_source' in declaration or 'statement_at' in declaration:
        raise ValueError('Declaration provenance requires exact text.')
    if declaration.get('statement_at') is not None:
        from .assessment import instant
        instant(declaration['statement_at'])  # Reported statement time, never the event recording time.
    request = declaration['request_id']
    try:
        if not isinstance(request, str) or str(UUID(request)) != request:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ValueError('request_id must be a canonical UUID.') from None
    if (not isinstance(declaration['kind'], str) or declaration['kind'] not in KINDS or
            not isinstance(declaration['timing'], str) or declaration['timing'] not in TIMINGS or
            not isinstance(declaration['origin'], str) or declaration['origin'] not in ORIGINS):
        raise ValueError('Unknown assistance kind, timing or origin.')
    steps = declaration['steps']
    if (not isinstance(steps, list) or not steps or
            any(not isinstance(s, str) or s not in STEPS for s in steps) or
            len(steps) != len(set(steps))):
        raise ValueError('Assistance steps must be distinct supported steps.')
    if declaration['kind'] == 'none_declared' and (
            declaration['origin'] != 'learner_declaration' or
            declaration['timing'] != 'during_work' or 'concept_practice' in steps):
        raise ValueError('No-help statements are scoped learner declarations about work, not observations.')
    if declaration['kind'] == 'concept_support' and steps != ['concept_practice']:
        raise ValueError('Concept support must be scoped to conceptual practice.')
    bound, submitted, _ = bindings(store, attempt_id, failed_attempt_id)
    support = None
    if declaration['origin'] == 'parent_event':
        reference = declaration.get('support_event_id')
        support = store.db.execute('SELECT * FROM events WHERE event_id=?', (reference,)).fetchone() if isinstance(reference, str) else None
        if (not support or support['event_type'] != 'teaching.integration_finished' or
                support['session_id'] != bound['session_id'] or
                support['source'] != 'gurukul.hermes_adapter'):
            raise ValueError('Supporting teaching event must belong to this artifact session; cross-ledger imports are not supported.')
        payload = json.loads(support['payload_json'])
        if (digest(payload) != declaration.get('support_payload_sha256') or
                payload.get('status') != 'PASS' or payload.get('grants_mastery') is not False or
                payload.get('provenance', {}).get('exercise_sha256') != bound['exercise_sha256']):
            raise ValueError('Supporting parent event content/provenance mismatch.')
    elif {'support_event_id', 'support_payload_sha256'} & declaration.keys():
        raise ValueError('Unverified support references cannot be labelled learner declarations.')
    fact = dict(declaration, steps=sorted(steps))
    return {'schema_version': 1, 'bindings': bound, 'fact': fact,
            'provenance': {'status': 'supported_observation' if support else 'declared_only',
                           'support_event_id': support['event_id'] if support else None,
                           'support_payload_sha256': digest(json.loads(support['payload_json'])) if support else None,
                           'limitation': 'Recorded provenance does not verify absence of external assistance.'}}, submitted['event_id']


def verified_evaluation(store, evaluation_id, root):
    row = store.db.execute('SELECT * FROM evaluations WHERE id=?', (evaluation_id,)).fetchone()
    if not row:
        raise ValueError('Unknown evaluation ID.')
    result = json.loads(row['result_json'])
    if not isinstance(result, dict) or not set(CONTEXT_KEYS) <= result.keys():
        raise ValueError('Evaluation bindings are incomplete.')
    bound, _, exercise = bindings(store, row['attempt_id'], result['failed_attempt_id'])
    attempt, _ = checks.snapshot(store, row['attempt_id'])
    failed = checks.snapshot(store, result['failed_attempt_id'])[0] if result['failed_attempt_id'] else None
    spec_bytes = (Path(root) / 'content/checks/d01-v1.json').read_bytes()
    spec = json.loads(spec_bytes)
    expected = {k: bound[k] for k in ('attempt_id', 'source_sha256', 'exercise_id',
                                      'exercise_version', 'exercise_sha256',
                                      'failed_attempt_id', 'failed_source_sha256')}
    expected.update(checker_id=spec['checker_id'], checker_version=spec['checker_version'],
                    checker_sha256=hashlib.sha256(Path(checks.__file__).read_bytes()).hexdigest(),
                    spec_sha256=hashlib.sha256(spec_bytes).hexdigest(),
                    execution_sha256=digest(attempt['execution']),
                    failed_execution_sha256=digest(failed['execution']) if failed else None)
    checked = event_for(store, 'assessment.checked', evaluation_id)
    if (any(result.get(k) != v for k, v in expected.items()) or
            digest(expected) != evaluation_id or result.get('evaluation_id') != evaluation_id or
            result.get('grants_mastery') is not False or result.get('independence') != 'not_verified' or
            checked['session_id'] != bound['session_id'] or
            json.loads(checked['payload_json']) != result):
        raise ValueError('Evaluation differs from bound artifacts, checker or parent event.')
    if result['outcome'] == 'CHECKS_PASS' and (not result.get('checks') or
            any(c.get('status') != 'PASS' for c in result['checks'])):
        raise ValueError('Inconsistent passing evaluation.')
    _, proof = orientation(Path(root), json.loads(exercise['content_json']))
    curriculum = {k: proof[k] for k in ('curriculum_version', 'canonical_sha256', 'map_sha256')}
    return result, bound, checked, curriculum


def occurrence_relevance(store, bound, original, fact, recorded_sequence, exact):
    """Reported timing stays relative to ORIGINAL work, never a hash-matched pair.

    Submission events bound the retained work, not its unobserved blank-file
    beginning. Recording order supplies an upper bound on known exposure only;
    a late report does not say when an after-submission occurrence happened.
    """
    original_end = event_for(store, 'execution.submitted', original['attempt_id'])
    target_end = event_for(store, 'execution.submitted', bound['attempt_id'])
    target_start = event_for(store, 'execution.submitted', bound['failed_attempt_id'] or bound['attempt_id'])
    basis = {'reported_timing': fact['timing'],
             'original_submission_event_id': original_end['event_id'],
             'original_submission_sequence': original_end['sequence'],
             'target_submission_event_id': target_end['event_id'],
             'target_submission_sequence': target_end['sequence'],
             'target_first_submission_sequence': min(target_start['sequence'], target_end['sequence']),
             'recorded_sequence': recorded_sequence}
    if fact['kind'] == 'none_declared':
        return 'exact_declaration', basis
    if fact['kind'] == 'concept_support':
        return 'conceptual_practice_only', basis
    if fact['timing'] == 'after_submission' and target_end['sequence'] <= original_end['sequence']:
        return 'after_completed_work', basis
    if fact['kind'] == 'unknown' or fact['timing'] == 'unknown':
        return 'unresolved', basis
    if exact:
        return 'original_work', basis
    if fact['kind'] == 'solution_exposure':
        before_target = original_end['sequence'] < basis['target_first_submission_sequence']
        if before_target and (fact['timing'] in {'before_work', 'during_work'} or
                recorded_sequence < basis['target_first_submission_sequence']):
            return 'prior_variant_exposure', basis
    # Shared bytes/attempts identify candidates, not causal proof of help.
    return 'unresolved', basis


def relevant_assistance(store, bound):
    facts = []
    target_ids = {bound['attempt_id'], bound['failed_attempt_id']} - {None}
    hashes = {bound['source_sha256'], bound['failed_source_sha256']} - {None}
    for row in store.db.execute("SELECT * FROM events WHERE event_type='assistance.recorded' ORDER BY sequence"):
        payload = json.loads(row['payload_json'])
        other = payload.get('bindings', {})
        if other.get('exercise_sha256') != bound['exercise_sha256']:
            continue
        fact = payload.get('fact', {})
        exact = (other.get('attempt_id') == bound['attempt_id'] and
                 other.get('failed_attempt_id') == bound['failed_attempt_id'])
        overlap = bool(target_ids & {other.get('attempt_id'), other.get('failed_attempt_id')})
        same_source = bool(hashes & {other.get('source_sha256'), other.get('failed_source_sha256')})
        exposure = fact.get('kind') == 'solution_exposure'
        # Positive declarations never transfer to a new attempt, source or failure pair.
        if not (exact or (fact.get('kind') != 'none_declared' and (overlap or same_source or exposure))):
            continue
        prepared, cause = prepare_assistance(store, other['attempt_id'], fact, other.get('failed_attempt_id'))
        if (prepared != payload or row['source'] != 'gurukul.evidence' or
                row['session_id'] != other['session_id'] or row['subject_id'] != other['attempt_id'] or
                row['causation_id'] != cause or row['idempotency_key'] != 'assistance.recorded:' + fact['request_id']):
            raise ValueError('Assistance event bindings/provenance mismatch.')
        relevance, basis = occurrence_relevance(store, bound, other, fact, row['sequence'], exact)
        facts.append({'event_id': row['event_id'], 'payload_sha256': digest(payload),
                      'provenance': payload['provenance'], 'fact': fact,
                      'original_bindings': other, 'recorded_at': row['recorded_at'],
                      'relevance': relevance, 'timing_basis': basis,
                      'exact_pair': exact, 'same_source': same_source})
    return facts


def prepare_eligibility(store, evaluation_id, root):
    result, bound, checked, curriculum = verified_evaluation(store, evaluation_id, root)
    facts = relevant_assistance(store, bound)
    coverage, helped, unknown, direct_unknown, exposed = set(), set(), set(), set(), False
    supported = False
    for entry in facts:
        fact = entry['fact']
        supported |= entry['provenance']['status'] == 'supported_observation'
        steps = set(fact['steps']) & {'construction', 'repair'}
        relevance = entry['relevance']
        if relevance == 'exact_declaration':
            coverage |= steps
        elif relevance in {'after_completed_work', 'conceptual_practice_only'}:
            continue
        elif relevance == 'unresolved':
            affected = {'construction', 'repair'} if fact['kind'] == 'solution_exposure' else steps
            unknown |= affected
            if entry['exact_pair']:
                direct_unknown |= affected
        elif fact['kind'] == 'solution_exposure':
            exposed = True
        elif relevance == 'original_work' and fact['kind'] in {'hint', 'code_or_repair'}:
            helped |= steps
    conflicts = coverage & (helped | direct_unknown)
    reasons = []
    if result['outcome'] != 'CHECKS_PASS': reasons.append('D01 deterministic evidence is incomplete, failed, blocked or requires review.')
    if coverage != {'construction', 'repair'}: reasons.append('No complete exact-pair no-help declaration for construction and repair.')
    if helped: reasons.append('Relevant assistance recorded for: ' + ', '.join(sorted(helped)) + '.')
    if unknown: reasons.append('Assistance occurrence, scope or relevance remains unresolved for: ' + ', '.join(sorted(unknown)) + '.')
    if exposed: reasons.append('Solution exposure affects this work or predates its saved attempts; this slice cannot establish a fresh assessment variant.')
    if conflicts: reasons.append('Conflicting assistance declarations/observations remain in the audit.')
    ready = not reasons
    status = ('ASSISTED_OR_EXPOSED' if helped or exposed else
              'UNKNOWN' if unknown or coverage != {'construction', 'repair'} else 'DECLARED_ONLY')
    body = {'schema_version': 1, 'bindings': dict(bound, evaluation_id=evaluation_id,
                evaluation_sha256=digest(result)), 'curriculum': curriculum,
            'policy_version': POLICY_VERSION,
            'policy_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'checker_outcome': result['outcome'],
            'deterministic_checks': result['checks'], 'not_verified': result['not_verified'],
            'practice_evidence': 'retained', 'independence_status': status,
            'assistance_provenance': 'CONFLICTING' if conflicts else 'SUPPORTED_OBSERVATIONS' if supported else 'DECLARED_ONLY' if facts else 'UNKNOWN',
            'assistance': facts,
            'eligibility': 'READY_FOR_REVIEW' if ready else 'HOLD',
            'requires_review': True, 'reasons': reasons or ['Declaration-only readiness; independent performance still requires review.'],
            'outstanding_requirements': reasons + [c['detail'] for c in result['checks'] if c['status'] != 'PASS'] + [
                'Independent construction and debugging are not verified by this record.',
                'Read/closed-book, blank-file origin and deliberate-error claims remain unverifiable by deterministic checks.',
                'No C0 gate pass: applicable independent reconstruction/variation and critical-dimension review remain outstanding.'],
            'grants_verified_independence': False, 'grants_mastery': False,
            'changes_session_phase': False, 'advances_curriculum': False}
    body['decision_id'] = digest(body)
    return body, checked['event_id']


def eligibility(store, attempt_id, root, failed_attempt_id=None):
    """Read saved execution, reuse deterministic checks, persist current review eligibility."""
    result = checks.evaluate(store, attempt_id, root, failed_attempt_id)
    return store.record_eligibility(result['evaluation_id'], root)
