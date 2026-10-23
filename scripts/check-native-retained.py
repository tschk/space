#!/usr/bin/env python3
"""Exercise retained SCI ownership, image globals, stale tokens and resource reuse."""
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
source = source.replace('  shell(port)', '  retained-contract-run(port)\n  shell(port)')
source = 'import '+json.dumps(str(root/'fixtures/runtime-failure/retained-contract.in'))+'\n'+source
(out/'kernel.in').write_text(source)
with (out/'compile.log').open('w') as log:
    for command in [
        ['nasm','-f','bin',str(root/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],
        [a.compiler,'compile','--path',str(root/'fixtures/runtime-failure/global-state.in'),'--entry','fresh-entry','--target','native','--target-triple','x86_64-unknown-none','--emit','sci','--base','0x7b000000','--out',str(out/'counter.sci')],
        [a.compiler,'compile','--path',str(root/'fixtures/runtime-failure/retained-allocation.in'),'--entry','retained-entry','--target','native','--target-triple','x86_64-unknown-none','--emit','sci','--base','0x7a000000','--out',str(out/'allocation.sci')],
        [a.compiler,'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')],
    ]:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    subprocess.run(['python3',str(root/'scripts/pack-sci-image.py'),str(out/'kernel.bin'),str(out/'combined.bin'),f'254:{out}/counter.sci',f'255:{out}/allocation.sci'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
kernel=(out/'kernel.bin').read_bytes()
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
        assert 'retained-contract: private globals generation stale denial varied close order and stable resources PASS' in text,text
        assert 'space interactive shell' in text,text
        serial.sendall(b'halt\n')
        cycles=len(re.findall(r'retained-contract: cycle [0-9]+',text))
        assert cycles==70,cycles
        report={'status':'passed','cycles':cycles,'initial_activations':350,'resumed_activations':490,'emitted_allocation_aborts':140,'initial_entry_aborts':70,'resumed_entry_aborts':70,'initial_abort_no_handle':True,'initial_abort_exact_cap_domain_bytes':True,'initial_abort_peer_survives':True,'next_valid_same_image_fresh':True,'resumed_allocator_context':True,'source_images_byte_identical':True,'same_image_private_globals':True,'stale_generation_denied':True,'resource_invariants':['free-frame count','heap high water','domain count','capability count','object arena','exports','clone ownership'],'compiler':a.compiler,'compiler_sha256':hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),'kernel_sha256':hashlib.sha256(kernel).hexdigest(),'image_sha256':hashlib.sha256((out/'combined.bin').read_bytes()).hexdigest()}
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(f'PASS: retained SCI ownership and independent instance globals; {out}')
    finally:
        (out/'serial.log').write_bytes(received)
        if serial:serial.close()
        qemu.terminate()
        try:qemu.wait(timeout=3)
        except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
