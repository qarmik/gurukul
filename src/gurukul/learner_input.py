"""Parent-owned input and references. Model proposals never author learner text."""
import hashlib
import re
from gurukul.terminal_text import normalize_input


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def capture(raw):
    normalized, hygiene = normalize_input(raw)
    return {'schema_version': 1, 'raw_input': raw, 'raw_sha256': digest(raw),
            'normalized_input': normalized, 'normalized_sha256': digest(normalized),
            'normalization_policy': hygiene['policy']}


def verify(record):
    if record != capture(record['raw_input']):
        raise ValueError('Authoritative learner input changed or corrupted')
    return record['normalized_input']


def references(message):
    """Bounded parent-generated code-point ranges; whole input supports code answers."""
    ranges = [(0, len(message))] if message else []
    for match in re.finditer(r'[^\n!?;]+(?:[!?;]|$)', message):
        if match.span() not in ranges:
            ranges.append(match.span())
        if len(ranges) >= 64:
            break
    return [{'ref': 's'+str(i), 'start': start, 'end': end, 'text': message[start:end]}
            for i, (start, end) in enumerate(ranges)]


def resolve(value, message):
    """Legacy exact quotes are verified then sliced; new proposals use references."""
    if value == '':
        return '', None
    if isinstance(value, dict) and set(value) == {'ref'}:
        item = next((x for x in references(message) if x['ref'] == value['ref']), None)
        if item is None:
            raise ValueError('Unknown learner input reference')
        start, end = item['start'], item['end']
    elif isinstance(value, dict) and set(value) == {'start', 'end'}:
        start, end = value['start'], value['end']
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(message):
            raise ValueError('Invalid learner input offsets')
    elif isinstance(value, str) and value in message:
        start = message.index(value)
        end = start + len(value)
    else:
        raise ValueError('Model span is not derivable from learner input')
    return message[start:end], {'start': start, 'end': end, 'input_sha256': digest(message)}


def verify_admission(admission, message):
    if admission.get('learner_input_sha256') != digest(message):
        raise ValueError('Admission is bound to different learner input')
    spans=admission.get('learner_verified_spans', {})
    for field,binding in spans.items():
        text,expected=resolve({'start':binding['start'],'end':binding['end']},message)
        if binding != dict(expected,text=text) or admission['intents'].get(field) != text:
            raise ValueError('Verified learner span changed or corrupted')
    for field,value in admission.get('intents', {}).items():
        if field.endswith('_span') and value and field not in spans:
            raise ValueError('Learner span lacks a verified source binding')
