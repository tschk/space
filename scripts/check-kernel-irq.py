#!/usr/bin/env python3
"""Verify actual CPL0 PIT interrupts preserve interrupted CPU state."""
from boot_fixture_layout import stage_fixture
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
p.add_argument('--trampoline', type=Path, help='Explicit retained baseline CPU trampoline for negative control')
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
var kernel-irq-state:Int=0
fn kernel-irq-check-tick(vector:Int)->void{
 store64(kernel-irq-state,load64(kernel-irq-state)+1);
 store64(kernel-irq-state+16,invoke1(load64(0x4198),0)&1024);
 store64(kernel-irq-state+32,vector);
 invoke1(0x2e0400,0);
 outb(0x20,0x20);
}
fn user-syscall-check(port:Int)->void{
 kernel-irq-state=alloc(48);
 store64(0x2e0600,kernel-irq-check-tick);store64(0x2e0608,0);
 let original=load64(0x4000);let cycle=0;
 while cycle<16{
  store64(kernel-irq-state,0);store64(kernel-irq-state+8,0);store64(kernel-irq-state+16,0);
  store64(kernel-irq-state+24,(cycle%2)*8);store64(kernel-irq-state+32,0);
  cli();store64(0x4000,0x2e0500);sti();
  let result=invoke1(0x2e0000,kernel-irq-state);
  cli();store64(0x4000,original);sti();
  if result!=42 || load64(kernel-irq-state+16)!=0 || load64(kernel-irq-state+32)!=32 || load64(0x2e0608)!=8{
   serial-write-cstr(port,"irq: result ");serial-write-hex(port,result);
   serial-write-cstr(port," R11 ");serial-write-hex(port,load64(kernel-irq-state+8));
   serial-write-cstr(port," callback DF ");serial-write-hex(port,load64(kernel-irq-state+16));
   panic("kernel IRQ context corruption");
  }
  cycle=cycle+1;
 }
 serial-write-cstr(port,"irq: CPL0 real PIT aligned scratch GP FPU DF both stack alignments PASS");serial-nl(port);
}
'''
(out/'kernel.in').write_text(source)
with (out/'compile.log').open('w') as log:
    for command in [
        (['cp',str(a.trampoline),str(out/'trampoline.bin')] if a.trampoline else ['nasm','-f','bin',str(root/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')]),
        ['nasm','-f','bin',str(root/'fixtures/runtime-failure/kernel-irq.asm'),'-o',str(out/'user-syscall.bin')],
        [a.compiler,'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')],
    ]:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
kernel=(out/'kernel.bin').read_bytes();payload=(out/'user-syscall.bin').read_bytes()
assert len(kernel)<=0x1e0000 and len(payload)==4096
(out/'combined.bin').write_bytes(stage_fixture(kernel,payload,0x2e0000))
received=bytearray();serial=None
report={'status':'failed','compiler':a.compiler,'kernel_sha256':hashlib.sha256(kernel).hexdigest(),'payload_sha256':hashlib.sha256(payload).hexdigest()}
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
        assert 'irq: CPL0 real PIT aligned scratch GP FPU DF both stack alignments PASS' in text,text
        assert 'space interactive shell' in text,text
        serial.sendall(b'halt\n')
        report={'status':'passed','executions':16,'irqs_minimum':48,'interrupted_alignments':[0,8],'native_callee_entry_alignment':8,'parameter_home_bytes':64,'cpu':a.cpu,'compiler':a.compiler,'compiler_sha256':hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),'kernel_sha256':hashlib.sha256(kernel).hexdigest(),'payload_sha256':hashlib.sha256(payload).hexdigest()}
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(f'PASS: actual kernel IRQ context preservation; {out}')
    finally:
        (out/'serial.log').write_bytes(received)
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        if serial:serial.close()
        qemu.terminate()
        try:qemu.wait(timeout=3)
        except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
