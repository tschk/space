#!/usr/bin/env python3
"""Prove actual bounded Windows composed sections and ownership refusals."""
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
p.add_argument('--profile',type=int,choices=[10,11],default=10,help='11 additionally exercises explicit UTF8 services in main and callback')
a=p.parse_args();out=a.out.resolve();a.compiler=a.compiler.resolve()
assert not out.exists() or not any(out.iterdir()),'--out must be new or empty'
out.mkdir(parents=True,exist_ok=True)
def absolute_imports(source):
    return re.sub(r'import "([^"]+)"',lambda m:'import '+json.dumps(str((ROOT/'components'/m.group(1)).resolve())),source)


protected=absolute_imports((ROOT/'components/windows-protected.in').read_text())
assert protected.count('domain-user-syscall-hook = windows-protected-dispatch')==1
protected=protected.replace('domain-user-syscall-hook = windows-protected-dispatch','domain-user-syscall-hook = windows-composed-test-dispatch')
(out/'windows-protected.in').write_text(protected)
hub=absolute_imports((ROOT/'components/personality-hub.in').read_text()).replace(json.dumps(str(ROOT/'components/windows-protected.in')),json.dumps(str(out/'windows-protected.in')))
(out/'personality-hub.in').write_text(hub)
source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(ROOT/m.group(1))),(ROOT/'kernel/kernel-root.in').read_text()).replace(json.dumps(str(ROOT/'components/personality-hub.in')),json.dumps(str(out/'personality-hub.in')))
assert source.count('  shell(port)')==1
source=source.replace('  shell(port)','  windows-composed-check(port)\n  shell(port)')
source+=r'''

var windows-composed-test-config:Int=0
var windows-composed-test-line:Int=0
var windows-composed-test-env:Int=0
var windows-composed-test-rb:Int=-1
var windows-composed-test-observed:Int=0
var windows-composed-test-executions:Int=0
var windows-composed-test-rtc-unavailable:Int=0
var windows-composed-test-transient:Int=0
fn windows-composed-test-dispatch(frame:Int)->Int{
 let num=load64(frame+112);
 if windows-protected-profile!=10 || windows-protected-count!=87 || windows-protected-owned-pages(0x10000000,10)!=87{panic("Composed owned ledger mismatch");}
 if windows-parameters-composed-data==0 || load64(windows-parameters-composed-data)!=1 || load64(windows-parameters-composed-data+8)!=96 || windows-parameters-composed-data==windows-composed-test-config{panic("Composed descriptor not owned");}
 let private=windows-parameters-composed-data;
 let i=0;while i<windows-protected-count{if load64(windows-protected-frames+i*8)==private{panic("Composed config aliases user page");}i=i+1;}
 if private==windows-parameters-local-data || private==windows-parameters-critical-data || private==windows-parameters-heap-records || private==windows-parameters-env-data || private==windows-parameters-env-work{panic("Composed private backing alias");}
 if windows-composed-test-observed==0{
  windows-composed-test-observed=1;windows-composed-test-executions=windows-composed-test-executions+1;
  // Mutating the borrowed caller configuration and inputs after entry must
  // not change owned grants, line, canonical environment or private config.
  store64(windows-composed-test-config+32,-1);store64(windows-composed-test-config+40,-1);store64(windows-composed-test-config+80,0);
  store8(windows-composed-test-line,88);store8(windows-composed-test-env,88);
  windows-protected-store32(0x140005020,private);windows-protected-store32(0x140005024,0);
 }
 if num==0x100100{
  let op=load64(frame+96);if op==1{cap-revoke(windows-parameters-time-authority);}if op==2{cap-revoke(windows-parameters-heap-authority);}
  if op==3{windows-composed-test-rb=time-component-rtc-read(0x0b);outb(0x70,0x0b);outb(0x71,windows-composed-test-rb|128);}
  store64(frame+112,0);return 1;
 }
 let previous=counter-last;let control=windows-protected-dispatch(frame);
 if num==0x100011 && control==0 && load64(frame+112)==125{windows-composed-test-rtc-unavailable=1;}
 if num==0x100012 && load64(frame+96)==0 && (counter-last!=previous || load64(frame+112)!=0){panic("Composed invalid pointer read provider");}
 return control;
}
fn windows-composed-test-free()->Int{let n=0;let f=free-list;while f!=0 && n<4096{n=n+1;f=load64(f);}return n;}
fn windows-composed-test-clean()->void{
 if windows-protected-count!=0 || windows-protected-busy!=0 || windows-protected-profile!=0 || windows-parameters-active!=0 || windows-parameters-heap-active!=0 || windows-parameters-heap-authority!=-1 || windows-parameters-heap-records!=0 || windows-parameters-heap-handle!=0 || windows-parameters-critical-data!=0 || windows-parameters-local-data!=0 || windows-parameters-composed-active!=0 || windows-parameters-composed-data!=0 || windows-parameters-composed-flags!=0 || windows-parameters-env-active!=0 || windows-parameters-env-data!=0 || windows-parameters-time-active!=0 || windows-parameters-time-authority!=-1 || domain-user-syscall-hook!=0 || user-budget-active!=0 || user-context-active!=0 || domain-current!=0{panic("Composed ownership leaked");}
}
fn windows-composed-test-reset(memory:Int,timer:Int,flags:Int)->void{
 let p=windows-composed-test-config;
 store64(p,1);store64(p+8,96);store64(p+16,-1);store64(p+24,-1);store64(p+32,memory);store64(p+40,timer);
 store64(p+48,windows-composed-test-line);store64(p+56,12);store64(p+64,windows-composed-test-env);store64(p+72,11);store64(p+80,flags);store64(p+88,0);
 let line="sqlite3.exe";let env="ALPHA=one";let i=0;while i<12{store8(windows-composed-test-line+i,load8(line+i));i=i+1;}
 i=0;while i<10{store8(windows-composed-test-env+i,load8(env+i));i=i+1;}store8(windows-composed-test-env+10,0);
 windows-composed-test-observed=0;windows-composed-test-rtc-unavailable=0;
}
fn windows-composed-test-run(memory:Int,timer:Int,flags:Int,mode:Int)->Int{
 windows-composed-test-reset(memory,timer,flags);store64(0x10000000+7680,mode);
 let seconds=time-component-wallclock();if seconds<0{return -11;}
 store64(0x10000000+7680+80,(seconds+11644473600)*10000000);store64(0x10000000+7680+88,(seconds+11644473600+60)*10000000);
 let available=0;if counter-frequency-authorized(timer)>0{available=1;}store64(0x10000000+7680+8,available);
 let result=windows-command-composed-run(0x10000000,9728,windows-composed-test-config);
 if windows-composed-test-rb>=0{outb(0x70,0x0b);outb(0x71,windows-composed-test-rb);windows-composed-test-rb=-1;}
 if result==125{
  if windows-composed-test-rtc-unavailable!=1{panic("Composed untyped125 must not be retried");}
  if mode!=12 && mode!=13{windows-composed-test-transient=windows-composed-test-transient+1;windows-composed-test-clean();}
 }
 return result;
}
fn windows-composed-check(port:Int)->void{
 let image=0x10000000;if heap-next>=image{panic("Composed fixture collision");}heap-end=image;
 if dyn-resolve-idx("windows-command-composed-run")!=-1 || dyn-resolve-idx("windows-parameters-composed-prepare")!=-1{panic("Composed private registry exported");}
 windows-composed-test-config=alloc(96);windows-composed-test-line=alloc(32);windows-composed-test-env=alloc(32);
 let private=boot-image-find(254);let before-private=heap-next;let caps-private=cap-count;let domains-private=domain-count;
 if private==0 || sci-load-runtime-component(port,private,"private-composed",1,1,0)!=-1 || heap-next!=before-private || cap-count!=caps-private || domain-count!=domains-private{panic("Composed private SCI admitted/allocated");}
 serial-write-cstr(port,"windows-composed-registry: actual valid SCI private helper import refused before allocation PASS");serial-nl(port);
 let memory=cap-mint(root-realm,cap-memory());let timer=cap-mint(root-realm,cap-timer());let weak=cap-mint(root-realm,cap-serial());
 if windows-command-critical-run(image,9728,-1,-1,memory,"sqlite3.exe",12)!=-8 || windows-command-local-run(image,9728,-1,-1,memory,"sqlite3.exe",12)!=-8 || windows-command-counter-run(image,9728,-1,-1,timer,"sqlite3.exe",12)!=-8{panic("Older profiles widened composed imports");}
 let i=0;while i<12{
  windows-composed-test-reset(memory,timer,1);let p=windows-composed-test-config;
  if i==0{store64(p,2);}if i==1{store64(p+8,88);}if i==2{store64(p+88,1);}if i==3{store64(p+80,2);}if i==4{store64(p+80,4);}if i==5{store64(p+32,weak);}if i==6{store64(p+40,weak);}if i==7{store64(p+80,0);store64(p+40,-1);}
  if i==8{store64(p+16,-2);}if i==9{store64(p+24,-2);}if i==10{store8(windows-composed-test-line+11,1);}if i==11{store8(windows-composed-test-env+10,1);}
  let before=heap-next;let free=free-list;let domains=domain-count;let expected=-22;if i>=5 && i<=7{expected=-13;}
  if windows-command-composed-run(image,9728,p)!=expected || heap-next!=before || free-list!=free || domain-count!=domains{panic("Composed descriptor refusal mutated");}windows-composed-test-clean();i=i+1;
 }
 // Exact cold cache admission: all172 conservative frame reservations are
 // distinct from the26912-byte retained bump cache.
 let held=alloc(200*8);i=0;while i<200{store64(held+i*8,frame-alloc());i=i+1;}if free-list!=0{panic("Composed cold pool not fully owned");}
 i=0;while i<171{frame-free(load64(held+i*8));i=i+1;}
 windows-composed-test-reset(memory,timer,1);let original-end=heap-end;let before=heap-next;let free=free-list;let domains=domain-count;
 heap-end=heap-next+26912;let cold-attempt=0;let refused=-11;while refused==-11 && cold-attempt<32{refused=windows-command-composed-run(image,9728,windows-composed-test-config);cold-attempt=cold-attempt+1;}heap-end=original-end;
 if refused!=-12 || heap-next!=before || free-list!=free || domain-count!=domains || windows-protected-frames!=0{panic("Composed cold refusal mutated");}windows-composed-test-clean();
 frame-free(load64(held+171*8));
 let attempt=0;let result=-11;while (result==-11 || result==125) && attempt<32{heap-end=heap-next+26912;result=windows-composed-test-run(memory,timer,1,0);heap-end=original-end;attempt=attempt+1;}
 if result!=42 || heap-next!=before+26912 || windows-composed-test-free()!=172{serial-write-dec-wide(port,result);panic("Composed exact cold recovery failed");}windows-composed-test-clean();
 i=172;while i<200{frame-free(load64(held+i*8));i=i+1;}
 serial-write-cstr(port,"windows-composed-cold:171 frames refuse172 recover exact26912 retained bytes PASS");serial-nl(port);
 let callerfs=rdmsr(0xc0000100);let callergs=rdmsr(0xc0000101);wrmsr64(0xc0000100,0x23456000);wrmsr64(0xc0000101,0x34567000);
 let cycle=0;let heap=0;let pool=0;let count=0;let caller-cap=current-cap;let pic=inb(0x21);
 while cycle<21{let mode=0;while mode<14{if mode!=5 && mode!=6{
  if mode==3 || mode==4{windows-protected-budget=5;}
  attempt=0;result=-11;while (result==-11 || (result==125 && mode!=12 && mode!=13)) && attempt<32{result=windows-composed-test-run(memory,timer,1,mode);attempt=attempt+1;}windows-protected-budget=100;
  let expected=42;if mode==2 || mode==8 || mode==9 || mode==10{expected=142;}if mode==3 || mode==4{expected=124;}if mode==11{expected=127;}if mode==12 || mode==13{expected=125;}
  if result!=expected{serial-write-dec-wide(port,mode);serial-put(port,32);serial-write-dec-wide(port,result);panic("Composed mixed result mismatch");}
  if windows-composed-test-observed!=1{panic("Composed guest not entered");}windows-composed-test-clean();
  if current-cap!=caller-cap || inb(0x21)!=pic || rdmsr(0xc0000100)!=0x23456000 || rdmsr(0xc0000101)!=0x34567000{panic("Composed caller TLS bases changed");}count=count+1;
 }mode=mode+1;}
 if cycle==0{heap=heap-next;pool=windows-composed-test-free();domains=domain-count;}else{if heap!=heap-next || pool!=windows-composed-test-free() || domains!=domain-count{panic("Composed repeated cleanup leaked");}}cycle=cycle+1;}
 let live-timer=cap-mint(root-realm,cap-timer());let live-memory=cap-mint(root-realm,cap-memory());
 attempt=0;result=-11;while (result==-11 || result==125) && attempt<32{result=windows-composed-test-run(memory,live-timer,1,5);attempt=attempt+1;}if result!=42 || cap-check(live-timer,cap-timer())!=0{panic("Composed live timer revoke failed");}windows-composed-test-clean();
 attempt=0;result=-11;while (result==-11 || (result==125 && cap-check(live-memory,cap-memory())!=0)) && attempt<32{result=windows-composed-test-run(live-memory,timer,1,6);attempt=attempt+1;}if result!=42 || cap-check(live-memory,cap-memory())!=0{panic("Composed live memory revoke failed");}windows-composed-test-clean();
 let required=42;if counter-frequency-authorized(timer)<0{required=-38;}
 attempt=0;result=-11;while (result==-11 || result==125) && attempt<32{result=windows-composed-test-run(memory,timer,3,0);attempt=attempt+1;}if result!=required{panic("Composed required hardware policy mismatch");}windows-composed-test-clean();
 attempt=0;result=-11;while (result==-11 || result==125) && attempt<32{result=windows-composed-test-run(memory,timer,1,0);attempt=attempt+1;}if result!=42{panic("Composed fresh activation failed");}windows-composed-test-clean();
 if heap!=heap-next || pool!=windows-composed-test-free() || domains!=domain-count{panic("Composed revoke fresh cleanup leaked");}
 // A separate declared memory-only fixture imports no clocks. No timer
 // authority is needed; the original mixed import graph still refusesflags0.
 i=0;while i<9728{store8(image+i,load8(0x12000000+i));i=i+1;}
 attempt=0;result=-11;while (result==-11 || result==125) && attempt<32{result=windows-composed-test-run(memory,-1,0,0);attempt=attempt+1;}if result!=42{panic("Composed memory-only no timer failed");}windows-composed-test-clean();
 if heap!=heap-next || pool!=windows-composed-test-free() || domains!=domain-count{panic("Composed memory-only cleanup leaked");}
 wrmsr64(0xc0000100,callerfs);wrmsr64(0xc0000101,callergs);cap-revoke(memory);cap-revoke(timer);cap-revoke(weak);
 serial-write-cstr(port,"windows-composed-receipt:");serial-write-dec-wide(port,windows-composed-test-executions);serial-put(port,32);serial-write-dec-wide(port,windows-composed-test-transient);serial-nl(port);
 serial-write-cstr(port,"windows-composed:257 mixed activations optional required hardware grants callbacks snapshots faults deadlines cleanup PASS");serial-nl(port);
}
'''

names=['components/windows-process-composed.in','components/windows-process-local.in','components/windows-protected.in','components/windows-pe-application.in','components/windows-process-parameters.in','components/windows-pe-startup.in','components/windows-pe-view.in','fixtures/windows-protected/composed.asm','fixtures/windows-protected/composed-private.in']
if a.profile==11:names+=['components/text-unicode.in','components/windows-process-unicode.in','fixtures/windows-protected/unicode-mixed.asm','fixtures/windows-protected/unicode-private.in']
source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
if a.profile==11:
 source=source.replace('windows-command-composed-run(', 'windows-command-unicode-run(').replace('windows-protected-profile!=10','windows-protected-profile!=11').replace('9728','10752').replace('7680','8704')
(out/'kernel.in').write_text(source)
commands=[['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],['nasm','-f','bin',str(ROOT/('fixtures/windows-protected/unicode-mixed.asm' if a.profile==11 else 'fixtures/windows-protected/composed.asm')),'-o',str(out/'process.exe')],[str(a.compiler),'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')]]
commands.insert(0,['nasm','-DNO_CLOCK=1','-f','bin',str(ROOT/('fixtures/windows-protected/unicode-mixed.asm' if a.profile==11 else 'fixtures/windows-protected/composed.asm')),'-o',str(out/'memory.exe')])
commands.insert(0,[str(a.compiler),'compile','--path',str(ROOT/('fixtures/windows-protected/unicode-private.in' if a.profile==11 else 'fixtures/windows-protected/composed-private.in')),'--entry','private-entry','--emit','sci','--base','0x7a000000','--target','native','--target-triple','x86_64-unknown-none','--out',str(out/'private.sci')])
commands.append(['python',str(ROOT/'scripts/pack-sci-image.py'),str(out/'kernel.bin'),str(out/'combined.bin'),f'254:{out}/private.sci'])
with (out/'compile.log').open('w') as log:
 for command in commands:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
kernel=(out/'combined.bin').read_bytes();payload=(out/'process.exe').read_bytes();assert len(payload)==(10752 if a.profile==11 else 9728) and 0x100000+len(kernel)<0x10000000
runs=[]
for label,machine in [('pc','pc'),('q35','q35'),('no-hpet','pc,hpet=off')]:
 run=out/label;run.mkdir();path=run/'serial.sock';received=bytearray();serial=None
 command=['qemu-system-x86_64','-kernel',str(out/'combined.bin'),'-machine',machine,'-m','512M','-display','none','-no-reboot','-rtc','base=2026-10-23T12:34:56,clock=vm','-serial',f'unix:{path},server=on,wait=on','-device',f'loader,file={out/"process.exe"},addr=0x10000000,force-raw=on','-device',f'loader,file={out/"memory.exe"},addr=0x12000000,force-raw=on']
 with (run/'qemu.log').open('w') as log:
  qemu=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
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
   text=received.decode(errors='replace')
   if a.profile==11:assert 'DENIED unresolved import windows-command-unicode-run' in text,text
   assert 'INVALID private composed entry' not in text and 'windows-composed-registry: actual valid SCI private helper import refused before allocation PASS' in text,text
   assert 'windows-composed-cold:171 frames refuse172 recover exact26912 retained bytes PASS' in text,text
   assert 'windows-composed:257 mixed activations optional required hardware grants callbacks snapshots faults deadlines cleanup PASS' in text and 'space> ' in text,text
  finally:
   (run/'serial.log').write_bytes(received)
   if serial:serial.close()
   qemu.terminate()
   try:qemu.wait(timeout=5)
   except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
 receipt=re.search(r'windows-composed-receipt:(\d+) (\d+)',text);assert receipt,text
 runs.append(dict(machine=machine,command=command,executions=int(receipt[1]),natural_rtc_terminal125=int(receipt[2]),required_counter='refused-before-entry' if label=='no-hpet' else 'executed'))
report=dict(status='passed',profile=a.profile,runs=runs,executions=sum(x['executions'] for x in runs),compiler_sha256=hashlib.sha256(a.compiler.read_bytes()).hexdigest(),kernel_sha256=hashlib.sha256(kernel).hexdigest(),fixture_sha256=hashlib.sha256(payload).hexdigest(),source_sha256=source_hashes,source_changed=[name for name,value in source_hashes.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=value],commands=commands)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS Windows composed mixed services pc q35 noHPET')
