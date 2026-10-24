#!/usr/bin/env python3
"""Execute the actual NVMe command owner against bounded CQ/doorbell fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',required=True,type=Path)
p.add_argument('--out',required=True,type=Path)
p.add_argument('--source',type=Path,default=ROOT/'components/storage.in')
a=p.parse_args();a.out=a.out.resolve();a.compiler=a.compiler.resolve()
if a.out.exists() and any(a.out.iterdir()):p.error('--out must be new or empty')
a.out.mkdir(parents=True,exist_ok=True)
text=a.source.read_text();start=text.index('fn nvme-io-submit(');function=text[start:text.index('\n}',start)+2]
source='var memory:[Int]=['+','.join(['0']*12288)+'];\n'
source+='''const NVME-CMD-FLUSH=0;const NVME-CMD-WRITE=1;const NVME-CMD-READ=2;const NVME-IO-Q=64;
var nvme-iosq:Int=1024;var nvme-iocq:Int=6144;var nvme-io-sq-tail:Int=0;var nvme-io-cq-head:Int=0;var nvme-io-cq-phase:Int=1;
var nvme-cid:Int=0;var storage-ready:Int=1;var nvme-flush-completions:Int=0;
var mode:Int=0;var sq-rings:Int=0;var cq-rings:Int=0;
fn load32(p:Int)->Int{return memory[p]&0xFFFFFFFF;}
fn store32(p:Int,v:Int)->void{memory[p]=v&0xFFFFFFFF;}
fn load64(p:Int)->Int{return load32(p)|(load32(p+4)<<32);}
fn store64(p:Int,v:Int)->void{store32(p,v);store32(p+4,(v>>32)&0xFFFFFFFF);}
fn com1()->Int{return 0;}
fn serial-write-cstr(p:Int,s:Int)->void{}
fn serial-write-dec-wide(p:Int,n:Int)->void{}
fn serial-nl(p:Int)->void{}
fn pause()->void{}
fn nvme-sq-db(n:Int)->Int{return 11;}
fn nvme-cq-db(n:Int)->Int{return 12;}
fn nvme-w32(reg:Int,value:Int)->void{
 if reg==11{
  sq-rings=sq-rings+1;
  if mode!=2{
   let cid=nvme-cid;let queue=1;let status=0;
   if mode==1{status=16386;}if mode==3{cid=cid+1;}if mode==4{queue=2;}
   let cqe=nvme-iocq+nvme-io-cq-head*16;
   store32(cqe+8,queue<<16);store32(cqe+12,cid|(nvme-io-cq-phase<<16)|(status<<17));
  }
 }else{cq-rings=cq-rings+1;}
}
fn reset()->void{
 let i=0;while i<12288{memory[i]=0;i=i+1;}
 nvme-io-sq-tail=0;nvme-io-cq-head=0;nvme-io-cq-phase=1;nvme-cid=0;storage-ready=1;nvme-flush-completions=0;sq-rings=0;cq-rings=0;mode=0;
}
'''+function+'''
fn main()->Int{
 reset();
 if nvme-io-submit(0,0,0,0)!=0{return 100;}
 if nvme-flush-completions!=1 || sq-rings!=1 || cq-rings!=1{return 101;}
 if load32(1024)!=65536 || load32(1028)!=1{return 102;}
 let i=8;while i<64{if load32(1024+i)!=0{return 103;}i=i+4;}
 let cycle=1;while cycle<130{if nvme-io-submit(0,0,0,0)!=0{return 104;}cycle=cycle+1;}
 if nvme-flush-completions!=130 || nvme-io-cq-head!=2 || nvme-io-sq-tail!=2 || nvme-io-cq-phase!=1{return 105;}
 reset();nvme-cid=65535;if nvme-io-submit(0,0,0,0)!=0 || nvme-cid!=1{return 106;}
 reset();mode=1;if nvme-io-submit(0,0,0,0)!=16386 || nvme-flush-completions!=0 || storage-ready!=1 || cq-rings!=1{return 107;}
 mode=0;if nvme-io-submit(0,0,0,0)!=0 || nvme-flush-completions!=1{return 108;}
 reset();mode=2;
 if nvme-io-submit(0,0,0,0)!=-1 || nvme-flush-completions!=0 || storage-ready!=0 || cq-rings!=0{return 109;}
 reset();mode=3;if nvme-io-submit(0,0,0,0)!=-1 || storage-ready!=0 || nvme-flush-completions!=0{return 110;}
 reset();mode=4;if nvme-io-submit(0,0,0,0)!=-1 || storage-ready!=0 || nvme-flush-completions!=0{return 111;}
 reset();
 if nvme-io-submit(0,1,0,0)!=-1 || nvme-io-submit(0,0,1,0)!=-1 || nvme-io-submit(0,0,0,4096)!=-1{return 112;}
 if nvme-io-submit(3,0,1,4096)!=-1 || nvme-io-submit(1,0,0,4096)!=-1 || nvme-io-submit(2,0,9,4096)!=-1{return 113;}
 if sq-rings!=0 || cq-rings!=0 || nvme-cid!=0{return 114;}
 if nvme-io-submit(1,123,8,8192)!=0 || nvme-flush-completions!=0{return 115;}
 if load32(1024)!=65537 || load32(1028)!=1 || load64(1048)!=8192 || load32(1064)!=123 || load32(1072)!=7{return 116;}
 return 42;
}
'''
(a.out/'owner.in').write_text(source)
report={'status':'running','owner_source':str(a.source.resolve()),'owner_sha256':hashlib.sha256(a.source.read_bytes()).hexdigest(),'compiler':str(a.compiler),'profiles':[]}
try:
 for profile in ('default','lean','harden'):
  command=[str(a.compiler),'compile','--path',str(a.out/'owner.in'),'--target','jit','--entry','main','--profile',profile,'--out',str(a.out/profile),'--json']
  result=subprocess.run(command,capture_output=True,text=True,timeout=180)
  (a.out/f'{profile}.json').write_text(result.stdout);(a.out/f'{profile}.stderr').write_text(result.stderr)
  emitted=json.loads(result.stdout)
  assert result.returncode==0 and emitted.get('success') and emitted.get('eval_result')=={'Int':42},emitted
  report['profiles'].append({'name':profile,'status':'passed','command':command})
  print(f'PASS {profile}: actual FLUSH owner SQE, CID/SQID/status, phase wrap, timeout/offline, refusals and successful-only counter',flush=True)
 report['status']='passed'
except Exception as error:
 report.update(status='failed',error=str(error));print('FAIL:',error,flush=True)
finally:(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='passed' else 1)
