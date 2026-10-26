#!/usr/bin/env python3
"""Build pinned unchanged QuickJS/GNU sed sources as static Linux applications."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--application',choices=['quickjs','sed'],required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--archive',type=Path,help='Existing pinned release archive; otherwise download')
    a=p.parse_args();out=a.out.resolve()
    if out.exists() and any(out.iterdir()):p.error('--out must be new or empty')
    out.mkdir(parents=True,exist_ok=True)
    version={'quickjs':'2024-01-13','sed':'4.9'}[a.application]
    pin=json.loads((ROOT/'fixtures/applications'/f'{a.application}-{version}.json').read_text())
    archive=a.archive.resolve() if a.archive else out/'source.tar.xz'
    report={'status':'running','application':a.application,'version':version,'source_url':pin['source']['url'],'source_sha256':pin['source']['sha256'],'source_modified':False,'commands':[]}
    try:
        if not a.archive:
            with urllib.request.urlopen(pin['source']['url'],timeout=60) as source,archive.open('xb') as target:
                shutil.copyfileobj(source,target)
        if sha(archive)!=pin['source']['sha256']:raise ValueError('upstream archive SHA256 mismatch')
        with tarfile.open(archive) as bundle:
            bundle.extractall(out,filter='data')
            original={m.name:hashlib.sha256(bundle.extractfile(m).read()).hexdigest() for m in bundle.getmembers() if m.isfile() and (Path(m.name).suffix in ['.c','.h','.js','.in','.ac','.am'] or Path(m.name).name in ['Makefile','LICENSE','COPYING'])}
        checkout=out/f'{a.application}-{version}'
        env={**os.environ,'LC_ALL':'C','TZ':'UTC','SOURCE_DATE_EPOCH':'0'}
        if a.application=='quickjs':
            commands=[['make','-j2','qjs','CONFIG_LTO=','LDFLAGS=-static -no-pie -Wl,--build-id=none']]
            built=checkout/'qjs';notice=checkout/'LICENSE'
        else:
            env.update(FORCE_UNSAFE_CONFIGURE='1',CFLAGS='-O2',LDFLAGS='-static -no-pie -Wl,--build-id=none')
            commands=[['./configure','--disable-nls','--disable-acl','--without-selinux'],['make','-j2']]
            built=checkout/'sed/sed';notice=checkout/'COPYING'
        report.update(commands=commands,environment={k:env[k] for k in ['LC_ALL','TZ','SOURCE_DATE_EPOCH','FORCE_UNSAFE_CONFIGURE','CFLAGS','LDFLAGS'] if k in env},compiler=subprocess.check_output(['gcc','--version'],text=True).splitlines()[0],linker=subprocess.check_output(['ld','--version'],text=True).splitlines()[0])
        with (out/'build.log').open('w') as log:
            for command in commands:subprocess.run(command,cwd=checkout,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
        changed=[name for name,digest in original.items() if not (out/name).is_file() or sha(out/name)!=digest]
        report.update(upstream_source_files=len(original),changed_upstream_source=changed)
        if changed:raise ValueError('upstream source bytes changed during build')
        binary=out/('qjs' if a.application=='quickjs' else 'sed');shutil.copy2(built,binary)
        strip=['strip','--strip-debug',str(binary)];report['commands'].append(strip);subprocess.run(strip,check=True,timeout=30)
        shutil.copy2(notice,out/'LICENSE');report['license_sha256']=sha(out/'LICENSE')
        if sha(out/'LICENSE')!=pin['build']['license_sha256']:raise ValueError('pinned license notice mismatch')
        headers=subprocess.check_output(['readelf','-lW',str(binary)],text=True)
        if 'INTERP' in headers:raise ValueError('unexpected dynamic ELF interpreter')
        expected=pin['apps'][0];matches=sha(binary)==expected['sha256'] and binary.stat().st_size==expected['size_bytes']
        report.update(binary=str(binary),binary_sha256=sha(binary),binary_size=binary.stat().st_size,elf_program_headers=headers,matches_pinned_build=matches)
        if not matches:raise ValueError('built artifact differs from pinned diagnostic build; review retained output before updating pin')
        report['status']='passed'
    except Exception as error:report.update(status='failed',error=str(error))
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'].upper()+': '+str(out/'report.json'))
    return 0 if report['status']=='passed' else 1
if __name__=='__main__':raise SystemExit(main())
