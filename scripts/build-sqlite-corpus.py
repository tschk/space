#!/usr/bin/env python3
"""Build pinned unmodified upstream SQLite as a static Linux corpus application."""
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


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='New or empty build/evidence directory')
    parser.add_argument('--archive', type=Path, help='Cached official archive; all source checks remain required')
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        parser.error('--out must be new or empty')
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / 'fixtures/applications/sqlite-3.46.1.json').read_text())
    source = manifest['source']
    archive = args.archive.resolve() if args.archive else out / 'sqlite-autoconf-3460100.tar.gz'
    if not args.archive:
        with urllib.request.urlopen(source['url'], timeout=60) as response, archive.open('xb') as target:
            shutil.copyfileobj(response, target)
    if sha256(archive) != source['sha256']:
        raise SystemExit('Official SQLite archive SHA256 mismatch')
    with tarfile.open(archive) as contents:
        contents.extractall(out, filter='data')
    checkout = out / 'sqlite-autoconf-3460100'
    core = checkout / 'sqlite3.c'
    core_hash = hashlib.sha3_256(core.read_bytes()).hexdigest()
    found = re.search(r'^#define SQLITE_SOURCE_ID\s+"([^"]+)"', core.read_text(), re.MULTILINE)
    source_id = found.group(1) if found else None
    if core_hash != source['sqlite3_c_sha3_256'] or source_id != source['source_id']:
        raise SystemExit('SQLite core SHA3-256/source ID differs from official release reference')
    command = manifest['build']['command']
    environment = {**os.environ, 'LC_ALL': 'C', 'TZ': 'UTC', 'SOURCE_DATE_EPOCH': '0'}
    with (out / 'build.log').open('w') as log:
        subprocess.run(command, cwd=checkout, env=environment, stdout=log, stderr=subprocess.STDOUT,
                       check=True, timeout=300)
    binary = out / 'sqlite3'
    shutil.copy2(checkout / 'sqlite3', binary)
    expected = manifest['apps'][0]
    version = subprocess.check_output([str(binary), ':memory:', 'select sqlite_source_id();'],
                                     text=True, env={'LC_ALL': 'C', 'HOME': '/'}, timeout=10).strip()
    if version != source_id:
        raise SystemExit('Built SQLite reports an incorrect upstream source ID')
    receipt = {
        'source_url': source['url'], 'source_sha256': sha256(archive),
        'verification_reference': source['verification_reference'],
        'sqlite3_c_sha3_256': core_hash, 'source_id': source_id, 'source_modified': False,
        'license': manifest['license'], 'license_reference': 'https://www.sqlite.org/copyright.html',
        'license_declaration': core.read_text().split('*/', 1)[0] + '*/',
        'command': command, 'environment': {key: environment[key] for key in ['LC_ALL', 'TZ', 'SOURCE_DATE_EPOCH']},
        'compiler': subprocess.check_output([command[0], '--version'], text=True).splitlines()[0],
        'linker': subprocess.check_output(['ld', '--version'], text=True).splitlines()[0],
        'compile_options': subprocess.check_output([str(binary), ':memory:', 'pragma compile_options;'],
                                                  text=True, env={'LC_ALL': 'C', 'HOME': '/'}, timeout=10).splitlines(),
        'elf_program_headers': subprocess.check_output(['readelf', '-lW', str(binary)], text=True),
        'binary': str(binary), 'binary_sha256': sha256(binary), 'binary_size': binary.stat().st_size,
        'matches_pinned_build': sha256(binary) == expected['sha256'] and binary.stat().st_size == expected['size_bytes'],
        'host_cases': [],
        'corpus_scope': 'memory database cases only; file database execution is a separate runtime gate',
        'excluded_file_cases': [],
    }
    cases = json.loads((ROOT / 'fixtures/applications/sqlite-3.46.1-cases.json').read_text())
    for case in cases['cases']:
        if 'stdin' in case or 'file' in case:
            receipt['excluded_file_cases'].append(case['name'])
            continue
        result = subprocess.run(case['argv'], executable=str(binary), env={'LC_ALL': 'C', 'HOME': '/'},
                                text=True, capture_output=True, timeout=15)
        passed = (result.returncode == case.get('expected_exit', 0)
                  and result.stdout == case['expected_stdout'] and result.stderr == case.get('expected_stderr', ''))
        receipt['host_cases'].append({'name': case['name'], 'argv': case['argv'], 'exit': result.returncode,
                                     'stdout': result.stdout, 'stderr': result.stderr, 'passed': passed})
    if not receipt['host_cases']:
        raise SystemExit('SQLite memory corpus is empty')
    (out / 'report.json').write_text(json.dumps(receipt, indent=2) + '\n')
    if not receipt['matches_pinned_build']:
        raise SystemExit('Built SQLite differs from pinned toolchain/profile artifact; review retained receipt')
    if not all(case['passed'] for case in receipt['host_cases']):
        raise SystemExit('Built SQLite disagrees with the declared memory-corpus contracts')
    print('PASS: official unmodified SQLite source, core SHA3/source ID, pinned static ELF and host memory corpus; ' + str(binary))


if __name__ == '__main__':
    main()
