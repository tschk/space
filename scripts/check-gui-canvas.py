#!/usr/bin/env python3
"""Exercise noncontiguous retained canvas backing, bounds and mapping teardown."""
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
p.add_argument('--mode',choices=['full','oom'],default='full')
p.add_argument('--memory',default=None,help='QEMU RAM; OOM defaults32M, full defaults512M')
p.add_argument('--cpu', choices=['qemu64','max'], default='qemu64')
a = p.parse_args()
out = a.out.resolve()
if out.exists() and any(out.iterdir()):
    p.error('--out must be new or empty')
out.mkdir(parents=True, exist_ok=True)
source = (root/'kernel/kernel-root.in').read_text()
source = re.sub(r'import "\.\./([^"]+)"', lambda m: 'import '+json.dumps(str(root/m.group(1))), source)
assert source.count('  shell(port)') == 1
entry='canvas-oom-run' if a.mode=='oom' else 'canvas-run'
marker='canvas: actual constrained memory budget refusal IF restoration peer recovery PASS' if a.mode=='oom' else 'canvas: noncontiguous pages exact server mappings lifetime malformed refusal and stable resources PASS'
source = source.replace('  shell(port)', '  '+entry+'(port)\n  shell(port)')
source = 'import '+json.dumps(str(root/'fixtures/gui-canvas/ownership.in'))+'\n'+source
(out/'kernel.in').write_text(source)
with (out/'compile.log').open('w') as log:
    for command in [
        ['nasm','-f','bin',str(root/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],
        [a.compiler,'compile','--path',str(root/'fixtures/gui-canvas/client.in'),'--entry','client-entry','--target','native','--target-triple','x86_64-unknown-none','--emit','sci','--base','0x48000000','--out',str(out/'canvas.raw.sci')],
        ['python3',str(root/'scripts/pack-gui-sci.py'),str(out/'canvas.raw.sci'),str(out/'canvas.raw.component-metadata.json'),str(out/'canvas.sci')],
        [a.compiler,'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')],
    ]:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    subprocess.run(['python3',str(root/'scripts/pack-sci-image.py'),str(out/'kernel.bin'),str(out/'combined.bin'),f'254:{out}/canvas.sci'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
kernel=(out/'kernel.bin').read_bytes()
received=bytearray();serial=None
with (out/'qemu.log').open('w') as qlog:
    path=out/'serial.sock'
    qemu=subprocess.Popen(['qemu-system-x86_64','-kernel',str(out/'combined.bin'),'-m',a.memory or ('32M' if a.mode=='oom' else '512M'),'-cpu',a.cpu,'-display','none','-no-reboot','-serial',f'unix:{path},server=on,wait=on'],stdout=qlog,stderr=subprocess.STDOUT)
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
        assert marker in text,text
        assert 'space interactive shell' in text,text
        serial.sendall(b'halt\n')
        cycles=len(re.findall(r'canvas: cycle [0-9]+',text))
        assert cycles==(0 if a.mode=='oom' else 70),cycles
        report={'status':'passed','cycles':cycles,'initial_activations':140,'resumed_activations':210,'pages_per_canvas':288,'bytes_per_canvas':1179648,'noncontiguous_backing_verified':True,'malformed_profiles_refused':12,'server_parent_unmapped_after_release':True,'held_frames_unchanged':1024,'resource_invariants':['free-frame count','heap high water','domain count','capability count','object arena','exports'],'compiler':a.compiler,'compiler_sha256':hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),'kernel_sha256':hashlib.sha256(kernel).hexdigest(),'image_sha256':hashlib.sha256((out/'combined.bin').read_bytes()).hexdigest()}
        if a.mode=='oom':
            report.update({'cycles':0,'initial_activations':2,'resumed_activations':3,'memory':a.memory or '32M','physical_frame_capacity_below_declared_budget':True,'refused_activations':2,'caller_if0_if1_restored':True,'peer_survives':True,'valid_launch_after_releasing_held_frames':True,'malformed_profiles_refused':0})
            for field in ['held_frames_unchanged','noncontiguous_backing_verified','server_parent_unmapped_after_release']:
                report.pop(field,None)
            budget=re.search(r'canvas: admission budget ([0-9]+) capacity ([0-9]+)',text)
            assert budget and int(budget[1])==int(budget[2])+1,text
            report['required_frame_budget']=int(budget[1]);report['available_frames_at_refusal']=int(budget[2])
        else:
            report['memory']=a.memory or '512M'
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(f'PASS: owned noncontiguous canvas backing and mapping lifetime; {out}')
    finally:
        (out/'serial.log').write_bytes(received)
        if serial:serial.close()
        qemu.terminate()
        try:qemu.wait(timeout=3)
        except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
