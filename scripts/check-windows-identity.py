#!/usr/bin/env python3
"""Exercise protected Windows process/thread identity and TEB LastError."""
from boot_fixture_layout import stage_fixture
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
source=source.replace('  shell(port)','  windows-identity-check(port)\n  shell(port)')
source+='''

fn windows-identity-free()->Int{let n=0;let f=free-list;while f!=0 && n<4096{n=n+1;f=load64(f);}return n;}
fn windows-identity-check(port:Int)->void{
 let image=0x2f0000;let line="sqlite3.exe -version";
 if windows-application-entry(image,7168)!=-8 || windows-startup-entry(image,7168)!=-8{panic("Previous Windows profiles widened identity imports");}
 let caller-fs=rdmsr(0xc0000100);let caller-gs=rdmsr(0xc0000101);
 wrmsr64(0xc0000100,0x140005000);wrmsr64(0xc0000101,0x23456000);
 let cycle=0;let heap=0;let free=0;let domains=0;
 while cycle<21{
  let mode=0;while mode<6{
   store64(image+5120,mode);if mode==5{windows-protected-budget=5;}
   let status=windows-command-run(image,7168,-1,-1,line,strlen(line)+1);windows-protected-budget=100;
   let expected=42;if mode==4{expected=142;}if mode==5{expected=124;}
   if status!=expected{serial-write-dec-wide(port,mode);serial-write-dec-wide(port,status);panic("Windows identity/error result mismatch");}
   if rdmsr(0xc0000100)!=0x140005000 || rdmsr(0xc0000101)!=0x23456000 || windows-protected-error!=0 || windows-protected-profile!=0{panic("Windows identity/error activation state leaked");}
   if windows-protected-count!=0 || windows-protected-busy!=0 || domain-current!=0 || user-budget-active!=0 || domain-user-syscall-hook!=0 || windows-parameters-active!=0{panic("Windows identity ownership leak");}
   mode=mode+1;
  }
  if cycle==0{heap=heap-next;free=windows-identity-free();domains=domain-count;}
  else{if heap-next!=heap || windows-identity-free()!=free || domain-count!=domains{panic("Windows identity repeated cleanup leak");}}
  cycle=cycle+1;
 }
 wrmsr64(0xc0000100,caller-fs);wrmsr64(0xc0000101,caller-gs);
 serial-write-cstr(port,"windows-identity: 126 executions current process thread TEB LastError pseudo-handle refusal fault deadline stable cleanup PASS");serial-nl(port);
}
'''
(out/'kernel.in').write_text(source)
commands = [
    ['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],
    ['nasm','-f','bin',str(ROOT/'fixtures/windows-protected/identity.asm'),'-o',str(out/'process.exe')],
    [a.compiler,'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')],
]
with (out/'compile.log').open('w') as log:
    for command in commands:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
kernel=(out/'kernel.bin').read_bytes();payload=(out/'process.exe').read_bytes()
assert len(kernel)<=0x1f0000 and len(payload)==7168
(out/'combined.bin').write_bytes(stage_fixture(kernel,payload,0x2f0000))
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
        assert 'windows-identity: 126 executions current process thread TEB LastError pseudo-handle refusal fault deadline stable cleanup PASS' in text,text
        assert 'space> ' in text,text
    finally:
        (out/'serial.log').write_bytes(received)
        if serial:serial.close()
        qemu.terminate()
        try:qemu.wait(timeout=5)
        except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
report={'result':'PASS','executions':126,'compiler_sha256':hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),'boot_sha256':hashlib.sha256((ROOT/'boot/multiboot.asm').read_bytes()).hexdigest(),'fixture_sha256':hashlib.sha256(payload).hexdigest(),'kernel_sha256':hashlib.sha256(kernel).hexdigest(),'admission_refusals':0,'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['components/windows-process-identity.in','components/windows-process-parameters.in','components/windows-pe-startup.in','components/windows-pe-application.in','components/windows-protected.in','fixtures/windows-protected/identity.asm','components/domain.in','components/user-budget.in']},'commands':commands,'qemu_command':qemu_command}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
