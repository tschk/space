#!/usr/bin/env python3
"""Execute the native lease owner against an independent per-byte oracle."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',required=True,type=Path)
p.add_argument('--out',required=True,type=Path)
a=p.parse_args();a.out=a.out.resolve();a.compiler=a.compiler.resolve()
if a.out.exists() and any(a.out.iterdir()):p.error('--out must be new or empty')
a.out.mkdir(parents=True,exist_ok=True)
owner=ROOT/'components/file-range-leases.in'
source='var memory:[Int]=['+','.join(['0']*32768)+'];\n'
source+='''const SF-SB-INODE-COUNT=20;const SF-IN-TYPE=0;const SF-TYPE-FILE=1;
var sf-super:Int=16;var sf-disk-ready:Int=1;var sf-mount-id:Int=1;
var heap:Int=4096;var allocations:Int=0;
fn load64(p:Int)->Int{return memory[p];}
fn store64(p:Int,v:Int)->void{memory[p]=v;}
fn load32(p:Int)->Int{return memory[p];}
fn sf-inode-addr(n:Int)->Int{return 256+n*256;}
fn alloc(n:Int)->Int{let p=heap;heap=heap+n;allocations=allocations+1;return p;}
'''
source+=owner.read_text().replace('package space.kernel','')
source+='''
fn mask(owner:Int,kind:Int)->Int{
 let result=0;let byte=0;
 while byte<64{
  let found=-1;let i=0;
  while i<fs-range-count{
   let p=fs-range-table+i*48;
   if load64(p)==owner && load64(p+8)==1 && load64(p+16)==2 && load64(p+24)<=byte && (load64(p+32)<0 || load64(p+32)>byte){
    if found!=-1{return 123456789;}found=load64(p+40);
   }i=i+1;
  }
  if found==kind{result=result|(1<<byte);}byte=byte+1;
 }return result;
}
fn main()->Int{
 store64(sf-super+SF-SB-INODE-COUNT,4);store64(sf-inode-addr(1),1);
'''
state={owner:[-1]*64 for owner in range(1,5)}
rng=random.Random(105741)
operations=[]
def signed(value):return value if value<1<<63 else value-(1<<64)
for index in range(250):
    who=rng.randrange(1,5);start=rng.randrange(64);length=rng.randrange(1,65-start);kind=rng.randrange(3)
    end=start+length
    conflict=kind!=2 and any(state[other][byte]>=0 and (kind==1 or state[other][byte]==1) for other in state if other!=who for byte in range(start,end))
    expected=-2 if conflict else 0
    if not conflict:
        for byte in range(start,end):state[who][byte]=-1 if kind==2 else kind
    source+=f' if fs-range-lease({who},1,2,{start},{length},{kind})!={expected}{{return {1000+index};}}\n'
    for person in state:
        for held in range(2):
            expected_mask=signed(sum(1<<byte for byte,value in enumerate(state[person]) if value==held))
            source+=f' if mask({person},{held})!={expected_mask}{{return {2000+index};}}\n'
    operations.append({'owner':who,'start':start,'length':length,'kind':kind,'expected':expected})
source+='''
 if allocations!=2{return 3001;}
 fs-range-release-owner-file(1,1,2);if mask(1,0)!=0 || mask(1,1)!=0{return 3002;}
 fs-range-release-owner(2);fs-range-release-owner(3);fs-range-release-owner(4);
 if fs-range-count!=0{return 3003;}return 42;
}
'''
(a.out/'owner.in').write_text(source)
report={'status':'running','compiler':str(a.compiler),'compiler_sha256':hashlib.sha256(a.compiler.read_bytes()).hexdigest(),'owner_sha256':hashlib.sha256(owner.read_bytes()).hexdigest(),'operations':operations,'profiles':[]}
try:
    for profile in ('default','lean','harden'):
        command=[str(a.compiler),'compile','--path',str(a.out/'owner.in'),'--target','jit','--entry','main','--profile',profile,'--out',str(a.out/profile),'--json']
        result=subprocess.run(command,capture_output=True,text=True,timeout=180)
        (a.out/f'{profile}.json').write_text(result.stdout)
        (a.out/f'{profile}.stderr').write_text(result.stderr)
        emitted=json.loads(result.stdout)
        assert result.returncode==0 and emitted.get('success') and emitted.get('eval_result')=={'Int':42},emitted
        report['profiles'].append({'name':profile,'status':'passed','command':command})
        print(f'PASS {profile}: 250 native lease updates and 2,000 independent ownership masks',flush=True)
    report['status']='passed'
except Exception as error:
    report.update(status='failed',error=str(error))
    print('FAIL:',error,flush=True)
finally:(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='passed' else 1)
