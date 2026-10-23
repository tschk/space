#!/usr/bin/env python3
"""Exercise bounded Windows command-line and process startup APIs."""
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
source=source.replace('  shell(port)','  windows-parameters-check(port)\n  shell(port)')
source+=r'''

fn windows-parameters-free()->Int{let n=0;let f=free-list;while f!=0 && n<4096{n=n+1;f=load64(f);}return n;}
fn windows-parameters-refuse(image:Int,line:Int,bytes:Int)->void{
 let heap=heap-next;let free=free-list;let domains=domain-count;let owned=domain-user-owned;
 if windows-command-run(image,7168,-1,-1,line,bytes)!=-22 || heap-next!=heap || free-list!=free || domain-count!=domains || domain-user-owned!=owned || windows-parameters-active!=0{panic("Windows invalid command line mutated state");}
}
fn windows-parameters-copy(image:Int,line:Int,bytes:Int)->void{
 let i=0;while i<bytes{store8(image+5632+i,load8(line+i));i=i+1;}store64(image+5128,bytes);
}
fn windows-parameters-check(port:Int)->void{
 let image=0x280000;let line=alloc(1024);
 if windows-application-entry(image,7168)!=-8 || windows-startup-entry(image,7168)!=-8 || windows-protected-entry(image,7168)!=-8{panic("Existing Windows profiles widened imports");}
 let text="sqlite3.exe \":memory:\" \"select 6*7;\"";let bytes=strlen(text)+1;
 let i=0;while i<bytes{store8(line+i,load8(text+i));i=i+1;}
 windows-parameters-refuse(image,line,0);windows-parameters-refuse(image,line,1025);windows-parameters-refuse(image,0,bytes);
 store8(line+bytes - 1,65);windows-parameters-refuse(image,line,bytes);store8(line+bytes - 1,0);
 store8(line+1,0);windows-parameters-refuse(image,line,bytes);store8(line+1,113);
 store8(line+1,128);windows-parameters-refuse(image,line,bytes);store8(line+1,113);
 windows-parameters-copy(image,line,bytes);
 let caller-fs=rdmsr(0xc0000100);let caller-gs=rdmsr(0xc0000101);
 wrmsr64(0xc0000100,0x140005000);wrmsr64(0xc0000101,0x23456000);
 let cycle=0;let heap=0;let free=0;let domains=0;
 while cycle<21{
  let mode=0;while mode<13{
   store64(image+5120,mode);if mode==10{windows-protected-budget=5;}
   let status=windows-command-run(image,7168,-1,-1,line,bytes);windows-protected-budget=100;
   let expected=42;if mode==1 || mode==2 || mode==3 || mode==11{expected=142;}if mode==10{expected=124;}
   if status!=expected{serial-write-dec-wide(port,mode);serial-write-cstr(port," status ");serial-write-dec-wide(port,status);panic("Windows process parameters mismatch");}
   if rdmsr(0xc0000100)!=0x140005000 || rdmsr(0xc0000101)!=0x23456000{panic("Windows parameters segment restore");}
   if windows-protected-count!=0 || windows-protected-busy!=0 || domain-current!=0 || user-budget-active!=0 || domain-user-syscall-hook!=0 || windows-parameters-active!=0 || windows-parameters-line!=0 || windows-parameters-bytes!=0{panic("Windows parameters ownership leak");}
   i=0;while i<bytes{if load8(line+i)!=load8(image+5632+i){panic("Windows native input changed");}i=i+1;}
   mode=mode+1;
  }
  if cycle==0{heap=heap-next;free=windows-parameters-free();domains=domain-count;}
  else{if heap-next!=heap || windows-parameters-free()!=free || domain-count!=domains{panic("Windows parameters repeated cleanup leak");}}
  cycle=cycle+1;
 }
 store64(image+5120,0);store8(line,0);windows-parameters-copy(image,line,1);
 if windows-command-run(image,7168,-1,-1,line,1)!=42{panic("Windows empty command line");}
 i=0;while i<1023{store8(line+i,120);i=i+1;}store8(line+1023,0);windows-parameters-copy(image,line,1024);
 if windows-command-run(image,7168,-1,-1,line,1024)!=42{panic("Windows maximum command line");}
 if heap-next!=heap || windows-parameters-free()!=free || domain-count!=domains{panic("Windows command boundary resource leak");}
 wrmsr64(0xc0000100,caller-fs);wrmsr64(0xc0000101,caller-gs);
 serial-write-cstr(port,"windows-parameters: 275 executions command line startup info module handle pointer denials deadline stable cleanup PASS");serial-nl(port);
}
'''
(out/'kernel.in').write_text(source)
commands = [
    ['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],
    ['nasm','-f','bin',str(ROOT/'fixtures/windows-protected/parameters.asm'),'-o',str(out/'process.exe')],
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
        while not path.exists() and qemu.poll() is None and time.monotonic()<deadline:time.sleep(.02)
        serial=socket.socket(socket.AF_UNIX);serial.settimeout(.2);serial.connect(str(path))
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
        assert 'windows-parameters: 275 executions command line startup info module handle pointer denials deadline stable cleanup PASS' in text,text
        assert 'space> ' in text,text
    finally:
        (out/'serial.log').write_bytes(received)
        if serial:serial.close()
        qemu.terminate()
        try:qemu.wait(timeout=5)
        except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
report={'result':'PASS','executions':275,'compiler_sha256':hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),'boot_sha256':hashlib.sha256((ROOT/'boot/multiboot.asm').read_bytes()).hexdigest(),'fixture_sha256':hashlib.sha256(payload).hexdigest(),'kernel_sha256':hashlib.sha256(kernel).hexdigest(),'admission_refusals':6,'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['components/windows-process-parameters.in','components/windows-pe-startup.in','components/windows-pe-application.in','components/windows-protected.in','fixtures/windows-protected/parameters.asm','components/domain.in','components/user-budget.in']},'commands':commands,'qemu_command':qemu_command}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
