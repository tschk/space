#!/usr/bin/env python3
"""Exercise emitted allocation abort and actual CPL3 UD2/page-fault recovery."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--in', dest='compiler', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
a = parser.parse_args()
root = Path(__file__).resolve().parents[1]
a.compiler = a.compiler.resolve(); a.out = a.out.resolve()
if a.out.exists() and any(a.out.iterdir()):
    parser.error('--out must be new or empty')
a.out.mkdir(parents=True, exist_ok=True)

def run(command, name):
    with (a.out / name).open('w') as log:
        subprocess.run([str(x) for x in command], stdout=log, stderr=subprocess.STDOUT,
                       check=True, timeout=180, cwd=root)

run(['nasm','-f','bin',root/'boot/multiboot.asm','-o',a.out/'trampoline.bin'], 'nasm.log')
for source, entry, base, output in [
    ('components/libspace.in','lib-entry','0x3F000000','libspace.sci'),
    ('components/appapi.in','api-entry','0x3E000000','appapi.sci'),
    ('components/app-calc.in','app-calc-entry','0x73000000','calc.sci'),
    ('fixtures/runtime-failure/allocation.in','failure-entry','0x7A000000','allocation.sci'),
]:
    run([a.compiler,'compile','--path',root/source,'--entry',entry,'--target','native',
         '--target-triple','x86_64-unknown-none','--emit','sci','--base',base,'--out',a.out/output],output+'.log')
run([a.compiler,'compile','--path',root/'kernel/kernel-root.in','--entry','kernel-entry',
     '--target','native','--target-triple','x86_64-unknown-none','--emit','boot','--trampoline',
     a.out/'trampoline.bin','--linkage','static-lib','--out',a.out/'kernel.bin'],'kernel.log')
run(['nasm','-f','bin',root/'fixtures/runtime-failure/user-fault.asm','-o',a.out/'ud2.sci'],'ud2.log')
run(['nasm','-DPAGE_FAULT','-f','bin',root/'fixtures/runtime-failure/user-fault.asm','-o',a.out/'pf.sci'],'pf.log')
run(['nasm','-DLOAD_BASE=0x7A000000','-f','bin',root/'fixtures/runtime-failure/user-fault.asm','-o',a.out/'kernel-ud2.sci'],'kernel-ud2.log')
run(['python3',root/'scripts/pack-sci-image.py',a.out/'kernel.bin',a.out/'combined.bin',
     f'7:{a.out}/libspace.sci',f'14:{a.out}/appapi.sci',f'9:{a.out}/calc.sci',
     f'17:{a.out}/allocation.sci',f'5:{a.out}/ud2.sci',f'6:{a.out}/pf.sci'],'pack.log')
report = {'compiler_sha256': hashlib.sha256(a.compiler.read_bytes()).hexdigest(),
          'image_sha256': hashlib.sha256((a.out/'combined.bin').read_bytes()).hexdigest(),
          'scope': 'Trusted CPL0 scoped allocation abort and actual CPL3 guest exception recovery; no clone-domain reclamation claim.',
          'checks': []}
serial_path = a.out/'serial.sock'
data = bytearray()
serial = None
with (a.out/'qemu.log').open('w') as log:
    process = subprocess.Popen(['qemu-system-x86_64','-kernel',str(a.out/'combined.bin'),'-m','256M',
                                '-display','none','-no-reboot','-serial',f'unix:{serial_path},server=on,wait=on'],
                               stdout=log,stderr=subprocess.STDOUT)
    try:
        deadline=time.monotonic()+15
        while not serial_path.exists():
            if process.poll() is not None or time.monotonic()>deadline: raise RuntimeError('no QEMU serial socket')
            time.sleep(.02)
        serial=socket.socket(socket.AF_UNIX);serial.settimeout(.1);serial.connect(str(serial_path))
        def wait(marker, start=0):
            deadline=time.monotonic()+20
            while marker.encode() not in data[start:]:
                if b'nanokernel fault' in data[start:] or b'*** CPU EXCEPTION' in data[start:]:
                    raise AssertionError('kernel fault instead of instance recovery')
                if time.monotonic()>deadline: raise TimeoutError(f'waiting for {marker!r}')
                try:
                    block=serial.recv(65536)
                    if not block: raise RuntimeError('serial closed')
                    data.extend(block)
                except socket.timeout:
                    if process.poll() is not None: raise RuntimeError('QEMU exited')
        def command(text):
            start=len(data);serial.sendall(text.encode()+b'\n');return start
        def calc():
            start=command('runapp calc');wait('calc: integer REPL',start)
            start=command('2+3*4');wait('calc: 2+3*4 = 14',start)
            start=command('q');wait('runapp: app-calc returned 0x0000000000000000',start)
        wait('space interactive shell')
        for cycle in range(2):
            start=command('runapp sum')
            wait('runtime-failure: before allocation',start)
            wait('SCI: app-sum aborted 0x0000000000000086',start)
            wait('runapp: app-sum returned 0x0000000000000086',start)
            assert b'INVALID resumed' not in data[start:]
            calc()
            report['checks'].append(f'emitted allocation failure {cycle+1}: abort134, no return to expression, calculator survives')
        for command_name, vector, status in [('hello','0000000000000006','0000000000000086'),
                                             ('uecho','000000000000000e','000000000000008e')]:
            start=command(command_name)
            wait('guest fault vector 0x'+vector,start)
            wait('SCI: component returned status 0x'+status,start)
            calc()
            report['checks'].append(f'CPL3 {command_name} fault: exact vector/status, calculator survives')
        start=command('halt');wait('halting on request',start)
    finally:
        (a.out/'serial.log').write_bytes(data)
        (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        if serial: serial.close()
        if process.poll() is None: process.terminate()
        try: process.wait(timeout=3)
        except subprocess.TimeoutExpired: process.kill();process.wait()
        if serial_path.exists(): serial_path.unlink()
# A fault raised by a trusted CPL0 component must remain fatal even while a
# scoped runtime continuation exists. It cannot masquerade as a user exception.
run(['python3',root/'scripts/pack-sci-image.py',a.out/'kernel.bin',a.out/'kernel-fault.bin',
     f'7:{a.out}/libspace.sci',f'14:{a.out}/appapi.sci',f'9:{a.out}/calc.sci',
     f'17:{a.out}/kernel-ud2.sci'],'kernel-fault-pack.log')
report['kernel_fault_image_sha256']=hashlib.sha256((a.out/'kernel-fault.bin').read_bytes()).hexdigest()
data=bytearray();serial=None
with (a.out/'kernel-fault-qemu.log').open('w') as log:
    process=subprocess.Popen(['qemu-system-x86_64','-kernel',str(a.out/'kernel-fault.bin'),'-m','256M',
                              '-display','none','-no-reboot','-serial',f'unix:{serial_path},server=on,wait=on'],
                             stdout=log,stderr=subprocess.STDOUT)
    try:
        deadline=time.monotonic()+15
        while not serial_path.exists():
            if process.poll() is not None or time.monotonic()>deadline: raise RuntimeError('no kernel control serial socket')
            time.sleep(.02)
        serial=socket.socket(socket.AF_UNIX);serial.settimeout(.1);serial.connect(str(serial_path))
        wait('space interactive shell')
        start=command('runapp sum')
        # This control expects the fatal marker that ordinary wait() refuses.
        deadline=time.monotonic()+15
        while b'nanokernel fault handler halting' not in data[start:]:
            if time.monotonic()>deadline: raise TimeoutError('kernel fault was not fatal')
            try:
                block=serial.recv(65536)
                if not block: raise RuntimeError('kernel control serial closed')
                data.extend(block)
            except socket.timeout: pass
        assert b'*** CPU EXCEPTION vector 0x0000000000000006' in data[start:]
        assert b'guest fault vector' not in data[start:]
        serial.sendall(b'runapp calc\n')
        deadline=time.monotonic()+1
        while time.monotonic()<deadline:
            try: data.extend(serial.recv(65536))
            except socket.timeout: pass
        assert b'calc: integer REPL' not in data[start:]
        report['checks'].append('CPL0 UD2 remains fatal with active scoped continuation; no fabricated recovery')
        report['passed']=True
    finally:
        (a.out/'kernel-fault-serial.log').write_bytes(data)
        (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        if serial: serial.close()
        if process.poll() is None: process.terminate()
        try: process.wait(timeout=3)
        except subprocess.TimeoutExpired: process.kill();process.wait()
        if serial_path.exists(): serial_path.unlink()
print(f"PASS: {len(report['checks'])} runtime failure/recovery scenarios; {a.out/'report.json'}")
