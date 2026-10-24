#!/usr/bin/env python3
"""Execute real Darwin file syscalls from a private CPL3 Mach-O fixture."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import time
import sys
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();out=a.out.resolve()
if out.exists() and any(out.iterdir()):p.error('--out must be new or empty')
out.mkdir(parents=True,exist_ok=True)
tracked_sources=sorted(set(root.glob('components/*.in'))|set(root.glob('boot/*.asm'))|set(root.glob('kernel/*.in'))|set((root/'fixtures/darwin-files').glob('*.asm'))|{Path(__file__).resolve()})
source_hashes={str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in tracked_sources}
report={'status':'running','compiler':a.compiler,'compiler_sha256':hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),'source_sha256':source_hashes,'compile_commands':[]}
def failure_receipt(kind,error,traceback):
    report.update(status='failed',error=str(error)[-4000:],source_changed_during_run=[str(path.relative_to(root)) for path in tracked_sources if hashlib.sha256(path.read_bytes()).hexdigest()!=source_hashes[str(path.relative_to(root))]])
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    sys.__excepthook__(kind,error,traceback)
sys.excepthook=failure_receipt
source=(root/'kernel/kernel-root.in').read_text()
source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(root/m.group(1))),source)
# Explicit test-only syscall revokes borrowed storage inside the active guest.
provider=(root/'components/darwin-protected.in').read_text()
provider=re.sub(r'import "([^"]+)"',lambda m:'import '+json.dumps(str(root/'components'/m.group(1))),provider)
assert provider.count('domain-user-syscall-hook = darwin-protected-dispatch')==1
provider=provider.replace('domain-user-syscall-hook = darwin-protected-dispatch','domain-user-syscall-hook = darwin-files-test-dispatch')
(out/'darwin-protected.in').write_text(provider)
hub=(root/'components/personality-hub.in').read_text()
hub=re.sub(r'import "([^"]+)"',lambda m:'import '+json.dumps(str((root/'components'/m.group(1)).resolve())),hub)
hub=hub.replace(json.dumps(str(root/'components/darwin-protected.in')),json.dumps(str(out/'darwin-protected.in')))
(out/'personality-hub.in').write_text(hub)
source=source.replace(json.dumps(str(root/'components/personality-hub.in')),json.dumps(str(out/'personality-hub.in')))
assert source.count('  shell(port)')==1
source=source.replace('  shell(port)','  darwin-files-check(port)\n  shell(port)')
source+='''
fn darwin-files-test-dispatch(frame:Int)->Int{
 if load64(frame+112)==0x2FFFFFE{
  if domain-current!=darwin-protected-domain || darwin-protected-busy==0{panic("Darwin revoke control wrong domain");}
  cap-revoke(darwin-protected-storage);store64(frame+112,0);store64(frame+136,load64(frame+136)&-2);return 1;
 }
 return darwin-protected-dispatch(frame);
}
fn darwin-files-invoke(image:Int,size:Int,serial:Int,storage:Int,budget:Int)->Int{
 let fs=rdmsr(0xC0000100);let gs=rdmsr(0xC0000101);
 wrmsr64(0xC0000100,0x42000000);wrmsr64(0xC0000101,0x42001000);
 let status=darwin-protected-run-services(image,size,serial,storage,budget);
 let returned-fs=rdmsr(0xC0000100);let returned-gs=rdmsr(0xC0000101);
 wrmsr64(0xC0000100,fs);wrmsr64(0xC0000101,gs);
 if returned-fs!=0x42000000 || returned-gs!=0x42001000{panic("Darwin caller FS GS base not restored");}
 return status;
}
fn darwin-files-free()->Int{let n=0;let f=free-list;while f!=0 && n<4096{n=n+1;f=load64(f);}return n;}
fn darwin-files-check(port:Int)->void{
 if sf-mem-disk==0 || volume-ready!=0{panic("Darwin fixture requires owned RAM SparkFS");}
 let image=0x10000000;let seed=alloc(8192);let j=0;
 while j<8192{store8(seed+j,load8("0123456789abcdef"+(j&15)));j=j+1;}
 if fs-write-file("darwin-file-api.txt",seed,8192)!=0{panic("Darwin file seed failed");}
 if fs-write-file("abcdefghijklmnopqrstuvwx",seed,16)!=0{panic("Darwin24byte name seed failed");}
 let serial=cap-mint(root-realm,cap-serial());let storage=cap-mint(root-realm,cap-storage());
 let host=vfs-open("darwin-file-api.txt",VFS-O-RDONLY);
 if host!=3{panic("Darwin fixture requires ambient host fd3 sentinel");}
 let first=vfs-fd-alloc();let path=load64(vfs-fd-table+host*32);
 let caps=cap-count;let cycle=0;let heap=0;let free=0;let domains=0;
 while cycle<21{
  let mode=0;
  while mode<27{
   if mode!=8{
    store64(image+4096,mode);let grant=storage;if mode==1 || mode==18{grant=-1;}
    let budget=1000;if mode==7{budget=5;}
    let result=darwin-files-invoke(image,8192,serial,grant,budget);
    let expected=42;if mode==6 || mode==25 || mode==26{expected=142;}if mode==7{expected=124;}
    if result!=expected{serial-write-cstr(port,"darwin-files: mode ");serial-write-dec-wide(port,mode);serial-write-cstr(port," result ");serial-write-dec-wide(port,result);serial-nl(port);panic("Darwin file fixture mismatch");}
    if vfs-fd-alloc()!=first || vfs-fd-valid(host)==0 || vfs-fd-offset(host)!=0 || load64(vfs-fd-table+host*32)!=path{panic("Darwin host fd ownership changed");}
    if darwin-protected-count!=0 || darwin-protected-busy!=0 || darwin-protected-storage!=-1 || domain-current!=0 || domain-user-syscall-hook!=0 || user-budget-active!=0 || cap-count!=caps{panic("Darwin file activation leaked");}
    let retired=darwin-protected-last-domain;
    if load64(domain-table+retired*24)!=0 || load64(domain-table+retired*24+8)!=DOMAIN-FREE{panic("Darwin file domain leaked");}
   }
   mode=mode+1;
  }
  if cycle==0{heap=heap-next;free=darwin-files-free();domains=domain-count;}
  else{if heap-next!=heap || darwin-files-free()!=free || domain-count!=domains{panic("Darwin repeated file resources leaked");}}
  cycle=cycle+1;
 }
 let revocable=cap-mint(root-realm,cap-storage());store64(image+4096,8);
 if darwin-files-invoke(image,8192,serial,revocable,1000)!=42 || cap-check(revocable,cap-storage())!=0 || vfs-fd-alloc()!=first{panic("Darwin live storage revoke failed");}
 if heap-next!=heap || darwin-files-free()!=free || domain-count!=domains{panic("Darwin revoked file resources leaked");}
 store64(image+4096,0);
 if darwin-files-invoke(image,8192,serial,storage,1000)!=42{panic("Darwin fresh files after fault timeout revoke failed");}
 if vfs-close(host)!=0{panic("Darwin host descriptor final close failed");}
 cap-revoke(storage);cap-revoke(serial);
 serial-write-cstr(port,"darwin-files: 21 cycles 548 CPL3 executions PASS");serial-nl(port);
}
'''
(out/'kernel.in').write_text(source)
with (out/'compile.log').open('w') as log:
    for command in [
        ['nasm','-f','bin',str(root/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],
        ['nasm','-f','bin',str(root/'fixtures/darwin-files/process.asm'),'-o',str(out/'process.macho')],
        [a.compiler,'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')],
    ]:
        report['compile_commands'].append(command)
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180,cwd=root)
kernel=(out/'kernel.bin').read_bytes();payload=(out/'process.macho').read_bytes()
# Multiboot loads at 1 MiB; the fixture is a separate QEMU loader region.
# Keep explicit non-overlap even when the compiler relocates boot data.
assert len(kernel)<0x0FF00000 and len(payload)==8192
received=bytearray();serial=None
with (out/'qemu.log').open('w') as qlog:
    path=out/'serial.sock'
    qemu_args=['qemu-system-x86_64','-kernel',str(out/'kernel.bin'),'-device',f'loader,file={out / "process.macho"},addr=0x10000000,force-raw=on','-m','512M','-display','none','-no-reboot','-serial',f'unix:{path},server=on,wait=on']
    report['qemu_command']=qemu_args
    qemu=subprocess.Popen(qemu_args,stdout=qlog,stderr=subprocess.STDOUT)
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
                if b'nanokernel fault handler halting' in received or b'space: halting' in received:break
            except socket.timeout:
                if qemu.poll() is not None:break
        text=received.decode(errors='replace')
        assert 'darwin-files: 21 cycles 548 CPL3 executions PASS' in text,text
        assert 'space interactive shell' in text,text
        serial.sendall(b'halt\n')
        report.update({'status':'passed','cycles':21,'executions':548,'profile':'five-command typed libSystem and raw Darwin syscall Mach-O fixture','compiler':a.compiler,'compiler_sha256':hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),'source_sha256':source_hashes,'source_changed_during_run':[str(path.relative_to(root)) for path in tracked_sources if hashlib.sha256(path.read_bytes()).hexdigest()!=source_hashes[str(path.relative_to(root))]],'kernel_sha256':hashlib.sha256(kernel).hexdigest(),'payload_sha256':hashlib.sha256(payload).hexdigest()})
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(f'PASS: Darwin owned file syscalls, 21 cycles, 548 CPL3 executions; {out}')
    finally:
        (out/'serial.log').write_bytes(received)
        if serial:serial.close()
        qemu.terminate()
        try:qemu.wait(timeout=3)
        except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
