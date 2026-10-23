#!/usr/bin/env python3
"""Execute extracted owning allocator functions against independent byte oracles."""
import argparse,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--in',dest='compiler',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out=a.out.resolve()
if a.out.exists() and any(a.out.iterdir()):p.error('--out must be new or empty')
a.out.mkdir(parents=True,exist_ok=True)
provider=ROOT/'components/darwin-owned-heap.in';original=provider.read_text();digest=hashlib.sha256(provider.read_bytes()).hexdigest()
def extract(name):
 start=original.index('fn '+name+'(');return original[start:original.index('\n}',start)+2]
source='var bytes:[Int]=['+','.join(['0']*73728)+'];\n'
source+='''
const DARWIN-HEAP-BASE=0x4D000000
const DARWIN-HEAP-BYTES=65536
const DARWIN-HEAP-RECORDS=128
var darwin-heap-metadata:Int=4096
var missing:Int=-1
fn load8(p:Int)->Int{return bytes[p];}
fn store8(p:Int,v:Int)->Void{bytes[p]=v&255;}
fn load64(p:Int)->Int{let v=0;let i=0;while i<8{v=v|(load8(p+i)<<(8*i));i+=1;}return v;}
fn store64(p:Int,v:Int)->Void{let i=0;while i<8{store8(p+i,v>>(8*i));i+=1;}return;}
fn darwin-protected-physical(p:Int)->Int{if p<DARWIN-HEAP-BASE||p>=DARWIN-HEAP-BASE+65536{return 0;}if (p - DARWIN-HEAP-BASE)/4096==missing{return 0;}return 8192+p - DARWIN-HEAP-BASE;}
fn reset()->Void{let i=0;while i<4096{store8(4096+i,0);i+=1;}store64(4112,65536);store64(4120,1);missing=-1;return;}
fn byte(p:Int)->Int{return load8(8192+p - DARWIN-HEAP-BASE);}
fn put(p:Int,v:Int)->Void{store8(8192+p - DARWIN-HEAP-BASE,v);return;}
'''
for name in ['find','span','zero','copy','malloc','free','calloc','realloc']:source+=extract('darwin-heap-'+name)+'\n'
source+='''
fn main()->Int{
 reset();let a=darwin-heap-malloc(33);let b=darwin-heap-malloc(64);
 if a!=DARWIN-HEAP-BASE||b!=a+48{return 1;}
 let i=0;while i<33{put(a+i,(i*37+19)&255);i+=1;}
 let next=darwin-heap-realloc(a,9000);if next==0||next==a{return 2;}
 i=0;while i<33{if byte(next+i)!=((i*37+19)&255){return 3;}i+=1;}
 if byte(next+8999)!=0{return 4;}
 if darwin-heap-realloc(next,-1)!=0||darwin-heap-find(next)==0||byte(next+32)!=((32*37+19)&255){return 5;}
 if darwin-heap-realloc(next,17)!=next||byte(next+16)!=((16*37+19)&255){return 6;}
 let zero=darwin-heap-realloc(next,0);if zero==0||zero==next||darwin-heap-find(next)!=0||darwin-heap-find(zero)==0{return 7;}
 if darwin-heap-free(zero)!=0||darwin-heap-free(zero)!=-1||darwin-heap-free(b)!=0{return 8;}
 let whole=darwin-heap-malloc(65536);if whole!=DARWIN-HEAP-BASE{return 9;}
 if darwin-heap-realloc(whole,0)!=0||darwin-heap-find(whole)==0{return 10;}
 if darwin-heap-free(whole+1)!=-1||darwin-heap-realloc(whole+1,32)!=-1{return 11;}
 if darwin-heap-free(whole)!=0{return 12;}
 let c=darwin-heap-calloc(0,-1);let d=darwin-heap-calloc(-1,0);if c==0||d==0||c==d||darwin-heap-calloc(2,-1)!=0||darwin-heap-calloc(65536,65536)!=0{return 13;}
 darwin-heap-free(c);darwin-heap-free(d);
 let cycle=0;while cycle<512{let p=darwin-heap-calloc(3,3000);if p!=DARWIN-HEAP-BASE{return 14;}i=0;while i<9000{if byte(p+i)!=0{return 15;}i+=1;}put(p+8999,127);darwin-heap-free(p);cycle+=1;}
 reset();i=0;while i<128{if darwin-heap-malloc(512)!=DARWIN-HEAP-BASE+i*512{return 16;}i+=1;}
 if darwin-heap-malloc(1)!=0{return 17;}
 darwin-heap-free(DARWIN-HEAP-BASE+1024);darwin-heap-free(DARWIN-HEAP-BASE+1536);
 if darwin-heap-malloc(1024)!=DARWIN-HEAP-BASE+1024{return 18;}
 reset();i=0;while i<127{if darwin-heap-malloc(1)==0{return 19;}i+=1;}
 if darwin-heap-malloc(1)!=0{return 20;}
 reset();missing=1;if darwin-heap-malloc(8192)!=0||load64(4112)!=65536||load64(4120)!=1{return 21;}
 missing=-1;if darwin-heap-malloc(65536)!=DARWIN-HEAP-BASE{return 22;}
 return 42;
}
'''
(a.out/'owner.in').write_text(source);report={'status':'running','provider_sha256':digest,'profiles':[],'model':'Only native byte loads/stores and owned-page translation replaced; exact allocator bodies unchanged.'}
try:
 for profile in ['default','lean','harden']:
  command=[str(a.compiler.resolve()),'compile','--path',str(a.out/'owner.in'),'--out',str(a.out/profile),'--target','jit','--entry','main','--profile',profile,'--json'];run=subprocess.run(command,capture_output=True,text=True,timeout=120);(a.out/(profile+'.json')).write_text(run.stdout);(a.out/(profile+'.stderr')).write_text(run.stderr);result=json.loads(run.stdout)
  assert run.returncode==0 and result.get('success') and result.get('eval_result')=={'Int':42},(profile,run.stdout[-3000:],run.stderr[-1000:]);report['profiles'].append({'profile':profile,'command':command,'status':'passed'});print('PASS',profile,flush=True)
 # Generated-source regression control restores the incorrect reject-before-zero
 # calloc ordering; the independent zero*SIZE_MAX assertion must catch it.
 control=source.replace('if count == 0 || size == 0 { return darwin-heap-malloc(0) }','if count < 0 || size < 0 { return 0 }\n  if count == 0 || size == 0 { return darwin-heap-malloc(0) }')
 assert control!=source;(a.out/'negative-control.in').write_text(control)
 command=[str(a.compiler.resolve()),'compile','--path',str(a.out/'negative-control.in'),'--out',str(a.out/'negative-control'),'--target','jit','--entry','main','--json'];run=subprocess.run(command,capture_output=True,text=True,timeout=120);(a.out/'negative-control.json').write_text(run.stdout);result=json.loads(run.stdout)
 assert run.returncode==0 and result.get('success') and result.get('eval_result')=={'Int':13},run.stdout
 report['negative_control']={'command':command,'observed_result':13,'expected_assertion':'calloc(0,SIZE_MAX) and calloc(SIZE_MAX,0) must succeed'}
 assert hashlib.sha256(provider.read_bytes()).hexdigest()==digest;report['status']='passed'
except Exception as error:report.update(status='failed',error=str(error));print('FAIL',error,flush=True)
finally:(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='passed' else 1)
