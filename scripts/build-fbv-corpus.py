#!/usr/bin/env python3
"""Build pinned upstream fbv BMP profile without C/H source changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--archive', type=Path)
a = p.parse_args()
out = a.out.resolve()
assert not out.exists() or not any(out.iterdir()), '--out must be new or empty'
out.mkdir(parents=True,exist_ok=True)
manifest_path = ROOT/'fixtures/applications/fbv-1.1.json'
manifest=json.loads(manifest_path.read_text());app=manifest['apps'][0]
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
report=dict(status='running',classification='Host source build/CLI oracles only; no Space or GUI execution',manifest_sha256=sha(manifest_path))
try:
    archive=out/'upstream.tar.gz'
    if a.archive:archive.write_bytes(a.archive.read_bytes())
    else:
        with urllib.request.urlopen(manifest['source']['url'],timeout=60) as response:archive.write_bytes(response.read())
    assert sha(archive)==manifest['source']['sha256'],'source archive mismatch'
    with tarfile.open(archive) as source_archive:source_archive.extractall(out,filter='data')
    source=out/('fbv-'+manifest['source']['commit'])
    original={str(x.relative_to(source)):sha(x) for x in source.rglob('*') if x.is_file()}
    assert original['COPYING']==manifest['source']['license_file_sha256']
    report['original_source_sha256']=original
    environment=dict(os.environ,LC_ALL='C',TZ='UTC',SOURCE_DATE_EPOCH='0',FRAMEBUFFER='/dev/fb0')
    commands=manifest['build']['commands'];report['commands']=commands
    with (out/'build.log').open('w') as log:
        for command in commands:subprocess.run(command,cwd=source,env=environment,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    # configure legitimately replaces the tracked Make.conf template and emits
    # config.h. Neither is an application implementation patch.
    assert all(sha(source/name)==digest for name,digest in original.items() if name!='Make.conf'),'upstream implementation modified'
    binary=out/'fbv';binary.write_bytes((source/'fbv').read_bytes());binary.chmod(0o755)
    assert sha(binary)==app['sha256'] and binary.stat().st_size==app['size_bytes'],'different pinned toolchain/profile artifact; inspect retained build'
    report['binary_sha256']=sha(binary);report['compiler']=subprocess.check_output(['gcc','--version'],text=True).splitlines()[0]
    report['generated_configuration_sha256']={name:sha(source/name) for name in ['Make.conf','config.h']}
    report['host_oracles']=[]
    for case in manifest['cli_oracles']:
        process=subprocess.run(case['argv'],executable=str(binary),cwd='/',env={'HOME':'/','LC_ALL':'C'},umask=0o22,capture_output=True,timeout=10)
        assert process.returncode==case['exit'] and hashlib.sha256(process.stdout).hexdigest()==case['stdout_sha256'] and hashlib.sha256(process.stderr).hexdigest()==case['stderr_sha256']
        merged=subprocess.run(case['argv'],executable=str(binary),cwd='/',env={'HOME':'/','LC_ALL':'C'},umask=0o22,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=10)
        assert merged.returncode==process.returncode
        report['host_oracles'].append(dict(argv=case['argv'],exit=process.returncode,stdout=process.stdout.decode(),stderr=process.stderr.decode(),merged_output=merged.stdout.decode()))
    report['status']='passed'
    print('PASS pinned fbv build and host CLI oracles; no GUI execution:',binary)
except Exception as error:
    report.update(status='failed',error=str(error));raise
finally:
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
