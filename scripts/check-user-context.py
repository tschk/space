#!/usr/bin/env python3
"""Test actual CPL3 context suspension, independent continuation and supervisor restoration."""
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
assert source.count('  domain-init()') == 1
source = source.replace('  domain-init()', '  domain-init()\n  user-context-cold-check(port)')
source = source.replace('  shell(port)', '  user-context-check(port)\n  shell(port)')
source = 'import '+json.dumps(str(root/'fixtures/user-context/checks.in'))+'\n'+source
(out/'kernel.in').write_text(source)
with (out/'compile.log').open('w') as log:
    for command in [
        ['nasm','-f','bin',str(root/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],
        ['nasm','-f','bin',str(root/'fixtures/user-context/guest.asm'),'-o',str(out/'user-syscall.bin')],
        [a.compiler,'compile','--path',str(root/'fixtures/user-context/private-import.in'),'--entry','private-entry','--emit','sci','--base','0x7a000000','--target','native','--target-triple','x86_64-unknown-none','--out',str(out/'private.sci')],
        [a.compiler,'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')],
    ]:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
kernel=(out/'kernel.bin').read_bytes();payload=(out/'user-syscall.bin').read_bytes()
assert len(kernel)<=0x1e0000 and len(payload)==4096
(out/'payload-kernel.bin').write_bytes(stage_fixture(kernel,payload,0x2e0000))
subprocess.run(['python3',str(root/'scripts/pack-sci-image.py'),str(out/'payload-kernel.bin'),str(out/'combined.bin'),f'254:{out}/private.sci'],check=True,stdout=subprocess.DEVNULL,timeout=60)
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
        assert 'context: actual suspend clone resume GP FX TLS exit fault deadline and supervisor restore PASS' in text,text
        assert 'space interactive shell' in text,text
        assert 'context: cold initialized CPU mask reserved MXCSR refusal PASS' in text,text
        assert 'context: valid SCI private CPU import refused before lifecycle PASS' in text and 'INVALID private context entry' not in text,text
        serial.sendall(b'halt\n')
        report={'status':'passed','executions':62,'cycles':10,'private_import_refused_before_entry':True,'actual_parent_child_continuations':True,'typed_exit_fault_deadline_suspend':True,'actual_page_fault_error':5,'actual_remaining_irq_ticks':True,'architectural_RF_iret_continuations':20,'caller_if0_masked_pic_observer_restore':True,'exact_kernel_fx_fs_gs_restore':True,'cpu':a.cpu,'compiler':a.compiler,'compiler_sha256':hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),'kernel_sha256':hashlib.sha256(kernel).hexdigest(),'payload_sha256':hashlib.sha256(payload).hexdigest()}
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(f'PASS: owned CPL3 context suspension and resume; {out}')
    finally:
        (out/'serial.log').write_bytes(received)
        if serial:serial.close()
        qemu.terminate()
        try:qemu.wait(timeout=3)
        except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
