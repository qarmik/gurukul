"""Local sessions and bounded execution; no automatic capability assessment."""
import argparse
import json
import sys
from pathlib import Path
from .store import Store
from .submissions import submit, inspect
from .checks import evaluate
from .evidence import eligibility


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='Project root containing content/ and var/')
    parser.add_argument('command', choices=('start', 'resume', 'events', 'run', 'result', 'check', 'assistance', 'eligibility'))
    parser.add_argument('target', nargs='?', help='.py file for run; attempt UUID for result')
    parser.add_argument('--timeout', type=float, default=5.0)
    parser.add_argument('--output-limit', type=int, default=65536)
    parser.add_argument('--failed-attempt', help='Earlier unquoted-text failure UUID for D01 check')
    parser.add_argument('--assistance-file', type=Path, help='Explicit structured assistance JSON; only for assistance')
    args = parser.parse_args()
    if args.command in ('run', 'result', 'check', 'assistance', 'eligibility') and not args.target:
        parser.error('run/result/check/assistance/eligibility requires a target')
    if args.failed_attempt and args.command not in ('check', 'assistance', 'eligibility'):
        parser.error('--failed-attempt is only valid with check, assistance or eligibility')
    if bool(args.assistance_file) != (args.command == 'assistance'):
        parser.error('--assistance-file is required only with assistance')
    store = Store(args.root / 'var' / 'gurukul.sqlite3')
    try:
        if args.command == 'start':
            content = json.loads((args.root / 'content/c0_b01/d01.json').read_text(encoding='utf-8'))
            store.start(content)
            result = store.resume()
        elif args.command == 'resume':
            result = store.resume()
        elif args.command == 'run':
            result = submit(store, args.target, args.timeout, args.output_limit)
        elif args.command == 'result':
            result = inspect(store, args.target)
        elif args.command == 'check':
            result = evaluate(store, args.target, args.root, args.failed_attempt)
        elif args.command == 'assistance':
            path = args.assistance_file
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 16384:
                raise ValueError('Assistance file must be a regular JSON file of at most 16 KiB.')
            declaration = json.loads(path.read_text(encoding='utf-8'))
            result = store.record_assistance(args.target, declaration, args.failed_attempt)
        elif args.command == 'eligibility':
            result = eligibility(store, args.target, args.root, args.failed_attempt)
        else:
            result = store.events()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
    finally:
        store.close()
