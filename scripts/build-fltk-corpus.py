#!/usr/bin/env python3
"""Build unmodified pinned FLTK fluid; building does not establish Space GUI support."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--archive', type=Path, help='Existing official archive; otherwise acquire the pinned URL')
p.add_argument('--x11-prefix', type=Path, help='Optional extracted X11 development dependency root')
p.add_argument('--jobs', type=int, default=4)
a = p.parse_args()
if not 1 <= a.jobs <= 8:
    p.error('--jobs must be 1..8')
a.out = a.out.resolve()
if a.out.exists() and any(a.out.iterdir()):
    p.error('--out must be new or empty')
a.out.mkdir(parents=True, exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest_path = ROOT / 'fixtures/applications/fltk-1.3.9.json'
manifest = json.loads(manifest_path.read_text())
report = {'status': 'running', 'scope': 'host artifact build only; no Space execution',
          'manifest_sha256': sha(manifest_path), 'commands': []}
try:
    archive = a.out / 'fltk-1.3.9-source.tar.gz'
    if a.archive:
        shutil.copyfile(a.archive, archive)
    else:
        with urllib.request.urlopen(manifest['source']['url'], timeout=60) as response:
            data = response.read(16 * 1024 * 1024 + 1)
        if len(data) > 16 * 1024 * 1024:
            raise ValueError('source archive exceeds acquisition bound')
        archive.write_bytes(data)
    if sha(archive) != manifest['source']['sha256']:
        raise ValueError('source archive checksum mismatch')
    with tarfile.open(archive) as source:
        source.extractall(a.out, filter='data')
    directory = a.out / 'fltk-1.3.9'
    environment = dict(os.environ)
    if a.x11_prefix:
        prefix = a.x11_prefix.resolve()
        environment['CPPFLAGS'] = environment.get('CPPFLAGS', '') + ' -I' + str(prefix / 'usr/include')
        environment['LDFLAGS'] = environment.get('LDFLAGS', '') + ' -L' + str(prefix / 'usr/lib/x86_64-linux-gnu')
    report['build_environment'] = {name: environment.get(name, '') for name in ('CC', 'CXX', 'CPPFLAGS', 'CFLAGS', 'CXXFLAGS', 'LDFLAGS')}
    report['compiler'] = subprocess.check_output([environment.get('CXX') or 'g++', '--version'], text=True).splitlines()[0]
    commands = [manifest['build']['configure']]
    commands += [['make', '-j' + str(a.jobs), '-C', part] for part in ('src', 'jpeg', 'zlib', 'png', 'fluid')]
    for index, command in enumerate(commands):
        log_path = a.out / ('build-' + str(index) + '.log')
        report['commands'].append({'command': command, 'cwd': str(directory), 'log': str(log_path)})
        with log_path.open('w') as log:
            subprocess.run(command, cwd=directory, env=environment, stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=300)
    binary = directory / 'fluid/fluid'
    expected = manifest['apps'][0]
    if sha(binary) != expected['sha256'] or binary.stat().st_size != expected['size_bytes']:
        raise ValueError('built artifact differs from pinned profile; preserve build evidence and inspect toolchain/configuration')
    shutil.copy2(binary, a.out / 'fluid')
    shutil.copy2(directory / 'COPYING', a.out / 'COPYING')
    report.update(status='passed', artifact_sha256=sha(binary), artifact_size=binary.stat().st_size,
                  application_status='not-executed-on-Space')
except Exception as error:
    report.update(status='failed', error=str(error))
finally:
    (a.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['status'].upper() + ': FLTK host artifact build; ' + str(a.out / 'report.json'))
raise SystemExit(0 if report['status'] == 'passed' else 1)
