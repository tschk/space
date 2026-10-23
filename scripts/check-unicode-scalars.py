#!/usr/bin/env python3
"""Execute pure scalar providers against independent vectors in three profiles.

Vectors are emitted by check-windows-unicode.py from Python Unicode oracles.
This source model is separate from that gate's actual CPL3 executions.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--oracles',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();out=a.out.resolve();a.compiler=a.compiler.resolve()
assert not out.exists() or not any(out.iterdir()),'--out must be new or empty'
out.mkdir(parents=True,exist_ok=True)
data=a.oracles.read_bytes();_,count,offset,_=struct.unpack_from('<4Q',data)
assert count>3000 and offset>=4096 and offset+count*64==len(data)
values=struct.unpack_from('<'+'q'*(count*8),data,offset)
owner=ROOT/'components/text-unicode.in'
source=re.sub(r'(?m)^package .*$', '', owner.read_text())
source+='\nvar oracle:[Int]=['+','.join(map(str,values))+'];\n'
source+=r'''
fn main()->Int{
 let i=0;while i<MODELCOUNT{let row=i*8;let kind=oracle[row];let value=0;
  if kind==0{value=unicode-utf8-decode(oracle[row+2],oracle[row+3],oracle[row+4],oracle[row+5],oracle[row+1]);}
  if kind==1{value=unicode-utf16-decode(oracle[row+2],oracle[row+3],oracle[row+1]);}
  if kind==2{let scalar=oracle[row+1];let width=unicode-utf8-width(scalar);if width!=oracle[row+3]{return 10000+i;}let j=0;while j<width{if unicode-utf8-byte(scalar,j)!=((oracle[row+2]>>(j*8))&255){return 20000+i;}j=j+1;}value=oracle[row+6];}
  if kind==3{value=unicode-utf8-invalid-prefix(oracle[row+2],oracle[row+3],oracle[row+4],oracle[row+1]);}
  if value!=oracle[row+6]{return 30000+i;}i=i+1;
 }return 42;
}
'''.replace('MODELCOUNT',str(count))
(out/'scalars.in').write_text(source)
report=dict(status='running',classification='Pure scalar provider source model; no CPL3 or guest-memory proof',scalar_cases_per_profile=count,compiler_sha256=hashlib.sha256(a.compiler.read_bytes()).hexdigest(),provider_sha256=hashlib.sha256(owner.read_bytes()).hexdigest(),oracle_sha256=hashlib.sha256(data).hexdigest(),profiles=[])
try:
 for profile in ['default','lean','harden']:
  command=[str(a.compiler),'compile','--path',str(out/'scalars.in'),'--target','jit','--entry','main','--profile',profile,'--out',str(out/profile),'--json']
  result=subprocess.run(command,capture_output=True,text=True,timeout=240)
  (out/(profile+'.json')).write_text(result.stdout);(out/(profile+'.stderr')).write_text(result.stderr)
  emitted=json.loads(result.stdout)
  assert result.returncode==0 and emitted.get('success') and emitted.get('eval_result')=={'Int':42},emitted
  report['profiles'].append(dict(name=profile,status='passed',command=command));print('PASS',profile,count,'independent pure scalar cases',flush=True)
 report['status']='passed'
finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
