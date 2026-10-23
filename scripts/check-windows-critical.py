#!/usr/bin/env python3
"""Prove actual bounded Windows critical sections and ownership refusals."""
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
protected=protected.replace('domain-user-syscall-hook = windows-protected-dispatch','domain-user-syscall-hook = windows-critical-test-dispatch')
(out/'windows-protected.in').write_text(protected)
hub=absolute_imports((ROOT/'components/personality-hub.in').read_text()).replace(json.dumps(str(ROOT/'components/windows-protected.in')),json.dumps(str(out/'windows-protected.in')))
(out/'personality-hub.in').write_text(hub)
source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(ROOT/m.group(1))),(ROOT/'kernel/kernel-root.in').read_text()).replace(json.dumps(str(ROOT/'components/personality-hub.in')),json.dumps(str(out/'personality-hub.in')))
assert source.count('  shell(port)')==1
source=source.replace('  shell(port)','  windows-critical-check(port)\n  shell(port)')
source+=r'''

var windows-critical-test-scratch:Int=0
fn windows-critical-test-address(i:Int)->Int{if i<40{return 0x140005100+i;}return 0x140005000+8168+i - 40;}
fn windows-critical-test-dispatch(frame:Int)->Int{
 let num=load64(frame+112);let mode=windows-protected-load64(0x140005000);
 if num==0x100100{
  if windows-protected-profile!=9 || domain-current!=windows-protected-domain{panic("Critical control owner mismatch");}
  let op=load64(frame+96);let address=0x140005100;let row=windows-parameters-critical-find(address);
  if op==0 || op==1{store64(row+8,1);store64(row+24,2);if op==1{store64(row+8,0x7fffffff);store64(row+24,1);}windows-parameters-critical-write(row);}
  if op==2{cap-revoke(windows-parameters-heap-authority);}
  if op==3{windows-protected-store32(0x140005010,windows-parameters-critical-data);windows-protected-store32(0x140005014,0);}
  if op==4{domain-map-user-readonly(windows-protected-domain,0x140005000,windows-protected-physical(0x140005000));}
  store64(frame+112,0);return 1;
 }
 let observing=0;let address=load64(frame+96);let readable=0;
 if num>=0x100025 && num<=0x10002a{
  observing=1;if windows-protected-count!=windows-protected-owned-pages(0x10000000,9){panic("Critical ledger backing mismatch");}
  let i=0;while i<2048{store8(windows-critical-test-scratch+i,load8(windows-parameters-critical-data+i));i=i+1;}
  i=0;while i<64{store8(windows-critical-test-scratch+2048+i,load8(windows-protected-physical(windows-critical-test-address(i))));i=i+1;}
  readable=windows-protected-span(address,40,0);if readable!=0{i=0;while i<40{store8(windows-critical-test-scratch+2112+i,load8(windows-protected-physical(address+i)));i=i+1;}}
 }
 let control=windows-protected-dispatch(frame);
 if observing!=0{
  let failed=0;if control==0{failed=1;}if (num==0x100026 || num==0x100028) && load64(frame+112)==0{failed=1;}
  if failed!=0{
   let i=0;while i<2048{if load8(windows-critical-test-scratch+i)!=load8(windows-parameters-critical-data+i){panic("Failed critical API mutated native ledger");}i=i+1;}
   i=0;while i<64{if load8(windows-critical-test-scratch+2048+i)!=load8(windows-protected-physical(windows-critical-test-address(i))){panic("Failed critical API partial guest write");}i=i+1;}
   if readable!=0{i=0;while i<40{if load8(windows-critical-test-scratch+2112+i)!=load8(windows-protected-physical(address+i)){panic("Failed critical API changed target");}i=i+1;}}
  }
 }
 return control;
}
fn windows-critical-test-free()->Int{let n=0;let f=free-list;while f!=0 && n<4096{n=n+1;f=load64(f);}return n;}
fn windows-critical-test-clean()->void{
 if windows-protected-count!=0 || windows-protected-busy!=0 || windows-protected-profile!=0 || windows-parameters-active!=0 || windows-parameters-heap-active!=0 || windows-parameters-heap-authority!=-1 || windows-parameters-heap-records!=0 || windows-parameters-heap-handle!=0 || windows-parameters-critical-data!=0 || domain-user-syscall-hook!=0 || user-budget-active!=0 || domain-current!=0{panic("Critical ownership leaked");}
}
fn windows-critical-check(port:Int)->void{
 let image=0x10000000;if heap-next>=image{panic("Critical fixture collision");}heap-end=image;
 let private=boot-image-find(254);if private==0 || dyn-resolve-idx("serial-write-cstr")<0 || dyn-resolve-idx("windows-parameters-critical-dispatch")!=-1 || dyn-resolve-idx("windows-command-critical-run")!=-1{panic("Critical registry visibility mismatch");}
 let before=heap-next;let caps-before=cap-count;let domains-before=domain-count;let live-before=runtime-instance-live;
 if sci-load-runtime-component(port,private,"private-critical",1,1,0)!=-1 || heap-next!=before || cap-count!=caps-before || domain-count!=domains-before || runtime-instance-live!=live-before{panic("Actual private critical SCI import admitted/allocated");}
 serial-write-cstr(port,"windows-critical-registry: actual valid SCI private helper import refused before allocation PASS");serial-nl(port);
 windows-critical-test-scratch=alloc(2304);let memory=cap-mint(root-realm,cap-memory());let weak=cap-mint(root-realm,cap-serial());let line="sqlite3.exe -version";let bytes=strlen(line)+1;
 if windows-command-heap-run(image,8192,-1,-1,memory,line,bytes)!=-8 || windows-command-local-run(image,8192,-1,-1,memory,line,bytes)!=-8 || windows-command-run(image,8192,-1,-1,line,bytes)!=-8{panic("Existing profiles widened critical imports");}
 before=heap-next;let free-head=free-list;domains-before=domain-count;
 if windows-command-critical-run(image,8192,-1,-1,weak,line,bytes)!=-13 || heap-next!=before || free-list!=free-head || domain-count!=domains-before{panic("Critical weak grant admission mutated");}windows-critical-test-clean();
 // Reserve first-use bump caches independently of real free frames; prove
 // the new native critical ledger consumes one additional frame reservation.
 if windows-protected-frames!=0 || windows-parameters-critical-data!=0{panic("Critical cold reserve was warmed");}
 let held=alloc(200*8);let i=0;while i<200{store64(held+i*8,frame-alloc());i=i+1;}
 if free-list!=0{panic("Critical cold fixture needs a fully owned free pool");}
 i=0;while i<158{frame-free(load64(held+i*8));i=i+1;}
 let original-end=heap-end;let cold-heap=heap-next;let cold-free=free-list;let cold-domains=domain-count;
 heap-end=heap-next+26912;
 let refused=windows-command-critical-run(image,8192,-1,-1,memory,line,bytes);heap-end=original-end;
 if refused!=-12 || heap-next!=cold-heap || free-list!=cold-free || domain-count!=cold-domains || windows-protected-frames!=0{panic("Critical missing ledger frame admission mutated");}windows-critical-test-clean();
 frame-free(load64(held+158*8));heap-end=heap-next+26912;store64(image+6144,0);
 let recovered=windows-command-critical-run(image,8192,-1,-1,memory,line,bytes);heap-end=original-end;
 if recovered!=42 || heap-next!=cold-heap+26912 || windows-critical-test-free()!=159{panic("Critical exact retained and frame recovery failed");}windows-critical-test-clean();
 i=159;while i<200{frame-free(load64(held+i*8));i=i+1;}
 serial-write-cstr(port,"windows-critical-cold:158 frames refuse159 recover exact26912 bump bytes PASS");serial-nl(port);
 let fs=rdmsr(0xc0000100);let gs=rdmsr(0xc0000101);wrmsr64(0xc0000100,0x140005000);wrmsr64(0xc0000101,0x23456000);
 let cycle=0;let heap=0;let free=0;let domains=0;let caps=cap-count;
 while cycle<21{let mode=0;while mode<32{if mode!=20{
  store64(image+6144,mode);if mode==24{windows-protected-budget=5;}
  let result=windows-command-critical-run(image,8192,-1,-1,memory,line,bytes);windows-protected-budget=100;
  let expected=42;if mode==11 || mode==12 || mode==14 || mode==15 || mode==17 || mode==18 || mode==19 || mode==29 || mode==30 || mode==31{expected=127;}
  if mode==16 || mode==22 || mode==23 || mode==28{expected=142;}if mode==24{expected=124;}
  if result!=expected{serial-write-dec-wide(port,mode);serial-put(port,32);serial-write-dec-wide(port,result);panic("Critical actual result mismatch");}
  windows-critical-test-clean();if rdmsr(0xc0000100)!=0x140005000 || rdmsr(0xc0000101)!=0x23456000 || cap-count!=caps || cap-check(memory,cap-memory())==0{panic("Critical context/live grant changed");}
 }mode=mode+1;}
 if cycle==0{heap=heap-next;free=windows-critical-test-free();domains=domain-count;}else{if heap-next!=heap || windows-critical-test-free()!=free || domain-count!=domains{panic("Critical repeated cleanup leaked");}}cycle=cycle+1;}
 let live=cap-mint(root-realm,cap-memory());store64(image+6144,20);
 if windows-command-critical-run(image,8192,-1,-1,live,line,bytes)!=126 || cap-check(live,cap-memory())!=0{panic("Critical live revoke did not stop void API");}windows-critical-test-clean();
 store64(image+6144,0);if windows-command-critical-run(image,8192,-1,-1,memory,line,bytes)!=42{panic("Fresh critical activation failed");}windows-critical-test-clean();
 if heap-next!=heap || windows-critical-test-free()!=free || domain-count!=domains{panic("Critical revoke/fresh cleanup leak");}
 wrmsr64(0xc0000100,fs);wrmsr64(0xc0000101,gs);cap-revoke(memory);cap-revoke(weak);
 serial-write-cstr(port,"windows-critical:653 protected activations real recursive ownership try leave delete init limits reuse pointers no partial writes foreignowner denial live revoke fault deadline stable cleanup PASS");serial-nl(port);
}
'''
names=['components/windows-process-critical.in','components/windows-process-heap.in','components/windows-process-parameters.in','components/windows-protected.in','components/windows-pe-application.in','fixtures/windows-protected/critical.asm','fixtures/windows-protected/critical-private.in','boot/multiboot.asm','components/user-budget.in']
source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
(out/'kernel.in').write_text(source)
commands=[['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],['nasm','-f','bin',str(ROOT/'fixtures/windows-protected/critical.asm'),'-o',str(out/'process.exe')],[str(a.compiler),'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')]]
commands.insert(0,[str(a.compiler),'compile','--path',str(ROOT/'fixtures/windows-protected/critical-private.in'),'--entry','private-entry','--emit','sci','--base','0x7a000000','--target','native','--target-triple','x86_64-unknown-none','--out',str(out/'private.sci')])
commands.append(['python',str(ROOT/'scripts/pack-sci-image.py'),str(out/'kernel.bin'),str(out/'combined.bin'),f'254:{out}/private.sci'])
with (out/'compile.log').open('w') as log:
 for command in commands:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
kernel=(out/'combined.bin').read_bytes();payload=(out/'process.exe').read_bytes();assert len(payload)==8192 and 0x100000+len(kernel)<0x10000000
path=out/'serial.sock';received=bytearray();serial=None
qemu_command=['qemu-system-x86_64','-kernel',str(out/'combined.bin'),'-m','512M','-display','none','-no-reboot','-serial',f'unix:{path},server=on,wait=on','-device',f'loader,file={out/"process.exe"},addr=0x10000000,force-raw=on']
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
  text=received.decode(errors='replace');assert 'INVALID private critical entry' not in text and 'windows-critical-cold:158 frames refuse159 recover exact26912 bump bytes PASS' in text;assert 'windows-critical:653 protected activations real recursive ownership try leave delete init limits reuse pointers no partial writes foreignowner denial live revoke fault deadline stable cleanup PASS' in text and 'space> ' in text,text
 finally:
  (out/'serial.log').write_bytes(received)
  if serial:serial.close()
  qemu.terminate()
  try:qemu.wait(timeout=5)
  except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
report=dict(status='passed',executions=654,focused_activations=653,cold_recovery_activations=1,admission_refusals=2,private_sci_import_refusal=True,compiler_sha256=hashlib.sha256(a.compiler.read_bytes()).hexdigest(),kernel_sha256=hashlib.sha256(kernel).hexdigest(),fixture_sha256=hashlib.sha256(payload).hexdigest(),private_sci_sha256=hashlib.sha256((out/'private.sci').read_bytes()).hexdigest(),source_sha256=source_hashes,source_changed=[name for name,value in source_hashes.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=value],commands=commands,qemu_command=qemu_command)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS Windows critical653 activations and actual private SCI denial')
