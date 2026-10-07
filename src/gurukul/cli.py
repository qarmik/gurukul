"""Local sessions and bounded execution; no automatic capability assessment."""
import argparse
import json
import sys
from pathlib import Path
from .store import Store
from .submissions import submit, inspect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='Project root containing content/ and var/')
    parser.add_argument('command', choices=('start', 'resume', 'events', 'run', 'result'))
    parser.add_argument('target', nargs='?', help='.py file for run; attempt UUID for result')
    parser.add_argument('--timeout', type=float, default=5.0)
    parser.add_argument('--output-limit', type=int, default=65536)
    args = parser.parse_args()
    if args.command in ('run', 'result') and not args.target:
        parser.error('run/result requires a target')
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
        else:
            result = store.events()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
    finally:
        store.close()
