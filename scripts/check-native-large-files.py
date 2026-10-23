#!/usr/bin/env python3
"""Exercise actual SparkFS multi-block/indirect writes and remount over NVMe."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

from importlib.util import module_from_spec, spec_from_file_location
spec=spec_from_file_location('native_persistence',Path(__file__).with_name('check-native-persistence.py'))
persistence=module_from_spec(spec)
spec.loader.exec_module(persistence)
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--file-source',type=Path,help='explicit alternate fs2-file owner for negative controls')
a=p.parse_args();a.out=a.out.resolve();a.compiler=a.compiler.resolve()
if a.out.exists() and any(a.out.iterdir()):p.error('--out must be new or empty')
a.out.mkdir(parents=True,exist_ok=True)
size=14*4096+47
original=bytes((i*37+11)%251 for i in range(size))
patched=bytearray(original);patched[4090:4127]=original[1000:1037]
holes=bytearray(original[:48])+bytearray(size-48-23)+bytearray(original[1000:1023])
for index in range(2):holes.extend(bytes(4096)+original[1000:1023])
payload=a.out/'payload.bin';payload.write_bytes(original+patched+holes)
disk=a.out/'owned-nvme.img'
with disk.open('xb') as f:f.truncate(64*1024*1024)
base=(ROOT/'kernel/kernel-root.in').read_text()
base=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(ROOT/m.group(1))),base)
if a.file_source:
    a.file_source=a.file_source.resolve()
    hub=(ROOT/'components/storage-hub.in').read_text()
    hub=re.sub(r'import "([^"]+)"',lambda m:'import '+json.dumps(str((ROOT/'components'/m.group(1)).resolve())),hub)
    hub=hub.replace(json.dumps(str(ROOT/'components/fs2-file.in')),json.dumps(str(a.file_source)))
    (a.out/'storage-hub.in').write_text(hub)
    base=base.replace(json.dumps(str(ROOT/'components/storage-hub.in')),json.dumps(str(a.out/'storage-hub.in')))
base='import '+json.dumps(str(ROOT/'fixtures/native-persistence/large-file.in'))+'\n'+base
assert base.count('  shell(port)')==1
report={'status':'running','compiler':str(a.compiler),'compiler_sha256':persistence.sha(a.compiler),
        'payload_sha256':persistence.sha(payload),'size':size,'boots':[],
        'source_sha256':{str(p.relative_to(ROOT)):persistence.sha(p) for p in
                         [ROOT/'components/fs2-block.in',ROOT/'components/fs2-inode.in',ROOT/'components/fs2-file.in',ROOT/'components/fs2-dir.in',ROOT/'components/fs2-path.in',ROOT/'fixtures/native-persistence/large-file.in']}}
if a.file_source:report['alternate_file_source']={'path':str(a.file_source),'sha256':persistence.sha(a.file_source)}
try:
    subprocess.run(['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(a.out/'trampoline.bin')],check=True)
    for label,write in [('A',1),('B',0),('C',2)]:
        out=a.out/label;out.mkdir()
        source=base.replace('  shell(port)',f'  large-file-proof(port, {write}, 0x18000000, {size})')
        (out/'kernel.in').write_text(source)
        command=[str(a.compiler),'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(a.out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')]
        with (out/'compile.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
        row={'name':label,'disk_before_sha256':persistence.sha(disk),'compile_command':command};report['boots'].append(row)
        qcommand=['qemu-system-x86_64','-kernel',str(out/'kernel.bin'),'-m','512M','-display','none','-no-reboot',
                  '-serial','file:'+str(out/'serial.log'),'-drive',f'file={disk},format=raw,if=none,id=owned,cache=writethrough',
                  '-device','nvme,drive=owned,serial=large-file-proof','-device',f'loader,file={payload},addr=0x18000000,force-raw=on']
        row['qemu_command']=qcommand
        with (out/'qemu.log').open('w') as log:
            qemu=subprocess.Popen(qcommand,stdout=log,stderr=subprocess.STDOUT)
            try:
                deadline=time.monotonic()+60
                while time.monotonic()<deadline:
                    serial=(out/'serial.log').read_bytes() if (out/'serial.log').exists() else b''
                    if b'large-file: proof passed' in serial or b'large-file: failed' in serial or b'PANIC' in serial or qemu.poll() is not None:break
                    time.sleep(.05)
                assert b'large-file: proof passed' in serial,serial[-2500:].decode(errors='replace')
            finally:
                if qemu.poll() is None:
                    qemu.terminate()
                    try:qemu.wait(timeout=3)
                    except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
        row.update(disk_after_sha256=persistence.sha(disk),kernel_sha256=persistence.sha(out/'kernel.bin'))
        row['files']={}
        files=[('large.bin',patched),('grow.bin',original),('replace.bin',original),('holes.bin',holes),('trunc.bin',original[:32])]
        if label!='A':files.append(('after.bin',original))
        for name,expected in files:
            metadata,actual=persistence.read_disk_file(disk,name)
            assert actual==expected,(name,'raw disk bytes mismatch')
            row['files'][name]=metadata
        row['status']='passed'
        print(f'PASS boot{label}: real NVMe superblock, {size}byte indirect files and exact persisted bytes',flush=True)
    report['status']='passed'
except Exception as error:
    report.update(status='failed',error=str(error))
    if report['boots']: report['boots'][-1].update(status='failed',error=str(error))
    print('FAIL:',error,flush=True)
finally:
    (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='passed' else 1)
