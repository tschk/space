#!/usr/bin/env python3
"""Exercise actual strict CPL3 SYSCALL and INT80 with resumable register state."""
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
var bridge-calls=0
fn bridge-hook(frame:Int)->Int{
 bridge-calls=bridge-calls+1;
 let number=load64(frame+112);
 if number==701{
  if load64(frame+72)!=17 || load64(frame+80)!=23 || load64(frame+40)!=29{panic("bridge argument frame");}
  store64(frame+112,69);store64(frame+136,load64(frame+136)|1);return 1;
 }
 if number==702{store64(frame+112,77);store64(frame+136,load64(frame+136)&-2);return 1;}
 if number==703{store64(frame+112,load64(frame+72));return 0;}
 panic("bridge unexpected syscall");return 0;
}
fn user-syscall-check(port:Int)->void{
 let entropy=alloc(16);store64(entropy,12345);store64(entropy+8,67890);
 let random=load64(0x4170);if random==0{panic("missing hardware entropy capsule");}
 let random-status=invoke1(random,entropy);
 if random-status!=RANDOM-EXPECTED{panic("hardware entropy CPU contract");}
 if random-status==0{
  if invoke1(random,entropy+8)!=0{panic("hardware entropy second sample");}
  if load64(entropy)==12345 || load64(entropy+8)==67890 || load64(entropy)==load64(entropy+8){panic("hardware entropy repeated or unchanged");}
 }else{
  if load64(entropy)!=12345 || load64(entropy+8)!=67890{panic("unsupported entropy wrote output");}
 }
 let domain=domain-create-user();let stack=frame-alloc();let context=alloc(32);
 domain-map-user-code(domain,0x42000000,0x2e0000);
 domain-map-user-data(domain,0x43000000,stack);
 domain-user-syscall-hook=bridge-hook;
 let result=domain-enter-user-prepared(0x42000000,0,domain,0x43000ff0,context);
 domain-user-syscall-hook=0;
 if result!=42 || bridge-calls!=3{serial-write-hex(port,result);panic("bridge state or continuation");}
 if domain-destroy-user(domain)!=0{panic("bridge teardown");}
 frame-free(stack);
 serial-write-cstr(port,"bridge: strict CPL3 SYSCALL INT80 resume GP SSE RSP flags and exit PASS");serial-nl(port);
}
'''
source=source.replace('RANDOM-EXPECTED', '0' if a.cpu=='max' else '-38')
(out/'kernel.in').write_text(source)
with (out/'compile.log').open('w') as log:
    for command in [
        ['nasm','-f','bin',str(root/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],
        ['nasm','-f','bin',str(root/'fixtures/runtime-failure/user-syscall.asm'),'-o',str(out/'user-syscall.bin')],
        [a.compiler,'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')],
    ]:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
kernel=(out/'kernel.bin').read_bytes();payload=(out/'user-syscall.bin').read_bytes()
assert len(kernel)<=0x1e0000 and len(payload)==4096
(out/'combined.bin').write_bytes(stage_fixture(kernel,payload,0x2e0000))
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
        assert 'bridge: strict CPL3 SYSCALL INT80 resume GP SSE RSP flags and exit PASS' in text,text
        assert 'space interactive shell' in text,text
        serial.sendall(b'halt\n')
        report={'status':'passed','resumed_calls':2,'exit_calls':1,'cpu':a.cpu,'entropy':'hardware RDRAND' if a.cpu=='max' else 'unsupported; output unchanged','compiler':a.compiler,'compiler_sha256':hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),'kernel_sha256':hashlib.sha256(kernel).hexdigest(),'payload_sha256':hashlib.sha256(payload).hexdigest()}
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(f'PASS: strict CPL3 resumable SYSCALL/INT80 CPU bridge; {out}')
    finally:
        (out/'serial.log').write_bytes(received)
        if serial:serial.close()
        qemu.terminate()
        try:qemu.wait(timeout=3)
        except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
