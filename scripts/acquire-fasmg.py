#!/usr/bin/env python3
"""Acquire the three unchanged upstream executables and their pinned BSD notice."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True,help='Application cache, separate from repository')
    p.add_argument('--archive',type=Path,help='Existing pinned upstream archive')
    p.add_argument('--download',action='store_true',help='Download an absent pinned archive')
    a=p.parse_args();out=a.out.resolve()
    if out==ROOT or ROOT in out.parents:
        p.error('application cache must be outside the source repository')
    out.mkdir(parents=True,exist_ok=True)
    pin=json.loads((ROOT/'fixtures/applications/fasmg.json').read_text())
    archive=a.archive.resolve() if a.archive else out/'upstream.tar.gz'
    if not archive.is_file():
        if not a.download:
            p.error('pinned archive absent; supply --archive or --download')
        with tempfile.TemporaryDirectory(dir=out) as temporary:
            target=Path(temporary)/'archive'
            request=urllib.request.Request(pin['archive_url'],headers={'User-Agent':'Space application lab'})
            with urllib.request.urlopen(request,timeout=60) as source,target.open('xb') as dest:
                size=0
                while block:=source.read(65536):
                    size+=len(block)
                    if size>32*1024*1024:
                        raise ValueError('archive exceeds bounded acquisition size')
                    dest.write(block)
            if sha(target.read_bytes())!=pin['archive_sha256']:
                raise ValueError('archive SHA256 mismatch')
            target.replace(archive)
    if archive.stat().st_size>32*1024*1024 or sha(archive.read_bytes())!=pin['archive_sha256']:
        raise ValueError('archive size/hash mismatch')
    wanted=[(row['path'],'fasmg-'+row['personality'],row['sha256'],row['size_bytes']) for row in pin['apps']]
    wanted.append(('core/license.txt','LICENSE',pin['license_sha256'],None))
    report={'status':'passed','source_commit':pin['source_commit'],'archive_sha256':pin['archive_sha256'],'files':[]}
    with tarfile.open(archive,'r:gz') as bundle:
        members=bundle.getmembers()
        for relative,name,digest,length in wanted:
            matches=[m for m in members if m.name.split('/',1)[-1]==relative]
            if len(matches)!=1 or not matches[0].isfile() or matches[0].size>1024*1024:
                raise ValueError('absent/ambiguous/nonregular bounded archive member '+relative)
            data=bundle.extractfile(matches[0]).read()
            if sha(data)!=digest or (length is not None and len(data)!=length):
                raise ValueError('upstream member bytes mismatch '+relative)
            path=out/name
            if path.exists():
                if not path.is_file() or path.read_bytes()!=data:
                    raise ValueError('existing cache bytes mismatch '+str(path))
            else:
                with tempfile.TemporaryDirectory(dir=out) as temporary:
                    target=Path(temporary)/name;target.write_bytes(data)
                    target.chmod(0o644 if name=='LICENSE' else 0o755);target.replace(path)
            report['files'].append({'path':str(path),'sha256':digest,'size_bytes':len(data),'modified':False})
    (out/'provenance.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    main()
