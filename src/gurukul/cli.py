"""GURU-001: start/resume only; no simulated tutoring or execution."""
import argparse
import json
import sys
from pathlib import Path
from .store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='Project root containing content/ and var/')
    parser.add_argument('command', choices=('start', 'resume', 'events'))
    args = parser.parse_args()
    store = Store(args.root / 'var' / 'gurukul.sqlite3')
    try:
        if args.command == 'start':
            content = json.loads((args.root / 'content/c0_b01/d01.json').read_text(encoding='utf-8'))
            store.start(content)
            result = store.resume()
        elif args.command == 'resume':
            result = store.resume()
        else:
            result = store.events()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
    finally:
        store.close()
