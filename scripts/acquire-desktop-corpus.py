#!/usr/bin/env python3
"""Acquire exact upstream GUI artifacts without installing them into the host OS.

Extraction into owned directories is acquisition only. No package maintainer
scripts run. A successful acquisition is not a Space application pass.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--app', action='append', help='Selected manifest id; default all')
    parser.add_argument('--archive', type=Path, help='Use a cached archive; requires exactly one selected app')
    args = parser.parse_args()
    args.out = args.out.resolve(); args.out.mkdir(parents=True, exist_ok=False)
    manifest = ROOT / 'fixtures/applications/desktop-corpus.json'
    pins = json.loads(manifest.read_text())['apps']
    if args.app:
        assert set(args.app) <= {pin['id'] for pin in pins}, 'unknown app id'
        pins = [pin for pin in pins if pin['id'] in args.app]
    if args.archive and len(pins) != 1:
        parser.error('--archive requires one selected --app')
    report = dict(scope=__doc__, status='running', manifest_sha256=sha(manifest), apps=[])
    try:
        for pin in pins:
            folder = args.out / pin['id']; folder.mkdir()
            package = folder / pin['archive']['name']
            if args.archive:
                shutil.copyfile(args.archive, package)
            else:
                with urllib.request.urlopen(pin['archive']['browser_download_url'], timeout=60) as response, package.open('wb') as stream:
                    total = 0
                    while data := response.read(1024 * 1024):
                        total += len(data)
                        if total > pin['archive']['size']:
                            raise ValueError('archive exceeds pinned size')
                        stream.write(data)
            assert package.stat().st_size == pin['archive']['size'] and sha(package) == pin['archive']['sha256'], 'archive pin mismatch'
            root = folder / 'root'; root.mkdir()
            if package.name.endswith('.deb'):
                subprocess.run(['dpkg-deb', '-x', str(package), str(root)], check=True, timeout=120)
            else:
                with tarfile.open(package) as source:
                    source.extractall(root, filter='data')
            binary = root / pin['executable']
            assert binary.stat().st_size == pin['size_bytes'] and sha(binary) == pin['sha256'], 'executable pin mismatch'
            report['apps'].append(dict(id=pin['id'], binary=str(binary), archive=str(package), sha256=pin['sha256']))
            (args.out / 'applications.json').write_text(json.dumps(report, indent=2) + '\n')
            print(pin['name'] + ': acquired, not executed', flush=True)
        report['status'] = 'acquired-not-executed'
    except Exception as error:
        report.update(status='failed', error=str(error))
    finally:
        (args.out / 'applications.json').write_text(json.dumps(report, indent=2) + '\n')
    return 0 if report['status'] == 'acquired-not-executed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
