"""Local build receipts: content inputs AND outputs must match before reuse."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys

IGNORED = {'bin', 'obj', '__pycache__', '.git', '.pytest_cache'}


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def files_digest(paths):
    files = {}
    for value in paths:
        path = Path(value).resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        candidates = [path] if path.is_file() else path.rglob('*')
        for item in candidates:
            if item.is_file() and not any(part in IGNORED for part in item.relative_to(path.parent).parts):
                files[str(item)] = sha256(item)
    if not files:
        raise ValueError('La caché necesita archivos de entrada/salida verificables.')
    return dict(sorted(files.items()))


def fingerprint(inputs, context=''):
    payload = {'files': files_digest(inputs), 'context': context, 'schema': 1}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def matches(receipt, key, outputs):
    try:
        saved = json.loads(Path(receipt).read_text(encoding='utf-8'))
        return (saved['schema'] == 1 and saved['key'] == key
                and saved['outputs'] == files_digest(outputs))
    except (OSError, ValueError, KeyError, TypeError):
        return False


def record(receipt, key, outputs):
    receipt = Path(receipt)
    data = {'schema': 1, 'key': key, 'outputs': files_digest(outputs)}
    receipt.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt.with_suffix(f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
    temporary.replace(receipt)


def python_environment():
    """Changing the interpreter or installed build dependencies invalidates reuse."""
    return json.dumps({'python': sys.version, 'executable': sys.executable,
                       'platform': platform.platform(),
                       'packages': sorted((d.metadata.get('Name', ''), d.version)
                                          for d in importlib.metadata.distributions())}, sort_keys=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['key', 'check', 'record', 'environment'])
    parser.add_argument('--input', action='append', default=[])
    parser.add_argument('--output', action='append', default=[])
    parser.add_argument('--context', default='')
    parser.add_argument('--key')
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    if args.action == 'environment':
        print(python_environment())
    elif args.action == 'key':
        print(fingerprint(args.input, args.context))
    elif args.action == 'check':
        return 0 if matches(args.receipt, args.key, args.output) else 1
    else:
        record(args.receipt, args.key, args.output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
