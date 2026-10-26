#!/usr/bin/env python3
"""Execute actual eager Mach-O dependency validators against byte-level models."""
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
tracked=[ROOT/'components/darwin-eager-dependency.in',ROOT/'components/darwin-protected.in',ROOT/'fixtures/darwin-eager/process.asm',Path(__file__).resolve()]
report={'status':'running','profiles':[],'source_sha256':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in tracked}}
try:
 path=a.out/'process.macho';subprocess.run(['nasm','-f','bin',str(ROOT/'fixtures/darwin-eager/process.asm'),'-o',str(path)],check=True,timeout=30)
 binary=path.read_bytes();image=4096;size=len(binary);fix,extent=struct.unpack_from('<II',binary,208);imports,symbols=struct.unpack_from('<II',binary,fix+8)
 memory=[0]*40000;memory[image:image+size]=binary
 functions=''
 provider=ROOT/'components/darwin-protected.in'
 for name in ['darwin-protected-import-name','darwin-protected-import-symbol','darwin-protected-import-index']:functions+=extract(provider,name)+'\n'
 eager=ROOT/'components/darwin-eager-dependency.in'
 for name in ['darwin-eager-symbol','darwin-eager-entry','darwin-eager-fixups']:functions+=extract(eager,name)+'\n'
 # Materialize real source literals as model-backed byte strings, not hostptrs.
 for i,text in enumerate(['/usr/lib/libSystem.B.dylib','_write','_exit','_error','_open','_read','_close','_lseek','___error']):
  at=38000+i*64;raw=text.encode()+b'\0';memory[at:at+len(raw)]=raw;functions=functions.replace(json.dumps(text),str(at))
 functions=functions.replace('name: String','name: Int')  # Literal backing addresses above replace native string coercion.
 source='var heap:[Int]=['+','.join(map(str,memory))+'];\n'
 source+='''
fn load8(p:Int)->Int{return heap[p];}
fn store8(p:Int,v:Int)->Void{heap[p]=v&255;}
fn load16(p:Int)->Int{return load8(p)|(load8(p+1)<<8);}
fn store16(p:Int,v:Int)->Void{store8(p,v);store8(p+1,v>>8);}
fn load32(p:Int)->Int{let v=0;let i=0;while i<4{v=v|(load8(p+i)<<(i*8));i+=1;}return v;}
fn store32(p:Int,v:Int)->Void{let i=0;while i<4{store8(p+i,v>>(i*8));i+=1;}return;}
fn load64(p:Int)->Int{let v=0;let i=0;while i<8{v=v|(load8(p+i)<<(i*8));i+=1;}return v;}
fn store64(p:Int,v:Int)->Void{let i=0;while i<8{store8(p+i,v>>(i*8));i+=1;}return;}
fn darwin-protected-physical(p:Int)->Int{return 0;}
'''
 source+='\n'.join(line for line in provider.read_text().splitlines() if line.startswith('const DARWIN-PROTECTED-'))+'\n'
 source+='\n'.join(line for line in eager.read_text().splitlines() if line.startswith('const DARWIN-EAGER-'))+'\n'+functions
 source+='''
fn refuse(image:Int,offset:Int,value:Int,width:Int)->Int{
 let old=load32(image+offset);if width==8{old=load64(image+offset);}if width==2{old=load16(image+offset);}
 if width==8{store64(image+offset,value);}else{if width==2{store16(image+offset,value);}else{store32(image+offset,value);}}
 let result=darwin-eager-entry(image,IMAGE_SIZE,DARWIN-EAGER-IDENTITY);
 if width==8{store64(image+offset,old);}else{if width==2{store16(image+offset,old);}else{store32(image+offset,old);}}
 if result!=-8{return 0;}return 1;
}
fn main()->Int{
 let image=4096;let size=IMAGE_SIZE;let expected=ENTRY;
 if darwin-eager-entry(image,size,DARWIN-EAGER-IDENTITY)!=expected || darwin-eager-entry(image,size,0)!=-8 || darwin-eager-entry(0,size,DARWIN-EAGER-IDENTITY)!=-8 || darwin-eager-entry(image,271,DARWIN-EAGER-IDENTITY)!=-8{return 1;}
'''.replace('IMAGE_SIZE',str(size)).replace('ENTRY',str(0x41000000+struct.unpack_from('<Q',binary,184)[0]))
 mutations=[(0,0,4),(4,0,4),(8,0,4),(12,6,4),(16,6,4),(20,272,4),(24,0,4),(28,1,4),(32,0,4),(36,80,4),(56,0x40006000,8),(64,0,8),(64,65537,8),(72,4096,8),(80,271,8),(88,7,4),(92,7,4),(96,1,4),(104,0,4),(108,80,4),(128,0x41000000,8),(136,0,8),(144,0,8),(152,8193,8),(160,7,4),(164,7,4),(168,1,4),(176,5,4),(180,32,4),(184,271,8),(184,4096,8),(192,1,8),(200,0x80000022,4),(204,48,4),(208,0xffffffff,4),(212,0,4),(216,0,4),(220,64,4),(224,32,4),(228,1,4),(232,0,4),(236,0,4),(240,0,4),(fix,1,4),(fix+4,33,4),(fix+8,44,4),(fix+12,0,4),(fix+16,0,4),(fix+16,17,4),(fix+20,2,4),(fix+24,1,4),(fix+28,1,4),(fix+32,3,4),(fix+36,12,4),(fix+40,16,4),(fix+44,24,4),(fix+48,16384,2),(fix+50,2,2),(fix+52,0,8),(fix+60,1,4),(fix+64,3,2),(fix+66,0x8000,2),(fix+66,4092,2),(fix+imports,257,4),(fix+imports,2,4),(4352,0x8010000001000000,8),(4352,0x8010000100000000,8),(4352,0x8010000000000008,8),(4352,0x8008000000000000,8),(4352,0xa000000000000000,8),(4416,0x1e000000,8),(4416,1<<36,8),(152,4096,8)]
 mutations.append((binary.index(b'___error\0'),int.from_bytes(b'_error\0\0','little'),8))
 unknown=binary.index(b'_unknown\0')-(fix+symbols);mutations.append((fix+imports+28,1|(unknown<<9),4))
 for n,(offset,value,width) in enumerate(mutations):
  if value>=(1<<63):value-=1<<64
  source+=f' if refuse(image,{offset},{value},{width})==0{{return {100+n};}}\n'
 source+=f'''
 let h=image+{fix};
 // Exactly512 forward chain links are bounded and accepted;513 are refused.
 store16(h+66,0);store16(h+68,65535);
 let i=0;
 while i<512{{let raw=-9218868437227405312;if i==511{{raw=-9223372036854775807-1;}}store64(image+4096+i*8,raw);i+=1;}}
 if darwin-eager-entry(image,size,DARWIN-EAGER-IDENTITY)!=expected{{return 300;}}
 store16(h+68,0);
 if darwin-eager-entry(image,size,DARWIN-EAGER-IDENTITY)!=-8{{return 301;}}
 return 42;
}}
'''
 # -9218868437227405312 above is bindbit plus next2, no import addend.
 assert -9218868437227405312==(0x8010000000000000-(1<<64))
 source=source.replace('IMAGE_SIZE',str(size));(a.out/'owner.in').write_text(source)
 report['malformed_cases']=len(mutations)
 for profile in ['default','lean','harden']:
  command=[str(a.compiler.resolve()),'compile','--path',str(a.out/'owner.in'),'--out',str(a.out/profile),'--target','jit','--entry','main','--profile',profile,'--json'];run=subprocess.run(command,capture_output=True,text=True,timeout=90)
  (a.out/(profile+'.json')).write_text(run.stdout);(a.out/(profile+'.stderr')).write_text(run.stderr);result=json.loads(run.stdout)
  assert run.returncode==0 and result.get('success') and result.get('eval_result')=={'Int':42},(profile,run.stdout,run.stderr)
  report['profiles'].append({'name':profile,'status':'passed','command':command});print('PASS',profile,'actual chained dependency validators, malformed metadata/imports, genuine names and exact 512-link limit',flush=True)
 report['source_changed_during_run']=[name for name,digest in report['source_sha256'].items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest];assert not report['source_changed_during_run'];report['status']='passed'
except Exception as error:report.update(status='failed',error=str(error));print('FAIL:',error,flush=True)
finally:(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='passed' else 1)
