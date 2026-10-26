#!/usr/bin/env python3
"""Prove versioned Windows TLS/FLS and actual protected callbacks."""
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
p.add_argument('--boots',type=int,choices=range(1,17),default=1,help='repeat the same compiled image in fresh VMs')
a=p.parse_args();out=a.out.resolve();a.compiler=a.compiler.resolve()
assert not out.exists() or not any(out.iterdir()),'--out must be new or empty'
out.mkdir(parents=True,exist_ok=True)
def absolute_imports(source):
    return re.sub(r'import "([^"]+)"',lambda m:'import '+json.dumps(str((ROOT/'components'/m.group(1)).resolve())),source)


protected=absolute_imports((ROOT/'components/windows-protected.in').read_text())
assert protected.count('domain-user-syscall-hook = windows-protected-dispatch')==1
protected=protected.replace('domain-user-syscall-hook = windows-protected-dispatch','domain-user-syscall-hook = windows-local-test-dispatch')
(out/'windows-protected.in').write_text(protected)
hub=absolute_imports((ROOT/'components/personality-hub.in').read_text()).replace(json.dumps(str(ROOT/'components/windows-protected.in')),json.dumps(str(out/'windows-protected.in')))
(out/'personality-hub.in').write_text(hub)
source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(ROOT/m.group(1))),(ROOT/'kernel/kernel-root.in').read_text()).replace(json.dumps(str(ROOT/'components/personality-hub.in')),json.dumps(str(out/'personality-hub.in')))
assert source.count('  shell(port)')==1
source=source.replace('  shell(port)','  windows-local-check(port)\n  shell(port)')
source+=r'''

var windows-local-test-callbacks:Int=0
var windows-local-test-failed:Int=0
var windows-local-test-completions:Int=0
fn windows-local-test-dispatch(frame:Int)->Int{
 if load64(frame+112)==0x100100{if windows-protected-profile!=8{panic("Local control owner mismatch");}cap-revoke(windows-parameters-heap-authority);store64(frame+112,0);return 1;}
 if windows-protected-count!=windows-protected-owned-pages(0x10000000,8){panic("Windows owned ledger budget mismatch");}
 let num=load64(frame+112);let control=windows-protected-dispatch(frame);
 if control==2 && windows-parameters-local-pending==1 && windows-protected-load64(0x140005000)==21{store64(frame+136,load64(frame+136)|65536);}
 windows-local-test-callbacks=windows-protected-load64(0x140005018);windows-local-test-failed=windows-protected-load64(0x140005028);
 if num==0x100103{windows-local-test-completions=windows-local-test-completions+1;}
 return control;
}
fn windows-local-test-free()->Int{let n=0;let f=free-list;while f!=0 && n<4096{n=n+1;f=load64(f);}return n;}
fn windows-local-test-clean()->void{
 if windows-protected-count!=0 || windows-protected-busy!=0 || windows-protected-profile!=0 || windows-parameters-active!=0 || windows-parameters-heap-active!=0 || windows-parameters-heap-authority!=-1 || windows-parameters-heap-records!=0 || windows-parameters-heap-handle!=0 || windows-parameters-local-data!=0 || windows-parameters-local-pending!=0 || windows-parameters-local-callback!=0 || windows-parameters-local-budget!=0 || domain-user-syscall-hook!=0 || user-context-active!=0 || user-budget-active!=0 || domain-current!=0{panic("Windows local ownership leaked");}
}
fn windows-local-test-cold()->void{
 if windows-protected-frames!=0 || windows-protected-virtuals!=0 || windows-protected-context!=0 || windows-protected-files!=0 || windows-protected-paths!=0 || windows-protected-buffer!=0 || windows-protected-shares!=0{panic("Windows cold cache mutation");}
}
fn windows-local-check(port:Int)->void{
 let image=0x10000000;if heap-next>=image{panic("Local fixture collision");}heap-end=image;
 let fx-before=alloc(512);let fx-after=alloc(512);let memory=cap-mint(root-realm,cap-memory());let weak=cap-mint(root-realm,cap-serial());let line="sqlite3.exe -version";let bytes=strlen(line)+1;
 if windows-command-heap-run(image,7680,-1,-1,memory,line,bytes)!=-8 || windows-command-run(image,7680,-1,-1,line,bytes)!=-8{panic("Existing profiles widened TLS/FLS");}
 let before=heap-next;let free-head=free-list;let domains-before=domain-count;
 if windows-command-local-run(image,7680,-1,-1,weak,line,bytes)!=-13 || heap-next!=before || free-list!=free-head || domain-count!=domains-before{panic("Local authority refusal allocated");}
 // Prove cold retained buffers need bump bytes even with200 real free pages.
 if windows-protected-frames!=0 || windows-protected-virtuals!=0 || windows-protected-context!=0 || windows-protected-files!=0 || windows-protected-paths!=0 || windows-protected-buffer!=0 || windows-protected-shares!=0{panic("Local cold cache proof was warmed");}
 if windows-protected-owned-pages(image,8)!=83 || 1024+72>WINDOWS-PROTECTED-MAX-FRAMES{panic("Local maximum ledger bound mismatch");}
 let held=alloc(200*8);let i=0;while i<200{store64(held+i*8,frame-alloc());i=i+1;}i=0;while i<200{frame-free(load64(held+i*8));i=i+1;}
 let cold-heap=heap-next;let cold-free=free-list;let cold-domains=domain-count;let cold-owned=domain-user-owned;let original-end=heap-end;
 let bound=0;while bound<3{
  if bound==0{heap-next=-1;}if bound==1{heap-end=heap-next - 1;}if bound==2{heap-end=0x7fffffffffffffff;}
  let invalid=windows-command-local-run(image,7680,-1,-1,memory,line,bytes);
  if invalid!=-12{panic("Windows invalid heap bounds admitted");}heap-next=cold-heap;heap-end=original-end;
  if free-list!=cold-free || domain-count!=cold-domains || domain-user-owned!=cold-owned{panic("Windows invalid heap bounds changed state");}windows-local-test-cold();windows-local-test-clean();bound=bound+1;
 }
 heap-end=heap-next;
 let refused=windows-command-local-run(image,7680,-1,-1,memory,line,bytes);heap-end=original-end;
 if refused!=-12 || heap-next!=cold-heap || free-list!=cold-free || domain-count!=cold-domains || domain-user-owned!=cold-owned || windows-protected-frames!=0{panic("Local cold cache no bump admission mutated");}windows-local-test-clean();windows-local-test-cold();
 heap-end=heap-next+26911;
 refused=windows-command-local-run(image,7680,-1,-1,memory,line,bytes);heap-end=original-end;
 if refused!=-12 || heap-next!=cold-heap || free-list!=cold-free || domain-count!=cold-domains || windows-protected-frames!=0{panic("Local cold cache short bump admission mutated");}windows-local-test-clean();windows-local-test-cold();
 heap-end=heap-next+26912;store64(image+5632,0);
 let recovered=windows-command-local-run(image,7680,-1,-1,memory,line,bytes);heap-end=original-end;
 if recovered!=42 || heap-next!=cold-heap+26912 || windows-local-test-free()!=200 || windows-protected-frames==0 || windows-protected-shares==0{panic("Local exact retained byte recovery failed");}windows-local-test-clean();
 serial-write-cstr(port,"windows-local-cold:200 freeframes zero and short bump refuse exact26912 recovery owned83 max1096 PASS");serial-nl(port);
 let fs=rdmsr(0xc0000100);let gs=rdmsr(0xc0000101);wrmsr64(0xc0000100,0x140005000);wrmsr64(0xc0000101,0x23456000);
 let ignored=invoke1(0x11000800,fx-before);
 let cycle=0;let heap=0;let free=0;let domains=0;let caps=cap-count;
 while cycle<21{let mode=0;while mode<22{if mode!=16{
  store64(image+5632,mode);windows-local-test-callbacks=0;windows-local-test-failed=0;windows-local-test-completions=0;
  if mode==10 || mode==14{windows-protected-budget=5;}
  let result=windows-command-local-run(image,7680,-1,-1,memory,line,bytes);windows-protected-budget=100;
  let expected=42;if mode==9 || mode==13{expected=142;}if mode==10 || mode==14{expected=124;}if mode==12{expected=43;}if mode==17 || mode==18{expected=127;}
  let callbacks=0;if mode==4 || (mode>=9 && mode<=15) || mode==17 || mode==19 || mode==21{callbacks=1;}if mode==18{callbacks=64;}
  let completions=callbacks;if mode==9 || mode==10 || mode==13 || mode==14 || mode==17{completions=0;}
  if result!=expected || windows-local-test-failed!=0 || windows-local-test-callbacks!=callbacks || windows-local-test-completions!=completions{serial-write-dec-wide(port,mode);serial-put(port,32);serial-write-dec-wide(port,result);serial-put(port,32);serial-write-dec-wide(port,windows-local-test-callbacks);serial-put(port,32);serial-write-dec-wide(port,windows-local-test-failed);panic("Windows local actual result/callback mismatch");}
  let ignored=invoke1(0x11000900,fx-after);let offset=0;while offset<512{if load8(fx-before+offset)!=load8(fx-after+offset){panic("Windows callback kernel FX restore mismatch");}offset=offset+1;}
  windows-local-test-clean();if rdmsr(0xc0000100)!=0x140005000 || rdmsr(0xc0000101)!=0x23456000 || cap-count!=caps || cap-check(memory,cap-memory())==0{panic("Local context/grant leaked");}
 }mode=mode+1;}
 if cycle==0{heap=heap-next;free=windows-local-test-free();domains=domain-count;}else{if heap-next!=heap || windows-local-test-free()!=free || domain-count!=domains{panic("Windows local repeated cleanup leak");}}cycle=cycle+1;}
 let live=cap-mint(root-realm,cap-memory());store64(image+5632,16);
 if windows-command-local-run(image,7680,-1,-1,live,line,bytes)!=42 || cap-check(live,cap-memory())!=0{panic("Local live revoke failed");}windows-local-test-clean();
 store64(image+5632,4);if windows-command-local-run(image,7680,-1,-1,memory,line,bytes)!=42{panic("Fresh local callback after revoke failed");}windows-local-test-clean();
 if heap-next!=heap || windows-local-test-free()!=free || domain-count!=domains{panic("Local final cleanup leak");}
 wrmsr64(0xc0000100,fs);wrmsr64(0xc0000101,gs);cap-revoke(memory);cap-revoke(weak);
 serial-write-cstr(port,"windows-local: 443 activations TLS FLS actual CPL3 callbacks entry home GP FX shared TLS callback free exit fault deadline bounds stable cleanup PASS");serial-nl(port);
}
'''
names=['components/windows-process-local.in', 'components/windows-process-heap.in', 'components/windows-process-parameters.in', 'components/windows-protected.in', 'components/windows-pe-startup.in', 'components/windows-pe-application.in', 'fixtures/windows-protected/local.asm', 'components/user-context.in', 'fixtures/user-context/guest.asm', 'boot/multiboot.asm', 'components/user-budget.in']
source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
(out/'kernel.in').write_text(source)
commands=[['nasm','-f','bin',str(ROOT/'fixtures/user-context/guest.asm'),'-o',str(out/'kernel-fx.bin')],['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],['nasm','-f','bin',str(ROOT/'fixtures/windows-protected/local.asm'),'-o',str(out/'process.exe')],[str(a.compiler),'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')]]
with (out/'compile.log').open('w') as log:
 for command in commands:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
kernel=(out/'kernel.bin').read_bytes();payload=(out/'process.exe').read_bytes();assert len(payload)==7680 and len((out/'kernel-fx.bin').read_bytes())==4096 and 0x100000+len(kernel)<0x10000000
boots=[]
for index in range(a.boots):
 target=out/('boot-'+str(index));target.mkdir();path=target/'serial.sock';received=bytearray();serial=None
 qemu_command=['qemu-system-x86_64','-kernel',str(out/'kernel.bin'),'-m','512M','-display','none','-no-reboot','-serial',f'unix:{path},server=on,wait=on','-device',f'loader,file={out/"process.exe"},addr=0x10000000,force-raw=on','-device',f'loader,file={out/"kernel-fx.bin"},addr=0x11000000,force-raw=on']
 with (target/'qemu.log').open('w') as log:
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
   text=received.decode(errors='replace');assert 'windows-local-cold:200 freeframes zero and short bump refuse exact26912 recovery owned83 max1096 PASS' in text;assert 'windows-local: 443 activations TLS FLS actual CPL3 callbacks entry home GP FX shared TLS callback free exit fault deadline bounds stable cleanup PASS' in text and 'space> ' in text,text
  finally:
   (target/'serial.log').write_bytes(received)
   if serial:serial.close()
   qemu.terminate()
   try:qemu.wait(timeout=5)
   except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
 boots.append(dict(index=index,status='passed',executions=444,command=qemu_command))

report=dict(status='passed',executions=444*a.boots,focused_activations=443*a.boots,cold_recovery_activations=a.boots,admission_refusals=6*a.boots,boots=boots,compiler_sha256=hashlib.sha256(a.compiler.read_bytes()).hexdigest(),kernel_sha256=hashlib.sha256(kernel).hexdigest(),fixture_sha256=hashlib.sha256(payload).hexdigest(),kernel_fx_fixture_sha256=hashlib.sha256((out/'kernel-fx.bin').read_bytes()).hexdigest(),source_sha256=source_hashes,source_changed=[name for name,value in source_hashes.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=value],commands=commands,qemu_command=qemu_command)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS Windows local TLS/FLS '+str(443*a.boots)+' focused activations plus '+str(a.boots)+' cold recoveries across '+str(a.boots)+' boots')
