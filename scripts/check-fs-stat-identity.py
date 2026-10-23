#!/usr/bin/env python3
"""Execute fs-stat's owner against a dirty 64-byte Volume response copy."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--source',type=Path,default=ROOT/'components/filesystem.in')
a=p.parse_args();a.out=a.out.resolve();a.compiler=a.compiler.resolve()
if a.out.exists() and any(a.out.iterdir()):p.error('--out must be new or empty')
a.out.mkdir(parents=True,exist_ok=True)
text=a.source.read_text();start=text.index('fn fs-stat(');function=text[start:text.index('\n}',start)+2]
source='var memory:[Int]=['+','.join(['0']*1024)+'];\n'
source+='''const SF-ST-INODE=48;const SF-ST-MOUNT=56;
var volume-ready:Int=1;var response-status:Int=0;var copies:Int=0;
fn load64(p:Int)->Int{return memory[p];}
fn store64(p:Int,v:Int)->void{memory[p]=v;}
fn volume-rpc-stat(path:Int,buf:Int)->Int{
 if response-status!=0{return response-status;}
 let i=0;while i<64{store64(buf+i,load64(256+i));i=i+8;}copies=copies+1;return 0;
}
fn sparkfs-stat(path:Int,buf:Int)->Int{store64(buf+48,91);store64(buf+56,7);return 0;}
'''+function+'''
fn main()->Int{
 // Provider updates the defined first48 bytes; previous response dirt remains
 // in the trailing unsupported identities and is copied by the actual RPC ABI.
 let i=0;while i<64{store64(256+i,1000+i);i=i+8;}
 if fs-stat(99,0)!=0 || copies!=1{return 100;}
 if load64(0)!=1000 || load64(40)!=1040{return 101;}
 if load64(48)!=0 || load64(56)!=0{return 102;}
 store64(256+48,987654);store64(256+56,123456);
 if fs-stat(99,0)!=0 || load64(48)!=0 || load64(56)!=0{return 103;}
 response-status=-7;store64(48,71);store64(56,72);
 if fs-stat(99,0)!=-7 || copies!=2 || load64(48)!=71 || load64(56)!=72{return 104;}
 volume-ready=0;
 if fs-stat(99,0)!=0 || load64(48)!=91 || load64(56)!=7{return 105;}
 return 42;
}
'''
(a.out/'owner.in').write_text(source)
report={'status':'running','source':str(a.source.resolve()),'source_sha256':hashlib.sha256(a.source.read_bytes()).hexdigest(),'profiles':[]}
try:
 for profile in ('default','lean','harden'):
  command=[str(a.compiler),'compile','--path',str(a.out/'owner.in'),'--target','jit','--entry','main','--profile',profile,'--out',str(a.out/profile),'--json']
  result=subprocess.run(command,capture_output=True,text=True,timeout=90)
  (a.out/f'{profile}.json').write_text(result.stdout);(a.out/f'{profile}.stderr').write_text(result.stderr)
  emitted=json.loads(result.stdout)
  assert result.returncode==0 and emitted.get('success') and emitted.get('eval_result')=={'Int':42},emitted
  report['profiles'].append({'name':profile,'status':'passed','command':command})
  print(f'PASS {profile}: dirty Volume response identities cleared after copy; failures and direct identities preserved',flush=True)
 report['status']='passed'
except Exception as error:
 report.update(status='failed',error=str(error));print('FAIL:',error,flush=True)
finally:(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='passed' else 1)
