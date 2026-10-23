#!/usr/bin/env python3
"""Require actual unmodified BusyBox transfer beyond the native pipe ring.

This is an open acceptance gate: an honest unsupported blocking write fails it.
The completed nine-case child corpus is included unchanged before the new goal.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--in', dest='compiler', type=Path, required=True)
    parser.add_argument('--busybox', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--root', choices=['standard', 'minimal'], default='standard')
    parser.add_argument('--repeat', type=int, default=21)
    args = parser.parse_args()
    source = ROOT / 'fixtures/applications/busybox-1.36.1-children-cases.json'
    config = json.loads(source.read_text())
    config['classification'] = 'Unmodified upstream BusyBox blocking-transfer acceptance; goal remains OPEN until every case passes'
    config['generator_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    config.pop('pending_scenarios', None)
    config['cases'].append(dict(name='pipeline-beyond-ring',
                                argv=['/ash', '-c', 'cat @FILE@ | wc -c'],
                                file='abcdefghi\n' * 1090 + 'x\n',
                                expected_stdout='10902\n', expected_stderr='',
                                expected_exit=0, repeat=True))
    # The shared runner preserves the exact generated config in its output and
    # runs host and Space against the same declared input and pinned app bytes.
    with tempfile.TemporaryDirectory(prefix='space-blocking-pipeline-') as temp:
        path = Path(temp) / 'cases.json'
        path.write_text(json.dumps(config, indent=2) + '\n')
        return subprocess.run([sys.executable, str(ROOT / 'scripts/check-linux-corpus.py'),
                               '--in', str(args.compiler.resolve()),
                               '--app', str(args.busybox.resolve()),
                               '--application', 'busybox', '--case-config', str(path),
                               '--out', str(args.out.resolve()), '--root', args.root,
                               '--repeat', str(args.repeat), '--suite', '--input-suite',
                               '--trace'], check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
