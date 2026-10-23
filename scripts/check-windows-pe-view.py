#!/usr/bin/env python3
"""Exercise checked variable PE headers and larger private CPL3 images."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();out=a.out.resolve()
assert not out.exists() or not any(out.iterdir()),'--out must be new or empty'
out.mkdir(parents=True,exist_ok=True)
source=(ROOT/'kernel/kernel-root.in').read_text()
source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(ROOT/m.group(1))),source)
assert source.count('  shell(port)')==1
source=source.replace('  shell(port)','  windows-view-check(port)\n  shell(port)')
source+='''
fn windows-view-free()->Int{let n=0;let f=free-list;while f!=0 && n<8192{n=n+1;f=load64(f);}return n;}
fn windows-view-refuse(image:Int,size:Int,off:Int,value:Int,wide:Int)->void{
 let old=load32(image+off);if wide!=0{old=load64(image+off);}let heap=heap-next;let free=free-list;let domains=domain-count;let owned=domain-user-owned;
 store32(image+off,value);if wide!=0{store64(image+off,value);}let result=windows-application-run(image,size,-1,-1);
 store32(image+off,old);if wide!=0{store64(image+off,old);}
 if result!=-8 || heap-next!=heap || free-list!=free || domain-count!=domains || domain-user-owned!=owned{panic("Windows PE view malformed changed state");}
}
fn windows-view-one(image:Int,pe:Int)->void{
 let size=3147776;
 if windows-application-structure-entry(image,size)!=0x140001000 || windows-application-pages(image)!=778{panic("Windows large PE layout mismatch");}
 if windows-protected-entry(image,size)!=-8{panic("Windows strict profile widened PE view");}
 windows-view-refuse(image,size,60,60,0);windows-view-refuse(image,size,60,4096,0);windows-view-refuse(image,size,60,pe+1,0);
 windows-view-refuse(image,size,pe+6,17,0);windows-view-refuse(image,size,pe+4,0x14c,0);
 windows-view-refuse(image,size,pe+84,256,0);windows-view-refuse(image,size,pe+94,0xc160,0);
 windows-view-refuse(image,size,pe+264+8,0x400001,0);windows-view-refuse(image,size,pe+264+16,0x400200,0);
 let old-end=heap-end;let old-free=free-list;let old-heap=heap-next;let old-domains=domain-count;
 heap-end=heap-next;free-list=0;let refused=windows-application-run(image,size,-1,-1);heap-end=old-end;free-list=old-free;
 if refused!=-12 || heap-next!=old-heap || domain-count!=old-domains{panic("Windows large PE resource refusal changed state");}
 let caller-fs=rdmsr(0xc0000100);let caller-gs=rdmsr(0xc0000101);
 wrmsr64(0xc0000100,0x140303000);wrmsr64(0xc0000101,0x140303000);
 let cycle=0;let heap=0;let free=0;let domains=0;
 while cycle<3{
  let mode=0;while mode<9{
   store64(image+3147264,mode);if mode==6{windows-protected-budget=5;}
   let result=windows-application-run(image,size,-1,-1);windows-protected-budget=100;
   let expected=142;if mode==0{expected=42;}if mode==6{expected=124;}
   if result!=expected{serial-write-dec-wide(com1(),pe);serial-write-dec-wide(com1(),mode);serial-write-dec-wide(com1(),result);panic("Windows large PE execution mismatch");}
   if rdmsr(0xc0000100)!=0x140303000 || rdmsr(0xc0000101)!=0x140303000 || windows-protected-count!=0 || windows-protected-busy!=0 || domain-current!=0 || user-budget-active!=0 || domain-user-syscall-hook!=0{panic("Windows large PE ownership/segment leak");}
   mode=mode+1;
  }
  if cycle==0{heap=heap-next;free=windows-view-free();domains=domain-count;}
  else{if heap-next!=heap || windows-view-free()!=free || domain-count!=domains{panic("Windows large PE repeated cleanup leak");}}
  cycle=cycle+1;
 }
 wrmsr64(0xc0000100,caller-fs);wrmsr64(0xc0000101,caller-gs);
}
fn windows-view-check(port:Int)->void{
 if heap-next>=0x10000000{panic("Windows PE staging collides with heap");}heap-end=0x10000000;
 windows-view-one(0x10000000,64);windows-view-one(0x11000000,128);windows-view-one(0x12000000,256);
 serial-write-cstr(port,"windows-pe-view: 81 large-image executions variable headers last RX page CPU denials budget resource refusal stable cleanup PASS");serial-nl(port);
}
'''
(out/'kernel.in').write_text(source)
commands=[['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')]]
loaders=[]
for i,pe in enumerate([64,128,256]):
    payload=out/f'view-{pe}.exe'
    commands.append(['nasm','-f','bin',f'-DPE_OFFSET={pe}',str(ROOT/'fixtures/windows-protected/pe-view.asm'),'-o',str(payload)])
    loaders.extend(['-device',f'loader,file={payload},addr={0x10000000+i*0x1000000:#x},force-raw=on'])
commands.append([a.compiler,'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')])
with (out/'compile.log').open('w') as log:
    for command in commands:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
kernel=(out/'kernel.bin').read_bytes();assert 0x100000+len(kernel)<0x10000000
serial_path=out/'serial.sock';received=bytearray();serial=None
qemu_command=['qemu-system-x86_64','-kernel',str(out/'kernel.bin'),'-m','512M','-display','none','-no-reboot','-serial',f'unix:{serial_path},server=on,wait=on']+loaders
with (out/'qemu.log').open('w') as log:
    qemu=subprocess.Popen(qemu_command,stdout=log,stderr=subprocess.STDOUT)
    try:
        deadline=time.monotonic()+10
        while not serial_path.exists() and qemu.poll() is None and time.monotonic()<deadline:time.sleep(.02)
        serial=socket.socket(socket.AF_UNIX);serial.settimeout(.2);serial.connect(str(serial_path))
        deadline=time.monotonic()+180
        while b'space> ' not in received and time.monotonic()<deadline:
            try:
                block=serial.recv(65536)
                if not block:break
                received.extend(block)
                if b'PANIC' in received or b'nanokernel fault handler halting' in received:break
            except socket.timeout:
                if qemu.poll() is not None:break
        text=received.decode(errors='replace')
        assert 'windows-pe-view: 81 large-image executions variable headers last RX page CPU denials budget resource refusal stable cleanup PASS' in text,text
        assert 'space> ' in text,text
    finally:
        (out/'serial.log').write_bytes(received)
        if serial:serial.close()
        qemu.terminate()
        try:qemu.wait(timeout=5)
        except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
report=dict(status='passed',executions=81,refusals=30,compiler_sha256=hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),kernel_sha256=hashlib.sha256(kernel).hexdigest(),source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['components/windows-pe-view.in','components/windows-pe-application.in','components/windows-protected.in','components/windows-pe-startup.in','fixtures/windows-protected/pe-view.asm','boot/multiboot.asm']},commands=commands,qemu_command=qemu_command)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['status','executions','refusals']}))
