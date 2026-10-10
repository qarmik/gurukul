"""Bounded structural diagnostics; never include provider text or field values."""
import hashlib
import re


def safe_key(value):
    if isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9_]{0,63}', value):
        return value
    raw = value if isinstance(value, str) else type(value).__name__
    return '<key-sha256:' + hashlib.sha256(raw.encode()).hexdigest() + '>'


class ResponseContractError(ValueError):
    def __init__(self, message, *, stage, code, expected=None, actual=None, optional=()):
        super().__init__(message)
        self.diagnostics = {'validation_stage': stage, 'failure_code': code}
        if expected is not None and actual is not None:
            expected, actual, optional = set(expected), set(actual), set(optional)
            for name, values in [('expected_keys', expected), ('actual_keys', actual),
                                 ('missing_keys', expected - actual - optional),
                                 ('extra_keys', actual - expected)]:
                self.diagnostics[name] = sorted(safe_key(x) for x in values)[:64]
            if optional:
                self.diagnostics['optional_keys'] = sorted(safe_key(x) for x in optional)[:64]
                self.diagnostics['required_keys'] = sorted(safe_key(x) for x in expected - optional)[:64]


def schema_error(message, stage, expected, value, *, optional=()):
    return ResponseContractError(message, stage=stage, code='key_mismatch',
                                 expected=expected,
                                 actual=value if isinstance(value, dict) else (), optional=optional)
