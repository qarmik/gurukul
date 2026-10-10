#!/usr/bin/env python3
"""Dedicated local key entry and account model check; no generation or secret output."""
import argparse
import getpass
import json
import os
import stat
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from gurukul.anthropic_supervisor import AnthropicSupervisor
from gurukul.hermes_relay import private_key


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root',type=Path,default=Path.home()/'GurukulRuntime')
    parser.add_argument('--model',required=True,help='Reviewed Anthropic model ID')
    parser.add_argument('--key-file',type=Path,help='Explicit dedicated key file; otherwise enter privately')
    parser.add_argument('--thinking',choices=['between_tools','adaptive','disabled'],default='between_tools')
    args=parser.parse_args();os.umask(0o077)
    config=json.loads((ROOT/'config/maharishi.json').read_text());config.update(model=args.model,thinking=args.thinking)
    runtime=args.runtime_root.resolve()
    if runtime==ROOT or ROOT in runtime.parents:raise ValueError('Dedicated runtime must be outside the Git checkout')
    credentials=runtime/'credentials';credentials.mkdir(parents=True,exist_ok=True)
    key_path=args.key_file.resolve() if args.key_file else credentials/'anthropic-maharishi-api-key'
    if key_path==ROOT or ROOT in key_path.parents:raise ValueError('Keep dedicated credentials outside the Git checkout')
    if args.key_file:private_key(args.key_file) # Check original path too, rejecting symlinks.
    elif not key_path.exists():
        if not sys.stdin.isatty():raise ValueError('Use a real terminal for private key entry')
        secret=getpass.getpass('Dedicated Gurukul Anthropic API key (hidden; never paste in chat): ')
        if not secret or len(secret)>4096 or any(c.isspace() for c in secret):raise ValueError('Invalid key format')
        fd=os.open(str(key_path),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as stream:stream.write(secret+'\n')
        del secret
    adapter=AnthropicSupervisor(config,key_path);proof=adapter.verify_model()
    settings={'config':config,'key_file':str(key_path),'account_verification':proof}
    settings_path=runtime/'maharishi-settings.json'
    fd=os.open(str(settings_path),os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:
            raise ValueError('Supervisor settings must be an owner-only regular file')
        stream.seek(0);stream.truncate();stream.write(json.dumps(settings,indent=2)+'\n')
    print(json.dumps({'setup_status':'PASS','model':proof['model'],'max_input_tokens':proof['max_input_tokens'],
        'max_tokens':proof['max_tokens'],'generation_calls':0,'secret_printed':False},indent=2))

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('SETUP BLOCKED:',type(exc).__name__,'HTTP status:',getattr(exc,'http_status',None),
              'No generation call made. Check dedicated key, model and API access locally.')
        raise SystemExit(1)
