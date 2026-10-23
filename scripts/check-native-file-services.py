#!/usr/bin/env python3
"""Exercise actual native metadata, permissions, sync and range leases over NVMe."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import struct

from importlib.util import module_from_spec, spec_from_file_location
spec=spec_from_file_location('native_persistence',Path(__file__).with_name('check-native-persistence.py'))
persistence=module_from_spec(spec)
spec.loader.exec_module(persistence)
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)

a=p.parse_args();a.out=a.out.resolve();a.compiler=a.compiler.resolve()
if a.out.exists() and any(a.out.iterdir()):p.error('--out must be new or empty')
a.out.mkdir(parents=True,exist_ok=True)
disk=a.out/'owned-nvme.img'
with disk.open('xb') as f:f.truncate(64*1024*1024)
base=(ROOT/'kernel/kernel-root.in').read_text()
base=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(ROOT/m.group(1))),base)
base='import '+json.dumps(str(ROOT/'fixtures/native-file-services/check.in'))+'\n'+base
assert base.count('  shell(port)')==1
report={'status':'running','compiler':str(a.compiler),'compiler_sha256':persistence.sha(a.compiler),
        'boots':[],
        'source_sha256':{str(p.relative_to(ROOT)):persistence.sha(p) for p in
                         [ROOT/'components/fs2-block.in',ROOT/'components/fs2-inode.in',ROOT/'components/fs2-file.in',ROOT/'components/fs2-dir.in',ROOT/'components/fs2-path.in',ROOT/'components/filesystem.in',ROOT/'components/file-range-leases.in',ROOT/'components/fs2-layout.in',ROOT/'fixtures/native-file-services/check.in',Path(__file__).resolve()]}}
try:
    subprocess.run(['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(a.out/'trampoline.bin')],check=True)
    for label,write in [('RAM',-1),('A',1),('B',0),('C',2)]:
        out=a.out/label;out.mkdir()
        source=base.replace('  shell(port)',f'  native-file-service-proof(port, {write})')
        (out/'kernel.in').write_text(source)
        command=[str(a.compiler),'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(a.out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')]
        with (out/'compile.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
        row={'name':label,'disk_before_sha256':persistence.sha(disk),'compile_command':command};report['boots'].append(row)
        qcommand=['qemu-system-x86_64','-kernel',str(out/'kernel.bin'),'-m','512M','-display','none','-no-reboot','-serial','file:'+str(out/'serial.log')]
        if label!='RAM':qcommand+=['-drive',f'file={disk},format=raw,if=none,id=owned,cache=writethrough','-device','nvme,drive=owned,serial=file-services-proof']
        row['qemu_command']=qcommand
        with (out/'qemu.log').open('w') as log:
            qemu=subprocess.Popen(qcommand,stdout=log,stderr=subprocess.STDOUT)
            try:
                deadline=time.monotonic()+60
                while time.monotonic()<deadline:
                    serial=(out/'serial.log').read_bytes() if (out/'serial.log').exists() else b''
                    if b'file-services: actual metadata mode sync leases PASS' in serial or b'file-services: failed' in serial or b'PANIC' in serial or qemu.poll() is not None:break
                    time.sleep(.05)
                assert b'file-services: actual metadata mode sync leases PASS' in serial,serial[-2500:].decode(errors='replace')
            finally:
                if qemu.poll() is None:
                    qemu.terminate()
                    try:qemu.wait(timeout=3)
                    except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
        row.update(disk_after_sha256=persistence.sha(disk),kernel_sha256=persistence.sha(out/'kernel.bin'))
        if label!='RAM':
            metadata,actual=persistence.read_disk_file(disk,'lease.bin')
            assert actual==b'native lease content', 'raw file content changed'
            raw=disk.read_bytes()
            table=int.from_bytes(raw[40:48],'little')
            at=table*4096+metadata['inode']*256
            mode=int.from_bytes(raw[at+4:at+8],'little')
            assert mode==384,('persisted permissions',mode)
            row['file']=metadata;row['persisted_mode']=mode
        row['status']='passed'
        print(f'PASS {label}: actual metadata, permissions, honest sync, bounded range leases and stable resources',flush=True)
    report['status']='passed'
    report['source_changed_during_run']=[name for name,digest in report['source_sha256'].items() if persistence.sha(ROOT/name)!=digest]
except Exception as error:
    report.update(status='failed',error=str(error))
    if report['boots']: report['boots'][-1].update(status='failed',error=str(error))
    print('FAIL:',error,flush=True)
finally:
    (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='passed' else 1)
