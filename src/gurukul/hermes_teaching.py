"""Gurukul-owned source admission, disclosure checks and evidence persistence."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from uuid import uuid4

from gurukul.store import canonical, now

from gurukul.pedagogy import SYSTEM_PROMPT, build_prompt, orientation, turn_context, validate_response
from gurukul.response_contract import ResponseContractError
from gurukul.teaching_output import evaluate_output


_RECEIPT_RULE_CODES = {
    ('guru.response.schema', 'key_mismatch'): 'reply_schema_mismatch',
    ('guru.pedagogy.schema', 'key_mismatch'): 'reply_schema_mismatch',
    ('guru.layout.schema', 'key_mismatch'): 'reply_schema_mismatch',
    ('guru.parent_authority', 'invalid_parent_context'): 'reply_authority_failure',
    ('guru.parent_authority', 'conflicting_current_location'): 'reply_authority_failure',
    ('guru.parent_authority', 'conflicting_curriculum_version'): 'reply_authority_failure',
    ('guru.example', 'assignment_limit'): 'example_assignment_limit',
}


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def source_input(path, manifest, config, exercise):
    entry = manifest['sources'][config['source_id']]
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != entry['sha256'] or digest != config['source_sha256']:
        raise ValueError('Approved D01 source SHA-256 mismatch')
    if entry['access'] != 'approved_local_only' or config['source_section'] != exercise['id']:
        raise ValueError('Source policy/section mismatch')
    if not any(r['source_id'] == config['source_id'] for r in exercise['source']['references']):
        raise ValueError('Exercise does not approve this source')
    html = raw.decode('utf-8')
    concepts = re.search(r'<h2>Concepts to own</h2>\s*<div class="card">(.*?)</div>', html, re.S)
    day = re.search(r'<section class="day">(?:(?!</section>).)*?C0-B01-D01.*?</section>', html, re.S)
    if not concepts or not day:
        raise ValueError('Approved source sections missing')
    parser = PlainText()
    parser.feed(concepts.group(1) + '\n' + day.group())
    excerpt = ' '.join(' '.join(parser.parts).split())
    provenance = {'source_id': config['source_id'], 'source_sha256': digest,
                  'sections': ['Concepts to own', config['source_section']],
                  'excerpt_sha256': hashlib.sha256(excerpt.encode()).hexdigest(),
                  'manifest_sha256': hashlib.sha256(canonical(manifest).encode()).hexdigest(),
                  'exercise_sha256': hashlib.sha256(canonical(exercise).encode()).hexdigest()}
    prompt = ('Teach only C0-B01-D01: literal versus variable, quoted text, and reassignment. '
              'Other topics mentioned in the local material are out of scope. '
              'I have not supplied an answer yet; ask a diagnostic question. '
              'Return the requested JSON, with no exercise solution.\n\n'
              'APPROVED LOCAL MATERIAL (' + config['source_id'] + '):\n' + excerpt)
    return prompt, excerpt, provenance



def prepare_turn(root, exercise, excerpt, message, previous=None, history=()):
    curriculum, proof = orientation(root, exercise)
    context = turn_context(curriculum, previous, message, history)
    return context, build_prompt(context, excerpt), proof


class TeachingTurnError(Exception):
    """A bounded learner-facing failure, with no raw provider details."""


class TeachingPipeline:
    """Validate one D01 turn with optional, parent-admitted practice context."""

    def __init__(self, source, transport, *, reply_observer=None):
        self.source = Path(source)
        self.transport = transport
        self.reply_observer = reply_observer

    def _report_reply(self, code, *, validation_error=None):
        if self.reply_observer is not None:
            rule_code = None
            if isinstance(validation_error, ResponseContractError):
                diagnostics = validation_error.diagnostics
                rule_code = _RECEIPT_RULE_CODES.get(
                    (diagnostics['validation_stage'], diagnostics['failure_code']))
            self.reply_observer(code, validation_rule_code=rule_code)

    def reply(self, root, lease, question, *, prior=None):
        lease.check()
        exercise = json.loads((root / 'content/c0_b01/d01.json').read_text())
        if hashlib.sha256(canonical(exercise).encode()).hexdigest() != lease.exercise_sha256:
            raise ValueError('Teaching exercise differs from canonical learner authority.')
        manifest = json.loads((root / 'content/sources.json').read_text())
        config = json.loads((root / 'config/hermes-live.json').read_text())
        _, excerpt, _ = source_input(self.source, manifest, config, exercise)
        previous = history = None
        if prior is not None:
            teaching = prior['teaching']
            previous = {'teaching': teaching}
            history = ({
                'learner_message': prior['question'],
                'explanation': teaching['explanation'],
                'question': teaching['diagnostic_question'],
                'miniature_example': teaching['miniature_example'],
                'pedagogy': teaching['pedagogy'],
            },)
        context, prompt, _ = prepare_turn(root, exercise, excerpt, question, previous, history or ())
        lease.check()
        try:
            raw = self.transport(system_prompt=SYSTEM_PROMPT, prompt=prompt)
        except TeachingTurnError:
            raise
        except Exception as exc:
            raise TeachingTurnError('Guru could not answer right now. Please try again.') from exc
        lease.check()
        try:
            proposal = json.loads(raw)
        except (ValueError, TypeError, RecursionError) as exc:
            self._report_reply('invalid_reply_json')
            raise TeachingTurnError('Guru’s reply could not be validated.') from exc
        try:
            admission, display = evaluate_output(proposal, context)
        except (ValueError, TypeError, SyntaxError, RecursionError) as exc:
            self._report_reply('reply_validation_failed', validation_error=exc)
            raise TeachingTurnError('Guru’s reply could not be validated.') from exc
        if admission['conversation_status'] != 'CONTINUE':
            self._report_reply('reply_withheld_after_validation')
            raise TeachingTurnError('Guru’s reply could not be validated.')
        reply = '\n\n'.join(display[key] for key in
                            ('explanation', 'miniature_example', 'diagnostic_question') if display[key])
        # Carry only what was admitted for display and the metadata needed by turn_context.
        teaching = {key: display[key] for key in ('explanation', 'miniature_example', 'diagnostic_question')}
        teaching['pedagogy'] = {
            'concept': display['pedagogy']['concept'],
            'strategy': display['pedagogy']['strategy'],
            'judgment': admission['judgment'],
        }
        self._report_reply('reply_admitted')
        return {'question': question, 'reply': reply, 'teaching': teaching}

def teaching_response(text, context=None):
    result = json.loads(text)
    if isinstance(result, dict) and 'pedagogy' in result:
        return validate_response(result, context)
    if not isinstance(result, dict) or set(result) != {'explanation', 'diagnostic_question'}:
        raise ValueError('Teaching response schema mismatch')
    for value in result.values():
        if not isinstance(value, str) or not value.strip() or len(value) > 2500:
            raise ValueError('Teaching text missing/too long')
        if ('```' in value or re.search(r'\bprint\s*\(', value) or
                re.search(r'\b[A-Za-z_]\w*\s*=(?!=)', value)):
            raise ValueError('Code disclosure refused for this integration turn')
    return result


def record_result(store, call_id, session_id, result):
    """Parent-only append, preserving the generic ledger; no mastery/phase changes."""
    with store.db:
        store.db.execute('BEGIN IMMEDIATE')
        session = store.db.execute('SELECT phase,status FROM sessions WHERE id=?', (session_id,)).fetchone()
        if not session or session['status'] != 'active' or session['phase'] not in ('teaching', 'remediation'):
            raise ValueError('Tutoring is not admitted in this session phase')
        timestamp = now()
        if result.get('supervision'):
            audit=result['supervision']
            event_type='supervision.decision_recorded' if audit.get('status')!='NOT_INVOKED' else 'supervision.observed'
            store.db.execute('''INSERT INTO events(event_id,event_type,schema_version,
                occurred_at,recorded_at,source,subject_id,session_id,correlation_id,
                causation_id,idempotency_key,privacy_class,payload_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (str(uuid4()),event_type,1,timestamp,timestamp,'gurukul.maharishi_adapter',call_id,
                 session_id,result.get('root_call_id',call_id),(result.get('continuation') or {}).get('parent_event_id'),
                 event_type+':'+call_id,'personal_learning',canonical(audit)))
        store.db.execute('''INSERT INTO events(event_id,event_type,schema_version,
            occurred_at,recorded_at,source,subject_id,session_id,correlation_id,
            causation_id,idempotency_key,privacy_class,payload_json)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (str(uuid4()), 'teaching.integration_finished', 1, timestamp, timestamp,
             'gurukul.hermes_adapter', call_id, session_id, result.get('root_call_id', call_id),
             (result.get('continuation') or {}).get('parent_event_id'),
             'teaching.integration_finished:' + call_id, 'personal_learning', canonical(result)))
