#!/usr/bin/env python3
"""Execute actual Darwin startup validators with malformed byte-level inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--in',dest='compiler',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();a.out=a.out.resolve()
if a.out.exists() and any(a.out.iterdir()):p.error('--out must be new or empty')
a.out.mkdir(parents=True,exist_ok=True)
def extract(path,name):
 s=path.read_text();start=s.index('fn '+name+'(');return s[start:s.index('\n}',start)+2]
tracked=[ROOT/'components/darwin-process-startup.in',ROOT/'components/darwin-protected.in',ROOT/'fixtures/darwin-startup/process.asm',Path(__file__).resolve()]
report={'status':'running','profiles':[],'source_sha256':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in tracked}}
try:
 memory=[0]*40000;entries=[]
 memory[38000:38026]=b"/usr/lib/libSystem.B.dylib\0"
 for i,name in enumerate(['main','thread']):
  path=a.out/(name+'.macho');subprocess.run(['nasm','-f','bin',f'-DTHREAD={i}',str(ROOT/'fixtures/darwin-startup/process.asm'),'-o',str(path)],check=True,timeout=30)
  data=path.read_bytes();base=4096+i*8192;memory[base:base+8192]=data
  entries.append(struct.unpack_from('<Q',data,320 if i else 184)[0]+(0 if i else 0x41000000))
 source='var heap:[Int]=['+','.join(map(str,memory))+'];\n'
 source+='''
fn load8(p:Int)->Int{return heap[p];}
fn store8(p:Int,v:Int)->Void{heap[p]=v&255;}
fn load32(p:Int)->Int{let v=0;let i=0;while i<4{v=v|(load8(p+i)<<(i*8));i+=1;}return v;}
fn store32(p:Int,v:Int)->Void{let i=0;while i<4{store8(p+i,v>>(i*8));i+=1;}return;}
fn load64(p:Int)->Int{let v=0;let i=0;while i<8{v=v|(load8(p+i)<<(i*8));i+=1;}return v;}
fn store64(p:Int,v:Int)->Void{let i=0;while i<8{store8(p+i,v>>(i*8));i+=1;}return;}
fn darwin-protected-bind(image:Int,size:Int,bind:Int,data:Int,apply:Int)->Int{return -8;}
'''
 provider=ROOT/'components/darwin-protected.in'
 source+='\n'.join(line for line in provider.read_text().splitlines() if line.startswith('const DARWIN-PROTECTED-'))+'\n'
 # Model the literal's backing bytes, preserving the actual parser branches.
 source+=extract(provider,'darwin-protected-entry').replace('let name = "/usr/lib/libSystem.B.dylib"','let name = 38000')+'\n' 
 for name in ['darwin-startup-entry','darwin-startup-span','darwin-startup-input']:source+=extract(ROOT/'components/darwin-process-startup.in',name)+'\n'
 source+='''
fn refuse(image:Int,offset:Int,value:Int,wide:Int)->Int{
 let old=load64(image+offset);if wide==0{old=load32(image+offset);}
 if wide==0{store32(image+offset,value);}else{store64(image+offset,value);}
 let result=darwin-startup-entry(image,8192);
 if wide==0{store32(image+offset,old);}else{store64(image+offset,old);}
 if result!=-8{return 0;}return 1;
}
fn main()->Int{
'''
 source+=f' if darwin-startup-entry(4096,8192)!={entries[0]} || darwin-startup-entry(12288,8192)!={entries[1]}{{return 1;}}\n'
 mutations=[(0,0,0),(4,0,0),(8,0,0),(12,6,0),(16,4,0),(20,168,0),(24,0,0),(28,1,0),(32,0,0),(36,71,0),(56,0x1000,1),(64,0,1),(64,4095,1),(72,1,1),(80,359,1),(88,7,0),(92,7,0),(96,1,0),(104,0,0),(108,71,0),(128,0x41000000,1),(136,-1,1),(144,0,1),(152,4097,1),(160,7,0),(164,7,0),(168,1,0),(176,0x80000028,0),(180,176,0),(184,1,0),(188,41,0),(320,0x41000000+359,1),(320,0x41001000,1)]
 for n,(off,value,wide) in enumerate(mutations):source+=f' if refuse(12288,{off},{value},{wide})==0{{return {100+n};}}\n'
 for word in range(21):
  if word!=16:source+=f' if refuse(12288,{192+word*8},1,1)==0{{return {200+word};}}\n'
 source+='''
 if darwin-startup-entry(0,8192)!=-8 || darwin-startup-entry(12288,359)!=-8 || darwin-startup-entry(12288,0x200001)!=-8{return 300;}
 let base=30000;let vec=base+64;
 let group=0;
 while group<3{store64(base+group*16,0);store64(base+group*16+8,vec+group*136);store64(vec+group*136,0);group+=1;}
 if darwin-startup-input(base,4096)!=0{return 301;}
 group=0;
 while group<3{store64(base+group*16,16);let i=0;while i<16{store64(vec+group*136+i*8,base+512);i+=1;}store64(vec+group*136+128,0);group+=1;}
 let i=0;while i<63{store8(base+512+i,65);i+=1;}store8(base+575,0);
 // 48 strings of64 bytes including NUL exactly meet3072-byte budget.
 if darwin-startup-input(base,4096)!=0{return 302;}
 store8(base+575,65);store8(base+576,0);
 if darwin-startup-input(base,4096)!=-7{return 303;}
 store64(base,17);if darwin-startup-input(base,4096)!=-22{return 304;}store64(base,16);
 store64(base+8,base+4090);if darwin-startup-input(base,4096)!=-14{return 305;}store64(base+8,vec);
 store64(vec+128,1);if darwin-startup-input(base,4096)!=-22{return 306;}store64(vec+128,0);
 group=0;while group<3{store64(base+group*16,0);store64(vec+group*136,0);group+=1;}
 store64(base,1);store64(vec,base+512);store64(vec+8,0);
 i=0;while i<255{store8(base+512+i,65);i+=1;}store8(base+767,0);
 if darwin-startup-input(base,4096)!=0{return 307;}
 store8(base+767,65);if darwin-startup-input(base,4096)!=-7{return 308;}
 store64(vec,base+4096);if darwin-startup-input(base,4096)!=-14{return 309;}
 if darwin-startup-input(base,47)!=-14 || darwin-startup-input(base,4097)!=-14 || darwin-startup-input(0,4096)!=-14{return 310;}
 return 42;
}
'''
 (a.out/'owner.in').write_text(source)
 for profile in ['default','lean','harden']:
  command=[str(a.compiler.resolve()),'compile','--path',str(a.out/'owner.in'),'--out',str(a.out/profile),'--target','jit','--entry','main','--profile',profile,'--json']
  run=subprocess.run(command,capture_output=True,text=True,timeout=90);(a.out/(profile+'.json')).write_text(run.stdout);(a.out/(profile+'.stderr')).write_text(run.stderr)
  result=json.loads(run.stdout);assert run.returncode==0 and result.get('success') and result.get('eval_result')=={'Int':42},(profile,run.stdout,run.stderr)
  report['profiles'].append({'name':profile,'status':'passed','command':command});print('PASS',profile,'actual startup validators: genuine Mach-O, malformed UNIXTHREAD state/layout, vectors, exact aggregate and string limits',flush=True)
 report['source_changed_during_run']=[name for name,digest in report['source_sha256'].items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest]
 assert not report['source_changed_during_run'];report['status']='passed'
except Exception as error:report.update(status='failed',error=str(error));print('FAIL:',error,flush=True)
finally:(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='passed' else 1)
