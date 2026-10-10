"""Tool-free Anthropic Messages adapter. Fixed host, no redirects/retries/SDK agents."""
import http.client
import json
import re
import ssl
from pathlib import Path
from typing import Protocol
from gurukul.hermes_relay import private_key
from gurukul.maharishi import SYSTEM, validate_directive
from gurukul.store import canonical, now
from gurukul.response_contract import ResponseContractError


class SupervisorProvider(Protocol):
    def decide(self, snapshot):
        """Return a directive proposal and provider usage metadata."""
        ...


class SupervisorAPIError(ValueError):
    def __init__(self,status):
        self.http_status=status
        super().__init__('Anthropic request failed; HTTP status recorded locally')


class AnthropicSupervisor:
    def __init__(self, config, key_path):
        if (config.get('provider')!='anthropic_direct' or config.get('automatic_retry') is not False
            or config.get('tools')!=[] or config.get('max_requests_per_episode')!=1
            or type(config.get('max_requests_per_session')) is not int or not 1<=config['max_requests_per_session']<=4
            or type(config.get('max_output_tokens')) is not int or not 128<=config['max_output_tokens']<=512
            or config.get('api_version')!='2023-06-01' or config.get('thinking') not in {'between_tools','adaptive','disabled'}):
            raise ValueError('Unsupported supervisory provider policy')
        if not re.fullmatch(r'claude-[a-z0-9-]{1,80}',config.get('model','')):raise ValueError('Invalid configured model ID')
        self.config=dict(config);self.key_path=Path(key_path);self.used=False;self.metadata={}

    def _request(self, method, path, body=None):
        if not (method=='POST' and path=='/v1/messages' or method=='GET' and re.fullmatch(r'/v1/models/claude-[a-z0-9-]{1,80}',path)):
            raise ValueError('Anthropic route denied')
        secret=private_key(self.key_path)
        wire=canonical(body).encode() if body is not None else None
        if wire and len(wire)>24000:raise ValueError('Supervisory request exceeds byte budget')
        connection=http.client.HTTPSConnection('api.anthropic.com',timeout=45,context=ssl.create_default_context())
        try:
            if method=='POST':self.metadata['generation_requests']=1
            connection.request(method,path,body=wire,headers={'x-api-key':secret,
                'anthropic-version':self.config['api_version'],'content-type':'application/json'})
            response=connection.getresponse();data=response.read(200001)
            request_id=response.getheader('request-id') or ''
            safe_id=request_id if re.fullmatch(r'[A-Za-z0-9_-]{1,120}',request_id) and secret not in request_id else None
            self.metadata.update(http_status=response.status,provider_request_id=safe_id)
            if response.status!=200:raise SupervisorAPIError(response.status)
            if len(data)>200000:raise ValueError('Anthropic response exceeds byte budget')
            if secret.encode() in data:raise ValueError('Credential echo refused')
            return json.loads(data)
        finally:connection.close()

    def verify_model(self):
        model=self._request('GET','/v1/models/'+self.config['model'])
        if model.get('id')!=self.config['model']:raise ValueError('Provider model resolution mismatch')
        if (type(model.get('max_input_tokens')) is not int or model['max_input_tokens']<24000
            or type(model.get('max_tokens')) is not int or model['max_tokens']<self.config['max_output_tokens']):
            raise ValueError('Model limits not verified')
        return {'model':model['id'],'max_input_tokens':model['max_input_tokens'],
                'max_tokens':model['max_tokens'],'capabilities':model.get('capabilities'),
                'verified_at':now(),'endpoint':'GET /v1/models/{model}','generation_calls':0}

    def decide(self, snapshot):
        if self.used:raise ValueError('One request per supervisor episode')
        if len(canonical(snapshot).encode())>20000:raise ValueError('Snapshot exceeds provider policy')
        self.used=True
        self.metadata={'provider':'anthropic_direct','requested_model':self.config['model'],
                       'started_at':now(),'request_parameters':{'max_tokens':self.config['max_output_tokens'],
                       'thinking':self.config['thinking'],'tools':[]},'actual_cost_usd':None,'generation_requests':0}
        body={'model':self.config['model'],'max_tokens':self.config['max_output_tokens'],
              'thinking':{'type':self.config['thinking']},'system':SYSTEM,
              'messages':[{'role':'user','content':canonical(snapshot)}],'stream':False}
        response=self._request('POST','/v1/messages',body)
        self.metadata.update(finished_at=now(),resolved_model=response.get('model'),usage=response.get('usage'),
                             stop_reason=response.get('stop_reason'))
        if response.get('model')!=self.config['model'] or response.get('stop_reason')!='end_turn':
            raise ValueError('Incomplete/mismatched supervisor response')
        blocks=response.get('content')
        if not isinstance(blocks,list) or any(x.get('type') not in {'text','thinking','redacted_thinking'} for x in blocks):
            raise ValueError('Supervisor tools/unknown response blocks denied')
        texts=[x['text'] for x in blocks if x.get('type')=='text']
        if len(texts)!=1 or len(texts[0])>4000:raise ValueError('Expected one bounded directive')
        try:
            proposal=json.loads(texts[0])
        except json.JSONDecodeError:
            raise ResponseContractError('Expected a JSON supervisory directive',
                                        stage='maharishi.directive.json',code='invalid_json') from None
        directive=validate_directive(proposal)
        usage=response.get('usage') or {};price=self.config.get('pricing',{})
        tokens=[usage.get('input_tokens'),usage.get('output_tokens')]
        if (price.get('model')==self.config['model'] and all(type(x) is int and x>=0 for x in tokens)
            and not usage.get('cache_read_input_tokens') and not usage.get('cache_creation_input_tokens')):
            self.metadata.update(estimated_cost_usd=(tokens[0]*price['input_usd_per_million']+tokens[1]*price['output_usd_per_million'])/1000000,
                                 cost_status='estimated_from_provider_usage',pricing_source=price['source'],pricing_date=price['checked_at'])
        else:self.metadata.update(estimated_cost_usd=None,cost_status='unknown')
        return directive,dict(self.metadata)


def configured_provider(runtime):
    """Dedicated explicit setup only; never inspect a personal Claude profile/env."""
    import os
    import stat
    fd=os.open(str(Path(runtime)/'maharishi-settings.json'),os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd) as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:
            raise ValueError('Supervisor settings must be an owner-only regular file')
        text=stream.read(64001)
    if len(text)>64000:raise ValueError('Supervisor settings too large')
    settings=json.loads(text);proof=settings['account_verification'];config=settings['config']
    if proof.get('model')!=config.get('model') or proof.get('generation_calls')!=0:
        raise ValueError('Dedicated supervisor model not account-verified')
    adapter=AnthropicSupervisor(config,settings['key_file']);private_key(adapter.key_path)
    adapter.key_path=adapter.key_path.resolve()
    return adapter
