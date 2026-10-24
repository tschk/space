#!/usr/bin/env python3
"""Prove Windows QPC against real HPET, including denial, failure and cleanup."""
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

# Instrument calls without replacing any native provider result. Fault controls
# exist only in this supervisor test image, never in the Windows ABI profile.
for name in ['windows-process-time.in','windows-process-counter.in']:
    content=(ROOT/'components'/name).read_text()
    content=content.replace('counter-read-authorized(', 'windows-counter-test-read(').replace('counter-frequency-authorized(', 'windows-counter-test-frequency(')
    (out/name).write_text(content)
parameters=absolute_imports((ROOT/'components/windows-process-parameters.in').read_text())
for name in ['windows-process-time.in','windows-process-counter.in']:
    parameters=parameters.replace(json.dumps(str(ROOT/'components'/name)),json.dumps(str(out/name)))
(out/'windows-process-parameters.in').write_text(parameters)
protected=absolute_imports((ROOT/'components/windows-protected.in').read_text())
protected=protected.replace(json.dumps(str(ROOT/'components/windows-process-parameters.in')),json.dumps(str(out/'windows-process-parameters.in')))
assert protected.count('domain-user-syscall-hook = windows-protected-dispatch')==1
protected=protected.replace('domain-user-syscall-hook = windows-protected-dispatch','domain-user-syscall-hook = windows-counter-test-dispatch')
(out/'windows-protected.in').write_text(protected)
hub=absolute_imports((ROOT/'components/personality-hub.in').read_text()).replace(json.dumps(str(ROOT/'components/windows-protected.in')),json.dumps(str(out/'windows-protected.in')))
(out/'personality-hub.in').write_text(hub)
source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(ROOT/m.group(1))),(ROOT/'kernel/kernel-root.in').read_text())
source=source.replace(json.dumps(str(ROOT/'components/personality-hub.in')),json.dumps(str(out/'personality-hub.in')))
assert source.count('  shell(port)')==1
source=source.replace('  shell(port)','  windows-counter-check(port,mb-info)\n  shell(port)')
source+=r'''
var windows-counter-test-reads:Int=0
var windows-counter-test-frequencies:Int=0
var windows-counter-test-last:Int=-1
var windows-counter-test-saved:Int=-1
var windows-counter-test-observed:Int=0
var windows-counter-test-buffer:Int=0
var windows-counter-test-transients:Int=0
fn windows-counter-test-read(timer:Int)->Int{windows-counter-test-reads=windows-counter-test-reads+1;let n=counter-read-authorized(timer);windows-counter-test-last=n;return n;}
fn windows-counter-test-frequency(timer:Int)->Int{windows-counter-test-frequencies=windows-counter-test-frequencies+1;let n=counter-frequency-authorized(timer);windows-counter-test-last=n;return n;}
fn windows-counter-test-hardware(value:Int)->void{
 let config=load64(counter-base+0x10);store64(counter-base+0x10,config&(-2));store64(counter-base+0xf0,value);store64(counter-base+0x10,config);
}
fn windows-counter-test-address(i:Int)->Int{if i<80{return 0x140005000+248+i;}if i<96{return 0x140005000+4090+i - 80;}return 0x140005000+8186+i - 96;}
fn windows-counter-test-dispatch(frame:Int)->Int{
 let num=load64(frame+112);
 if num==0x100100{
  if domain-current!=windows-protected-domain || windows-protected-busy==0{panic("Counter control owner mismatch");}
  let op=load64(frame+96);
  if op==0{cap-revoke(windows-parameters-time-authority);}
  if op==1 || op==3{windows-counter-test-saved=counter-last;let value=0;if op==3{value=1<<63;}windows-counter-test-hardware(value);}
  if op==2{windows-counter-test-hardware(counter-last+4294967296);serial-write-cstr(com1(),"windows-counter-wide: ");serial-write-dec-wide(com1(),load64(counter-base+0xf0));serial-nl(com1());}
  if op==4{
   if (invoke1(load64(0x4198),0)&512)!=0{panic("Counter syscall is not IF0");}
   let tick=ticks;let first=counter-read-authorized(windows-parameters-time-authority);let i=0;while i<10000{pause();i=i+1;}let last=counter-read-authorized(windows-parameters-time-authority);
   if last<=first || ticks!=tick{panic("Windows counter depends on IRQ delivery");}
  }
  store64(frame+112,0);return 1;
 }
 let output=load64(frame+96);let observed=0;
 if num==0x100012 || num==0x100013{observed=1;let i=0;while i<102{store8(windows-counter-test-buffer+i,load8(windows-protected-physical(windows-counter-test-address(i))));i=i+1;}}
 let result=windows-protected-dispatch(frame);
 if observed!=0{
  windows-counter-test-observed=windows-counter-test-observed+1;let success=load64(frame+112);
  if success!=0 && success!=1{panic("Windows QPC BOOL is not zero or one");}
  let i=0;while i<102{let address=windows-counter-test-address(i);if success==0 || address<output || address>=output+8{if load8(windows-protected-physical(address))!=load8(windows-counter-test-buffer+i){panic("Windows QPC partial/outside write");}}i=i+1;}
  if success==1{if windows-protected-load64(output)!=windows-counter-test-last || windows-counter-test-last<0{panic("Windows QPC fabricated/truncated native sample");}}
 }
 return result;
}
fn windows-counter-test-free()->Int{let n=0;let f=free-list;while f!=0 && n<4096{n=n+1;f=load64(f);}return n;}
fn windows-counter-test-run(image:Int,timer:Int)->Int{
 let attempt=0;while attempt<32{
  windows-counter-test-reads=0;windows-counter-test-frequencies=0;windows-counter-test-observed=0;
  let heap=heap-next;let free=free-list;let domains=domain-count;let line="sqlite3.exe -version";
  let result=windows-command-counter-run(image,7168,-1,-1,timer,line,strlen(line)+1);
  if result!=-11 && result!=125{return result;}
  if result==-11{if heap-next!=heap || free-list!=free || domain-count!=domains || windows-counter-test-observed!=0{panic("Counter RTC admission allocated");}}
  windows-counter-test-transients=windows-counter-test-transients+1;attempt=attempt+1;pause();
 }panic("Counter coherent RTC retry exhausted");return -11;
}
fn windows-counter-test-clean()->void{
 if windows-protected-count!=0 || windows-protected-busy!=0 || windows-protected-profile!=0 || domain-current!=0 || user-budget-active!=0 || domain-user-syscall-hook!=0 || windows-parameters-active!=0 || windows-parameters-time-active!=0 || windows-parameters-time-authority!=-1 || windows-parameters-time-anchor!=0{panic("Windows counter scope leaked");}
}
fn windows-counter-test-refuse(image:Int,timer:Int,line:Int,bytes:Int,expected:Int)->void{
 let heap=heap-next;let free=free-list;let domains=domain-count;windows-counter-test-reads=0;windows-counter-test-frequencies=0;
 let status=windows-command-counter-run(image,7168,-1,-1,timer,line,bytes);
 if status!=expected || windows-counter-test-reads!=0 || windows-counter-test-frequencies!=0 || heap-next!=heap || free-list!=free || domain-count!=domains{panic("Counter early admission touched provider/state");}windows-counter-test-clean();
}
fn windows-counter-check(port:Int,mb:Int)->void{
 let image=0x10000000;if heap-next>=image{panic("Counter payload/heap collision");}heap-end=image;
 windows-counter-test-buffer=alloc(128);let timer=cap-mint(root-realm,cap-timer());let weak=cap-mint(root-realm,cap-serial());let line="sqlite3.exe -version";
 if windows-command-run(image,7168,-1,-1,line,strlen(line)+1)!=-8 || windows-command-time-run(image,7168,-1,-1,timer,line,strlen(line)+1)!=-8 || windows-application-entry(image,7168)!=-8{panic("Earlier Windows profiles widened QPC");}
 windows-counter-test-refuse(image,-1,line,strlen(line)+1,-13);windows-counter-test-refuse(image,weak,line,strlen(line)+1,-13);
 let revoked=cap-mint(root-realm,cap-timer());cap-revoke(revoked);windows-counter-test-refuse(image,revoked,line,strlen(line)+1,-13);
 windows-counter-test-refuse(image,timer,line,0,-22);let magic=load32(image);store32(image,0);windows-counter-test-refuse(image,timer,line,strlen(line)+1,-8);store32(image,magic);
 if counter-frequency()<=0{
  let heap=heap-next;let free=free-list;let domains=domain-count;let i=0;
  while i<21{if windows-counter-test-run(image,timer)!=-38 || heap-next!=heap || free-list!=free || domain-count!=domains{panic("Unavailable HPET fabricated counter/allocated");}windows-counter-test-clean();i=i+1;}
  if windows-counter-test-run(image,weak)!=-13{panic("Unavailable counter bypassed authority");}
  let seconds=time-component-wallclock();if seconds<0{panic("Unavailable HPET damaged RTC");}
  let timeimage=0x11000000;store64(timeimage+5128,(seconds+11644473600)*10000000);store64(timeimage+5136,(seconds+11644473600+60)*10000000);
  let result=-11;let attempts=0;while attempts<32 && (result==-11 || result==125){result=windows-command-time-run(timeimage,7168,-1,-1,timer,line,strlen(line)+1);attempts=attempts+1;}
  if result!=42{panic("No HPET blocked independent protected FILETIME");}windows-counter-test-clean();
  serial-write-cstr(port,"windows-counter: unavailable HPET 21 allocation-free refusals RTC retained PASS");serial-nl(port);return;
 }
 let frequency=counter-frequency();let period=(load64(counter-base)>>32)&0xffffffff;
 if frequency*period!=1000000000000000{panic("Counter period/frequency mismatch");}store64(image+5128,frequency);
 serial-write-cstr(port,"windows-counter-frequency: ");serial-write-dec-wide(port,frequency);serial-put(port,32);serial-write-dec-wide(port,period);serial-nl(port);
 if windows-counter-test-run(image,weak)!=-13 || windows-counter-test-reads!=0 || windows-counter-test-frequencies!=0{panic("Counter weak grant touched provider");}
 let fs=rdmsr(0xc0000100);let gs=rdmsr(0xc0000101);wrmsr64(0xc0000100,0x140005000);wrmsr64(0xc0000101,0x23456000);
 let cycle=0;let heap=0;let free=0;let domains=0;let caps=cap-count;
 while cycle<21{let mode=0;while mode<15{if mode!=6{
  store64(image+5120,mode);if mode==9{windows-protected-budget=5;}
  let result=windows-counter-test-run(image,timer);windows-protected-budget=100;
  let expected=42;if mode==9{expected=124;}
  if result!=expected{serial-write-dec-wide(port,mode);serial-put(port,32);serial-write-dec-wide(port,result);panic("Windows QPC execution mismatch");}
  let reads=3;let frequencies=2;let observed=3;
  if mode==1 || mode==3 || mode==4 || mode==13{observed=4;}
  if mode==2 || mode==12{observed=4;}
  if mode==5 || mode==11{reads=4;observed=4;}
  if mode==14{frequencies=3;observed=4;}
  if mode==7 || mode==8{reads=4;frequencies=3;observed=5;}
  if windows-counter-test-reads!=reads || windows-counter-test-frequencies!=frequencies || windows-counter-test-observed!=observed{serial-write-dec-wide(port,mode);serial-put(port,32);serial-write-dec-wide(port,windows-counter-test-reads);serial-put(port,32);serial-write-dec-wide(port,windows-counter-test-frequencies);serial-put(port,32);serial-write-dec-wide(port,windows-counter-test-observed);panic("Windows QPC validation/provider count mismatch");}
  if mode==7 || mode==8{if counter-ready!=0 || counter-read()!=-1 || counter-frequency()!=-1{panic("Counter bad hardware remained ready");}windows-counter-test-hardware(windows-counter-test-saved+1000);if counter-init(mb)!=0{panic("Trusted counter fault-test epoch recovery failed");}}
  windows-counter-test-clean();if rdmsr(0xc0000100)!=0x140005000 || rdmsr(0xc0000101)!=0x23456000 || cap-count!=caps || cap-check(timer,cap-timer())==0{panic("Windows counter caller context/grant leaked");}
 }mode=mode+1;}
 if cycle==0{heap=heap-next;free=windows-counter-test-free();domains=domain-count;}else{if heap-next!=heap || windows-counter-test-free()!=free || domain-count!=domains{panic("Windows counter repeated cleanup leaked");}}cycle=cycle+1;}
 let live=cap-mint(root-realm,cap-timer());store64(image+5120,6);
 if windows-counter-test-run(image,live)!=42 || cap-check(live,cap-timer())!=0 || windows-counter-test-reads!=3 || windows-counter-test-frequencies!=2 || windows-counter-test-observed!=5{panic("Windows counter live revocation mismatch");}
 store64(image+5120,0);if windows-counter-test-run(image,timer)!=42{panic("Windows fresh counter activation failed");}windows-counter-test-clean();
 if heap-next!=heap || windows-counter-test-free()!=free || domain-count!=domains{panic("Windows counter post-revoke cleanup leak");}
 wrmsr64(0xc0000100,fs);wrmsr64(0xc0000101,gs);cap-revoke(timer);cap-revoke(weak);
 serial-write-cstr(port,"windows-counter: 296 executions real HPET IF0 64bit BOOL errors pointers live revoke backward overflow fresh cleanup PASS");serial-nl(port);
}
'''
(out/'kernel.in').write_text(source)
commands=[['nasm','-f','bin',str(ROOT/'fixtures/windows-protected/filetime.asm'),'-o',str(out/'filetime.exe')],['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],['nasm','-f','bin',str(ROOT/'fixtures/windows-protected/counter.asm'),'-o',str(out/'process.exe')],[str(a.compiler),'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')]]
with (out/'compile.log').open('w') as log:
    for command in commands:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
kernel=(out/'kernel.bin').read_bytes();payload=(out/'process.exe').read_bytes()
assert 0x100000+len(kernel)<0x10000000 and len(payload)==7168
names=['components/windows-process-counter.in','components/windows-process-time.in','components/windows-process-parameters.in','components/windows-protected.in','components/windows-pe-application.in','components/counter.in','fixtures/windows-protected/counter.asm','boot/multiboot.asm','components/user-budget.in']
report=dict(status='running',compiler_sha256=hashlib.sha256(a.compiler.read_bytes()).hexdigest(),kernel_sha256=hashlib.sha256(kernel).hexdigest(),source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names},commands=commands,boots=[])
try:
 for machine in ['pc','q35','pc,hpet=off']:
    target=out/machine.replace(',','-').replace('=','-');target.mkdir();serial_path=target/'serial.sock';received=bytearray();serial=None
    command=['qemu-system-x86_64','-machine',machine,'-kernel',str(out/'kernel.bin'),'-m','512M','-display','none','-no-reboot','-rtc','base=2026-10-23T12:00:00,clock=vm','-serial',f'unix:{serial_path},server=on,wait=on','-device',f'loader,file={out/"process.exe"},addr=0x10000000,force-raw=on','-device',f'loader,file={out/"filetime.exe"},addr=0x11000000,force-raw=on']
    with (target/'qemu.log').open('w') as log:
     qemu=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
     try:
      deadline=time.monotonic()+10
      while not serial_path.exists() and qemu.poll() is None and time.monotonic()<deadline:time.sleep(.02)
      serial=socket.socket(socket.AF_UNIX);serial.settimeout(.2);serial.connect(str(serial_path));deadline=time.monotonic()+180
      while b'space> ' not in received and time.monotonic()<deadline:
       try:
        block=serial.recv(65536)
        if not block:break
        received.extend(block)
        if b'PANIC' in received or b'nanokernel fault handler halting' in received:break
       except socket.timeout:
        if qemu.poll() is not None:break
      text=received.decode(errors='replace')
      marker='windows-counter: unavailable HPET 21 allocation-free refusals RTC retained PASS' if 'off' in machine else 'windows-counter: 296 executions real HPET IF0 64bit BOOL errors pointers live revoke backward overflow fresh cleanup PASS'
      assert marker in text and 'space> ' in text,text
     finally:
      (target/'serial.log').write_bytes(received)
      if serial:serial.close()
      qemu.terminate()
      try:qemu.wait(timeout=5)
      except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
    wide=[int(value) for value in re.findall(r'^windows-counter-wide: (\d+)$',text,re.MULTILINE)]
    if 'off' not in machine:assert len(wide)==21 and all(value>4294967295 for value in wide),wide
    report['boots'].append(dict(machine=machine,status='passed',executions=1 if 'off' in machine else 296,early_admission_refusals=5,full_width_samples=wide,command=command));(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS Windows QPC '+machine,flush=True)
 report['status']='passed';report['executions']=593
except Exception as error:
 report.update(status='failed',error=str(error));raise
finally:
 report['source_changed']=[name for name,value in report['source_sha256'].items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=value]
 (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
