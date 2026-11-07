"""One-turn inference relay. Hermes owns the agent call; this only polices HTTP.

The provider secret never enters the worker. No general proxy/CONNECT, arbitrary
URL, alternate model, native tools, provider fallback, or automatic retry exists.
"""
import hashlib
import http.client
import json
import os
import re
from pathlib import Path
import secrets
import ssl
import stat
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from gurukul.store import now

REQUEST_LIMIT = 120000
RESPONSE_LIMIT = 256000
# Exact GET waterfall in pinned agent/model_metadata.py:detect_local_server_type.
# These remain HTTP 403, never forwarded and never presented as model metadata.
STARTUP_PROBE_PATHS = frozenset({'/api/v1/models', '/api/tags', '/v1/props', '/props', '/version'})

REJECTION_CODES = {
    'route denied': 'route_denied',
    'authentication failed': 'authentication_failed',
    'prior policy violation prevents turn admission': 'prior_policy_violation',
    'route or turn not authorized': 'route_or_turn_not_authorized',
    'one-request budget exhausted': 'request_budget_exhausted',
    'request policy mismatch': 'request_policy_mismatch',
    'CONNECT denied': 'connect_denied',
}


def provider_error(data, secret):
    """Retain a bounded diagnostic, never the raw error body or credential echo."""
    try:
        body = json.loads(data)
    except ValueError:
        return {'type': 'unparseable_provider_error'}
    return _provider_error_fields(body, secret)


def _provider_error_fields(body, secret):
    error = body.get('error') if isinstance(body, dict) else None
    if not isinstance(error, dict):
        return {'type': 'unparseable_provider_error'}
    result = {}
    for name in ('type', 'code', 'param', 'message'):
        value = error.get(name)
        if value is None:
            result[name] = None
        elif isinstance(value, str):
            # Credential-bearing diagnostics are unnecessary for parameter debugging.
            if (secret in value or re.search(r'(?i)sk-|api.?key|authorization|bearer|credential', value)):
                result[name] = '[credential-related diagnostic omitted]'
            else:
                result[name] = ' '.join(value.split())[:600 if name == 'message' else 120]
        else:
            result[name] = '[non-text diagnostic omitted]'
    return result


def private_key(path):
    fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('Credential must be an owner-only regular file')
        value = stream.read(4097).strip()
    if not value or len(value) > 4096 or any(c.isspace() for c in value):
        raise ValueError('Invalid local credential format')
    return value


def validate_request(body, model, prompt, max_tokens):
    if not isinstance(body, dict):
        raise ValueError('Request must be an object')
    permitted = {'model', 'messages', 'stream', 'max_tokens', 'max_completion_tokens',
                 'temperature', 'top_p', 'reasoning_effort', 'response_format',
                 'tools', 'tool_choice', 'parallel_tool_calls', 'store', 'n',
                 'prompt_cache_key', 'prompt_cache_retention'}
    if set(body) - permitted:
        raise ValueError('Unexpected request fields')
    if body.get('model') != model or body.get('stream', False) is not False:
        raise ValueError('Model switch or streaming denied')
    if body.get('tools') not in (None, []) or body.get('tool_choice') not in (None, 'none'):
        raise ValueError('Tools denied')
    if body.get('parallel_tool_calls') not in (None, False) or body.get('store') not in (None, False):
        raise ValueError('Parallel tools or provider storage denied')
    if body.get('n', 1) != 1:
        raise ValueError('Multiple completions denied')
    limits = [body[k] for k in ('max_tokens', 'max_completion_tokens') if body.get(k) is not None]
    if len(limits) != 1 or type(limits[0]) is not int or not 1 <= limits[0] <= max_tokens:
        raise ValueError('Missing or excessive output limit')
    messages = body.get('messages')
    if not isinstance(messages, list) or not 1 <= len(messages) <= 8:
        raise ValueError('Invalid messages')
    user_text = []
    for msg in messages:
        if not isinstance(msg, dict) or set(msg) - {'role', 'content'}:
            raise ValueError('Unexpected message fields')
        if msg.get('role') not in ('system', 'developer', 'user'):
            raise ValueError('Only the fresh teaching prompt is allowed')
        content = msg.get('content')
        if isinstance(content, list):
            if any(not isinstance(p, dict) or set(p) != {'type', 'text'} or
                   p['type'] != 'text' or not isinstance(p['text'], str) for p in content):
                raise ValueError('Only local text input is allowed')
            content = ''.join(p['text'] for p in content)
        if not isinstance(content, str):
            raise ValueError('Only text messages are allowed')
        if msg['role'] == 'user':
            user_text.append(content)
    if user_text != [prompt]:
        raise ValueError('Teaching input differs from approved local input')
    return body


def upstream_request(body, model, prompt, max_tokens):
    """Translate the pinned Hermes token field for this OpenAI Chat route."""
    validate_request(body, model, prompt, max_tokens)
    forwarded = dict(body)
    legacy_limit = forwarded.pop('max_tokens', None)
    if legacy_limit is not None:
        forwarded['max_completion_tokens'] = legacy_limit
    validate_request(forwarded, model, prompt, max_tokens)
    return forwarded


class Relay:
    def __init__(self, config, key_path, prompt, *, system_prompt=None):
        self.config, self.key_path, self.prompt = config, Path(key_path), prompt
        self.token = secrets.token_urlsafe(32)
        self.calls = []
        self.rejections = []
        self.blocked_startup_probes = []
        self.ready = False
        self.response = None
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass  # Never print headers, secrets, or learner content.

            def setup(self):
                super().setup()
                self.connection.settimeout(15)

            def reply(self, status, body):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def reject(self, reason):
                owner.rejections.append({'reason': reason, 'reason_code': REJECTION_CODES[reason],
                                         'method': self.command,
                                         'path': self.path.split('?', 1)[0][:160]})
                self.reply(403, {'error': {'message': 'Gurukul relay: ' + reason,
                                         'type': 'permission_error', 'code': 'relay_denied'}})

            def do_GET(self):
                if (not owner.ready and self.path in STARTUP_PROBE_PATHS and
                        self.headers.get('Authorization') == 'Bearer ' + owner.token):
                    owner.blocked_startup_probes.append({'method': 'GET', 'path': self.path,
                                                        'status': 403, 'forwarded': False})
                    return self.reply(403, {'error': {'message': 'Local backend discovery is disabled',
                                                     'type': 'permission_error', 'code': 'probe_denied'}})
                if self.path == '/health' and self.headers.get('Authorization') == 'Bearer ' + owner.token:
                    self.reply(200, {'status': 'ready', 'inference_calls': len(owner.calls)})
                else:
                    self.reject('route denied')

            def do_POST(self):
                if self.headers.get('Authorization') != 'Bearer ' + owner.token:
                    return self.reject('authentication failed')
                if self.path == '/ready':
                    if owner.rejections:
                        return self.reject('prior policy violation prevents turn admission')
                    owner.ready = True
                    return self.reply(200, {'status': 'ready'})
                if self.path != '/v1/chat/completions' or not owner.ready:
                    return self.reject('route or turn not authorized')
                if owner.calls:
                    return self.reject('one-request budget exhausted')
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= REQUEST_LIMIT or self.headers.get('Transfer-Encoding'):
                        raise ValueError('Request size or transfer encoding denied')
                    raw = self.rfile.read(size)
                    if len(raw) != size:
                        raise ValueError('Incomplete request')
                    body = validate_request(json.loads(raw), owner.config['model'], owner.prompt,
                                            owner.config['max_output_tokens'])
                    forwarded = upstream_request(body, owner.config['model'], owner.prompt,
                                                 owner.config['max_output_tokens'])
                    if system_prompt is not None:
                        # Rebuild the workspace request from parent-approved text and
                        # fixed controls; worker-added system text/metadata never leaves.
                        forwarded = {
                            'model': owner.config['model'],
                            'messages': [{'role': 'system', 'content': system_prompt},
                                         {'role': 'user', 'content': owner.prompt}],
                            'max_completion_tokens': forwarded['max_completion_tokens'],
                            'reasoning_effort': 'none',
                            'response_format': {'type': 'json_object'},
                            'stream': False, 'store': False,
                        }
                except (ValueError, OSError):
                    return self.reject('request policy mismatch')
                call = {'started_at': now(), 'requested_model': owner.config['model'],
                        'provider': owner.config['provider'], 'request_sha256': hashlib.sha256(raw).hexdigest(),
                        'tool_count': 0, 'estimated_cost': None, 'actual_cost': None,
                        'currency': 'USD', 'cost_status': 'not_available', 'pricing_source': None,
                        'pricing_version': None, 'escalation': False, 'escalation_reason': None}
                call['request_fields'] = sorted(body)
                call['request_parameters'] = {k: body[k] for k in
                    ('model', 'max_tokens', 'max_completion_tokens', 'reasoning_effort', 'stream', 'store') if k in body}
                call['upstream_request_parameters'] = {k: forwarded[k] for k in
                    ('model', 'max_completion_tokens', 'reasoning_effort', 'stream', 'store') if k in forwarded}
                call['upstream_request_sha256'] = hashlib.sha256(json.dumps(forwarded).encode()).hexdigest()
                call['adapter_transform'] = 'max_tokens_to_max_completion_tokens' if body.get('max_tokens') is not None else 'none'
                owner.calls.append(call)  # Reserve before network I/O, even if it fails.
                call['upstream_stage'] = 'before_forward'
                try:
                    status, response = owner.forward(forwarded, call=call)
                    if status == 200:
                        call['upstream_stage'] = 'provider_response_validation'
                    call.update(resolved_model=response.get('model'), usage=response.get('usage'),
                                outcome='completed' if status == 200 else 'provider_rejected')
                    usage = response.get('usage') or {}
                    call.update(input_tokens=usage.get('prompt_tokens'), output_tokens=usage.get('completion_tokens'),
                                cached_input_tokens=(usage.get('prompt_tokens_details') or {}).get('cached_tokens'),
                                reasoning_tokens=(usage.get('completion_tokens_details') or {}).get('reasoning_tokens'),
                                usage_source='provider_response' if usage else 'unavailable')
                    if status == 200:
                        resolved = response.get('model')
                        if not isinstance(resolved, str) or not (resolved == owner.config['model'] or
                                resolved.startswith(owner.config['model'] + '-')):
                            raise ValueError('Provider returned an unexpected model')
                        choices = response.get('choices', [])
                        if len(choices) != 1 or choices[0].get('message', {}).get('tool_calls') or choices[0].get('message', {}).get('function_call'):
                            raise ValueError('Provider returned tools or unexpected choices')
                        owner.response = response
                        call['upstream_stage'] = 'completed'
                        self.reply(200, response)
                    else:
                        call['provider_error'] = response.get('error')
                        self.reply(status, {'error': {'message': 'OpenAI request rejected; inspect local HTTP status.',
                                                     'type': 'provider_error', 'code': 'provider_rejected'}})
                except Exception as exc:
                    call.update(outcome='blocked', error_type=type(exc).__name__)
                    self.reply(502, {'error': {'message': 'Gurukul provider connection blocked',
                                             'type': 'provider_error', 'code': 'relay_blocked'}})
                finally:
                    call['finished_at'] = now()

            def do_CONNECT(self):
                self.reject('CONNECT denied')

        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def forward(self, body, *, call):
        # Transport forwarding only: the genuine Hermes client constructed this request.
        # HTTPSConnection does not consult ambient proxy env or follow redirects.
        call['upstream_stage'] = 'local_credential'
        secret = private_key(self.key_path)
        call['upstream_stage'] = 'connection_or_send'
        connection = http.client.HTTPSConnection('api.openai.com', timeout=60,
                                                  context=ssl.create_default_context())
        try:
            connection.request('POST', '/v1/chat/completions', json.dumps(body).encode(),
                               {'Authorization': 'Bearer ' + secret, 'Content-Type': 'application/json'})
            call['upstream_stage'] = 'response_headers'
            reply = connection.getresponse()
            call.update(http_status=reply.status, provider_http_error=400 <= reply.status <= 599)
            request_id = reply.getheader('x-request-id')
            if (isinstance(request_id, str) and re.fullmatch(r'req_[A-Za-z0-9_-]{1,128}', request_id)
                    and secret not in request_id):
                call['provider_request_id'] = request_id
            call['upstream_stage'] = 'response_body_read'
            data = reply.read(RESPONSE_LIMIT + 1)
            if len(data) > RESPONSE_LIMIT:
                raise ValueError('Provider response too large')
            call['upstream_stage'] = 'response_body_decode'
            if reply.status != 200:
                try:
                    body = json.loads(data)
                except ValueError:
                    return reply.status, {'error': {'type': 'unparseable_provider_error'}}
                call['upstream_stage'] = ('provider_http_error' if call['provider_http_error']
                                          else 'unexpected_http_status')
                return reply.status, {'error': _provider_error_fields(body, secret)}
            return reply.status, json.loads(data)
        finally:
            connection.close()

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
