#!/usr/bin/env python3
"""Execute actual native caller-buffer normalization against independent paths."""
import argparse
import hashlib
import json
from pathlib import Path
import posixpath
import random
import re
import subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();out=a.out.resolve();a.compiler=a.compiler.resolve()
assert not out.exists() or not any(out.iterdir()),'--out must be new or empty'
out.mkdir(parents=True,exist_ok=True)
cases=[]
def case(cwd,path,cap=1024,scratch=2048,error=None,flags=0):
    c=cwd.encode() if isinstance(cwd,str) else cwd;q=path.encode() if isinstance(path,str) else path
    expected=b''
    if error is None:
        joined=q if q.startswith(b'/') else c+b'/'+q
        expected=posixpath.normpath(b'/'+joined.lstrip(b'/'))
        error=len(expected) if len(expected)<cap else -36
    cases.append(dict(cwd=c,path=q,capacity=cap,scratch=scratch,status=error,flags=flags,expected=expected))
for cwd,path in [('/','/'),('/','.'),('/','..'),('/a/b','../c'),('/a/b','../../../../c'),('/a/b','./x//y/../z/'),('/a/../b','../c'),('/a/b','/x/../é/😀'),('///a//b','////x//y'),('/','one two'),('/','*?'),('/'+'a'*1022,'.'),('/'+'a'*1022,'../b'),('/'+'a'*1022,'b'*1023),('/','a'*1023)]:case(cwd,path)
rng=random.Random(2401024)
for _ in range(200):
    cwd='/'+('/'.join(rng.choice(['a','b','c','é','😀']) for _ in range(rng.randrange(6))))
    path=('/' if rng.randrange(3)==0 else '')+'/'.join(rng.choice(['a','b','..','.','','é','😀']) for _ in range(rng.randrange(1,12)))
    if not path:path='.'
    case(cwd,path)
for cap in [2,3,4,8,16]:case('/a/b','../../c/d',cap=cap)
case('/a/b','../c',flags=1)
case('/','x',scratch=2,error=-36)
for cwd,path in [('relative','x'),('/',''),('','x'),('/a\0b','x'),('/','a\0b'),('/','x'*1024)]:case(cwd,path,error=-22)
case('/a/b','c',cap=1,error=-22)
case('/a/b','c',scratch=4097,error=-22)
case('/a/b','c',flags=2,error=-22)
case('/a/b','c',flags=3,error=-22)
case('/a/b','c',flags=4,error=-22)
values=[]
for c in cases:
    body=list(c['cwd'])+list(c['path'])+list(c['expected'])
    values += [len(c['cwd']),len(c['path']),c['capacity'],c['scratch'],c['status'],c['flags'],len(c['expected']),8+len(body)]+body
owner=ROOT/'components/fs-path-normalize.in'
source=re.sub(r'(?m)^package .*$', '',owner.read_text())
source+='\nvar memory:[Int]=['+','.join(['0']*16384)+'];\nvar original:[Int]=['+','.join(['0']*1024)+'];\nvar vectors:[Int]=['+','.join(map(str,values))+'];\n'
source+=r'''
fn load8(p:Int)->Int{if p<0 || p>=16384{return 0;}return memory[p]&255;}
fn store8(p:Int,value:Int)->void{if p>=0 && p<16384{memory[p]=value&255;}}
fn main()->Int{
 let row=0;let index=0;while index<CASES{
  let i=0;while i<16384{memory[i]=90;i=i+1;}
  let cwdbytes=vectors[row];let pathbytes=vectors[row+1];let capacity=vectors[row+2];let scratchbytes=vectors[row+3];let expected=vectors[row+4];let flags=vectors[row+5];let bytes=vectors[row+6];
  i=0;while i<cwdbytes{memory[256+i]=vectors[row+8+i];i=i+1;}i=0;while i<pathbytes{memory[2048+i]=vectors[row+8+cwdbytes+i];i=i+1;}
  let cwd=256;let output=4096;let scratch=8192;if flags==1{output=cwd;}if flags==2{scratch=cwd;}if flags==3{scratch=output;}if flags==4{cwd=0;}
  i=0;while i<capacity{original[i]=load8(output+i);i=i+1;}
  let result=fs-path-normalize-into(cwd,cwdbytes,2048,pathbytes,output,capacity,scratch,scratchbytes);
  if result!=expected{return 10000+index;}
  if result>=0{
   i=0;while i<bytes{if load8(output+i)!=vectors[row+8+cwdbytes+pathbytes+i]{return 20000+index;}i=i+1;}
   if load8(output+bytes)!=0{return 30000+index;}i=bytes+1;
  }else{i=0;}
  while i<capacity{if load8(output+i)!=original[i]{return 40000+index;}i=i+1;}
  row=row+vectors[row+7];index=index+1;
 }return 42;
}
'''.replace('CASES',str(len(cases)))
(out/'normalizer.in').write_text(source)
report=dict(status='running',classification='Actual native helper source model; not guest or filesystem execution',cases_per_profile=len(cases),compiler_sha256=hashlib.sha256(a.compiler.read_bytes()).hexdigest(),provider_sha256=hashlib.sha256(owner.read_bytes()).hexdigest(),profiles=[])
try:
 for profile in ['default','lean','harden']:
  command=[str(a.compiler),'compile','--path',str(out/'normalizer.in'),'--target','jit','--entry','main','--profile',profile,'--out',str(out/profile),'--json']
  result=subprocess.run(command,capture_output=True,text=True,timeout=240)
  (out/(profile+'.json')).write_text(result.stdout);(out/(profile+'.stderr')).write_text(result.stderr)
  emitted=json.loads(result.stdout);assert result.returncode==0 and emitted.get('success') and emitted.get('eval_result')=={'Int':42},emitted
  report['profiles'].append(dict(name=profile,status='passed',command=command));print('PASS',profile,len(cases),'independent paths atomic output no allocation',flush=True)
 report['status']='passed'
finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
