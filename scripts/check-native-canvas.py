#!/usr/bin/env python3
"""Actual private native canvas upload: CPL3 producers, scene pixels and lifetimes."""
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
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();out=a.out.resolve();compiler=a.compiler.resolve()
assert not out.exists() or not any(out.iterdir()),'--out must be new or empty'
out.mkdir(parents=True,exist_ok=True)
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
paths=[x for d in ['components','kernel','protocol','services','fixtures/native-canvas'] for x in (ROOT/d).rglob('*') if x.suffix in ['.in','.asm']]
paths += [ROOT/'boot/multiboot.asm',Path(__file__).resolve()]
contents={str(x.relative_to(ROOT)):x.read_bytes() for x in paths}
assert all(x.read_bytes()==contents[str(x.relative_to(ROOT))] for x in paths)
snapshot=out/'source'
for name,data in contents.items():
    target=snapshot/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
inventory={name:hashlib.sha256(data).hexdigest() for name,data in contents.items()}
(out/'source-hashes.json').write_text(json.dumps(inventory,indent=2)+'\n')
# Instrument only the frozen private provider; retain canonical and compiled hashes.
provider=snapshot/'components/native-canvas.in'
canonical=provider.read_bytes()
old=b'result=user-space-copy-in('
assert canonical.count(old)==1
instrumented=canonical.replace(old,b'result=nct-transfer(')
assert instrumented.replace(b'result=nct-transfer(',old)==canonical
provider.write_bytes(instrumented)
report=dict(status='running',goal_status='OPEN',classification='Private native provider with synthetic CPL3 producers; not original foreign GUI execution or SCI service isolation',compiler_sha256=sha(compiler),source_sha256=inventory,screenshots=[])
report['test_only_override']={'path':'components/native-canvas.in','canonical_sha256':hashlib.sha256(canonical).hexdigest(),'compiled_sha256':sha(provider),'replacement':'one real copy-in call through fixture revocation interposer'}
process=None;serial=None;monitor=None;received=bytearray()
def connect(path):
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        channel=socket.socket(socket.AF_UNIX);channel.settimeout(.2)
        try:channel.connect(str(path));return channel
        except (FileNotFoundError,ConnectionRefusedError):channel.close();time.sleep(.02)
    raise AssertionError('QEMU socket unavailable: '+str(path))
def wait(marker):
    deadline=time.monotonic()+120
    while marker not in received:
        assert b'PANIC' not in received,received[-2000:]
        assert process.poll() is None,'QEMU exited early'
        assert time.monotonic()<deadline,(marker,received[-2000:])
        try:
            block=serial.recv(65536);assert block;received.extend(block)
        except socket.timeout:pass
    (out/'serial.log').write_bytes(received)
def expected_frame(stage):
    rgb=bytearray(bytes((0x11,0x16,0x1f))*(1024*768))
    colors=[(0x33,0x66,0x99),(0x66,0x33,0x22)]
    if stage==2:colors[0]=(0,0,0)
    if stage>=3:colors[0]=None
    if stage==4:colors[1]=None
    for slot,color in enumerate(colors):
        if color is None:continue
        x=64+slot*288
        for y in range(64,192):
            offset=(y*1024+x)*3;rgb[offset:offset+256*3]=bytes(color)*256
    for x in range(892,909):rgb[(700*1024+x)*3:(700*1024+x)*3+3]=b'\xff'*3
    for y in range(692,709):rgb[(y*1024+900)*3:(y*1024+900)*3+3]=b'\xff'*3
    return rgb
try:
    private=out/'private.in'
    private.write_text('package space.fixture\ninterrupt fn native-canvas-new(owner:Int,width:Int,height:Int,x:Int,y:Int)->Int{}\nfn private-entry(info:Int)->Int{return native-canvas-new(info,256,128,0,0); }\n')
    with (out/'private.log').open('w') as log:
        subprocess.run([str(compiler),'compile','--path',str(private),'--entry','private-entry','--emit','sci','--base','0x7a000000','--target','native','--target-triple','x86_64-unknown-none','--out',str(out/'private.sci')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    private_size=(out/'private.sci').stat().st_size
    assert 0<private_size<=0x10000
    source=(snapshot/'kernel/kernel-root.in').read_text()
    source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(snapshot/m[1])),source)
    source='const NCT-PRIVATE-SIZE = '+str(private_size)+'\nimport '+json.dumps(str(snapshot/'fixtures/native-canvas/checks.in'))+'\n'+source
    assert source.count('  shell(port)')==1
    source=source.replace('  shell(port)','  native-canvas-check(port)\n  shell(port)')
    (out/'kernel.in').write_text(source)
    commands=[['nasm','-f','bin',str(snapshot/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],['nasm','-f','bin',str(snapshot/'fixtures/native-canvas/producer.asm'),'-o',str(out/'producer.bin')],[str(compiler),'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')]]
    with (out/'compile.log').open('w') as log:
        for command in commands:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    metadata=json.loads((out/'kernel.component-metadata.json').read_text());assert metadata['boot_layout']['load_end']<=0x2f0000
    assert (out/'producer.bin').stat().st_size==4096
    command=['qemu-system-x86_64','-kernel',str(out/'kernel.bin'),'-m','512M','-cpu','max','-vga','std','-display','none','-no-reboot','-serial',f'unix:{out}/serial.sock,server=on,wait=on','-monitor',f'unix:{out}/monitor.sock,server=on,wait=off','-device',f'loader,file={out}/producer.bin,addr=0x13000000,force-raw=on','-device',f'loader,file={out}/private.sci,addr=0x2f0000,force-raw=on']
    report.update(qemu_command=command,kernel_sha256=sha(out/'kernel.bin'),producer_sha256=sha(out/'producer.bin'))
    with (out/'qemu.log').open('w') as log:
        process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        serial=connect(out/'serial.sock');monitor=connect(out/'monitor.sock')
        for stage in range(5):
            wait(f'native-canvas: pixels {stage}\n'.encode())
            path=out/f'pixels-{stage}.ppm';monitor.sendall(f'screendump {path}\n'.encode())
            deadline=time.monotonic()+5
            while (not path.exists() or path.stat().st_size<1024*768*3+16) and time.monotonic()<deadline:time.sleep(.02)
            frame=path.read_bytes().split(b'\n',3);assert frame[:3]==[b'P6',b'1024 768',b'255'];expected=expected_frame(stage)
            if frame[3]!=expected:
                first=next((i for i,(got,want) in enumerate(zip(frame[3],expected)) if got!=want),-1)
                raise AssertionError(('frame mismatch',stage,first,(first//3)%1024,(first//3)//1024,len(frame[3])))
            report['screenshots'].append(dict(stage=stage,sha256=sha(path),rgb_bytes_checked=len(expected)))
            serial.sendall(b'q')
        wait(b'native-canvas: actual owned upload two producers 132 entries 22 PF 21 stable cycles PASS\n')
        wait(b'space> ')
    assert all((ROOT/name).read_bytes()==data for name,data in contents.items()),'source changed during run'
    assert sha(compiler)==report['compiler_sha256']
    assert b'DENIED unresolved import native-canvas-new' in received
    report['private_sci_sha256']=sha(out/'private.sci')
    text=received.decode(errors='replace');assert text.count('native-canvas: lifecycle ')==22
    assert text.count('space: guest fault vector 0x000000000000000e')==22
    report.update(status='passed',actual_cpl3_entries=132,actual_write_pf=22,measured_resource_cycles=21)
    print('PASS native owned canvas:132 real CPL3 entries,22 PF, two producers, exact five full frames,21 lifetime cycles')
except Exception as error:
    report.update(status='failed',error=str(error));raise
finally:
    (out/'serial.log').write_bytes(received)
    if serial:serial.close()
    if monitor:monitor.close()
    if process:
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait()
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
