#!/usr/bin/env python3
"""Exercise bounded protected Windows TEB/static TLS startup and CPU-state cleanup."""
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
source=source.replace('  shell(port)','  windows-startup-check(port)\n  shell(port)')
source+='''
fn windows-startup-free()->Int{let n=0;let f=free-list;while f!=0 && n<4096{n=n+1;f=load64(f);}return n;}
fn windows-startup-refuse(image:Int,off:Int,value:Int,wide:Int)->void{
 let old=load32(image+off);if wide!=0{old=load64(image+off);}let heap=heap-next;let free=free-list;let domains=domain-count;let owned=domain-user-owned;
 store32(image+off,value);if wide!=0{store64(image+off,value);}let result=windows-startup-run(image,5632,-1,-1);
 store32(image+off,old);if wide!=0{store64(image+off,old);}
 if result!=-8 || heap-next!=heap || free-list!=free || domain-count!=domains || domain-user-owned!=owned{serial-write-dec-wide(com1(),off);panic("Windows TLS malformed changed state");}
}
fn windows-startup-check(port:Int)->void{
 let image=0x280000;
 if windows-application-entry(image,5632)!=-8 || windows-protected-entry(image,5632)!=-8{panic("Existing PE profiles widened");}
 windows-startup-refuse(image,340,39,0);
 windows-startup-refuse(image,336,0x6ff0,0);
 windows-startup-refuse(image,4608,0x100000,1);
 windows-startup-refuse(image,4616,0x140003000,1);
 windows-startup-refuse(image,4624,0x140003080,1);
 windows-startup-refuse(image,4624,0x140005011,1);
 windows-startup-refuse(image,4632,0x100000,1);
 windows-startup-refuse(image,4632,0x140006000,1);
 windows-startup-refuse(image,4632,0x140003041,1);
 windows-startup-refuse(image,4640,4096,0);
 windows-startup-refuse(image,4644,0x00e00000,0);
 windows-startup-refuse(image,4644,1,0);
 windows-startup-refuse(image,4672,0x140003080,1);
 windows-startup-refuse(image,4672,0x100000,1);
 windows-startup-refuse(image,4672,0x140005000,1);
 let caller-fs=rdmsr(0xc0000100);let caller-gs=rdmsr(0xc0000101);
 wrmsr64(0xc0000100,0x140005000);wrmsr64(0xc0000101,0x23456000);
 let cycle=0;let heap=0;let free=0;let domains=0;
 while cycle<21{
  let mode=0;while mode<8{
   store64(image+5120,mode);if mode==2{windows-protected-budget=5;}
   let status=windows-startup-run(image,5632,-1,-1);windows-protected-budget=100;
   let expected=42;if mode==1 || mode==4 || mode==5 || mode==6 || mode==7{expected=142;}if mode==2{expected=124;}if mode==3{expected=141;}
   if status!=expected{serial-write-dec-wide(port,mode);serial-write-cstr(port," status ");serial-write-dec-wide(port,status);panic("Windows TLS execution mismatch");}
   if rdmsr(0xc0000100)!=0x140005000 || rdmsr(0xc0000101)!=0x23456000{panic("Windows segment bases not restored");}
   if windows-protected-count!=0 || windows-protected-busy!=0 || domain-current!=0 || user-budget-active!=0 || domain-user-syscall-hook!=0{panic("Windows TLS cleanup leaked");}
   if load32(image+5136)!=0xdeadbeef || load64(image+5128)!=0 || load64(image+4736)!=-8613303245920329199{panic("Windows TLS source changed");}
   mode=mode+1;
  }
  if cycle==0{heap=heap-next;free=windows-startup-free();domains=domain-count;}
  else{if heap-next!=heap || windows-startup-free()!=free || domain-count!=domains{panic("Windows TLS repeated cleanup leak");}}
  cycle=cycle+1;
 }
 // Eight callbacks accepted; a ninth non-null callback refused before entry.
 let first=load64(image+4672);let second=load64(image+4680);let callback-array=load64(image+4632);
 let c=0;while c<8{store64(image+4864+c*8,first);c=c+1;}store64(image+4920,second);store64(image+4928,0);
 store64(image+4632,0x140003100);store64(image+5120,0);
 windows-startup-refuse(image,4928,first,1);
 if windows-startup-run(image,5632,-1,-1)!=42{panic("Windows eight TLS callbacks failed");}
 store64(image+4632,0);store64(image+5120,8);
 if windows-startup-run(image,5632,-1,-1)!=42{panic("Windows null TLS callbacks failed");}
 let directory=load64(image+336);store64(image+336,0);store64(image+5120,9);
 if windows-startup-run(image,5632,-1,-1)!=42{panic("Windows TEB without TLS failed");}
 store64(image+336,directory);store64(image+4632,callback-array);
 if rdmsr(0xc0000100)!=0x140005000 || rdmsr(0xc0000101)!=0x23456000{panic("Windows boundary segment restore failed");}
 wrmsr64(0xc0000100,caller-fs);wrmsr64(0xc0000101,caller-gs);
 serial-write-cstr(port,"windows-startup: 171 executions TEB TLS callbacks CPU denials deadline segment restoration stable cleanup PASS");serial-nl(port);
}
'''
(out/'kernel.in').write_text(source)
commands = [
    ['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],
    ['nasm','-f','bin',str(ROOT/'fixtures/windows-protected/startup.asm'),'-o',str(out/'process.exe')],
    [a.compiler,'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')],
]
with (out/'compile.log').open('w') as log:
    for command in commands:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
kernel=(out/'kernel.bin').read_bytes();payload=(out/'process.exe').read_bytes()
assert len(kernel)<=0x180000 and len(payload)==5632
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
        assert 'windows-startup: 171 executions TEB TLS callbacks CPU denials deadline segment restoration stable cleanup PASS' in text,text
        assert 'space> ' in text,text
    finally:
        (out/'serial.log').write_bytes(received)
        if serial:serial.close()
        qemu.terminate()
        try:qemu.wait(timeout=5)
        except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
report={'result':'PASS','executions':171,'compiler_sha256':hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),'boot_sha256':hashlib.sha256((ROOT/'boot/multiboot.asm').read_bytes()).hexdigest(),'fixture_sha256':hashlib.sha256(payload).hexdigest(),'kernel_sha256':hashlib.sha256(kernel).hexdigest(),'admission_refusals':16,'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['components/windows-pe-startup.in','components/windows-pe-application.in','components/windows-protected.in','fixtures/windows-protected/startup.asm','components/domain.in','components/user-budget.in']},'commands':commands,'qemu_command':qemu_command}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
