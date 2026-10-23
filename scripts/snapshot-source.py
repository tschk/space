#!/usr/bin/env python3
"""Capture verified working source in a separate Git worktree for stable tests."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,default=Path(__file__).resolve().parents[1])
p.add_argument('--out',type=Path,required=True,help='New or empty directory outside source')
a=p.parse_args();root=a.source.resolve();out=a.out.resolve()
if out==root or root in out.parents or out in root.parents:p.error('--out must be separate from the source tree')
if out.exists() and (not out.is_dir() or any(out.iterdir())):p.error('--out must be new or empty')
head=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
paths=subprocess.check_output(['git','-C',str(root),'ls-files','--cached','--others','--exclude-standard','-z']).decode().split('\0')
contents={}
for name in paths:
    if not name or '__pycache__' in Path(name).parts:continue
    path=root/name
    if path.is_file():contents[name]=(path.read_bytes(),path.stat().st_mode)
hashes={name:hashlib.sha256(data).hexdigest() for name,(data,_) in contents.items()}
changed=[name for name,digest in hashes.items() if not (root/name).is_file() or hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest]
if changed:raise SystemExit('Source changed while capturing; rerun: '+', '.join(changed))
subprocess.run(['git','-C',str(root),'worktree','add','--detach',str(out),head],check=True)
# Remove tracked files deleted in the working source as well as copying edits.
tracked=subprocess.check_output(['git','-C',str(root),'ls-files','-z']).decode().split('\0')
for name in tracked:
    if name and name not in contents:
        path=out/name
        if path.is_file() or path.is_symlink():path.unlink()
for name,(data,mode) in contents.items():
    target=out/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);target.chmod(mode&0o777)
gitlinks=subprocess.check_output(['git','-C',str(root),'ls-files','--stage'],text=True).splitlines()
gitlinks=[line for line in gitlinks if line.startswith('160000 ')]
receipt={'gitlinks':gitlinks,'base_commit':head,'source':str(root),'snapshot':str(out),'source_sha256':hashes,'source_changed_during_capture':changed}
receipt_path=out.parent/(out.name+'.source.json');receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
print(f'Verified {len(contents)} source files; {receipt_path}')
print(f'Run tests from {out}; keep build artifacts in separate output directories.')
