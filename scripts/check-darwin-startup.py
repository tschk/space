#!/usr/bin/env python3
"""Execute distinct protected LC_MAIN/LC_UNIXTHREAD startup ABIs in actual CPL3."""
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
p.add_argument('--app',type=Path,help='Inspect and prove allocation-free refusal of checksum-pinned original macOS jq')
p.add_argument('--ledger-limit-control',action='store_true',help='Test-only frozen source: reduce mapping ledger to8slots and prove exit-stub capacity failure cleanup')
a=p.parse_args();a.out=a.out.resolve();a.compiler=a.compiler.resolve()
if a.ledger_limit_control and a.app:p.error('--ledger-limit-control cannot be combined with --app')
if a.out.exists() and any(a.out.iterdir()):p.error('--out must be new or empty')
a.out.mkdir(parents=True,exist_ok=True)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
snapshot=a.out/'source';snapshot.mkdir()
for directory in ['components','kernel','boot','protocol','services']:
    shutil.copytree(ROOT/directory,snapshot/directory)
shutil.copytree(ROOT/'fixtures/darwin-startup',snapshot/'fixtures/darwin-startup')
variance={}
if a.ledger_limit_control:
    provider=snapshot/'components/darwin-protected.in'
    text=provider.read_text();old='const DARWIN-PROTECTED-MAX-FRAMES = 64';assert text.count(old)==1
    provider.write_text(text.replace(old,'const DARWIN-PROTECTED-MAX-FRAMES = 8'))
    variance['components/darwin-protected.in']='test-only ledger bound64 to8; exit stub take-frame must return0 after2image+6stack pages'
tracked=sorted(f for f in snapshot.rglob('*') if f.is_file())
hashes={str(f.relative_to(snapshot)):sha(f) for f in tracked}
report={'status':'running','runner_sha256':sha(Path(__file__).resolve()),'compiler':str(a.compiler),'compiler_sha256':sha(a.compiler),'frozen_source_sha256':hashes,'source_test_variance':variance,'compile_commands':[]}
source=(snapshot/'kernel/kernel-root.in').read_text()
source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(snapshot/m.group(1))),source)
source='import '+json.dumps(str(snapshot/'components/darwin-process-startup.in'))+'\n'+source
assert source.count('  shell(port)')==1
source=source.replace('  shell(port)','  darwin-startup-check(port)')
if a.app:
    import importlib.util
    spec=importlib.util.spec_from_file_location('darwin_requirements',ROOT/'scripts/inspect-darwin-application.py')
    inspector=importlib.util.module_from_spec(spec);spec.loader.exec_module(inspector)
    report['original_application']=inspector.inspect(a.app)
    (a.out/'original-application-requirements.json').write_text(json.dumps(report['original_application'],indent=2)+'\n')
source+=''' 
fn startup-free()->Int{let f=free-list;let n=0;while f!=0 && n<4096{n+=1;f=load64(f);}return n;}
fn startup-string(dest:Int,text:Int)->void{let i=0;let c=-1;while c!=0{c=load8(text+i);store8(dest+i,c);i+=1;}return;}
fn startup-invoke(image:Int,input:Int,serial:Int,budget:Int)->Int{
 let fs=rdmsr(0xC0000100);let gs=rdmsr(0xC0000101);
 wrmsr64(0xC0000100,0x42000000);wrmsr64(0xC0000101,0x42000000);
 let result=darwin-startup-run(image,8192,input,1024,serial,-1,budget);
 let final-fs=rdmsr(0xC0000100);let final-gs=rdmsr(0xC0000101);
 wrmsr64(0xC0000100,fs);wrmsr64(0xC0000101,gs);
 if final-fs!=0x42000000 || final-gs!=0x42000000{panic("Darwin startup caller TLS bases not restored");}
 return result;
}
fn darwin-startup-check(port:Int)->void{
 if dyn-kernel-exportable("darwin-startup-run")!=0 || dyn-kernel-exportable("darwin-startup-copy")!=0 || dyn-resolve-idx("darwin-startup-run")!=-1{panic("Darwin raw startup provider exported");}
 let input=alloc(4096);
 store64(input,2);store64(input+8,input+64);
 store64(input+16,2);store64(input+24,input+88);
 store64(input+32,1);store64(input+40,input+112);
 store64(input+64,input+512);store64(input+72,input+528);store64(input+80,0);
 store64(input+88,input+544);store64(input+96,input+560);store64(input+104,0);
 store64(input+112,input+576);store64(input+120,0);
 startup-string(input+512,"startup-fixture");startup-string(input+528,"two words");
 startup-string(input+544,"A=alpha");startup-string(input+560,"EMPTY=");startup-string(input+576,"executable_path=/fixture");
 let serial=cap-mint(root-realm,cap-serial());let storage=cap-mint(root-realm,cap-storage());let caps=cap-count;
 // First-use caches must fit bump memory even with ample real free frames.
 if darwin-protected-frames!=0 || darwin-startup-context!=0 || darwin-file-table!=0{panic("Darwin first-use proof requires fresh startup caches");}
 let retained=alloc(65*8);let held=0;
 while held<65{store64(retained+held*8,frame-alloc());held+=1;}
 held=0;while held<65{frame-free(load64(retained+held*8));held+=1;}
 let original-end=heap-end;let cold-heap=heap-next;let cold-free=free-list;let cold-domains=domain-count;
 heap-end=heap-next;
 let cold-status=startup-invoke(0x10000000,input,serial,1000);
 heap-end=original-end;
 if cold-status!=-12 || heap-next!=cold-heap || free-list!=cold-free || domain-count!=cold-domains || darwin-protected-frames!=0 || darwin-startup-context!=0{panic("Darwin first-use bump refusal mutated state");}
 heap-end=heap-next+1840;
 let recovered=startup-invoke(0x10000000,input,serial,1000);
 heap-end=original-end;
 if recovered!=42 || heap-next!=cold-heap+1840 || darwin-file-table!=0{panic("Darwin exact first-use bump recovery failed");}
 let file-heap=heap-next;let file-free=free-list;let file-domains=domain-count;
 heap-end=heap-next+8304;
 let file-status=darwin-startup-run(0x10000000,8192,input,1024,serial,storage,1000);
 heap-end=original-end;
 if file-status!=-12 || heap-next!=file-heap || free-list!=file-free || domain-count!=file-domains || darwin-file-table!=0{panic("Darwin file-cache bump refusal mutated state");}
 heap-end=heap-next+8320;
 let file-recovered=darwin-startup-run(0x10000000,8192,input,1024,serial,storage,1000);
 heap-end=original-end;
 if file-recovered!=42 || heap-next!=file-heap+8320 || darwin-file-table==0{panic("Darwin exact file-cache bump recovery failed");}
 cap-revoke(storage);
 // Exercise both maximum64-KiB segments:39 privately owned backing pages.
 let maximum-profile=0;
 while maximum-profile<2{
  let image=0x10000000+maximum-profile*8192;
  let text-vm=load64(image+64);let data-vm=load64(image+136);
  store64(image+64,65536);store64(image+136,65536);store64(image+4096,10);
  let maximum-status=startup-invoke(image,input,serial,1000);
  store64(image+64,text-vm);store64(image+136,data-vm);
  if maximum-status!=42{panic("Darwin maximum mapped segments failed");}
  maximum-profile+=1;
 }
 if serial<0{panic("Darwin startup test serial grant failed");}
 let first=vfs-fd-alloc();let heap=0;let free=0;let domains=0;let executions=0;
 let cycle=0;
 while cycle<21{
  let profile=0;
  while profile<2{
   let image=0x10000000+profile*8192;
   if darwin-startup-entry(image,8192)<0{panic("Darwin startup fixture admission failed");}
   if profile==1 && darwin-protected-entry(image,8192)!=-8{panic("Darwin old profile unexpectedly admitted UNIXTHREAD");}
   let mode=0;
   while mode<8{
    store64(image+4096,mode);store64(image+4104,input);
    let budget=1000;if mode==2{budget=3;}
    let status=startup-invoke(image,input,serial,budget);
    let expected=142;if mode==0{expected=42;}if mode==2{expected=124;}
    if status!=expected{serial-write-cstr(port,"startup: profile ");serial-write-dec-wide(port,profile);serial-write-cstr(port," mode ");serial-write-dec-wide(port,mode);serial-write-cstr(port," status ");serial-write-dec-wide(port,status);serial-nl(port);panic("Darwin startup guest ABI failed");}
    let kind=USER-CONTEXT-FAULT;if mode==0{kind=USER-CONTEXT-EXIT;}if mode==2{kind=USER-CONTEXT-DEADLINE;}
    if darwin-startup-last-kind!=kind{panic("Darwin startup typed stop mismatch");}
    if vfs-fd-alloc()!=first || darwin-protected-count!=0 || darwin-protected-busy!=0 || darwin-protected-domain!=0 || darwin-protected-authority!=-1 || darwin-protected-storage!=-1 || domain-current!=0 || domain-user-syscall-hook!=0 || user-context-active!=0 || user-budget-active!=0 || cap-count!=caps{panic("Darwin startup execution ownership leaked");}
    let retired=darwin-protected-last-domain;
    if load64(domain-table+retired*24)!=0 || load64(domain-table+retired*24+8)!=DOMAIN-FREE{panic("Darwin startup domain not retired");}
    executions+=1;mode+=1;
   }
   profile+=1;
  }
  if cycle==0{heap=heap-next;free=startup-free();domains=domain-count;}
  else{if heap-next!=heap || startup-free()!=free || domain-count!=domains{panic("Darwin startup repeated resources grew");}}
  cycle+=1;
 }
 // Exact supported vector-count boundaries in both genuine entry contracts.
 let boundary-profile=0;
 while boundary-profile<2{
  let image=0x10000000+boundary-profile*8192;
  store64(input,0);store64(input+16,0);store64(input+32,0);
  store64(input+8,input+64);store64(input+24,input+88);store64(input+40,input+112);
  store64(input+64,0);store64(input+88,0);store64(input+112,0);
  store64(image+4096,8);
  if startup-invoke(image,input,serial,1000)!=42{panic("Darwin startup empty vectors failed");}
  store64(input,16);store64(input+16,16);store64(input+32,16);
  store64(input+8,input+64);store64(input+24,input+208);store64(input+40,input+352);
  startup-string(input+512,"x");let group=0;
  while group<3{let vec=load64(input+group*16+8);let n=0;while n<16{store64(vec+n*8,input+512);n+=1;}store64(vec+128,0);group+=1;}
  store64(image+4096,9);
  if startup-invoke(image,input,serial,1000)!=42{panic("Darwin startup maximum vectors failed");}
  boundary-profile+=1;
 }
 store64(input,2);store64(input+16,2);store64(input+32,1);
 store64(input+8,input+64);store64(input+24,input+88);store64(input+40,input+112);
 store64(input+64,input+512);store64(input+72,input+528);store64(input+80,0);
 store64(input+88,input+544);store64(input+96,input+560);store64(input+104,0);
 store64(input+112,input+576);store64(input+120,0);
 startup-string(input+512,"startup-fixture");
 let image=0x10000000;
 // Invalid inputs are rejected before mapping/allocating a process.
 store64(input,17);if startup-invoke(image,input,serial,1000)!=-22{panic("Darwin startup count bound failed");}store64(input,2);
 store64(input+8,input+1020);if startup-invoke(image,input,serial,1000)!=-14{panic("Darwin startup vector span failed");}store64(input+8,input+64);
 store64(input+80,1);if startup-invoke(image,input,serial,1000)!=-22{panic("Darwin startup vector terminator failed");}store64(input+80,0);
 store64(input+64,input+1024);if startup-invoke(image,input,serial,1000)!=-14{panic("Darwin startup string pointer failed");}store64(input+64,input+512);
 let i=0;while i<256{store8(input+768+i,65);i+=1;}
 store64(input+64,input+768);if startup-invoke(image,input,serial,1000)!=-7{panic("Darwin startup string length failed");}store64(input+64,input+512);
 if darwin-startup-run(image,8192,input,47,serial,-1,1000)!=-14 || darwin-startup-run(image,8192,input,4097,serial,-1,1000)!=-14{panic("Darwin startup span length failed");}
 let wrong=cap-mint(root-realm,cap-storage());
 if startup-invoke(image,input,wrong,1000)!=-13{panic("Darwin startup serial authority failed");}cap-revoke(wrong);
 let saved=load32(image+176);store32(image+176,5);
 if darwin-startup-entry(image,8192)!=-8{panic("Darwin mixed entry command accepted");}store32(image+176,saved);
 let thread=0x10002000;store64(thread+248,0x4F003E00);
 if darwin-startup-entry(thread,8192)!=-8{panic("Darwin unowned UNIXTHREAD state accepted");}store64(thread+248,0);
 if heap-next!=heap || startup-free()!=free || domain-count!=domains || vfs-fd-alloc()!=first{panic("Darwin startup refused input allocated resources");}
 cap-revoke(serial);
 serial-write-cstr(port,"darwin-startup: 21 cycles 344 CPL3 executions and input refusals PASS");serial-nl(port);
 outb(0xF4,16);
}
'''
if a.ledger_limit_control:
    start=source.index('fn darwin-startup-check(port:Int)->void{')
    setup=source[source.index(' let input=alloc(4096);',start):source.index(' let serial=cap-mint',start)]
    source=source[:start]+'fn darwin-startup-check(port:Int)->void{\n'+setup+'''
 let cycle=0;let heap=0;let free=0;let domains=0;let first=vfs-fd-alloc();let caps=cap-count;
 while cycle<21{
  let status=darwin-startup-run(0x10000000,8192,input,1024,-1,-1,1000);
  if status!=-12 || darwin-protected-count!=0 || darwin-protected-busy!=0 || darwin-protected-domain!=0 || domain-current!=0 || user-context-active!=0 || domain-user-syscall-hook!=0 || user-budget-active!=0 || cap-count!=caps || vfs-fd-alloc()!=first{panic("Darwin stub-zero error cleanup failed");}
  let retired=darwin-protected-last-domain;
  if load64(domain-table+retired*24)!=0 || load64(domain-table+retired*24+8)!=DOMAIN-FREE{panic("Darwin stub-zero domain retained");}
  if cycle==0{heap=heap-next;free=startup-free();domains=domain-count;}
  else{if heap-next!=heap || startup-free()!=free || domain-count!=domains{panic("Darwin stub-zero resources grew");}}
  cycle+=1;
 }
 serial-write-cstr(port,"darwin-startup: actual stub-zero21 cleanup cycles PASS");serial-nl(port);outb(0xF4,16);
}
'''
if a.app:
    source=source.replace(' cap-revoke(serial);',f''' let refusal-heap=heap-next;let refusal-free=free-list;let refusal-domains=domain-count;
 if darwin-startup-run(0x11000000,{a.app.stat().st_size},input,1024,serial,-1,1000)!=-8 || heap-next!=refusal-heap || free-list!=refusal-free || domain-count!=refusal-domains{{panic("original macOS jq startup refusal changed resources");}}
 cap-revoke(serial);''')
(a.out/'kernel.in').write_text(source)
try:
    commands=[['nasm','-f','bin',str(snapshot/'boot/multiboot.asm'),'-o',str(a.out/'trampoline.bin')]]
    for name,thread in [('main',0),('thread',1)]:
        commands.append(['nasm','-f','bin',f'-DTHREAD={thread}',str(snapshot/'fixtures/darwin-startup/process.asm'),'-o',str(a.out/(name+'.macho'))])
    commands.append([str(a.compiler),'compile','--path',str(a.out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(a.out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(a.out/'kernel.bin')])
    with (a.out/'compile.log').open('w') as log:
        for command in commands:
            report['compile_commands'].append(command)
            subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    # Independent host structural oracle over real Mach-O commands.
    report['fixtures']=[]
    for name,kind in [('main',0x80000028),('thread',5)]:
        payload=(a.out/(name+'.macho')).read_bytes()
        assert len(payload)==8192 and struct.unpack_from('<7I',payload)[:5]==(0xfeedfacf,0x1000007,3,2,3)
        offset=32;commands=[]
        for _ in range(3):
            cmd,length=struct.unpack_from('<II',payload,offset)
            assert length>=8 and offset+length<=len(payload)
            commands.append((cmd,length));offset+=length
        assert commands==[(0x19,72),(0x19,72),(kind,24 if name=='main' else 184)]
        assert offset==32+struct.unpack_from('<I',payload,20)[0]
        report['fixtures'].append({'name':name,'commands':commands,'sha256':sha(a.out/(name+'.macho'))})
    assert (a.out/'kernel.bin').stat().st_size < 0xff00000
    command=['qemu-system-x86_64','-kernel',str(a.out/'kernel.bin'),'-m','512M','-display','none','-no-reboot','-serial','file:'+str(a.out/'serial.log'),'-device','isa-debug-exit,iobase=0xf4,iosize=0x04']
    for name,addr in [('main',0x10000000),('thread',0x10002000)]:
        command+=['-device',f'loader,file={a.out/(name+".macho")},addr={addr},force-raw=on']
    if a.app:command+=['-device',f'loader,file={a.app.resolve()},addr=0x11000000,force-raw=on']
    report['qemu_command']=command
    with (a.out/'qemu.log').open('w') as log:run=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=90)
    serial=(a.out/'serial.log').read_text()
    expected='darwin-startup: actual stub-zero21 cleanup cycles PASS' if a.ledger_limit_control else 'darwin-startup: 21 cycles 344 CPL3 executions and input refusals PASS'
    assert run.returncode==33 and expected in serial,serial[-6000:]
    report['frozen_source_changed_during_run']=[name for name,digest in hashes.items() if sha(snapshot/name)!=digest]
    assert not report['frozen_source_changed_during_run']
    report.update(status='passed',cycles=21,executions=0 if a.ledger_limit_control else 344,kernel_sha256=sha(a.out/'kernel.bin'))
    if a.app:report['original_application']['actual_startup_admission']=-8
    print('PASS actual exit-stub capacity refusal and21 cleanup cycles (test-only ledger bound8; no guest executions)' if a.ledger_limit_control else 'PASS actual LC_MAIN and UNIXTHREAD, owned arguments/process stack/return, FS/GS isolation, fault/deadline cleanup and bounded input refusals',flush=True)
except Exception as error:
    report.update(status='failed',error=str(error));print('FAIL:',error,flush=True)
finally:(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='passed' else 1)
