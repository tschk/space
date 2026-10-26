#!/usr/bin/env python3
"""Execute protected Win64 writable VFS APIs with exact byte/error checks."""
from boot_fixture_layout import stage_fixture
import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
out = a.out.resolve()
if out.exists() and any(out.iterdir()):
    p.error('--out must be new or empty')
out.mkdir(parents=True, exist_ok=True)
source = (ROOT/'kernel/kernel-root.in').read_text()
source = re.sub(r'import "\.\./([^"]+)"', lambda m: 'import '+json.dumps(str(ROOT/m.group(1))), source)
assert source.count('  shell(port)') == 1
source = source.replace('  shell(port)', '  windows-write-check(port)\n  shell(port)')
# Test-only dispatcher adds one supervisor revocation control, absent in production.
windows_source=(ROOT/'components/windows-protected.in').read_text()
windows_source=re.sub(r'import \"([^\"]+)\"',lambda m:'import '+json.dumps(str(ROOT/'components'/m.group(1))),windows_source)
assert windows_source.count('domain-user-syscall-hook = windows-protected-dispatch')==1
windows_source=windows_source.replace('domain-user-syscall-hook = windows-protected-dispatch','domain-user-syscall-hook = windows-files-test-dispatch')
(out/'windows-protected.in').write_text(windows_source)
hub=(ROOT/'components/personality-hub.in').read_text()
hub=re.sub(r'import "([^"/]+)"',lambda m:'import '+json.dumps(str(ROOT/'components'/m.group(1))),hub)
hub=hub.replace(json.dumps(str(ROOT/'components/windows-protected.in')),json.dumps(str(out/'windows-protected.in')))
(out/'personality-hub.in').write_text(hub)
source=source.replace(json.dumps(str(ROOT/'components/personality-hub.in')),json.dumps(str(out/'personality-hub.in')))
source += '''
fn windows-files-test-dispatch(frame:Int)->Int{
 if load64(frame+112)==0x100100{
  if domain-current!=windows-protected-domain || windows-protected-busy==0{panic("Windows revoke control wrong domain");}
  cap-revoke(windows-protected-storage);store64(frame+112,0);return 1;
 }
 return windows-protected-dispatch(frame);
}
fn windows-write-free()->Int{let n=0;let f=free-list;while f!=0 && n<4096{n=n+1;f=load64(f);}return n;}
fn windows-write-check(port:Int)->void{
 let image=0x2f0000;let output=alloc(8192);
 if fs-write-file("windows-host-api.txt","host",4)!=0{panic("Windows write host seed");}
 if fs-write-file("windows-file-api.txt","0123456789abcdef",16)!=0{panic("Windows write seed");}
 let host=vfs-open("windows-host-api.txt",VFS-O-RDONLY);if host!=3{panic("Windows write host fd");}
 let first=vfs-fd-alloc();let authority=cap-mint(root-realm,cap-serial());let storage=cap-mint(root-realm,cap-storage());let caps=cap-count;
 let cycle=0;let free=0;let domains=0;let growth=0;let last-heap=0;
 while cycle<21{
  let mode=0;
  while mode<26{
   if mode!=13{
    if mode==1 || mode==3{if fs-stat("windows-missing-api.txt",output)==0{if fs-delete("windows-missing-api.txt")!=0{panic("Windows new path delete");}}}
    if fs-write-file("windows-file-api.txt","0123456789abcdef",16)!=0{panic("Windows write reset");}
    store64(image+9472,mode);let before=heap-next;let status=0;
    if mode==23{windows-protected-budget=5;}
    if mode==14{status=windows-protected-run-granted(image,12800,authority);}
    else{status=windows-protected-run-files(image,12800,authority,storage);}
    windows-protected-budget=100;
    let expected=42;if mode==22{expected=142;}if mode==23{expected=124;}
    if status!=expected{serial-write-cstr(port,"windows-write: failed mode ");serial-write-dec-wide(port,mode);serial-write-cstr(port," result ");serial-write-dec-wide(port,status);serial-nl(port);panic("Windows writable execution mismatch");}
    if cycle>0{
     let delta=heap-next - before;
     if mode==1 || mode==3{if delta!=0{panic("Windows FS creation allocated after warm-up");}growth=growth+delta;}
     else{if delta!=0{serial-write-dec-wide(port,mode);panic("Windows non-create activation allocated");}}
    }
    if vfs-fd-alloc()!=first || vfs-fd-valid(host)==0 || vfs-fd-offset(host)!=0{panic("Windows writable host descriptor corrupted");}
    if windows-protected-count!=0 || windows-protected-busy!=0 || windows-protected-storage!=-1 || domain-current!=0 || user-budget-active!=0 || domain-user-syscall-hook!=0 || cap-count!=caps{panic("Windows writable activation leaked");}
    let length=fs-read-file("windows-file-api.txt",output,8192);let size=16;
    if mode==0{size=68;}if mode==4{size=0;}if mode==24{size=84;}
    if length!=size{serial-write-dec-wide(port,mode);panic("Windows write exact size mismatch");}
    let i=0;
    while i<size{
     let expected-byte=0;
     if mode==0{if i<64{expected-byte=65+i;if i>=13 && i<16{expected-byte=90;}}else{expected-byte=load8("tail"+i - 64);}}
     else{if i<16{expected-byte=load8("0123456789abcdef"+i);}if mode==18 && i<8{expected-byte=load8(image+512+i);}if (mode==22 || mode==23) && i<4{expected-byte=load8("TEST"+i);}if mode==24 && i>=80{expected-byte=load8("test"+i - 80);}}
     if load8(output+i)!=expected-byte{serial-write-dec-wide(port,mode);panic("Windows writable exact content mismatch");}i=i+1;
    }
    if mode==1{if fs-read-file("windows-missing-api.txt",output,8192)!=8 || load64(output)!=0x6867666564636261{panic("Windows CREATE_NEW content");}}
   }
   mode=mode+1;
  }
  if cycle==0{free=windows-write-free();domains=domain-count;}
  else{if windows-write-free()!=free || domain-count!=domains{panic("Windows writable repeated frame/domain leak");}}
  if cycle>0 && heap-next!=last-heap{panic("Windows whole-cycle filesystem metadata allocation leak");}
  last-heap=heap-next;cycle=cycle+1;
 }
 if fs-write-file("windows-file-api.txt","0123456789abcdef",16)!=0{panic("Windows revoke reset");}
 let revocable=cap-mint(root-realm,cap-storage());store64(image+9472,13);
 if windows-protected-run-files(image,12800,authority,revocable)!=42 || cap-check(revocable,cap-storage())!=0 || vfs-fd-alloc()!=first{panic("Windows live write revocation failed");}
 if fs-read-file("windows-file-api.txt",output,8192)!=16 || load64(output)!=0x3736353433323130{panic("Windows revoked write changed data");}
 store64(image+9472,0);if windows-protected-run-files(image,12800,authority,storage)!=42{panic("Windows fresh writer after revocation");}
 vfs-close(host);cap-revoke(storage);cap-revoke(authority);
 serial-write-cstr(port,"windows-write: real VFS create truncate seek overwrite append reopen counts permissions sharing PASS");serial-nl(port);
 serial-write-cstr(port,"windows-write: 21 cycles 527 executions grants fault timeout cleanup stable owned frames PASS");serial-nl(port);
 serial-write-cstr(port,"windows-write: observed filesystem creation metadata heap growth ");serial-write-dec-wide(port,growth);serial-nl(port);
}
'''
(out/'kernel.in').write_text(source)
commands = [
    ['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],
    ['nasm','-f','bin',str(ROOT/'fixtures/windows-protected/write-api.asm'),'-o',str(out/'process.exe')],
    [a.compiler,'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')],
]
with (out/'compile.log').open('w') as log:
    for command in commands:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
kernel=(out/'kernel.bin').read_bytes();payload=(out/'process.exe').read_bytes()
assert len(kernel)<=0x1f0000 and len(payload)==12800
(out/'combined.bin').write_bytes(stage_fixture(kernel,payload,0x2f0000))
received=bytearray();serial=None
with (out/'qemu.log').open('w') as qlog:
    path=out/'serial.sock'
    qemu_command=['qemu-system-x86_64','-kernel',str(out/'combined.bin'),'-m','512M','-display','none','-no-reboot','-serial',f'unix:{path},server=on,wait=on']
    qemu=subprocess.Popen(qemu_command,stdout=qlog,stderr=subprocess.STDOUT)
    try:
        deadline=time.monotonic()+10
        while not path.exists() and qemu.poll() is None and time.monotonic()<deadline:time.sleep(.02)
        serial=socket.socket(socket.AF_UNIX);serial.settimeout(.2);serial.connect(str(path))
        deadline=time.monotonic()+120
        while b'space> ' not in received and time.monotonic()<deadline:
            try:
                block=serial.recv(65536)
                if not block:break
                received.extend(block)
                if b'nanokernel fault handler halting' in received or b'PANIC' in received:break
            except socket.timeout:
                if qemu.poll() is not None:break
        text=received.decode(errors='replace')
        assert 'windows-write: real VFS create truncate seek overwrite append reopen counts permissions sharing PASS' in text,text
        assert 'windows-write: 21 cycles 527 executions grants fault timeout cleanup stable owned frames PASS' in text,text
        assert 'space interactive shell' in text and 'space> ' in text,text
        serial.sendall(b'halt\n')
        deadline=time.monotonic()+10
        while b'halting on request' not in received and time.monotonic()<deadline:
            try:
                block=serial.recv(65536)
                if not block:break
                received.extend(block)
            except socket.timeout:
                if qemu.poll() is not None:break
        assert b'halting on request' in received,received.decode(errors='replace')
        report={'status':'passed','cycles':21,'executions':527,'fixture_kind':'original bounded PE32+; not unmodified Windows app','imports':['GetStdHandle','WriteFile','GetCurrentProcessId','ExitProcess','GetLastError','CreateFileA','ReadFile','SetFilePointerEx','CloseHandle','GetFileSizeEx'],'compiler':a.compiler,'kernel_sha256':hashlib.sha256(kernel).hexdigest(),'payload_sha256':hashlib.sha256(payload).hexdigest()}
        report.update(compiler_sha256=hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),
                      source_sha256={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in [ROOT/'components/windows-protected.in',ROOT/'components/domain.in',ROOT/'components/vfs.in',ROOT/'components/user-budget.in',ROOT/'boot/multiboot.asm',ROOT/'fixtures/windows-protected/write-api.asm']})
        growth=re.search(r'windows-write: observed filesystem creation metadata heap growth ([0-9]+)',text)
        assert growth,text
        report['filesystem_creation_heap_growth_bytes']=int(growth.group(1))
        report['test_only_override']={'purpose':'supervisor revokes borrowed storage capability during an active protected guest; absent from production dispatcher','compiled_personality_sha256':hashlib.sha256((out/'windows-protected.in').read_bytes()).hexdigest()}
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(f'PASS: protected Windows writable VFS exact bytes, grants and cleanup; {out}')
    finally:
        (out/'serial.log').write_bytes(received)
        if serial:serial.close()
        qemu.terminate()
        try:qemu.wait(timeout=3)
        except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
