#!/usr/bin/env python3
"""Test actual PIT-driven CPL3 budget cancellation and resumable IRQ state."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import time

root = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--cpu', choices=['qemu64','max'], default='qemu64')
a = p.parse_args()
out = a.out.resolve()
if out.exists() and any(out.iterdir()):
    p.error('--out must be new or empty')
out.mkdir(parents=True, exist_ok=True)
source = (root/'kernel/kernel-root.in').read_text()
source = re.sub(r'import "\.\./([^"]+)"', lambda m: 'import '+json.dumps(str(root/m.group(1))), source)
assert source.count('  shell(port)') == 1
source = source.replace('  shell(port)', '  user-syscall-check(port)\n  shell(port)')
source += r'''
fn budget-hook(frame:Int)->Int{
 let number=load64(frame+112);
 if number==704{store64(frame+112,ticks);return 1;}
 if number==703{store64(frame+112,load64(frame+72));return 0;}
 panic("budget unexpected syscall");return 0;
}
fn user-syscall-check(port:Int)->void{
 let domain=domain-create-user();let stack=frame-alloc();let context=alloc(32);
 domain-map-user-code(domain,0x42000000,0x280000);domain-map-user-data(domain,0x43000000,stack);
 let previous-hook=domain-user-syscall-hook;domain-user-syscall-hook=budget-hook;
 let mask=inb(0x21);let before-cap=current-cap;
 let cycle=0;let stable-heap=0;
 while cycle<8{
  let mode=0;
  while mode<3{
   let before=ticks;
   let result=domain-enter-user-budgeted(0x42000000,mode,domain,0x43000ff0,context,10);
   let expected=124;if mode==1{expected=42;}if mode==2{expected=134;}
   if result!=expected{serial-write-hex(port,result);panic("budget outcome");}
   if mode==0 && ticks - before<10{panic("budget did not consume timer ticks");}
   if mode==1 && ticks - before<3{panic("finite workload did not observe timer IRQs");}
   if user-budget-active!=0 || inb(0x21)!=mask || current-cap!=before-cap || domain-user-syscall-hook!=budget-hook{panic("budget scope restore");}
   if (invoke1(load64(0x4198),0)&512)==0{panic("budget caller IF restore");}
   mode=mode+1;
  }
  if cycle==0{stable-heap=heap-next;}else{if heap-next!=stable-heap{panic("budget repeated entry allocated");}}
  cycle=cycle+1;
 }
 // The wrapper must unmask IRQ0 temporarily and restore a caller-masked PIC.
 outb(0x21,mask|1);
 let masked-result=domain-enter-user-budgeted(0x42000000,0,domain,0x43000ff0,context,2);
 if masked-result!=124 || inb(0x21)!=(mask|1){panic("budget masked PIC restore");}
 outb(0x21,mask);
 // An IF0 caller must remain IF0 after an interruptible guest activation.
 cli();
 let disabled-result=domain-enter-user-budgeted(0x42000000,1,domain,0x43000ff0,context,10);
 if disabled-result!=42 || (invoke1(load64(0x4198),0)&512)!=0{panic("budget IF0 caller restore");}
 sti();
 if domain-enter-user-budgeted(0x42000000,0,domain,0x43000ff0,context,0)!=-1{panic("budget invalid count accepted");}
 domain-user-syscall-hook=previous-hook;
 if domain-destroy-user(domain)!=0{panic("budget teardown");}frame-free(stack);
 serial-write-cstr(port,"budget: CPL3 IRQ0 infinite-loop cancellation finite GP FPU state fault and scope restore PASS");serial-nl(port);
}
'''
(out/'kernel.in').write_text(source)
with (out/'compile.log').open('w') as log:
    for command in [
        ['nasm','-f','bin',str(root/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],
        ['nasm','-f','bin',str(root/'fixtures/runtime-failure/user-budget.asm'),'-o',str(out/'user-syscall.bin')],
        [a.compiler,'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')],
    ]:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
kernel=(out/'kernel.bin').read_bytes();payload=(out/'user-syscall.bin').read_bytes()
assert len(kernel)<=0x180000 and len(payload)==4096
(out/'combined.bin').write_bytes(kernel+bytes(0x180000-len(kernel))+payload)
received=bytearray();serial=None
with (out/'qemu.log').open('w') as qlog:
    path=out/'serial.sock'
    qemu=subprocess.Popen(['qemu-system-x86_64','-kernel',str(out/'combined.bin'),'-m','512M','-cpu',a.cpu,'-display','none','-no-reboot','-serial',f'unix:{path},server=on,wait=on'],stdout=qlog,stderr=subprocess.STDOUT)
    try:
        deadline=time.monotonic()+10
        while not path.exists() and qemu.poll() is None and time.monotonic()<deadline:time.sleep(.02)
        serial=socket.socket(socket.AF_UNIX);serial.settimeout(.2);serial.connect(str(path))
        deadline=time.monotonic()+90
        while b'space interactive shell' not in received and time.monotonic()<deadline:
            try:
                block=serial.recv(65536)
                if not block:break
                received.extend(block)
                if b'nanokernel fault handler halting' in received or b'PANIC' in received:break
            except socket.timeout:
                if qemu.poll() is not None:break
        text=received.decode(errors='replace')
        assert 'budget: CPL3 IRQ0 infinite-loop cancellation finite GP FPU state fault and scope restore PASS' in text,text
        assert 'space interactive shell' in text,text
        serial.sendall(b'halt\n')
        report={'status':'passed','executions':26,'cycles':8,'masked_pic_restore':True,'caller_if0_restore':True,'cpu':a.cpu,'compiler':a.compiler,'compiler_sha256':hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),'kernel_sha256':hashlib.sha256(kernel).hexdigest(),'payload_sha256':hashlib.sha256(payload).hexdigest()}
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(f'PASS: scoped CPL3 IRQ0 execution budget; {out}')
    finally:
        (out/'serial.log').write_bytes(received)
        if serial:serial.close()
        qemu.terminate()
        try:qemu.wait(timeout=3)
        except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
