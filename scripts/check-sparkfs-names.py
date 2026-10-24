#!/usr/bin/env python3
"""Exercise actual SparkFS directory-name boundaries and remount over NVMe."""
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
p.add_argument('--file-source',type=Path,help='explicit alternate fs2-file owner for negative controls')
a=p.parse_args();a.out=a.out.resolve();a.compiler=a.compiler.resolve()
if a.out.exists() and any(a.out.iterdir()):p.error('--out must be new or empty')
a.out.mkdir(parents=True,exist_ok=True)
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
directory=(ROOT/'components/fs2-dir.in').read_text().replace('fn sf-dir-add(', 'fn name-real-dir-add(',1)
directory+='\nvar name-test-fail-add:Int=0\nfn sf-dir-add(parent:Int,name:Int,ino:Int,kind:Int)->Int{if name-test-fail-add!=0{return -1;}return name-real-dir-add(parent,name,ino,kind); }\n'
(a.out/'fs2-dir.in').write_text(directory)
if not a.file_source:
    hub=(ROOT/'components/storage-hub.in').read_text()
    hub=re.sub(r'import "([^"]+)"',lambda m:'import '+json.dumps(str((ROOT/'components'/m.group(1)).resolve())),hub)
else:hub=(a.out/'storage-hub.in').read_text()
hub=hub.replace(json.dumps(str(ROOT/'components/fs2-dir.in')),json.dumps(str(a.out/'fs2-dir.in')))
(a.out/'storage-hub.in').write_text(hub)
base=base.replace(json.dumps(str(ROOT/'components/storage-hub.in')),json.dumps(str(a.out/'storage-hub.in')))
base='import '+json.dumps(str(ROOT/'fixtures/sparkfs-names/check.in'))+'\n'+base
assert base.count('  shell(port)')==1
report={'status':'running','compiler':str(a.compiler),'compiler_sha256':persistence.sha(a.compiler),
        'path_bytes':325,'component_bytes':24,'boots':[],
        'source_sha256':{str(p.relative_to(ROOT)):persistence.sha(p) for p in
                         [ROOT/'components/fs2-block.in',ROOT/'components/fs2-inode.in',ROOT/'components/fs2-file.in',ROOT/'components/fs2-dir.in',ROOT/'components/fs2-path.in',ROOT/'fixtures/sparkfs-names/check.in',Path(__file__).resolve()]}}
if a.file_source:report['alternate_file_source']={'path':str(a.file_source),'sha256':persistence.sha(a.file_source)}
def check_raw_names(disk,label):
    data=disk.read_bytes()
    def u32(at):return struct.unpack_from('<I',data,at)[0]
    def u64(at):return struct.unpack_from('<Q',data,at)[0]
    assert u32(0)==0x53504146
    total,count,table,root=u64(12),u32(20),u64(40),u32(56)
    assert total<=len(data)//4096 and table*4096+count*256<=len(data)
    def inode(number):
        assert 0<=number<count
        return table*4096+number*256
    directories=0;live=0
    for number in range(count):
        record=inode(number)
        if u32(record):live+=1
        if u32(record)==2:directories+=1
    assert live==15 and directories==13,(live,directories,'orphan inode after refused create')
    bitmap=u64(24)*4096;start=u64(48)
    used=sum(bool(data[bitmap+n//8]&(1<<(n%8))) for n in range(start,total))
    assert used==13,(used,'leaked data block reservation')
    def lookup(parent,name):
        directory=inode(parent);assert u32(directory)==2 and u64(directory+16)<=12*4096
        found=None
        for index in range((u64(directory+16)+4095)//4096):
            block=u64(directory+64+index*8);assert start<=block<total
            for at in range(block*4096,(block+1)*4096,32):
                number,length=u32(at),data[at+4]
                if number:
                    assert 0<length<=24
                    entry=data[at+8:at+8+length]
                    assert entry!=b'rollback'
                    if entry==name:assert found is None;found=number
        assert found is not None,name
        return found
    current=root
    for part in [b'ABCDEFGHIJKLMNOPQRSTUVWX']*12+[b'abcdefghijklmnopqrstuvwx']:
        current=lookup(current,part)
    record=inode(current)
    assert u32(record)==1 and u32(record+176)==1 and u64(record+16)==17
    assert data[record+64:record+81]==b'name-file-content'
    return {'live_inodes':live,'directories':directories,'allocated_data_blocks':used,'nested_path_bytes':325,'nested_inode':current,'content_sha256':hashlib.sha256(data[record+64:record+81]).hexdigest()}

try:
    subprocess.run(['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(a.out/'trampoline.bin')],check=True)
    for label,write in [('A',1),('B',0),('C',2)]:
        out=a.out/label;out.mkdir()
        source=base.replace('  shell(port)',f'  names-proof(port, {write})')
        (out/'kernel.in').write_text(source)
        command=[str(a.compiler),'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(a.out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')]
        with (out/'compile.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
        row={'name':label,'disk_before_sha256':persistence.sha(disk),'compile_command':command};report['boots'].append(row)
        qcommand=['qemu-system-x86_64','-kernel',str(out/'kernel.bin'),'-m','512M','-display','none','-no-reboot',
                  '-serial','file:'+str(out/'serial.log'),'-drive',f'file={disk},format=raw,if=none,id=owned,cache=writethrough',
                  '-device','nvme,drive=owned,serial=name-proof']
        row['qemu_command']=qcommand
        with (out/'qemu.log').open('w') as log:
            qemu=subprocess.Popen(qcommand,stdout=log,stderr=subprocess.STDOUT)
            try:
                deadline=time.monotonic()+60
                while time.monotonic()<deadline:
                    serial=(out/'serial.log').read_bytes() if (out/'serial.log').exists() else b''
                    if b'names: real NVMe name proof PASS' in serial or b'names: failed' in serial or b'PANIC' in serial or qemu.poll() is not None:break
                    time.sleep(.05)
                assert b'names: real NVMe name proof PASS' in serial,serial[-2500:].decode(errors='replace')
            finally:
                if qemu.poll() is None:
                    qemu.terminate()
                    try:qemu.wait(timeout=3)
                    except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
        row.update(disk_after_sha256=persistence.sha(disk),kernel_sha256=persistence.sha(out/'kernel.bin'))
        row['files']={}
        metadata,actual=persistence.read_disk_file(disk,'abcdefghijklmnopqrstuvwx')
        assert actual==b'name-file-content', 'raw24byte filename content mismatch'
        row['files']['abcdefghijklmnopqrstuvwx']=metadata
        row['raw_metadata']=check_raw_names(disk,label)
        row['status']='passed'
        print(f'PASS boot{label}: real NVMe 24byte names, refused25byte names, deep path and exact persisted bytes',flush=True)
    report['status']='passed'
    report['source_changed_during_run']=[name for name,digest in report['source_sha256'].items() if persistence.sha(ROOT/name)!=digest]
except Exception as error:
    report.update(status='failed',error=str(error))
    if report['boots']: report['boots'][-1].update(status='failed',error=str(error))
    print('FAIL:',error,flush=True)
finally:
    (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='passed' else 1)
