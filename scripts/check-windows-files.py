#!/usr/bin/env python3
"""Execute protected Win64 file APIs over owned Space VFS descriptors."""
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
source = source.replace('  shell(port)', '  windows-files-check(port)\n  shell(port)')
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
fn windows-files-free()->Int{let n=0;let f=free-list;while f!=0 && n<4096{n=n+1;f=load64(f);}return n;}
fn windows-files-refuse(image:Int,off:Int,value:Int)->void{
 let old=load64(image+off);let heap=heap-next;let free=free-list;let domains=domain-count;
 store64(image+off,value);let result=windows-protected-run(image,8704);store64(image+off,old);
 if result!=-8 || heap-next!=heap || free-list!=free || domain-count!=domains{panic("Windows file import refusal changed state");}
}
fn windows-files-check(port:Int)->void{
 let image=0x280000;
 windows-files-refuse(image,4608+64+5*8,-1);
 windows-files-refuse(image,4608+64+10*8,0x31C0);
 windows-files-refuse(image,4608+160+10*8,0x31C0);
 windows-files-refuse(image,4608+448,0);
 windows-files-refuse(image,4608+512,0);
 if fs-write-file("windows-file-api.txt","0123456789abcdef",16)!=0{panic("Windows VFS seed failed");}
 let authority=cap-mint(root-realm,cap-serial());let storage=cap-mint(root-realm,cap-storage());
 let host=vfs-open("windows-file-api.txt",VFS-O-RDONLY);
 if host!=3{panic("Windows file gate requires host fd3");}
 let first=vfs-fd-alloc();let host-path=load64(vfs-fd-table+host*32);
 let cycle=0;let heap=0;let free=0;let domains=0;let caps=cap-count;
 while cycle<21{
  let mode=0;
  while mode<26{
   if mode!=21{
    store64(image+5376,mode);let status=0;
    if mode==23{windows-protected-budget=5;}
    if mode==1{status=windows-protected-run-granted(image,8704,authority);}
    else{status=windows-protected-run-files(image,8704,authority,storage);}
    windows-protected-budget=100;
    let expected=42;if mode==22{expected=142;}if mode==23{expected=124;}
    if status!=expected{serial-write-cstr(port,"windows-files: failed mode ");serial-write-dec-wide(port,mode);serial-write-cstr(port," result ");serial-write-dec-wide(port,status);serial-nl(port);panic("Windows file execution mismatch");}
    if vfs-fd-alloc()!=first || vfs-fd-valid(host)==0 || vfs-fd-offset(host)!=0 || load64(vfs-fd-table+host*32)!=host-path{panic("Windows borrowed host descriptor corrupted");}
    if windows-protected-count!=0 || windows-protected-busy!=0 || windows-protected-storage!=-1 || domain-current!=0 || user-budget-active!=0 || domain-user-syscall-hook!=0 || cap-count!=caps{panic("Windows file activation leaked");}
   }
   mode=mode+1;
  }
  if cycle==0{heap=heap-next;free=windows-files-free();domains=domain-count;}
  else{if heap-next!=heap || windows-files-free()!=free || domain-count!=domains{panic("Windows file repeated resources leaked");}}
  cycle=cycle+1;
 }
 let revocable=cap-mint(root-realm,cap-storage());store64(image+5376,21);
 if windows-protected-run-files(image,8704,authority,revocable)!=42 || cap-check(revocable,cap-storage())!=0 || vfs-fd-alloc()!=first{panic("Windows live storage revocation failed");}
 if heap-next!=heap || windows-files-free()!=free || domain-count!=domains{panic("Windows revoked file resources leaked");}
 store64(image+5376,0);
 if windows-protected-run-files(image,8704,authority,storage)!=42{panic("Windows fresh files after fault timeout revoke failed");}
 vfs-close(host);cap-revoke(storage);cap-revoke(authority);
 serial-write-cstr(port,"windows-files: CreateFileA ReadFile SetFilePointerEx CloseHandle GetFileSizeEx real VFS PASS");serial-nl(port);
 serial-write-cstr(port,"windows-files: 21 cycles 527 executions EOF errors ownership live revoke fault timeout cleanup PASS");serial-nl(port);
}
'''
(out/'kernel.in').write_text(source)
commands = [
    ['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],
    ['nasm','-f','bin',str(ROOT/'fixtures/windows-protected/file-api.asm'),'-o',str(out/'process.exe')],
    [a.compiler,'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')],
]
with (out/'compile.log').open('w') as log:
    for command in commands:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
kernel=(out/'kernel.bin').read_bytes();payload=(out/'process.exe').read_bytes()
assert len(kernel)<=0x180000 and len(payload)==8704
(out/'combined.bin').write_bytes(kernel+bytes(0x180000-len(kernel))+payload)
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
        assert 'windows-files: CreateFileA ReadFile SetFilePointerEx CloseHandle GetFileSizeEx real VFS PASS' in text,text
        assert 'windows-files: 21 cycles 527 executions EOF errors ownership live revoke fault timeout cleanup PASS' in text,text
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
                      source_sha256={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in [ROOT/'components/windows-protected.in',ROOT/'components/domain.in',ROOT/'components/vfs.in',ROOT/'components/user-budget.in',ROOT/'boot/multiboot.asm',ROOT/'fixtures/windows-protected/file-api.asm']})
        report['test_only_override']={'purpose':'supervisor revokes borrowed storage capability during an active protected guest; absent from production dispatcher','compiled_personality_sha256':hashlib.sha256((out/'windows-protected.in').read_bytes()).hexdigest()}
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(f'PASS: protected Windows real VFS file APIs, live revoke and cleanup; {out}')
    finally:
        (out/'serial.log').write_bytes(received)
        if serial:serial.close()
        qemu.terminate()
        try:qemu.wait(timeout=3)
        except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
