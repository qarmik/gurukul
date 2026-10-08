"""One-turn inference relay. Hermes owns the agent call; this only polices HTTP.

The provider secret never enters the worker. No general proxy/CONNECT, arbitrary
URL, alternate model, native tools, provider fallback, or automatic retry exists.
"""
import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import ssl
import stat
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from gurukul.store import now

REQUEST_LIMIT = 120000
RESPONSE_LIMIT = 256000


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


class Relay:
    def __init__(self, config, key_path, prompt):
        self.config, self.key_path, self.prompt = config, Path(key_path), prompt
        self.token = secrets.token_urlsafe(32)
        self.calls = []
        self.rejections = []
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
                owner.rejections.append(reason)
                self.reply(403, {'error': {'message': 'Gurukul relay: ' + reason,
                                         'type': 'permission_error', 'code': 'relay_denied'}})

            def do_GET(self):
                if self.path == '/health' and self.headers.get('Authorization') == 'Bearer ' + owner.token:
                    self.reply(200, {'status': 'ready', 'inference_calls': len(owner.calls)})
                else:
                    self.reject('route denied')

            def do_POST(self):
                if self.headers.get('Authorization') != 'Bearer ' + owner.token:
                    return self.reject('authentication failed')
                if self.path == '/ready':
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
                except (ValueError, OSError):
                    return self.reject('request policy mismatch')
                call = {'started_at': now(), 'requested_model': owner.config['model'],
                        'provider': owner.config['provider'], 'request_sha256': hashlib.sha256(raw).hexdigest(),
                        'tool_count': 0, 'estimated_cost': None, 'actual_cost': None,
                        'currency': 'USD', 'cost_status': 'not_available', 'pricing_source': None,
                        'pricing_version': None, 'escalation': False, 'escalation_reason': None}
                owner.calls.append(call)  # Reserve before network I/O, even if it fails.
                try:
                    status, response, request_id = owner.forward(body)
                    call.update(http_status=status, provider_request_id=request_id,
                                resolved_model=response.get('model'), usage=response.get('usage'),
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
                        self.reply(200, response)
                    else:
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

    def forward(self, body):
        # Transport forwarding only: the genuine Hermes client constructed this request.
        # HTTPSConnection does not consult ambient proxy env or follow redirects.
        secret = private_key(self.key_path)
        connection = http.client.HTTPSConnection('api.openai.com', timeout=60,
                                                  context=ssl.create_default_context())
        try:
            connection.request('POST', '/v1/chat/completions', json.dumps(body).encode(),
                               {'Authorization': 'Bearer ' + secret, 'Content-Type': 'application/json'})
            reply = connection.getresponse()
            data = reply.read(RESPONSE_LIMIT + 1)
            if len(data) > RESPONSE_LIMIT:
                raise ValueError('Provider response too large')
            if reply.status != 200:
                return reply.status, {}, reply.getheader('x-request-id')
            return reply.status, json.loads(data), reply.getheader('x-request-id')
        finally:
            connection.close()

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
