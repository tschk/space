#!/usr/bin/env python3
"""Execute genuine eager chained Mach-O imports against finite native adapters."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--app',type=Path,help='Prove allocation-free refusal of checksum-pinned original macOS jq')
a=p.parse_args();a.out=a.out.resolve();a.compiler=a.compiler.resolve()
if a.out.exists() and any(a.out.iterdir()):p.error('--out must be new or empty')
a.out.mkdir(parents=True,exist_ok=True)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
snapshot=a.out/'source';snapshot.mkdir()
for directory in ['components','kernel','boot','protocol','services']:shutil.copytree(ROOT/directory,snapshot/directory)
shutil.copytree(ROOT/'fixtures/darwin-eager',snapshot/'fixtures/darwin-eager')
# Explicit test-only raw request revokes the invocation's actual borrowed grant.
provider=snapshot/'components/darwin-eager-dependency.in';text=provider.read_text();line='domain-user-syscall-hook = darwin-protected-dispatch';assert text.count(line)==1
provider.write_text(text.replace(line,'domain-user-syscall-hook = eager-test-dispatch'))
tracked=sorted(f for f in snapshot.rglob('*') if f.is_file());hashes={str(f.relative_to(snapshot)):sha(f) for f in tracked}
report={'status':'running','compiler':str(a.compiler),'compiler_sha256':sha(a.compiler),'runner_sha256':sha(Path(__file__).resolve()),'requirements_inspector_sha256':sha(ROOT/'scripts/inspect-darwin-application.py'),'frozen_source_sha256':hashes,'source_test_variance':{'components/darwin-eager-dependency.in':'only dispatch assignment routes through test-only actual borrowed-cap revocation control'},'compile_commands':[]}
try:
 command=['nasm','-f','bin',str(snapshot/'fixtures/darwin-eager/process.asm'),'-o',str(a.out/'process.macho')];report['compile_commands'].append(command);subprocess.run(command,check=True,timeout=30)
 binary=(a.out/'process.macho').read_bytes();size=len(binary)
 assert struct.unpack_from('<8I',binary)==(0xfeedfacf,0x1000007,3,2,5,240,1,0)
 off=32;commands=[]
 for _ in range(5):
  kind,length=struct.unpack_from('<II',binary,off);commands.append((kind,length));off+=length
 assert commands==[(0x19,72),(0x19,72),(0x80000028,24),(0x80000034,16),(0xc,56)] and off==272
 fix,sizefix=struct.unpack_from('<II',binary,208);version,starts,imports,symbols,count,fmt,compressed=struct.unpack_from('<7I',binary,fix)
 assert (version,starts,count,fmt,compressed)==(0,32,8,1,0) and fix+sizefix==size
 assert struct.unpack_from('<HH',binary,fix+48)==(4096,6)
 # Independent host fixup oracle decodes both real pages and expected slot targets.
 named=[]
 for i in range(count):
  item=struct.unpack_from('<I',binary,fix+imports+i*4)[0];assert item&511==1
  name=binary[fix+symbols+(item>>9):fix+sizefix].split(b'\0',1)[0].decode();named.append(name)
 assert named==['_write','_exit','___error','_open','_read','_close','_lseek','_write']
 decoded=[]
 for page in range(2):
  pos=struct.unpack_from('<H',binary,fix+66+page*2)[0]
  while True:
   raw=struct.unpack_from('<Q',binary,4096+page*4096+pos)[0];ordinal=raw&0xffffff
   decoded.append({'offset':page*4096+pos,'symbol':named[ordinal] if raw>>63 else None,'rebase_target':None if raw>>63 else 0x41000000+(raw&((1<<36)-1))})
   step=((raw>>51)&4095)*4
   if not step:break
   pos+=step;assert pos<=4088
 assert len(decoded)==10 and decoded[-2]['rebase_target']==0x42000500 and decoded[-1]['offset']==4096
 report['fixture']={'sha256':sha(a.out/'process.macho'),'size':size,'commands':commands,'imports':named,'fixups':decoded}
 source=(snapshot/'kernel/kernel-root.in').read_text();source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(snapshot/m[1])),source)
 source='import '+json.dumps(str(snapshot/'components/darwin-eager-dependency.in'))+'\n'+source
 assert source.count('  shell(port)')==1;source=source.replace('  shell(port)','  eager-check(port)')
 source+='''
fn eager-test-dispatch(frame:Int)->Int{
 if load64(frame+112)==0x2FFFFFE{
  if domain-current!=darwin-protected-domain || darwin-protected-busy==0{panic("eager revoke wrong owner");}
  cap-revoke(darwin-protected-storage);store64(frame+112,0);store64(frame+136,load64(frame+136)&-2);return 1;
 }
 return darwin-protected-dispatch(frame);
}
fn eager-free()->Int{let f=free-list;let n=0;while f!=0 && n<4096{n+=1;f=load64(f);}return n;}
fn eager-cstr(p:Int,s:Int)->void{let i=0;let c=-1;while c!=0{c=load8(s+i);store8(p+i,c);i+=1;}return;}
fn eager-invoke(image:Int,input:Int,serial:Int,storage:Int,budget:Int)->Int{
 let fs=rdmsr(0xC0000100);let gs=rdmsr(0xC0000101);wrmsr64(0xC0000100,0x42000000);wrmsr64(0xC0000101,0x42000000);
 let result=darwin-eager-run(image,IMAGE_SIZE,input,1024,DARWIN-EAGER-IDENTITY,serial,storage,budget);
 let final-fs=rdmsr(0xC0000100);let final-gs=rdmsr(0xC0000101);wrmsr64(0xC0000100,fs);wrmsr64(0xC0000101,gs);
 if final-fs!=0x42000000 || final-gs!=0x42000000{panic("eager caller segment bases not restored");}return result;
}
fn eager-refuse(image:Int,input:Int,serial:Int,storage:Int,offset:Int,value:Int,width:Int)->void{
 let saved=load32(image+offset);if width==8{saved=load64(image+offset);}if width==2{saved=load16(image+offset);}
 let heap=heap-next;let free=free-list;let domains=domain-count;let caps=cap-count;
 if width==8{store64(image+offset,value);}else{if width==2{store16(image+offset,value);}else{store32(image+offset,value);}}
 let result=darwin-eager-run(image,IMAGE_SIZE,input,1024,DARWIN-EAGER-IDENTITY,serial,storage,1000);
 if width==8{store64(image+offset,saved);}else{if width==2{store16(image+offset,saved);}else{store32(image+offset,saved);}}
 if result!=-8 || heap-next!=heap || free-list!=free || domain-count!=domains || cap-count!=caps{serial-write-cstr(com1(),"eager refusal offset ");serial-write-dec-wide(com1(),offset);serial-nl(com1());panic("eager malformed import changed state");}
}
fn eager-check(port:Int)->void{
 if dyn-kernel-exportable("darwin-eager-run")!=0 || dyn-kernel-exportable("darwin-eager-fixups")!=0 || dyn-resolve-idx("darwin-eager-run")!=-1{panic("eager raw provider exported");}
 if sf-mem-disk==0 || volume-ready!=0{panic("eager proof requires native RAM files");}
 let image=0x10000000;let input=alloc(1024);
 store64(input,2);store64(input+8,input+64);store64(input+16,2);store64(input+24,input+88);store64(input+32,1);store64(input+40,input+112);
 store64(input+64,input+512);store64(input+72,input+528);store64(input+80,0);store64(input+88,input+544);store64(input+96,input+560);store64(input+104,0);store64(input+112,input+576);store64(input+120,0);
 eager-cstr(input+512,"startup-fixture");eager-cstr(input+528,"two words");eager-cstr(input+544,"A=alpha");eager-cstr(input+560,"EMPTY=");eager-cstr(input+576,"executable_path=/fixture");
 let seed=alloc(8192);let n=0;while n<8192{store8(seed+n,load8("0123456789abcdef"+(n&15)));n+=1;}
 if fs-write-file("darwin-eager.txt",seed,8192)!=0{panic("eager seed failed");}
 let host=vfs-open("darwin-eager.txt",0);if host<3{panic("eager ambient host sentinel failed");}
 let host-path=load64(vfs-fd-table+host*32);let first=vfs-fd-alloc();
 let serial=cap-mint(root-realm,cap-serial());let storage=cap-mint(root-realm,cap-storage());let caps=cap-count;
 let source-copy=alloc(IMAGE_SIZE);let source-byte=0;while source-byte<IMAGE_SIZE{store8(source-copy+source-byte,load8(image+source-byte));source-byte+=1;}
 if darwin-protected-frames!=0 || darwin-eager-context!=0 || darwin-file-table!=0{panic("eager pressure proof needs fresh caches");}
 let held=alloc(65*8);let hold=0;while hold<65{store64(held+hold*8,frame-alloc());hold+=1;}hold=0;while hold<65{frame-free(load64(held+hold*8));hold+=1;}
 let saved-end=heap-end;let cold=heap-next;let cold-free=free-list;let cold-domains=domain-count;
 heap-end=heap-next;let refused=eager-invoke(image,input,serial,storage,1000);heap-end=saved-end;
 if refused!=-12 || heap-next!=cold || free-list!=cold-free || domain-count!=cold-domains || darwin-protected-frames!=0 || darwin-eager-context!=0 || darwin-file-table!=0{panic("eager zero-bump refusal mutated state");}
 heap-end=heap-next+10160;let recovered=eager-invoke(image,input,serial,storage,1000);heap-end=saved-end;
 if recovered!=42 || heap-next!=cold+10160 || vfs-fd-alloc()!=first{panic("eager exact retained-byte recovery failed");}
 let heap=0;let free=0;let domains=0;let executions=0;let cycle=0;

 let original=load64(image+4352);let original-alias=load64(image+8192);let original-rebase=load64(image+4416);
 while cycle<21{
  let mode=0;
  while mode<13{
   if mode!=6{
    store64(image+4096,mode);let serial-grant=serial;let storage-grant=storage;if mode==1{storage-grant=-1;}if mode==2{serial-grant=-1;}
    let budget=1000;if mode==4{budget=3;}
    let result=eager-invoke(image,input,serial-grant,storage-grant,budget);
    let expected=42;if mode==3 || mode==8 || mode==9{expected=142;}if mode==4{expected=124;}
    if result!=expected{serial-write-cstr(port,"eager mode ");serial-write-dec-wide(port,mode);serial-write-cstr(port," result ");serial-write-dec-wide(port,result);serial-nl(port);panic("eager bound guest mismatch");}
    if load64(image+4352)!=original || load64(image+8192)!=original-alias || load64(image+4416)!=original-rebase{panic("eager changed caller image fixups");}
    source-byte=0;while source-byte<IMAGE_SIZE{if source-byte<4096 || source-byte>=4104{if load8(image+source-byte)!=load8(source-copy+source-byte){panic("eager changed caller image bytes");}}source-byte+=1;}
    if vfs-fd-alloc()!=first || vfs-fd-valid(host)==0 || vfs-fd-offset(host)!=0 || load64(vfs-fd-table+host*32)!=host-path{panic("eager changed ambient host descriptor");}
    if darwin-protected-count!=0 || darwin-protected-busy!=0 || darwin-protected-domain!=0 || darwin-protected-authority!=-1 || darwin-protected-storage!=-1 || domain-current!=0 || domain-user-syscall-hook!=0 || user-context-active!=0 || user-budget-active!=0 || cap-count!=caps{panic("eager activation leaked ownership");}
    let retired=darwin-protected-last-domain;if load64(domain-table+retired*24)!=0 || load64(domain-table+retired*24+8)!=DOMAIN-FREE{panic("eager domain leaked");}
    executions+=1;
   }
   mode+=1;
  }
  if cycle==0{heap=heap-next;free=eager-free();domains=domain-count;}else{if heap-next!=heap || eager-free()!=free || domain-count!=domains{panic("eager repeated resource growth");}}
  cycle+=1;
 }
 let revocable=cap-mint(root-realm,cap-storage());store64(image+4096,6);
 if eager-invoke(image,input,serial,revocable,1000)!=42 || cap-check(revocable,cap-storage())!=0 || vfs-fd-alloc()!=first || heap-next!=heap || eager-free()!=free || domain-count!=domains{panic("eager actual borrowed revocation failed");}
 // MUTATIONS
 let denied-heap=heap-next;let denied-free=free-list;let denied-domains=domain-count;
 if darwin-eager-run(image,IMAGE_SIZE,input,1024,0,serial,storage,1000)!=-8 || darwin-eager-run(image,IMAGE_SIZE,input,1024,DARWIN-EAGER-IDENTITY,storage,storage,1000)!=-13{panic("eager identity or authority refusal failed");}
 if heap-next!=denied-heap || free-list!=denied-free || domain-count!=denied-domains{panic("eager descriptor denial allocated");}
 // ORIGINAL_APP
 if vfs-close(host)!=0{panic("eager host final close failed");}cap-revoke(serial);cap-revoke(storage);
 serial-write-cstr(port,"darwin-eager: 21 cycles 254 CPL3 bound executions PASS");serial-nl(port);outb(0xF4,16);
}
'''
 mutations=[(200,0x80000022,4),(240,0x58,4),(232,0,4),(208,0xffffffff,4),(212,0,4),(fix,1,4),(fix+4,33,4),(fix+20,2,4),(fix+24,1,4),(fix+28,1,4),(fix+8,44,4),(fix+12,0,4),(fix+16,0,4),(fix+16,17,4),(fix+32,3,4),(fix+36,12,4),(fix+44,24,4),(fix+48,16384,2),(fix+50,2,2),(fix+52,0,8),(fix+60,1,4),(fix+64,3,2),(fix+66,0x8000,2),(fix+66,4092,2),(4352,0x8010000001000000,8),(4352,0x8010000100000000,8),(4352,0x8010000000000008,8),(4352,0x8008000000000000,8),(4352,0xa000000000000000,8),(4416,0x1e000000,8),(4416,1<<36,8),(fix+imports,257,4),(fix+imports,2,4),(152,4096,8)]
 mutations.append((binary.index(b'___error\0'),int.from_bytes(b'_error\0\0','little'),8))
 unknown=binary.index(b'_unknown\0')-(fix+symbols);mutations.append((fix+imports+28,1|(unknown<<9),4))
 source=source.replace('// MUTATIONS','\n'.join(f'eager-refuse(image,input,serial,storage,{offset},{value if value<(1<<63) else value-(1<<64)},{width});' for offset,value,width in mutations)).replace('IMAGE_SIZE',str(size))
 report['malformed_cases']=len(mutations)
 if a.app:
  import importlib.util
  spec=importlib.util.spec_from_file_location('darwin_requirements',ROOT/'scripts/inspect-darwin-application.py');inspector=importlib.util.module_from_spec(spec);spec.loader.exec_module(inspector);report['original_application']=inspector.inspect(a.app)
  source=source.replace('// ORIGINAL_APP',f'if darwin-eager-run(0x11000000,{a.app.stat().st_size},input,1024,DARWIN-EAGER-IDENTITY,serial,storage,1000)!=-8 || heap-next!=denied-heap || free-list!=denied-free || domain-count!=denied-domains{{panic("original macOS jq eager refusal changed state");}}')
 (a.out/'kernel.in').write_text(source)
 commands=[['nasm','-f','bin',str(snapshot/'boot/multiboot.asm'),'-o',str(a.out/'trampoline.bin')],[str(a.compiler),'compile','--path',str(a.out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(a.out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(a.out/'kernel.bin')]]
 with (a.out/'compile.log').open('w') as log:
  for command in commands:report['compile_commands'].append(command);subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
 assert (a.out/'kernel.bin').stat().st_size<0xff00000
 command=['qemu-system-x86_64','-kernel',str(a.out/'kernel.bin'),'-m','512M','-display','none','-no-reboot','-serial','file:'+str(a.out/'serial.log'),'-device','isa-debug-exit,iobase=0xf4,iosize=0x04','-device',f'loader,file={a.out/"process.macho"},addr=0x10000000,force-raw=on']
 if a.app:command+=['-device',f'loader,file={a.app.resolve()},addr=0x11000000,force-raw=on']
 report['qemu_command']=command
 with (a.out/'qemu.log').open('w') as log:run=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=90)
 serial=(a.out/'serial.log').read_text();assert run.returncode==33 and 'darwin-eager: 21 cycles 254 CPL3 bound executions PASS' in serial,serial[-6000:]
 report['frozen_source_changed_during_run']=[name for name,digest in hashes.items() if sha(snapshot/name)!=digest];assert not report['frozen_source_changed_during_run']
 report.update(status='passed',cycles=21,executions=254,kernel_sha256=sha(a.out/'kernel.bin'))
 if a.app:report['original_application']['actual_eager_admission']=-8
 print('PASS 254 actual CPL3 eager bound calls, chained aliases/rebases, capability/pointer denials, malformed import refusal, fault/deadline cleanup and 21 stable cycles',flush=True)
except Exception as error:report.update(status='failed',error=str(error));print('FAIL:',error,flush=True)
finally:(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='passed' else 1)
