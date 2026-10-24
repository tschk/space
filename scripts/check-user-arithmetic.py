#!/usr/bin/env python3
"""Trigger real CPL3 divide, breakpoint, x87 and SSE exceptions and recover."""
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
p.add_argument('--cpu', choices=['qemu64','max'], default='qemu64')
p.add_argument('--vector', type=int, choices=[0,3,16,19], help='Explicit single-vector scope; default tests all four')
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
fn user-syscall-check(port:Int)->void{
 let domain=domain-create-user();let stack=frame-alloc();let context=alloc(32);
 domain-map-user-code(domain,0x42000000,0x2e0000);domain-map-user-data(domain,0x43000000,stack);
 let cycle=0;
 while cycle<8{
  let mode=0;
  while mode<4{
   let vector=0;if mode==1{vector=3;}if mode==2{vector=16;}if mode==3{vector=19;}
   let result=domain-enter-user-prepared(0x42000000,vector,domain,0x43000ff0,context);
   if result!=128+vector{serial-write-hex(port,result);serial-write-cstr(port," mxcsr ");serial-write-hex(port,load64(stack+4080-8));panic("arithmetic exception outcome");}
   mode=mode+1;
  }
  cycle=cycle+1;
 }
 if domain-destroy-user(domain)!=0{panic("arithmetic exception teardown");}frame-free(stack);
 serial-write-cstr(port,"faults: selected CPL3 arithmetic vectors exact status and repeated recovery PASS");serial-nl(port);
}
'''
if a.vector is not None:
    source=source.replace('while mode<4{', 'while mode<1{').replace('let vector=0;if mode==1{vector=3;}if mode==2{vector=16;}if mode==3{vector=19;}',f'let vector={a.vector};')
(out/'kernel.in').write_text(source)
with (out/'compile.log').open('w') as log:
    for command in [
        ['nasm','-f','bin',str(root/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],
        ['nasm','-f','bin',str(root/'fixtures/runtime-failure/user-arithmetic.asm'),'-o',str(out/'user-syscall.bin')],
        [a.compiler,'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')],
    ]:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
kernel=(out/'kernel.bin').read_bytes();payload=(out/'user-syscall.bin').read_bytes()
assert len(kernel)<=0x1e0000 and len(payload)==4096
(out/'combined.bin').write_bytes(stage_fixture(kernel,payload,0x2e0000))
received=bytearray();serial=None
report={'status':'failed','executions_expected':32 if a.vector is None else 8,
        'vectors':[0,3,16,19] if a.vector is None else [a.vector],
        'cpu':a.cpu,'compiler':a.compiler,
        'compiler_sha256':hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),
        'kernel_sha256':hashlib.sha256(kernel).hexdigest(),
        'payload_sha256':hashlib.sha256(payload).hexdigest()}
with (out/'qemu.log').open('w') as qlog:
    path=out/'serial.sock'
    qemu=subprocess.Popen(['qemu-system-x86_64','-kernel',str(out/'combined.bin'),'-m','512M','-d','int','-D',str(out/'cpu-interrupts.log'),'-cpu',a.cpu,'-display','none','-no-reboot','-serial',f'unix:{path},server=on,wait=on'],stdout=qlog,stderr=subprocess.STDOUT)
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
        assert 'faults: selected CPL3 arithmetic vectors exact status and repeated recovery PASS' in text,text
        assert 'space interactive shell' in text,text
        serial.sendall(b'halt\n')
        report['status']='passed'
        print(f'PASS: real CPL3 arithmetic exception isolation; {out}')
    finally:
        (out/'serial.log').write_bytes(received)
        report['observed_vectors']=[int(v,16) for v in re.findall(rb'guest fault vector 0x([0-9a-f]+)',received)]
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        if serial:serial.close()
        qemu.terminate()
        try:qemu.wait(timeout=3)
        except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
