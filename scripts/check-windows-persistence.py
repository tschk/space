#!/usr/bin/env python3
"""Prove protected PE32+ file writes/truncations across independent NVMe boots.

Creates one new owned disposable raw disk beneath a new evidence directory.
Only boot A formats it, through Space. Guest CreateFileA/WriteFile/CloseHandle
produce the content; Python supplies only test-mode configuration and a read-only
raw-disk oracle. RAM fallback and hosted file forwarding are refused.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--qemu',default='qemu-system-x86_64')
p.add_argument('--timeout',type=int,default=90)
a=p.parse_args();a.out=a.out.resolve();a.compiler=a.compiler.resolve()
if a.out.exists() and any(a.out.iterdir()):p.error('--out must be new or empty')
a.out.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('native_persistence_oracle',ROOT/'scripts/check-native-persistence.py')
oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
source=(ROOT/'kernel/kernel-root.in').read_text()
source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(ROOT/m.group(1))),source)
assert source.count('  shell(port)')==1
source=source.replace('  shell(port)','  windows-persist-check(port)\n  shell(port)')
source+='''
fn windows-persist-used()->Int{
 let n=0;let i=0;let total=load64(sf-super+SF-SB-TOTAL-BLOCKS);
 while i<total{if sf-block-used(i)!=0{n=n+1;}i=i+1;}return n;
}
fn windows-persist-check(port:Int)->void{
 let image=0x10000000;let mode=load64(image+9472);
 // Reserve the staging payload from every subsequent heap/frame allocation.
 if heap-next>=image{panic("Windows persistence payload overlaps heap");}heap-end=image;
 if nvme-ready!=1 || sf-mem-disk!=0 || volume-ready!=0{panic("Windows persistence requires real direct NVMe");}
 if mode==100{if fs-format()!=0{panic("Windows persistence owned disk format failed");}}
 if sf-disk-ready!=1 || (mode!=100 && mode!=101 && mode!=102 && mode!=103 && mode!=104 && mode!=105){panic("Windows persistence stage/mount invalid");}
 let authority=cap-mint(root-realm,cap-serial());let storage=cap-mint(root-realm,cap-storage());
 let used=windows-persist-used();let descriptors=vfs-fd-alloc();
 let result=windows-protected-run-files(image,12800,authority,storage);
 if result!=42{serial-write-cstr(port,"windows-persist: failed mode ");serial-write-dec-wide(port,mode);serial-write-cstr(port," result ");serial-write-dec-wide(port,result);serial-nl(port);panic("Windows persisted file API execution failed");}
 if mode>=102 && windows-persist-used()!=used{panic("Windows truncate block allocation leaked");}
 if windows-protected-count!=0 || windows-protected-busy!=0 || windows-protected-storage!=-1 || domain-current!=0 || user-budget-active!=0 || domain-user-syscall-hook!=0 || vfs-fd-alloc()!=descriptors{panic("Windows persistent activation leaked");}
 cap-revoke(storage);cap-revoke(authority);
 serial-write-cstr(port,"windows-persist: protected PE32+ NVMe mode ");serial-write-dec-wide(port,mode);serial-write-cstr(port," exact8192 close reopen EOF and owned cleanup PASS");serial-nl(port);
}
'''
(a.out/'kernel.in').write_text(source)
with (a.out/'compile.log').open('w') as log:
    for command in [
        ['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(a.out/'trampoline.bin')],
        ['nasm','-f','bin',str(ROOT/'fixtures/windows-protected/write-api.asm'),'-o',str(a.out/'fixture.exe')],
        [str(a.compiler),'compile','--path',str(a.out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(a.out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(a.out/'kernel.bin')],
    ]:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
assert 0x100000+(a.out/'kernel.bin').stat().st_size<0x10000000
payload=(a.out/'fixture.exe').read_bytes();assert len(payload)==12800
expected=bytes(i%251 for i in range(4096))*2
disk=a.out/'owned-nvme.img'
with disk.open('xb') as file:file.truncate(64*1024*1024)
report={'status':'running','evidence':'actual protected PE32+ file APIs over direct NVMe in six independent QEMU processes','compiler':str(a.compiler),'compiler_sha256':oracle.sha(a.compiler),'kernel_sha256':oracle.sha(a.out/'kernel.bin'),'fixture_sha256':hashlib.sha256(payload).hexdigest(),'owned_disk':str(disk),'disk_initial_sha256':oracle.sha(disk),'boots':[]}
boot=None
try:
    for name,mode in [('A',100),('B',101),('C',102),('D',103),('E',104),('F',105)]:
        configured=bytearray(payload);struct.pack_into('<Q',configured,9472,mode)
        path=a.out/f'fixture-{name}.exe';path.write_bytes(configured)
        row={'name':name,'mode':mode,'status':'running','formatted':mode==100,'disk_before_sha256':oracle.sha(disk),'configured_fixture_sha256':oracle.sha(path)};report['boots'].append(row)
        # Boot helper owns process/serial lifecycle; loader stages bytes only.
        wrapper=a.out/f'qemu-{name}.sh'
        import shlex
        wrapper.write_text('#!/bin/sh\nexec '+shlex.quote(a.qemu)+' -device '+shlex.quote(f'loader,file={path},addr=0x10000000,force-raw=on')+' "$@"\n');wrapper.chmod(0o700)
        boot=oracle.Boot(a.out/'kernel.bin',disk,a.out/name,str(wrapper),a.timeout,row)
        text=bytes(boot.log).decode(errors='replace')
        marker=f'windows-persist: protected PE32+ NVMe mode {mode} exact8192 close reopen EOF and owned cleanup PASS'
        assert marker in text,text
        boot.halt();boot=None
        metadata,actual=oracle.read_disk_file(disk,'windows-persist.txt')
        expected_after=expected if mode<104 else b'WinPatch'+expected[8:]
        assert actual==expected_after,'NVMe raw disk bytes differ from the protected Windows client write'
        row.update(status='passed',disk_after_sha256=oracle.sha(disk),persisted_file=metadata,expected_content_sha256=hashlib.sha256(expected_after).hexdigest())
    report['status']='passed'
    print(f'PASS: protected Windows create/write/read/truncate/reopen across six independent NVMe boots; {a.out}')
except Exception as error:
    report.update(status='failed',error=f'{type(error).__name__}: {error}')
    raise
finally:
    if boot:boot.close()
    report['disk_final_sha256']=oracle.sha(disk)
    (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
