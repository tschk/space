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
    parser.add_argument('--wall-timeout', type=int, default=600,
                        help='external QEMU timeout only; actual guest IRQ budget is unchanged')
    args = parser.parse_args()
    source = ROOT / 'fixtures/applications/busybox-1.36.1-blocking-cases.json'
    config = json.loads(source.read_text())
    config['classification'] = 'Unmodified upstream BusyBox blocking-transfer acceptance; goal remains OPEN until every case passes'
    config['generator_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for case in config['cases']:
        recipe = case.pop('file_recipe', None)
        if recipe is not None:
            if recipe.get('kind') == 'numbered-lines':
                content = ''.join(str(index).zfill(recipe['width']) + '\n' for index in range(recipe['count']))
            else:
                content = recipe['pattern'] * recipe['repeat'] + recipe['suffix']
            payload = content.encode('utf-8')
            if len(payload) != recipe['size'] or hashlib.sha256(payload).hexdigest() != recipe['sha256']:
                raise ValueError('deterministic file recipe does not match pinned size/hash')
            case['file'] = content
            case['input_sha256'] = recipe['sha256']
            if case.pop('expected_stdout_from_file', False):
                case['expected_stdout'] = content
                case['expected_stdout_sha256'] = recipe['sha256']
    # The shared runner preserves the exact generated config in its output and
    # runs host and Space against the same declared input and pinned app bytes.
    with tempfile.TemporaryDirectory(prefix='space-blocking-pipeline-') as temp:
        path = Path(temp) / 'cases.json'
        path.write_text(json.dumps(config, indent=2) + '\n')
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/check-linux-corpus.py'),
                               '--in', str(args.compiler.resolve()),
                               '--app', str(args.busybox.resolve()),
                               '--application', 'busybox', '--case-config', str(path),
                               '--out', str(args.out.resolve()), '--root', args.root,
                               '--repeat', str(args.repeat), '--suite', '--input-suite',
                               '--wall-timeout', str(args.wall_timeout), '--trace'], check=False)
    report_path = args.out.resolve() / 'report.json'
    if report_path.exists():
        report = json.loads(report_path.read_text())
        observed = {row['filter']: row for row in report.get('space', {}).get('cases', [])}
        contracts = []
        for case in config['cases']:
            if 'input_sha256' not in case:
                continue
            actual = observed.get(case['name'])
            contracts.append(dict(name=case['name'], input_size=len(case['file'].encode()),
                                  input_sha256=case['input_sha256'],
                                  expected_stdout_sha256=hashlib.sha256(case['expected_stdout'].encode()).hexdigest(),
                                  actual_combined_output_sha256=(hashlib.sha256(actual['combined_serial_output'].encode()).hexdigest()
                                                                 if actual is not None else None),
                                  passed=actual is not None and actual['passed']))
        (args.out.resolve() / 'blocking-contract.json').write_text(json.dumps(
            dict(status=report.get('space_status', 'failed'),
                 acceptance_status=report.get('space_status', 'failed'),
                 acceptance_scope='pinned BusyBox twelve-case blocking corpus on the selected root',
                 overall_application_and_desktop_goal='OPEN',
                 generator_sha256=config['generator_sha256'],
                 config_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                 ring_capacity=4096, contracts=contracts), indent=2) + '\n')
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
