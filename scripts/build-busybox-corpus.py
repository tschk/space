#!/usr/bin/env python3
"""Build pinned, unmodified BusyBox using an explicit upstream static Kconfig profile."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='New or empty build/evidence directory')
    parser.add_argument('--archive', type=Path, help='Cached official archive; checksum is always enforced')
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        parser.error('--out must be new or empty')
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / 'fixtures/applications/busybox-1.36.1.json').read_text())
    source, build = manifest['source'], manifest['build']
    archive = args.archive.resolve() if args.archive else out / 'busybox-1.36.1.tar.bz2'
    if not args.archive:
        with urllib.request.urlopen(source['url'], timeout=60) as response, archive.open('xb') as target:
            shutil.copyfileobj(response, target)
    if digest(archive) != source['sha256']:
        raise SystemExit('Official BusyBox source checksum mismatch')
    with tarfile.open(archive) as contents:
        contents.extractall(out, filter='data')
    checkout = out / 'busybox-1.36.1'
    environment = {**os.environ, 'SOURCE_DATE_EPOCH': '0', 'KCONFIG_NOTIMESTAMP': '1', 'LC_ALL': 'C', 'TZ': 'UTC'}
    commands = []

    def make(*arguments):
        command = ['make', '-C', str(checkout), *arguments]
        commands.append(command)
        with (out / 'build.log').open('a') as log:
            subprocess.run(command, env=environment, stdin=subprocess.DEVNULL, stdout=log,
                           stderr=subprocess.STDOUT, check=True, timeout=300)

    make('allnoconfig')
    config = checkout / '.config'
    text = config.read_text()
    for key, value in build['kconfig'].items():
        pattern = r'^(?:' + re.escape(key) + r'=.*|# ' + re.escape(key) + r' is not set)$'
        replacement = key + '=' + value if value != 'n' else '# ' + key + ' is not set'
        text, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
        if count != 1:
            raise SystemExit('Unknown or ambiguous upstream Kconfig symbol: ' + key)
    config.write_text(text)
    make('oldconfig')
    resolved = config.read_text()
    for key, value in build['kconfig'].items():
        expected = key + '=' + value if value != 'n' else '# ' + key + ' is not set'
        if expected not in resolved.splitlines():
            raise SystemExit('Upstream Kconfig did not retain requested setting: ' + expected)
    shutil.copy2(config, out / 'resolved.config')
    make('-j4', 'V=1')
    binary = out / 'busybox'
    shutil.copy2(checkout / 'busybox', binary)
    expected = manifest['apps'][0]
    receipt = {
        'source_url': source['url'], 'source_sha256': digest(archive),
        'checksum_reference': source['checksum_reference'], 'source_modified': False,
        'license': manifest['license'], 'license_file_sha256': digest(checkout / 'LICENSE'),
        'commands': commands, 'environment': {key: environment[key] for key in
            ['SOURCE_DATE_EPOCH', 'KCONFIG_NOTIMESTAMP', 'LC_ALL', 'TZ']},
        'requested_kconfig': build['kconfig'], 'resolved_config_sha256': digest(out / 'resolved.config'),
        'compiler': subprocess.check_output(['gcc', '--version'], text=True).splitlines()[0],
        'linker': subprocess.check_output(['ld', '--version'], text=True).splitlines()[0],
        'make': subprocess.check_output(['make', '--version'], text=True).splitlines()[0],
        'elf_program_headers': subprocess.check_output(['readelf', '-lW', str(binary)], text=True),
        'binary': str(binary), 'binary_sha256': digest(binary), 'binary_size': binary.stat().st_size,
        'matches_pinned_build': (digest(binary) == expected['sha256']
            and binary.stat().st_size == expected['size_bytes']
            and digest(out / 'resolved.config') == build['resolved_config_sha256']
            and digest(checkout / 'LICENSE') == build['license_file_sha256']),
    }
    cases = json.loads((ROOT / 'fixtures/applications/busybox-1.36.1-cases.json').read_text())
    receipt['host_cases'] = []
    for index, case in enumerate(cases['cases']):
        fixture = out / ('host-file-' + str(index) + '.txt')
        if 'file' in case:
            fixture.write_text(case['file'])
        argv = [value.replace('@FILE@', str(fixture)) for value in case['argv']]
        result = subprocess.run(argv, executable=str(binary), input=case.get('stdin', ''),
                                text=True, capture_output=True, timeout=10)
        passed = (result.returncode == case['expected_exit']
            and result.stdout == case['expected_stdout'].replace('@FILE@', str(fixture))
            and result.stderr == case['expected_stderr'].replace('@FILE@', str(fixture)))
        receipt['host_cases'].append({'name': case['name'], 'argv': argv,
            'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr, 'passed': passed})
    (out / 'report.json').write_text(json.dumps(receipt, indent=2) + '\n')
    if not all(case['passed'] for case in receipt['host_cases']):
        raise SystemExit('BusyBox host execution disagrees with declared case contracts')
    if not receipt['matches_pinned_build']:
        raise SystemExit('Built BusyBox differs from pinned toolchain/profile artifact; review retained receipt')
    print('PASS: official unmodified BusyBox source and pinned static Linux artifact; ' + str(binary))


if __name__ == '__main__':
    main()
