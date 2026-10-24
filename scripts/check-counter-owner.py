#!/usr/bin/env python3
"""Execute native HPET discovery/read owners against malformed firmware/MMIO models."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--source',type=Path,default=ROOT/'components/counter.in')
a=p.parse_args();a.out=a.out.resolve();a.compiler=a.compiler.resolve()
if a.out.exists() and any(a.out.iterdir()):p.error('--out must be new or empty')
a.out.mkdir(parents=True,exist_ok=True)
provider=a.source.resolve();text=provider.read_text();text=text[text.index('var counter-ready:'):]
source='var memory:[Int]=['+','.join(['0']*32768)+'];\n'
source+='''const PAGE-NX=-9223372036854775808;
var current-cap:Int=7;var model-granted:Int=1;var model-advance:Int=1;var model-raw:Int=100;
var model-flags:Int=512;var model-reads:Int=0;var model-maps:Int=0;var model-writes:Int=0;
fn index(p:Int)->Int{
 if p>=0xF0000 && p<0xF1000{return p - 0xF0000;}
 if p>=0x1000000 && p<0x1002000{return 8192+p - 0x1000000;}
 if p>=0xFED00000 && p<0xFED01000{return 16384+p - 0xFED00000;}
 if p>=0 && p<32768{return p;}return -1;
}
fn load8(p:Int)->Int{let i=index(p);if i<0{return 0;}return memory[i]&255;}
fn store8(p:Int,value:Int)->void{let i=index(p);if i>=0{memory[i]=value&255;}}
fn load16(p:Int)->Int{return load8(p)|(load8(p+1)<<8);}
fn load32(p:Int)->Int{return load16(p)|(load16(p+2)<<16);}
fn invoke1(stub:Int,arg:Int)->Int{return model-flags;}
fn cli()->void{model-flags=model-flags&-513;}
fn sti()->void{model-flags=model-flags|512;}
fn load64(p:Int)->Int{
 if p==0x4198{return 1;}
 if p==0xFED000F0{
  model-reads=model-reads+1;
  if (load8(0xFED00010)&1)!=0 && model-advance!=0{model-raw=model-raw+model-advance;}
  return model-raw;
 }
 return load32(p)|(load32(p+4)<<32);
}
fn store32(p:Int,value:Int)->void{let i=0;while i<4{store8(p+i,(value>>(i*8))&255);i=i+1;}}
fn store64(p:Int,value:Int)->void{
 if p==0xFED00010{model-writes=model-writes+1;}
 store32(p,value);store32(p+4,(value>>32)&0xFFFFFFFF);
}
fn map-page(v:Int,p:Int,flags:Int)->void{model-maps=model-maps+1;if v!=p || flags!=(PAGE-NX|27){model-maps=-999;}}
fn cap-timer()->Int{return 2;}
fn cap-check(cap:Int,mask:Int)->Int{if cap==7 && model-granted==1 && mask==2{return 1;}return 0;}
'''+text
# Independent binary ACPI fixtures; addresses are mapped by model byte accessors.
mb=bytearray(52);struct.pack_into('<I',mb,0,0x40);struct.pack_into('<II',mb,44,48,0x6000)
mm=struct.pack('<IQQI',20,0,0x20000000,1)+struct.pack('<IQQI',20,0xFEC00000,0x1400000,2)
rsdp=bytearray(36);rsdp[:8]=b'RSD PTR ';rsdp[9:15]=b'MODEL ';struct.pack_into('<I',rsdp,16,0x1000000)
root=bytearray(44);root[:4]=b'RSDT';struct.pack_into('<I',root,4,40);root[8]=1;struct.pack_into('<I',root,36,0x1001000)
hpet=bytearray(56);hpet[:4]=b'HPET';struct.pack_into('<I',hpet,4,56);hpet[8]=1;struct.pack_into('<I',hpet,36,0x8086A201);struct.pack_into('<Q',hpet,44,0xFED00000)
cap=struct.pack('<Q',10_000_000<<32|0x8086A201)
source+='''
fn fixsum(p:Int,length:Int,at:Int)->void{store8(p+at,0);let n=0;let i=0;while i<length{n=(n+load8(p+i))&255;i=i+1;}store8(p+at,0 - n);}
fn reset()->void{
 let i=0;while i<32768{memory[i]=0;i=i+1;}
 counter-ready=0;counter-base=0;counter-hz=0;counter-last=0;counter-mmap=0;counter-mmap-size=0;counter-rsdp=0;counter-hpet-table=0;
 model-flags=512;model-granted=1;current-cap=7;model-advance=1;model-raw=100;model-reads=0;model-maps=0;model-writes=0;
'''
for address,blob in [(0x5000,mb),(0x6000,mm),(0xF0100,rsdp),(0x1000000,root),(0x1001000,hpet),(0xFED00000,cap)]:
 for offset,value in enumerate(blob):
  if value:source+=f' store8({address+offset},{value});\n'
source+='''fixsum(0xF0100,20,8);fixsum(0x1000000,40,9);fixsum(0x1001000,56,9);
}
fn failed()->Int{if counter-init(0x5000)!=-1 || counter-ready!=0 || counter-read()!=-1 || counter-frequency()!=-1{return 1;}return 0;}
fn main()->Int{
 reset();if counter-init(0x5000)!=0 || counter-frequency()!=100000000 || model-maps!=1{return 100;}
 let first=counter-read();let second=counter-read();if first<0 || second<=first{return 101;}
 if model-flags!=512{return 106;}
 model-flags=0;if counter-read()<second || model-flags!=0{return 107;}
 model-flags=512;
 let reads=model-reads;
 if counter-read-authorized(8)!=-13 || counter-frequency-authorized(-1)!=-13 || model-reads!=reads{return 102;}
 if counter-service-frequency()!=100000000 || counter-service-read()<second{return 103;}
 current-cap=8;reads=model-reads;if counter-service-read()!=-13 || model-reads!=reads{return 104;}
 current-cap=7;model-granted=0;if counter-read-authorized(7)!=-13 || model-reads!=reads{return 105;}
 reset();store32(0x5000,0);if failed()!=0 || model-maps!=0{return 110;}
 reset();store32(0x5000+44,8193);if failed()!=0{return 111;}
 reset();store32(0x6000,19);if failed()!=0{return 112;}
 reset();store32(0x6000,4096);if failed()!=0{return 113;}
 reset();store8(0xF0100+8,0);if failed()!=0 || model-maps!=0{return 114;}
 reset();store32(0x1000000+4,65537);if failed()!=0{return 115;}
 reset();store8(0x1000000+9,0);if failed()!=0{return 116;}
 reset();store32(0x1000000+36,0x80000000);fixsum(0x1000000,40,9);if failed()!=0{return 117;}
 reset();store8(0x1001000+9,0);if failed()!=0{return 118;}
 reset();store8(0x1001000+40,1);fixsum(0x1001000,56,9);if failed()!=0 || model-maps!=0{return 119;}
 reset();store8(0x1001000+41,32);fixsum(0x1001000,56,9);if failed()!=0{return 120;}
 reset();store64(0x1001000+44,0x1000000);fixsum(0x1001000,56,9);if failed()!=0 || model-maps!=0{return 121;}
 reset();store64(0x1001000+44,0xFED00008);fixsum(0x1001000,56,9);if failed()!=0{return 122;}
 reset();store32(0xFED00004,0);if failed()!=0 || model-writes!=0{return 123;}
 reset();store32(0xFED00004,100000001);if failed()!=0{return 124;}
 reset();store32(0xFED00004,3);if failed()!=0{return 125;}
 reset();store32(0xFED00000,0x80868201);store32(0x1001000+36,0x80868201);fixsum(0x1001000,56,9);if failed()!=0{return 126;}
 reset();store64(0xFED00010,2);model-writes=0;if failed()!=0 || model-writes!=0{return 127;}
 reset();store64(0xFED00100,4);if failed()!=0 || model-writes!=0{return 128;}
 reset();model-advance=0;if failed()!=0 || model-reads>100001 || load64(0xFED00010)!=0 || model-writes!=2{return 129;}
 reset();model-advance=-1;if failed()!=0 || load64(0xFED00010)!=0{return 130;}
 reset();if counter-init(0x5000)!=0{return 131;}
 model-advance=0;model-raw=50;if counter-read()!=-1 || counter-ready!=0{return 132;}
 reset();if counter-init(0x5000)!=0{return 133;}
 model-advance=0;model-raw=9223372036854775807;if counter-read()!=9223372036854775807{return 134;}
 model-raw=-9223372036854775808;if counter-read()!=-1 || counter-ready!=0 || counter-last!=9223372036854775807{return 135;}
 reset();store8(0x1001000+41,64);store8(0x1001000+43,4);fixsum(0x1001000,56,9);if counter-init(0x5000)!=0{return 138;}
 let maps=model-maps;let last=counter-last;if counter-init(0x5000)!=0 || model-maps!=maps || counter-last!=last{return 139;}
 reset();store32(0x1000000+4,552);fixsum(0x1000000,552,9);if failed()!=0{return 140;}
 reset();store32(0x1000000+4,41);fixsum(0x1000000,41,9);if failed()!=0{return 141;}
 reset();store32(0x1000000+4,44);store32(0x1000000+40,0x1001000);fixsum(0x1000000,44,9);if failed()!=0{return 142;}
 reset();store8(0x1001000+42,1);fixsum(0x1001000,56,9);if failed()!=0{return 143;}
 reset();store8(0x1001000+43,3);fixsum(0x1001000,56,9);if failed()!=0{return 144;}
 reset();store32(0x6000+24+20,1);if failed()!=0 || model-maps!=0{return 145;}
 reset();store32(0xFED00000,0x8086A202);if failed()!=0{return 146;}
 reset();store8(0xF0100+15,1);fixsum(0xF0100,20,8);if failed()!=0{return 147;}
 // Extended RSDP/XSDT path uses both checksums and 64-bit child pointers.
 reset();store8(0xF0100+15,2);store32(0xF0100+20,36);store64(0xF0100+24,0x1000000);
 store32(0x1000000,0x54445358);store32(0x1000000+4,44);store64(0x1000000+36,0x1001000);
 fixsum(0x1000000,44,9);fixsum(0xF0100,20,8);fixsum(0xF0100,36,32);
 if counter-init(0x5000)!=0{return 136;}
 reset();store8(0xF0100+15,2);store32(0xF0100+20,36);store64(0xF0100+24,0x1000000);fixsum(0xF0100,20,8);
 if failed()!=0{return 137;}
 return 42;
}
'''
(a.out/'owner.in').write_text(source)
report={'status':'running','compiler':str(a.compiler),'provider':str(provider),'provider_sha256':hashlib.sha256(provider.read_bytes()).hexdigest(),'profiles':[]}
try:
 for profile in ('default','lean','harden'):
  command=[str(a.compiler),'compile','--path',str(a.out/'owner.in'),'--target','jit','--entry','main','--profile',profile,'--out',str(a.out/profile),'--json']
  result=subprocess.run(command,capture_output=True,text=True,timeout=180)
  (a.out/f'{profile}.json').write_text(result.stdout);(a.out/f'{profile}.stderr').write_text(result.stderr)
  emitted=json.loads(result.stdout)
  assert result.returncode==0 and emitted.get('success') and emitted.get('eval_result')=={'Int':42},emitted
  report['profiles'].append({'name':profile,'status':'passed','command':command})
  print(f'PASS {profile}: native ACPI/HPET malformed discovery, exact frequency, IF-independent reads, width/overflow/refusal and authority',flush=True)
 report['status']='passed'
except Exception as error:
 report.update(status='failed',error=str(error));print('FAIL:',error,flush=True)
finally:(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='passed' else 1)
