#!/usr/bin/env python3
"""Run genuine Unicode CreateFileW/A paths across three independent NVMe boots.

Only boot A formats one newly owned64MiB disk. Guest APIs create/write/close and
reopen/read; Python stages a declared fixture and independently reads disk bytes.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import struct
import subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--qemu',default='qemu-system-x86_64')
p.add_argument('--timeout',type=int,default=120)
a=p.parse_args();out=a.out.resolve();a.compiler=a.compiler.resolve()
assert not out.exists() or not any(out.iterdir()),'--out must be new or empty'
out.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('native_disk_boot',ROOT/'scripts/check-native-persistence.py');bootutil=importlib.util.module_from_spec(spec);spec.loader.exec_module(bootutil)
source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(ROOT/m.group(1))),(ROOT/'kernel/kernel-root.in').read_text())
assert source.count('  shell(port)')==1;source=source.replace('  shell(port)','  windows-path-persist-check(port)\n  shell(port)')
source+=r'''
fn windows-path-persist-free()->Int{let n=0;let f=free-list;while f!=0 && n<4096{n=n+1;f=load64(f);}return n;}
fn windows-path-persist-config(config:Int,serial:Int,storage:Int,memory:Int,line:Int,env:Int)->void{
 store64(config,1);store64(config+8,96);store64(config+16,serial);store64(config+24,storage);store64(config+32,memory);store64(config+40,-1);store64(config+48,line);store64(config+56,strlen(line)+1);store64(config+64,env);store64(config+72,2);store64(config+80,0);store64(config+88,0);
}
fn windows-path-persist-check(port:Int)->void{
 let image=0x10000000;if heap-next>=image{panic("Path persistence fixture collision");}heap-end=image;let stage=load64(image+7680+200);
 if nvme-ready!=1 || sf-mem-disk!=0 || volume-ready!=0{panic("Unicode path persistence requires actual direct NVMe");}
 if stage==1{if fs-format()!=0 || fs-mkdir("/wp")<0{panic("Owned Unicode path disk format/setup failed");}}
 if sf-disk-ready!=1 || stage<1 || stage>3{panic("Unicode path persistence stage/mount invalid");}
 let config=alloc(96);let env=alloc(2);store8(env,0);store8(env+1,0);let buffer=alloc(64);let serial=cap-mint(root-realm,cap-serial());let storage=cap-mint(root-realm,cap-storage());let memory=cap-mint(root-realm,cap-memory());windows-path-persist-config(config,serial,storage,memory,"sqlite3.exe",env);
 let cycle=0;let heap=0;let free=0;let domains=0;let descriptors=vfs-fd-alloc();let fs=rdmsr(0xc0000100);let gs=rdmsr(0xc0000101);let cap=current-cap;
 while cycle<21{
  if cycle>0{store64(image+7680,11);}
  let result=windows-command-filesystem-run(image,11776,config);if result!=42{serial-write-dec-wide(port,stage);serial-put(port,32);serial-write-dec-wide(port,result);panic("Actual Unicode path NVMe API execution failed");}
  if windows-protected-busy!=0 || windows-protected-count!=0 || windows-parameters-path-data!=0 || windows-parameters-path-scratch!=0 || windows-parameters-composed-active!=0 || windows-parameters-composed-data!=0 || windows-parameters-heap-records!=0 || windows-parameters-local-data!=0 || windows-parameters-critical-data!=0 || windows-parameters-env-data!=0 || windows-parameters-active!=0 || domain-current!=0 || user-context-active!=0 || user-budget-active!=0 || domain-user-syscall-hook!=0 || vfs-fd-alloc()!=descriptors || rdmsr(0xc0000100)!=fs || rdmsr(0xc0000101)!=gs || current-cap!=cap{panic("Unicode path NVMe activation leaked");}
  if fs-read-file("/wp/é😀.txt",buffer,64)!=16 || load64(buffer)!=0x3736353433323130 || load64(buffer+8)!=0x4645444342413938{panic("Unicode path native provider bytes mismatch");}
  if cycle==0{heap=heap-next;free=windows-path-persist-free();domains=domain-count;}else{if heap-next!=heap || windows-path-persist-free()!=free || domain-count!=domains{panic("Unicode path NVMe repeated cleanup leaked");}}cycle=cycle+1;
 }
 cap-revoke(serial);cap-revoke(storage);cap-revoke(memory);serial-write-cstr(port,"windows-path-persist:21 actual Unicode cwd CreateFileW A write read EOF close NVMe activations PASS");serial-nl(port);
}
'''
(out/'kernel.in').write_text(source)
names=['components/fs-path-normalize.in','components/windows-process-paths.in','components/windows-process-composed.in','components/windows-protected.in','fixtures/windows-protected/paths.asm']
source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
commands=[['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],['nasm','-f','bin',str(ROOT/'fixtures/windows-protected/paths.asm'),'-o',str(out/'process.exe')],[str(a.compiler),'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')]]
with (out/'compile.log').open('w') as log:
 for command in commands:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
payload=(out/'process.exe').read_bytes();assert len(payload)==11776 and 0x100000+(out/'kernel.bin').stat().st_size<0x10000000

def disk_file(path,parts):
 data=path.read_bytes();u32=lambda p:struct.unpack_from('<I',data,p)[0];u64=lambda p:struct.unpack_from('<Q',data,p)[0]
 assert (u32(0),u32(4),u32(8))==(0x53504146,1,4096)
 total,count,table,number=u64(12),u32(20),u64(40),u32(56)
 assert 2<=total<=len(data)//4096 and 0<count<=4096 and table*4096+count*256<=len(data)
 def inode(n):assert 0<=n<count;return table*4096+n*256
 for part in parts:
  directory=inode(number);assert u32(directory)==2
  size=u64(directory+16);assert size<=12*4096;found=None
  for i in range((size+4095)//4096):
   block=u64(directory+64+i*8);assert 0<block<total
   for at in range(block*4096,(block+1)*4096,32):
    n=u32(at);length=data[at+4]
    if n and data[at+8:at+8+length]==part.encode():assert 0<length<=24;found=n;break
  assert found is not None,'missing persisted UTF8 component '+part
  number=found
 record=inode(number);assert u32(record)==1;size=u64(record+16);assert size==16 and u32(record+176)==1
 content=data[record+64:record+64+size]
 return dict(inode=number,bytes=size,utf8_components=[x.encode().hex() for x in parts],sha256=hashlib.sha256(content).hexdigest()),content

disk=out/'owned-nvme.img'
with disk.open('xb') as file:file.truncate(64*1024*1024)
report=dict(status='running',classification='Actual protected Win64 Unicode path APIs over direct NVMe; newly owned disk, only bootA formats',compiler_sha256=hashlib.sha256(a.compiler.read_bytes()).hexdigest(),kernel_sha256=hashlib.sha256((out/'kernel.bin').read_bytes()).hexdigest(),source_sha256=source_hashes,executions=63,boots=[],commands=commands)
boot=None
try:
 for label,stage,mode in [('A',1,10),('B',2,11),('C',3,11)]:
  configured=bytearray(payload);fields=[mode,42,0x80000000,3,3,1,0x12345678,0x140005100,0x140006000]
  for i,v in enumerate(fields):struct.pack_into('<Q',configured,7680+i*8,v)
  struct.pack_into('<Q',configured,7680+200,stage)
  wide='C:\\wp\\é😀.txt\0'.encode('utf-16-le');ascii_path='C:/wp/é😀.txt\0'.encode()
  configured[7680+256:7680+256+len(wide)]=wide;configured[7680+2304:7680+2304+len(ascii_path)]=ascii_path
  image=out/('fixture-'+label+'.exe');image.write_bytes(configured)
  row=dict(name=label,formatted=stage==1,disk_before_sha256=bootutil.sha(disk),fixture_sha256=bootutil.sha(image))
  report['boots'].append(row)
  wrapper=out/('qemu-'+label+'.sh');wrapper.write_text('#!/bin/sh\nexec '+shlex.quote(a.qemu)+' -device '+shlex.quote(f'loader,file={image},addr=0x10000000,force-raw=on')+' "$@"\n');wrapper.chmod(0o700)
  boot=bootutil.Boot(out/'kernel.bin',disk,out/label,str(wrapper),a.timeout,row)
  text=bytes(boot.log).decode(errors='replace');assert 'windows-path-persist:21 actual Unicode cwd CreateFileW A write read EOF close NVMe activations PASS' in text,text
  boot.halt();boot=None
  metadata,actual=disk_file(disk,['wp','é😀.txt']);assert actual==b'0123456789ABCDEF'
  row.update(status='passed',executions=21,persisted_file=metadata,disk_after_sha256=bootutil.sha(disk))
 report['status']='passed';print('PASS63 actual Unicode path NVMe activations across3 independent boots')
finally:
 if boot:boot.close()
 report['source_changed']=[name for name,value in source_hashes.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=value]
 (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
