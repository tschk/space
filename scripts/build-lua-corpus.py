#!/usr/bin/env python3
"""Build unmodified pinned Lua as a static Linux corpus application."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--out',type=Path,required=True,help='New or empty build/evidence directory')
p.add_argument('--archive',type=Path,help='Cached upstream archive; otherwise download the pinned source')
a=p.parse_args();a.out=a.out.resolve()
if a.out.exists() and any(a.out.iterdir()):p.error('--out must be new or empty')
a.out.mkdir(parents=True,exist_ok=True)
manifest=json.loads((ROOT/'fixtures/applications/lua-5.4.7.json').read_text())
source=manifest['source'];archive=a.archive.resolve() if a.archive else a.out/'lua-5.4.7.tar.gz'
if not a.archive:
    with urllib.request.urlopen(source['url'],timeout=60) as response,archive.open('xb') as target:
        while block:=response.read(65536):target.write(block)
assert hashlib.sha256(archive.read_bytes()).hexdigest()==source['sha256'],'upstream Lua source checksum mismatch'
with tarfile.open(archive) as contents:contents.extractall(a.out,filter='data')
checkout=a.out/'lua-5.4.7'
command=['make','-C',str(checkout/'src'),'-j4','lua','MYLDFLAGS=-static']
with (a.out/'build.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
binary=a.out/'lua';shutil.copy2(checkout/'src/lua',binary)
digest=hashlib.sha256(binary.read_bytes()).hexdigest();expected=manifest['apps'][0]
receipt={'source_url':source['url'],'source_sha256':source['sha256'],'source_modified':False,'command':command,
         'compiler':subprocess.check_output(['gcc','--version'],text=True).splitlines()[0],
         'binary':str(binary),'binary_sha256':digest,'binary_size':binary.stat().st_size,
         'matches_pinned_build':digest==expected['sha256'] and binary.stat().st_size==expected['size_bytes']}
(a.out/'report.json').write_text(json.dumps(receipt,indent=2)+'\n')
if not receipt['matches_pinned_build']:raise SystemExit('Built Lua differs from pinned compiler/profile artifact; receipt retained for explicit corpus review')
print('PASS: unmodified Lua source and pinned static Linux artifact; '+str(binary))
