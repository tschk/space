#!/usr/bin/env python3
"""Exercise process-owned Windows environments with real mutation/snapshot lifecycle."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
out = a.out.resolve()
if out.exists() and any(out.iterdir()):
    p.error('--out must be new or empty')
out.mkdir(parents=True, exist_ok=True)
source=(ROOT/'kernel/kernel-root.in').read_text()
source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(ROOT/m.group(1))),source)
assert source.count('  shell(port)')==1
source=source.replace('  shell(port)','  windows-environment-check(port)\n  shell(port)')
source+='''
fn windows-env-test-free()->Int{let n=0;let f=free-list;while f!=0 && n<4096{n=n+1;f=load64(f);}return n;}
fn windows-env-test-add(env:Int,pos:Int,text:Int)->Int{let i=0;while i<=strlen(text){store8(env+pos+i,load8(text+i));i=i+1;}return pos+i;}
fn windows-env-test-refuse(image:Int,env:Int,bytes:Int)->void{
 let line="sqlite3.exe -version";let heap=heap-next;let free=free-list;let domains=domain-count;let owned=domain-user-owned;
 if windows-command-environment-run(image,7168,-1,-1,line,strlen(line)+1,env,bytes)!=-22 || heap-next!=heap || free-list!=free || domain-count!=domains || domain-user-owned!=owned || windows-parameters-env-active!=0 || windows-parameters-env-input!=0 || windows-parameters-env-data!=0{panic("Windows invalid environment changed activation state");}
}
fn windows-environment-check(port:Int)->void{
 let image=0x280000;let line="sqlite3.exe -version";let env=alloc(2048);let bad=alloc(2048);
 let bytes=windows-env-test-add(env,0,"Zulu=last");bytes=windows-env-test-add(env,bytes,"ALPHA=one");bytes=windows-env-test-add(env,bytes,"EMPTY=");store8(env+bytes,0);bytes=bytes+1;
 if windows-application-entry(image,7168)!=-8 || windows-startup-entry(image,7168)!=-8 || windows-command-run(image,7168,-1,-1,line,strlen(line)+1)!=-8{panic("Previous Windows profiles widened environment imports");}
 windows-env-test-refuse(image,0,bytes);windows-env-test-refuse(image,env,1);windows-env-test-refuse(image,env,2049);
 store8(env+bytes - 1,65);windows-env-test-refuse(image,env,bytes);store8(env+bytes - 1,0);
 store8(env,0);windows-env-test-refuse(image,env,bytes);store8(env,90);
 store8(env+4,120);windows-env-test-refuse(image,env,bytes);store8(env+4,61);
 store8(env+1,128);windows-env-test-refuse(image,env,bytes);store8(env+1,117);
 let n=windows-env-test-add(bad,0,"A=1");n=windows-env-test-add(bad,n,"a=2");store8(bad+n,0);windows-env-test-refuse(image,bad,n+1);
 let i=0;while i<64{store8(bad+i,65);i=i+1;}store8(bad+64,61);store8(bad+65,120);store8(bad+66,0);store8(bad+67,0);windows-env-test-refuse(image,bad,68);
 store8(bad,65);store8(bad+1,61);i=2;while i<258{store8(bad+i,120);i=i+1;}store8(bad+258,0);store8(bad+259,0);windows-env-test-refuse(image,bad,260);
 i=0;while i<17{store8(bad+i*5,75);store8(bad+i*5+1,65+i);store8(bad+i*5+2,61);store8(bad+i*5+3,120);store8(bad+i*5+4,0);i=i+1;}store8(bad+85,0);windows-env-test-refuse(image,bad,86);
 let caller-fs=rdmsr(0xc0000100);let caller-gs=rdmsr(0xc0000101);wrmsr64(0xc0000100,0x140005000);wrmsr64(0xc0000101,0x23456000);
 let cycle=0;let heap=0;let free=0;let domains=0;let caps=cap-count;
 while cycle<21{
  let mode=0;while mode<18{
   store64(image+5120,mode);if mode==17{windows-protected-budget=5;}
   let result=windows-command-environment-run(image,7168,-1,-1,line,strlen(line)+1,env,bytes);windows-protected-budget=100;
   let expected=42;if mode==13 || mode==14 || mode==16{expected=142;}if mode==17{expected=124;}
   if result!=expected{serial-write-dec-wide(port,mode);serial-write-dec-wide(port,result);panic("Windows environment result mismatch");}
   if rdmsr(0xc0000100)!=0x140005000 || rdmsr(0xc0000101)!=0x23456000 || windows-protected-count!=0 || windows-protected-busy!=0 || windows-protected-profile!=0 || domain-current!=0 || user-budget-active!=0 || domain-user-syscall-hook!=0 || cap-count!=caps{panic("Windows environment execution scope leaked");}
   if windows-parameters-env-active!=0 || windows-parameters-env-input!=0 || windows-parameters-env-input-bytes!=0 || windows-parameters-env-data!=0 || windows-parameters-env-work!=0 || windows-parameters-env-count!=0 || windows-parameters-env-snapshots!=0{panic("Windows environment ownership leaked");}
   if load8(env)!=90 || load8(env+1)!=117 || load8(env+4)!=61 || load8(env+bytes - 1)!=0{panic("Windows host environment input changed");}
   mode=mode+1;
  }
  if cycle==0{heap=heap-next;free=windows-env-test-free();domains=domain-count;}
  else{if heap-next!=heap || windows-env-test-free()!=free || domain-count!=domains{panic("Windows environment repeated resources leaked");}}
  cycle=cycle+1;
 }
 store8(bad,0);store8(bad+1,0);store64(image+5120,18);
 if windows-command-environment-run(image,7168,-1,-1,line,strlen(line)+1,bad,2)!=42{panic("Windows explicit empty environment failed");}
 n=windows-env-test-add(bad,0,"ALPHA=one");i=0;while i<15{store8(bad+n,75);store8(bad+n+1,65+i);store8(bad+n+2,61);store8(bad+n+3,120);store8(bad+n+4,0);n=n+5;i=i+1;}store8(bad+n,0);store64(image+5120,20);
 if windows-command-environment-run(image,7168,-1,-1,line,strlen(line)+1,bad,n+1)!=42{panic("Windows full environment atomic refusal failed");}
 if heap-next!=heap || windows-env-test-free()!=free || domain-count!=domains{panic("Windows environment boundary resource leak");}
 wrmsr64(0xc0000100,caller-fs);wrmsr64(0xc0000101,caller-gs);
 serial-write-cstr(port,"windows-environment: 380 executions explicit owned map getters sorted UTF16 snapshots mutation free limits atomic denials stable cleanup PASS");serial-nl(port);
}
'''
(out/'kernel.in').write_text(source)
commands = [
    ['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],
    ['nasm','-f','bin',str(ROOT/'fixtures/windows-protected/environment.asm'),'-o',str(out/'process.exe')],
    [a.compiler,'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')],
]
with (out/'compile.log').open('w') as log:
    for command in commands:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
kernel=(out/'kernel.bin').read_bytes();payload=(out/'process.exe').read_bytes()
assert len(kernel)<=0x180000 and len(payload)==7168
(out/'combined.bin').write_bytes(kernel+bytes(0x180000-len(kernel))+payload)
received=bytearray();serial=None
with (out/'qemu.log').open('w') as qlog:
    path=out/'serial.sock'
    qemu_command=['qemu-system-x86_64','-kernel',str(out/'combined.bin'),'-m','512M','-display','none','-no-reboot','-serial',f'unix:{path},server=on,wait=on']
    qemu=subprocess.Popen(qemu_command,stdout=qlog,stderr=subprocess.STDOUT)
    try:
        deadline=time.monotonic()+10
        # A bound Unix socket can exist before QEMU starts listening. Retry
        # readiness within the same external deadline; guest limits/assertions
        # below are unchanged. Never treat pathname existence as a connection.
        while serial is None and qemu.poll() is None and time.monotonic()<deadline:
            candidate=socket.socket(socket.AF_UNIX);candidate.settimeout(.2)
            try:
                candidate.connect(str(path));serial=candidate
            except (FileNotFoundError,ConnectionRefusedError):
                candidate.close();time.sleep(.02)
        assert serial is not None,'QEMU serial did not become ready within10 seconds; inspect qemu.log'
        deadline=time.monotonic()+120
        while b'space> ' not in received and time.monotonic()<deadline:
            try:
                block=serial.recv(65536)
                if not block:break
                received.extend(block)
                if b'nanokernel fault handler halting' in received or b'PANIC' in received:break
            except socket.timeout:
                if qemu.poll() is not None:break
        text=received.decode(errors='replace')
        assert 'windows-environment: 380 executions explicit owned map getters sorted UTF16 snapshots mutation free limits atomic denials stable cleanup PASS' in text,text
        assert 'space> ' in text,text
    finally:
        (out/'serial.log').write_bytes(received)
        if serial:serial.close()
        qemu.terminate()
        try:qemu.wait(timeout=5)
        except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
report={'result':'PASS','executions':380,'compiler_sha256':hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),'boot_sha256':hashlib.sha256((ROOT/'boot/multiboot.asm').read_bytes()).hexdigest(),'fixture_sha256':hashlib.sha256(payload).hexdigest(),'kernel_sha256':hashlib.sha256(kernel).hexdigest(),'admission_refusals':11,'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['components/windows-process-environment.in','components/windows-process-identity.in','components/windows-process-parameters.in','components/windows-pe-startup.in','components/windows-pe-application.in','components/windows-protected.in','fixtures/windows-protected/environment.asm','components/domain.in','components/user-budget.in']},'commands':commands,'qemu_command':qemu_command}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
