#!/usr/bin/env python3
"""Check strict entry register confidentiality and exact kernel FX restoration."""
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
p.add_argument('--probe',choices=['all','gp','x87','xmm'],default='all',help='Independent observation for negative controls')
p.add_argument('--trampoline',type=Path,help='Existing trampoline for a negative control')
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
fn bridge-hook(frame:Int)->Int{store64(frame+112,load64(frame+72));return 0;}
fn initial-launch(info:Int)->Int{
 let domain=load64(info);let stack=load64(info+8);let context=load64(info+16);let mode=load64(info+24);let operation=mode&255;
 if operation>=2{return domain-enter-user-budgeted(0x42000000,mode,domain,0x43000ff0,context,if operation==2{2}else{100});}
 return domain-enter-user-prepared(0x42000000,mode,domain,0x43000ff0,context);
}
fn user-syscall-check(port:Int)->void{
 let domain=domain-create-user();let stack=frame-alloc();let context=alloc(32);let job=alloc(40);
 domain-map-user-code(domain,0x42000000,0x2e1000);domain-map-user-data(domain,0x43000000,stack);
 store64(job,initial-launch);store64(job+8,domain);store64(job+16,stack);store64(job+24,context);
 domain-user-syscall-hook=bridge-hook;
 let i=0;
 while i<16{
  let mode=i%4;store64(job+32,mode|PROBE-MASK);
  let expected=42;if mode==1{expected=134;}if mode==2{expected=124;}
  let result=invoke1(0x2e0000,job);
  if result!=expected{serial-write-hex(port,result);panic("initial state confidentiality or kernel restoration");}
  i=i+1;
 }
 domain-user-syscall-hook=0;
 if domain-destroy-user(domain)!=0{panic("initial state teardown");}frame-free(stack);
 serial-write-cstr(port,"bridge: strict entry GP x87 XMM zero and kernel FX exact restore normal fault timeout PASS");serial-nl(port);
}
'''
source=source.replace('PROBE-MASK',str({'all':0,'gp':0x600,'x87':0x500,'xmm':0x300}[a.probe]))
(out/'kernel.in').write_text(source)
with (out/'compile.log').open('w') as log:
    for command in [
        ['nasm','-f','bin',str(root/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],
        ['nasm','-f','bin',str(root/'fixtures/runtime-failure/user-initial-state.asm'),'-o',str(out/'user-syscall.bin')],
        [a.compiler,'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')],
    ]:
        if a.trampoline and command[0]=='nasm' and command[3]==str(root/'boot/multiboot.asm'):
            (out/'trampoline.bin').write_bytes(a.trampoline.read_bytes())
        else:
            subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
kernel=(out/'kernel.bin').read_bytes();payload=(out/'user-syscall.bin').read_bytes()
assert len(kernel)<=0x1e0000 and len(payload)==8192
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
        assert 'bridge: strict entry GP x87 XMM zero and kernel FX exact restore normal fault timeout PASS' in text,text
        assert 'space interactive shell' in text,text
        serial.sendall(b'halt\n')
        report={'status':'passed','probe':a.probe,'activations':16,'normal':4,'finite_interruptible':4,'fault':4,'timeout':4,'kernel_fx_exact_restore':True,'initial_gp_x87_xmm_zero':True,'cpu':a.cpu,'trampoline_sha256':hashlib.sha256((out/'trampoline.bin').read_bytes()).hexdigest(),'fs_gs':'unchanged; personality-owned','compiler':a.compiler,'compiler_sha256':hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),'kernel_sha256':hashlib.sha256(kernel).hexdigest(),'payload_sha256':hashlib.sha256(payload).hexdigest()}
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(f'PASS: strict entry confidentiality and kernel state restoration; {out}')
    finally:
        (out/'serial.log').write_bytes(received)
        if serial:serial.close()
        qemu.terminate()
        try:qemu.wait(timeout=3)
        except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
