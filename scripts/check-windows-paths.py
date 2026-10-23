#!/usr/bin/env python3
"""Prove owned Windows cwd and actual wide file paths against native storage."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import struct
import subprocess
import time
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();a.compiler=a.compiler.resolve();out=a.out.resolve()
assert not out.exists() or not any(out.iterdir()),'--out must be new or empty'
out.mkdir(parents=True,exist_ok=True)
PRESERVE=0x12345678;SRC=0x140005100;DST=0x140006000
cases=[]
def case(name,path='/',mode=0,result=1,error=PRESERVE,cwd='/wp',source=SRC,output=DST,access=0x80000000,sharing=3,disposition=3,alias=None,status=42,expectedout=False):
    if isinstance(path,bytes):data=path
    else:data=(path+'\0').encode('utf-8' if mode==3 else 'utf-16-le')
    expected=('C:'+cwd.replace('/','\\')+'\0').encode('utf-16-le')
    other=(alias if alias is not None else path if isinstance(path,str) else '').encode('utf-8')+b'\0'
    fields=[mode,status,access,sharing,disposition,result,error,source,output,len(data),len(expected),len(expected) if expectedout else 0,len(other),0,0,0]
    assert len(data)<=2048 and len(expected)<=2052 and len(other)<=1024
    raw=struct.pack('<16Q',*(v&0xffffffffffffffff for v in fields)).ljust(256,b'\0')+data
    raw=raw.ljust(3072,b'\0')+expected;raw=raw.ljust(6144,b'\0')+other
    cases.append(dict(name=name,fields=fields,input_hex=data.hex(),expected_cwd=cwd,alias_hex=other.hex(),raw=raw.ljust(8192,b'\0')))
case('root','/',cwd='/')
case('relative','sub',cwd='/wp/sub')
case('backslash-root','\\wp\\sub',cwd='/wp/sub')
case('drive-absolute','C:\\wp\\sub',cwd='/wp/sub')
case('drive-relative','c:sub',cwd='/wp/sub')
case('drive-current','C:',cwd='/wp')
case('dots','sub\\..\\.\\sub',cwd='/wp/sub')
case('root-clamp','../../../../',cwd='/')
case('unicode-directory','é😀',cwd='/wp/é😀')
for name,path,error in [('missing','missing',3),('file','existing.txt',267),('empty','',3),('drive','D:\\wp',15),('unc','\\\\server\\share',50),('device-prefix','\\\\?\\C:\\wp',50),('device','NUL',123),('device-extension','con.txt',123),('device-digit','lpt9',123),('wildcard','*',123),('colon','x:y',15),('trailing-dot','sub.',123),('trailing-space','sub ',123),('control','a\x01b',123),('component25','x'*25,206),('utf8component28','😀'*7,206)]:case(name,path,result=0,error=error)
case('null-source',source=0,result=0,error=87)
case('bad-source',source=0x70000000,result=0,error=998)
case('surrogate',path=struct.pack('<HH',0xd800,0),result=0,error=1113)
case('cwd-query',mode=1,result=6,disposition=0,output=0)
case('cwd-short',mode=1,result=6,disposition=1)
case('cwd-full',mode=1,result=5,disposition=2048,expectedout=True)
case('cwd-null',mode=1,result=0,disposition=2048,output=0,error=87)
case('cwd-bad',mode=1,result=0,disposition=2048,output=0x70000000,error=998)
case('cwd-readonly',mode=1,result=0,disposition=10,output=0x140003400,error=998)
case('cwd-cross-unmapped',mode=1,result=0,disposition=10,output=0x140006fff,error=998)
case('cwd-count-bound',mode=1,result=0,disposition=8193,error=8)
case('open-wide','existing.txt',mode=2,result=3)
case('open-drive','C:/wp/./existing.txt',mode=2,result=3)
case('open-ascii','existing.txt',mode=3,result=3)
case('open-utf8-invalid',path=b'\xed\xa0\x80\0',mode=3,result=-1,error=1113)
case('open-directory','sub',mode=2,result=-1,error=5)
case('open-missing','not-here',mode=2,result=-1,error=2)
case('open-bad-drive','D:/x',mode=2,result=-1,error=15)
case('open-device','COM1.log',mode=2,result=-1,error=123)
case('filetype-uart',mode=4,access=1,result=2)
case('filetype-invalid',mode=4,access=123,result=0,error=6)
case('roundtrip-unicode','é😀.txt',mode=10)
case('share-aw','existing.txt',mode=12,alias='C:/wp/./existing.txt')
case('private-workspace',mode=14,status=142)
case('held-deadline','deadline.txt',mode=15,status=124)
case('private-handlepath','private.txt',mode=17,status=142)
deep='/'.join(['d'*24]*40)
case('deep-cwd-over255',deep,cwd='/wp/'+deep)
case('exact1023-wide-and-A',deep+'/'+'f'*19,mode=10)
case('path1024-refused',deep+'/'+'f'*20,mode=2,result=-1,error=206)
case('unicode-component24','😀'*6,cwd='/wp/'+'😀'*6)
case('unicode-file-component24','😁'*6,mode=10)
case('ascii-component24','A'*24,cwd='/wp/'+'A'*24)
case('case-sensitive-native','a'*24,result=0,error=3)
case('create-component25','x'*25,mode=2,result=-1,error=206)
case('unterminated-bound',path=('x'*1024).encode('utf-16-le'),result=0,error=206)
case('wide-trailing-file-separator','existing.txt\\',mode=2,result=-1,error=123)
case('A-trailing-file-separator','existing.txt/',mode=3,result=-1,error=123)
case('wide-Unicode-trailing-file-separator','é😀.txt\\',mode=2,result=-1,error=123)
regular=len(cases)
case('live-storage','revoke.txt',mode=16)
(out/'cases.json').write_text(json.dumps([{k:v for k,v in c.items() if k!='raw'} for c in cases],indent=2)+'\n')
payload=struct.pack('<3Q',len(cases),regular,0).ljust(4096,b'\0')+b''.join(c['raw'] for c in cases)
(out/'oracles.bin').write_bytes(payload)
def absolute_imports(source):return re.sub(r'import "([^"]+)"',lambda m:'import '+json.dumps(str((ROOT/'components'/m.group(1)).resolve())),source)
protected=absolute_imports((ROOT/'components/windows-protected.in').read_text());assert protected.count('domain-user-syscall-hook = windows-protected-dispatch')==1
protected=protected.replace('domain-user-syscall-hook = windows-protected-dispatch','domain-user-syscall-hook = windows-path-test-dispatch');(out/'windows-protected.in').write_text(protected)
hub=absolute_imports((ROOT/'components/personality-hub.in').read_text()).replace(json.dumps(str(ROOT/'components/windows-protected.in')),json.dumps(str(out/'windows-protected.in')));(out/'personality-hub.in').write_text(hub)
source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(ROOT/m.group(1))),(ROOT/'kernel/kernel-root.in').read_text()).replace(json.dumps(str(ROOT/'components/personality-hub.in')),json.dumps(str(out/'personality-hub.in')))
assert source.count('  shell(port)')==1;source=source.replace('  shell(port)','  windows-path-check(port)\n  shell(port)')
source+=r'''
var windows-path-test-row:Int=0
var windows-path-test-first:Int=0
var windows-path-test-calls:Int=0
var windows-path-test-scratch:Int=0

var windows-path-test-fs-snapshot:Int=0
fn windows-path-test-fs-bitmap()->Int{return ((load64(sf-super+SF-SB-TOTAL-BLOCKS)+63)/64)*8;}
fn windows-path-test-fs-save()->void{let bitmap=windows-path-test-fs-bitmap();let inodes=load32(sf-super+SF-SB-INODE-COUNT)*SF-INODE-SIZE;let i=0;while i<bitmap{store64(windows-path-test-fs-snapshot+i,load64(sf-bitmap+i));i=i+8;}i=0;while i<inodes{store64(windows-path-test-fs-snapshot+bitmap+i,load64(sf-inodes+i));i=i+8;}}
fn windows-path-test-fs-same()->Int{let bitmap=windows-path-test-fs-bitmap();let inodes=load32(sf-super+SF-SB-INODE-COUNT)*SF-INODE-SIZE;let i=0;while i<bitmap{if load64(windows-path-test-fs-snapshot+i)!=load64(sf-bitmap+i){return 0;}i=i+8;}i=0;while i<inodes{if load64(windows-path-test-fs-snapshot+bitmap+i)!=load64(sf-inodes+i){return 0;}i=i+8;}return 1;}
fn windows-path-test-capture(guest:Int,output:Int,bytes:Int)->void{let i=0;while i<bytes{let p=windows-protected-physical(guest+i);let n=4096 - ((guest+i)&4095);if n>bytes - i{n=bytes - i;}let j=0;while j<n{let value=0;if p!=0{value=load8(p+j);}store8(output+i+j,value);j=j+1;}i=i+n;}}
fn windows-path-test-compare(guest:Int,expected:Int,bytes:Int)->Int{let i=0;while i<bytes{let p=windows-protected-physical(guest+i);let n=4096 - ((guest+i)&4095);if n>bytes - i{n=bytes - i;}let j=0;if p!=0{while j<n{if load8(p+j)!=load8(expected+i+j){return 0;}j=j+1;}}i=i+n;}return 1;}

fn windows-path-test-dispatch(frame:Int)->Int{
 let row=windows-path-test-row;let num=load64(frame+112);windows-path-test-calls=windows-path-test-calls+1;
 if windows-protected-profile!=12 || windows-protected-count!=87 || windows-parameters-path-data==0 || windows-parameters-path-scratch==0{panic("Path owner mismatch");}
 if windows-path-test-first==0{
  windows-path-test-first=1;let i=0;while i<load64(row+72){let p=windows-protected-physical(load64(row+56)+i);if p!=0{store8(p,load8(row+256+i));}i=i+1;}
  i=0;while i<load64(row+80){store8(windows-protected-physical(0x4d000000+i),load8(row+3072+i));i=i+1;}
  i=0;while i<load64(row+96){store8(windows-protected-physical(0x140005900+i),load8(row+6144+i));i=i+1;}
  windows-protected-store64(0x140005080,load64(row+80)/2);windows-protected-store64(0x140005090,windows-parameters-path-data);
  let private=windows-parameters-path-data;let n=0;while n<6{if n==1{private=windows-parameters-path-scratch;}if n>=2{private=windows-parameters-path-slot((n - 2)*4);}i=0;while i<windows-protected-count{if load64(windows-protected-frames+i*8)==private{panic("Private paths alias guest backing");}i=i+1;}n=n+1;}
 }
 if num==0x100100{if load64(frame+96)==1{cap-revoke(windows-protected-storage);}else{windows-protected-store64(0x140005090,windows-parameters-path-slot(3));}store64(frame+112,0);return 1;}
 let checked-fs=0;if num==0x100031 || ((num==0x100033 || num==0x100005) && (load64(row)==12 || load64(row)==16 || load64(row+40)==-1)){windows-path-test-fs-save();checked-fs=1;}let before-fd=vfs-fd-alloc();
 let observe=0;if num==0x100031 || num==0x100032 || num==0x100033 || num==0x100034 || num==0x100005{observe=1;}
 let output=load64(frame+88);let capacity=load64(frame+96)&0xffffffff;let observed-bytes=0;if num==0x100032 && capacity>0{observed-bytes=capacity*2;if observed-bytes>4096{observed-bytes=4096;}}let i=0;
 if observe!=0{while i<1024{store8(windows-path-test-scratch+i,load8(windows-parameters-path-data+i));i=i+1;}
  windows-path-test-capture(output,windows-path-test-scratch+1024,observed-bytes);i=0;while i<VFS-MAX-FDS{store64(windows-path-test-scratch+5120+i*8,load64(windows-protected-files+i*8));i=i+1;}
 }
 let control=windows-protected-dispatch(frame);let value=load64(frame+112);
 if observe!=0{
  let failed=0;if value==0{failed=1;}if (num==0x100033 || num==0x100005) && value==-1{failed=1;}
  if checked-fs!=0 && (failed!=0 || num==0x100031) && windows-path-test-fs-same()==0{panic("Denied path or directory API changed native inode/bitmap");}
  if failed!=0{if vfs-fd-alloc()!=before-fd{panic("Failed path API changed VFS descriptor pool");}i=0;while i<VFS-MAX-FDS{if load64(windows-path-test-scratch+5120+i*8)!=load64(windows-protected-files+i*8){panic("Failed path API changed owned handles");}i=i+1;}i=0;while i<1024{if load8(windows-parameters-path-data+i)!=load8(windows-path-test-scratch+i){panic("Failed path API changed cwd");}i=i+1;}}
  if num==0x100032 && (failed!=0 || value>=capacity){if windows-path-test-compare(output,windows-path-test-scratch+1024,observed-bytes)==0{panic("Failed or short GetCurrentDirectory partial write");}}
  if num==0x100032 && failed==0 && value<capacity{let written=(value+1)*2;if written<observed-bytes && windows-path-test-compare(output+written,windows-path-test-scratch+1024+written,observed-bytes - written)==0{panic("GetCurrentDirectory changed output tail");}}
  if num==0x100032 && load64(row)==1 && windows-path-test-calls>=4 && load64(row+88)>0 && value>0{let i=0;while i<load64(row+88){if load8(windows-protected-physical(output+i))!=load8(row+3072+i){panic("GetCurrentDirectory exact UTF16 mismatch");}i=i+1;}}
 }return control;
}
fn windows-path-test-free()->Int{let n=0;let f=free-list;while f!=0 && n<4096{n=n+1;f=load64(f);}return n;}
fn windows-path-test-clean()->void{
 if windows-protected-busy!=0 || windows-protected-count!=0 || windows-parameters-path-data!=0 || windows-parameters-path-scratch!=0 || windows-parameters-composed-active!=0 || windows-parameters-composed-data!=0 || windows-parameters-env-data!=0 || windows-parameters-heap-records!=0 || windows-parameters-local-data!=0 || windows-parameters-critical-data!=0 || windows-parameters-active!=0 || windows-parameters-time-active!=0 || domain-current!=0 || user-context-active!=0 || user-budget-active!=0 || domain-user-syscall-hook!=0{panic("Path activation ownership leaked");}
}
fn windows-path-test-config(config:Int,serial:Int,storage:Int,memory:Int,line:Int,env:Int)->void{
 store64(config,1);store64(config+8,96);store64(config+16,serial);store64(config+24,storage);store64(config+32,memory);store64(config+40,-1);store64(config+48,line);store64(config+56,strlen(line)+1);store64(config+64,env);store64(config+72,2);store64(config+80,0);store64(config+88,0);
}
fn windows-path-test-run(config:Int,row:Int)->Int{
 windows-path-test-row=row;windows-path-test-first=0;windows-path-test-calls=0;let i=0;while i<128{store8(0x10000000+7680+i,load8(row+i));i=i+1;}
 let budget=100;if load64(row)==15{budget=5;}windows-protected-budget=budget;let result=windows-command-filesystem-run(0x10000000,11776,config);windows-protected-budget=100;return result;
}
fn windows-path-check(port:Int)->void{
 let image=0x10000000;let oracle=0x12000000;if heap-next>=image{panic("Path fixture collision");}heap-end=image;
 if fs-mkdir("/wp")<0 || fs-mkdir("/wp/sub")<0 || fs-mkdir("/wp/é😀")<0 || fs-write-file("/wp/existing.txt","seed",4)!=0{panic("Path native directory/file seed failed");}
 let deep=alloc(1024);store8(deep,47);store8(deep+1,119);store8(deep+2,112);store8(deep+3,0);let length=3;let level=0;
 while level<40{store8(deep+length,47);length=length+1;let d=0;while d<24{store8(deep+length,100);length=length+1;d=d+1;}store8(deep+length,0);if fs-mkdir(deep)<0{panic("Deep native directory seed failed");}level=level+1;}
 if fs-mkdir("/wp/😀😀😀😀😀😀")<0 || fs-mkdir("/wp/AAAAAAAAAAAAAAAAAAAAAAAA")<0{panic("Exact component24 native seed failed");}
 let snapshotbytes=windows-path-test-fs-bitmap()+load32(sf-super+SF-SB-INODE-COUNT)*SF-INODE-SIZE;if snapshotbytes>1048576{panic("Path observer bounded FS snapshot exceeded");}windows-path-test-fs-snapshot=alloc(snapshotbytes);
 windows-path-test-scratch=alloc(5248);let config=alloc(96);let env=alloc(2);store8(env,0);store8(env+1,0);
 let serial=cap-mint(root-realm,cap-serial());let storage=cap-mint(root-realm,cap-storage());let memory=cap-mint(root-realm,cap-memory());windows-path-test-config(config,serial,storage,memory,"sqlite3.exe",env);
 let before=heap-next;let free=free-list;let domains=domain-count;if windows-command-unicode-run(image,11776,config)!=-8 || heap-next!=before || free-list!=free || domain-count!=domains{panic("Old profile admitted filesystem imports");}
 store64(config+24,-1);if windows-command-filesystem-run(image,11776,config)!=-13 || heap-next!=before || free-list!=free || domain-count!=domains{panic("Path missing Storage admission mutated");}store64(config+24,storage);windows-path-test-clean();
 if dyn-resolve-idx("fs-path-normalize-into")!=-1 || dyn-resolve-idx("windows-command-filesystem-run")!=-1{panic("Path private helpers exported");}
 let private=boot-image-find(254);before=heap-next;free=free-list;domains=domain-count;let caps-before=cap-count;
 if private==0 || sci-load-runtime-component(port,private,"private-native-path",1,1,0)!=-1 || heap-next!=before || free-list!=free || domain-count!=domains || cap-count!=caps-before{panic("Native path private SCI admitted/allocated");}
 serial-write-cstr(port,"windows-paths-registry: actual native pointer helper SCI import denied before allocation PASS");serial-nl(port);
 let held=alloc(220*8);let i=0;while i<220{store64(held+i*8,frame-alloc());i=i+1;}if free-list!=0{panic("Path cold pool not fully owned");}
 i=0;while i<177{frame-free(load64(held+i*8));i=i+1;}let original-end=heap-end;before=heap-next;free=free-list;domains=domain-count;heap-end=heap-next+26912;
 let refused=windows-command-filesystem-run(image,11776,config);heap-end=original-end;
 if refused!=-12 || heap-next!=before || free-list!=free || domain-count!=domains || windows-protected-frames!=0{panic("Path cold refusal mutated");}windows-path-test-clean();
 frame-free(load64(held+177*8));heap-end=heap-next+26912;let recovered=windows-path-test-run(config,oracle+4096);heap-end=original-end;
 if recovered!=42 || heap-next!=before+26912 || windows-path-test-free()!=178{serial-write-dec-wide(port,recovered);panic("Path exact cold recovery failed");}windows-path-test-clean();
 i=178;while i<220{frame-free(load64(held+i*8));i=i+1;}
 serial-write-cstr(port,"windows-paths-cold:177 frames refuse178 recover exact26912 retained bytes PASS");serial-nl(port);
 let cycle=0;let heap=0;let pool=0;let caps=cap-count;let descriptors=vfs-fd-alloc();let fs=rdmsr(0xc0000100);let gs=rdmsr(0xc0000101);let caller=current-cap;
 while cycle<21{let n=0;while n<load64(oracle+8){let row=oracle+4096+n*8192;let result=windows-path-test-run(config,row);let expected=load64(row+8);
  if result!=expected{serial-write-dec-wide(port,n);serial-put(port,32);serial-write-dec-wide(port,result);panic("Path actual case mismatch");}windows-path-test-clean();
  if vfs-fd-alloc()!=descriptors || cap-count!=caps || current-cap!=caller || rdmsr(0xc0000100)!=fs || rdmsr(0xc0000101)!=gs{panic("Path caller or descriptors changed");}n=n+1;
 }
 if cycle==0{heap=heap-next;pool=windows-path-test-free();domains=domain-count;}else{if heap_next_dummy!=0{}}
 cycle=cycle+1;}
 let live=cap-mint(root-realm,cap-storage());store64(config+24,live);if windows-path-test-run(config,oracle+4096+load64(oracle+8)*8192)!=42 || cap-check(live,cap-storage())!=0{panic("Path live Storage revoke failed");}windows-path-test-clean();
 store64(config+24,storage);if windows-path-test-run(config,oracle+4096)!=42{panic("Path fresh activation failed");}windows-path-test-clean();
 if heap-next!=heap || windows-path-test-free()!=pool || domain-count!=domains{panic("Path live revoke cleanup leaked");}
 cap-revoke(serial);cap-revoke(storage);cap-revoke(memory);serial-write-cstr(port,"windows-paths: actual owned cwd Unicode VFS A W share pointers denial fault deadline revoke cleanup PASS");serial-nl(port);
}
'''
source=source.replace('if heap_next_dummy!=0{}','if heap-next!=heap || windows-path-test-free()!=pool || domain-count!=domains{panic("Path repeated cleanup leaked");}')
names=['components/fs-path-normalize.in','components/windows-process-paths.in','components/windows-process-composed.in','components/windows-protected.in','components/windows-process-parameters.in','components/windows-pe-application.in','fixtures/windows-protected/paths.asm','fixtures/windows-protected/paths-private.in']
source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names};(out/'kernel.in').write_text(source)
commands=[['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],['nasm','-f','bin',str(ROOT/'fixtures/windows-protected/paths.asm'),'-o',str(out/'process.exe')],[str(a.compiler),'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')]]
commands.insert(0,[str(a.compiler),'compile','--path',str(ROOT/'fixtures/windows-protected/paths-private.in'),'--entry','private-entry','--emit','sci','--base','0x7a000000','--target','native','--target-triple','x86_64-unknown-none','--out',str(out/'private.sci')])
commands.append(['python',str(ROOT/'scripts/pack-sci-image.py'),str(out/'kernel.bin'),str(out/'combined.bin'),f'254:{out}/private.sci'])
with (out/'compile.log').open('w') as log:
 for command in commands:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
assert (out/'process.exe').stat().st_size==11776 and 0x100000+(out/'kernel.bin').stat().st_size<0x10000000
path=out/'serial.sock';received=bytearray();serial=None
command=['qemu-system-x86_64','-kernel',str(out/'combined.bin'),'-m','512M','-display','none','-no-reboot','-serial',f'unix:{path},server=on,wait=on','-device',f'loader,file={out/"process.exe"},addr=0x10000000,force-raw=on','-device',f'loader,file={out/"oracles.bin"},addr=0x12000000,force-raw=on']
with (out/'qemu.log').open('w') as log:
 qemu=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
 try:
  deadline=time.monotonic()+10
  while not path.exists() and qemu.poll() is None and time.monotonic()<deadline:time.sleep(.02)
  serial=socket.socket(socket.AF_UNIX);serial.settimeout(.2);serial.connect(str(path));deadline=time.monotonic()+240
  while b'space> ' not in received and time.monotonic()<deadline:
   try:
    block=serial.recv(65536)
    if not block:break
    received.extend(block)
    if b'PANIC' in received or b'nanokernel fault handler halting' in received:break
   except socket.timeout:
    if qemu.poll() is not None:break
  text=received.decode(errors='replace')
  assert 'DENIED unresolved import fs-path-normalize-into' in text and 'INVALID private native path entry' not in text,text
  assert 'windows-paths-cold:177 frames refuse178 recover exact26912 retained bytes PASS' in text,text
  assert 'windows-paths: actual owned cwd Unicode VFS A W share pointers denial fault deadline revoke cleanup PASS' in text and 'space> ' in text,text
 finally:
  (out/'serial.log').write_bytes(received)
  if serial:serial.close()
  qemu.terminate()
  try:qemu.wait(timeout=5)
  except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
report=dict(status='passed',executions=regular*21+3,unique_regular_cases=regular,compiler_sha256=hashlib.sha256(a.compiler.read_bytes()).hexdigest(),kernel_sha256=hashlib.sha256((out/'combined.bin').read_bytes()).hexdigest(),fixture_sha256=hashlib.sha256((out/'process.exe').read_bytes()).hexdigest(),oracle_sha256=hashlib.sha256(payload).hexdigest(),source_sha256=source_hashes,source_changed=[name for name,value in source_hashes.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=value],commands=commands,qemu_command=command)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS Windows owned paths',report['executions'],'actual activations')
