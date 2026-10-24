#!/usr/bin/env python3
"""Prove bounded owned Windows heaps with protected execution and cleanup."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import socket
import struct
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();out=a.out.resolve();a.compiler=a.compiler.resolve()
assert not out.exists() or not any(out.iterdir()),'--out must be new or empty'
out.mkdir(parents=True,exist_ok=True)
def absolute_imports(source):
    return re.sub(r'import "([^"]+)"',lambda m:'import '+json.dumps(str((ROOT/'components'/m.group(1)).resolve())),source)


protected=absolute_imports((ROOT/'components/windows-protected.in').read_text())
assert protected.count('domain-user-syscall-hook = windows-protected-dispatch')==1
protected=protected.replace('domain-user-syscall-hook = windows-protected-dispatch','domain-user-syscall-hook = windows-heap-test-dispatch')
(out/'windows-protected.in').write_text(protected)
hub=absolute_imports((ROOT/'components/personality-hub.in').read_text()).replace(json.dumps(str(ROOT/'components/windows-protected.in')),json.dumps(str(out/'windows-protected.in')))
(out/'personality-hub.in').write_text(hub)
source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(ROOT/m.group(1))),(ROOT/'kernel/kernel-root.in').read_text()).replace(json.dumps(str(ROOT/'components/personality-hub.in')),json.dumps(str(out/'personality-hub.in')))
assert source.count('  shell(port)')==1
source=source.replace('  shell(port)','  windows-heap-check(port)\n  shell(port)')
source+=r'''
var windows-heap-test-scratch:Int=0
var windows-heap-test-last-handle:Int=0
var windows-heap-test-calls:Int=0
fn windows-heap-test-dispatch(frame:Int)->Int{
 let num=load64(frame+112);
 if num==0x100100{if windows-protected-profile!=7 || windows-protected-domain!=domain-current{panic("Heap control owner mismatch");}cap-revoke(windows-parameters-heap-authority);store64(frame+112,0);return 1;}
 let observed=0;let saved=windows-protected-error;
 if num>=0x100018 && num<=0x10001c{observed=1;let i=0;while i<3072{store8(windows-heap-test-scratch+i,load8(windows-parameters-heap-records+i));i=i+1;}i=0;while i<64{store8(windows-heap-test-scratch+3072+i,load8(windows-protected-physical(WINDOWS-PARAMETERS-HEAP-BASE+i)));i=i+1;}}
 let control=windows-protected-dispatch(frame);
 if observed!=0{
  windows-heap-test-calls=windows-heap-test-calls+1;let value=load64(frame+112);let failure=0;if num==0x10001c{failure=-1;}
  if value==failure{let i=0;while i<3072{if load8(windows-heap-test-scratch+i)!=load8(windows-parameters-heap-records+i){panic("Failed heap API mutated ledger");}i=i+1;}i=0;while i<64{if load8(windows-heap-test-scratch+3072+i)!=load8(windows-protected-physical(WINDOWS-PARAMETERS-HEAP-BASE+i)){panic("Failed heap API mutated payload");}i=i+1;}}
  if num==0x100019 || num==0x10001b{
   if windows-protected-error!=saved{panic("HeapAlloc/ReAlloc changed LastError");}
   if value!=0{if (value&15)!=0 || value<WINDOWS-PARAMETERS-HEAP-BASE || value>=WINDOWS-PARAMETERS-HEAP-BASE+WINDOWS-PARAMETERS-HEAP-BYTES || (domain-page-flags(windows-protected-domain,value)&(PAGE-NX|7))!=(PAGE-NX|7){panic("Heap allocation violates owned RW/NX alignment");}}
  }
  if num==0x100018 && value!=0{windows-heap-test-last-handle=value;windows-protected-store32(0x140005010,windows-parameters-heap-records);windows-protected-store32(0x140005014,0);}
 }
 return control;
}
fn windows-heap-test-free()->Int{let n=0;let f=free-list;while f!=0 && n<4096{n=n+1;f=load64(f);}return n;}
fn windows-heap-test-clean()->void{
 if windows-protected-count!=0 || windows-protected-busy!=0 || windows-protected-profile!=0 || windows-parameters-active!=0 || windows-parameters-heap-active!=0 || windows-parameters-heap-authority!=-1 || windows-parameters-heap-records!=0 || windows-parameters-heap-handle!=0 || domain-user-syscall-hook!=0 || user-budget-active!=0 || domain-current!=0{panic("Windows heap ownership leaked");}
}
fn windows-heap-test-refuse(image:Int,memory:Int,bytes:Int,expected:Int)->void{
 let heap=heap-next;let free=free-list;let domains=domain-count;let generation=windows-parameters-heap-generation;let line="sqlite3.exe -version";
 if windows-command-heap-run(image,7168,-1,-1,memory,line,bytes)!=expected || heap-next!=heap || free-list!=free || domain-count!=domains || windows-parameters-heap-generation!=generation{panic("Heap admission mutated activation");}windows-heap-test-clean();
}
fn windows-heap-check(port:Int)->void{
 let image=0x10000000;if heap-next>=image{panic("Heap fixture collides with native heap");}heap-end=image;
 windows-heap-test-scratch=alloc(3200);let memory=cap-mint(root-realm,cap-memory());let weak=cap-mint(root-realm,cap-serial());let revoked=cap-mint(root-realm,cap-memory());cap-revoke(revoked);let line="sqlite3.exe -version";let bytes=strlen(line)+1;
 if windows-command-run(image,7168,-1,-1,line,bytes)!=-8 || windows-application-entry(image,7168)!=-8 || windows-startup-entry(image,7168)!=-8{panic("Earlier Windows profiles widened heap imports");}
 windows-heap-test-refuse(image,-1,bytes,-13);windows-heap-test-refuse(image,weak,bytes,-13);windows-heap-test-refuse(image,revoked,bytes,-13);windows-heap-test-refuse(image,memory,0,-22);
 let magic=load32(image);store32(image,0);windows-heap-test-refuse(image,memory,bytes,-8);store32(image,magic);
 let saved-free=free-list;let saved-end=heap-end;free-list=0;heap-end=heap-next;windows-heap-test-refuse(image,memory,bytes,-12);free-list=saved-free;heap-end=saved-end;
 let generation=windows-parameters-heap-generation;windows-parameters-heap-generation=0x7fffffff;windows-heap-test-refuse(image,memory,bytes,-12);windows-parameters-heap-generation=generation;
 let fs=rdmsr(0xc0000100);let gs=rdmsr(0xc0000101);wrmsr64(0xc0000100,0x140005000);wrmsr64(0xc0000101,0x23456000);
 let cycle=0;let heap=0;let free=0;let domains=0;let caps=cap-count;
 while cycle<21{let mode=0;while mode<24{if mode!=16{
  store64(image+5120,mode);store64(image+5128,windows-heap-test-last-handle);if mode==15{windows-protected-budget=5;}
  windows-heap-test-calls=0;let result=windows-command-heap-run(image,7168,-1,-1,memory,line,bytes);windows-protected-budget=100;let expected=42;if mode==13 || mode==14 || mode==23{expected=142;}if mode==15{expected=124;}
  if result!=expected{serial-write-dec-wide(port,mode);serial-put(port,32);serial-write-dec-wide(port,result);panic("Windows heap guest result mismatch");}
  windows-heap-test-clean();if rdmsr(0xc0000100)!=0x140005000 || rdmsr(0xc0000101)!=0x23456000 || cap-count!=caps || cap-check(memory,cap-memory())==0{panic("Heap context or borrowed grant changed");}
 }mode=mode+1;}
 if cycle==0{heap=heap-next;free=windows-heap-test-free();domains=domain-count;}else{if heap-next!=heap || windows-heap-test-free()!=free || domain-count!=domains{panic("Windows heap repeated cleanup leaked");}}cycle=cycle+1;}
 let live=cap-mint(root-realm,cap-memory());store64(image+5120,16);
 if windows-command-heap-run(image,7168,-1,-1,live,line,bytes)!=42 || cap-check(live,cap-memory())!=0{panic("Heap live revoke failed");}windows-heap-test-clean();
 store64(image+5120,0);if windows-command-heap-run(image,7168,-1,-1,memory,line,bytes)!=42{panic("Heap fresh activation after revoke failed");}windows-heap-test-clean();
 if heap-next!=heap || windows-heap-test-free()!=free || domain-count!=domains{panic("Heap revoke/fresh cleanup leak");}
 wrmsr64(0xc0000100,fs);wrmsr64(0xc0000101,gs);cap-revoke(memory);cap-revoke(weak);
 serial-write-cstr(port,"windows-heap: 485 executions owned RW NX alignment zero calloc realloc atomic limits invalid handles pointers free revoke fault deadline stable cleanup PASS");serial-nl(port);
}
'''
names=['components/windows-process-heap.in','components/windows-process-parameters.in','components/windows-protected.in','components/windows-pe-application.in','fixtures/windows-protected/heap.asm','boot/multiboot.asm','components/user-budget.in']
source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
(out/'kernel.in').write_text(source)
commands=[['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],['nasm','-f','bin',str(ROOT/'fixtures/windows-protected/heap.asm'),'-o',str(out/'process.exe')],[str(a.compiler),'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')]]
with (out/'compile.log').open('w') as log:
 for command in commands:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
kernel=(out/'kernel.bin').read_bytes();payload=(out/'process.exe').read_bytes();assert len(payload)==7168 and 0x100000+len(kernel)<0x10000000
path=out/'serial.sock';received=bytearray();serial=None
qemu_command=['qemu-system-x86_64','-kernel',str(out/'kernel.bin'),'-m','512M','-display','none','-no-reboot','-serial',f'unix:{path},server=on,wait=on','-device',f'loader,file={out/"process.exe"},addr=0x10000000,force-raw=on']
with (out/'qemu.log').open('w') as log:
 qemu=subprocess.Popen(qemu_command,stdout=log,stderr=subprocess.STDOUT)
 try:
  deadline=time.monotonic()+10
  while not path.exists() and qemu.poll() is None and time.monotonic()<deadline:time.sleep(.02)
  serial=socket.socket(socket.AF_UNIX);serial.settimeout(.2);serial.connect(str(path));deadline=time.monotonic()+180
  while b'space> ' not in received and time.monotonic()<deadline:
   try:
    block=serial.recv(65536)
    if not block:break
    received.extend(block)
    if b'PANIC' in received or b'nanokernel fault handler halting' in received:break
   except socket.timeout:
    if qemu.poll() is not None:break
  text=received.decode(errors='replace');assert 'windows-heap: 485 executions owned RW NX alignment zero calloc realloc atomic limits invalid handles pointers free revoke fault deadline stable cleanup PASS' in text and 'space> ' in text,text
 finally:
  (out/'serial.log').write_bytes(received)
  if serial:serial.close()
  qemu.terminate()
  try:qemu.wait(timeout=5)
  except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
names=['components/windows-process-heap.in','components/windows-process-parameters.in','components/windows-protected.in','components/windows-pe-application.in','fixtures/windows-protected/heap.asm','boot/multiboot.asm','components/user-budget.in']
report=dict(status='passed',executions=485,admission_refusals=7,compiler_sha256=hashlib.sha256(a.compiler.read_bytes()).hexdigest(),kernel_sha256=hashlib.sha256(kernel).hexdigest(),fixture_sha256=hashlib.sha256(payload).hexdigest(),source_sha256=source_hashes,source_changed=[name for name,value in source_hashes.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=value],commands=commands,qemu_command=qemu_command)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS Windows owned heap 485 executions')
