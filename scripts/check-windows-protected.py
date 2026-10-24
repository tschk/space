#!/usr/bin/env python3
"""Execute bounded protected PE32+ images and KERNEL32 imports inside Space."""
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
p.add_argument('--app', type=Path, help='also verify pinned original Windows jq is refused without allocation')
a = p.parse_args()
out = a.out.resolve()
if out.exists() and any(out.iterdir()):
    p.error('--out must be new or empty')
out.mkdir(parents=True, exist_ok=True)
app_metadata=None
if a.app:
    a.app=a.app.resolve()
    manifest=json.loads((ROOT/'fixtures/applications/jq-1.8.1.json').read_text())
    app_metadata=next(row for row in manifest['apps'] if row['personality']=='windows')
    assert hashlib.sha256(a.app.read_bytes()).hexdigest()==app_metadata['sha256'], 'original Windows jq checksum mismatch'
source = (ROOT/'kernel/kernel-root.in').read_text()
source = re.sub(r'import "\.\./([^"]+)"', lambda m: 'import '+json.dumps(str(ROOT/m.group(1))), source)
assert source.count('  shell(port)') == 1
source = source.replace('  shell(port)', '  windows-process-check(port)\n  shell(port)')
source += '''
fn windows-check-free()->Int{
 let n=0;let frame=free-list;while frame!=0 && n<2048{n=n+1;frame=load64(frame);}return n;
}
fn windows-check-refuse(image:Int,off:Int,value:Int,wide:Int)->void{
 let old=load32(image+off);if wide!=0{old=load64(image+off);}
 let heap=heap-next;let free=free-list;let domains=domain-count;let owned=domain-user-owned;
 store32(image+off,value);if wide!=0{store64(image+off,value);}
 let result=windows-protected-run(image,5120);
 store32(image+off,old);if wide!=0{store64(image+off,old);}
 if result!=-8 || heap!=heap-next || free!=free-list || domains!=domain-count || owned!=domain-user-owned{
  serial-write-cstr(com1(),"windows-protected: malformed offset ");serial-write-dec-wide(com1(),off);
  serial-write-cstr(com1()," result ");serial-write-dec-wide(com1(),result);serial-nl(com1());
  panic("Windows malformed admission changed state");
 }
}
fn windows-check-invalid-image(image:Int,size:Int,expected:Int)->void{
 let heap=heap-next;let free=free-list;let domains=domain-count;let owned=domain-user-owned;
 let result=windows-protected-run(image,size);
 if result!=expected || heap!=heap-next || free!=free-list || domains!=domain-count || owned!=domain-user-owned{panic("Windows malformed outer bounds changed state");}
}
fn windows-process-check(port:Int)->void{
 let image=0x2f0000;
 windows-check-invalid-image(0,5120,-8);windows-check-invalid-image(image,-1,-8);
 windows-check-invalid-image(image,1024,-8);windows-check-invalid-image(image,1536,-8);
 windows-check-invalid-image(image,5121,-8);windows-check-invalid-image(image,0x200200,-8);
 windows-protected-busy=1;windows-check-invalid-image(image,5120,-16);windows-protected-busy=0;
 let installed=domain-user-syscall-hook;domain-user-syscall-hook=windows-protected-dispatch;
 windows-check-invalid-image(image,5120,-16);domain-user-syscall-hook=installed;
 APP_ADMISSION
 windows-check-refuse(image,0,0,0);
 windows-check-refuse(image,60,127,0);
 windows-check-refuse(image,128,0,0);
 windows-check-refuse(image,132,0x14C,0);
 windows-check-refuse(image,134,10,0);
 windows-check-refuse(image,140,1,1);
 windows-check-refuse(image,148,224,0);
 windows-check-refuse(image,150,0x2023,0);
 windows-check-refuse(image,152,0x10B,0);
 windows-check-refuse(image,168,0x3000,0);
 windows-check-refuse(image,168,0x2000,0);
 windows-check-refuse(image,176,0x100000,1);
 windows-check-refuse(image,176,-4096,1);
 windows-check-refuse(image,184,512,0);
 windows-check-refuse(image,188,4096,0);
 windows-check-refuse(image,208,0x3000,0);
 windows-check-refuse(image,212,1024,0);
 windows-check-refuse(image,220,2,0);
 windows-check-refuse(image,222,0x140,0);
 windows-check-refuse(image,260,15,0);
 windows-check-refuse(image,264,1,1);
 windows-check-refuse(image,272,0,0);
 windows-check-refuse(image,276,20,0);
 windows-check-refuse(image,304,1,1);
 windows-check-refuse(image,400,0,0);
 windows-check-refuse(image,404,0,0);
 windows-check-refuse(image,408,5120,0);
 windows-check-refuse(image,412,0,0);
 windows-check-refuse(image,416,1,1);
 windows-check-refuse(image,428,0xE0000020,0);
 windows-check-refuse(image,440,65537,0);
 windows-check-refuse(image,444,0x1000,0);
 windows-check-refuse(image,448,4096,0);
 windows-check-refuse(image,452,4096,0);
 windows-check-refuse(image,468,0xE0000040,0);
 windows-check-refuse(image,4608,0x3070,0);
 windows-check-refuse(image,4612,1,0);
 windows-check-refuse(image,4620,0,0);
 windows-check-refuse(image,4624,0x1000,0);
 windows-check-refuse(image,4628,1,0);
 windows-check-refuse(image,4672,-1,1);
 windows-check-refuse(image,4672,0x3040,1);
 windows-check-refuse(image,4712,1,1);
 windows-check-refuse(image,4720,0x30B2,1);
 windows-check-refuse(image,4768,0,0);
 windows-check-refuse(image,4784,1,0);
 let bad-authority=cap-mint(root-realm,cap-memory());
 let before-heap=heap-next;let before-free=free-list;let before-domains=domain-count;let before-owned=domain-user-owned;
 if windows-protected-run-granted(image,5120,bad-authority)!=-13 || heap-next!=before-heap || free-list!=before-free || domain-count!=before-domains || domain-user-owned!=before-owned{panic("Windows invalid authority changed state");}
 cap-revoke(bad-authority);
 let authority=cap-mint(root-realm,cap-serial());let caps=cap-count;
 let other=domain-create-user();let other-frame=frame-alloc();store64(other-frame,123456);
 domain-map-user-data(other,0x43000000,other-frame);
 let cycle=0;let heap=0;let free=0;let domains=0;
 while cycle<21{
  let mode=0;
  while mode<24{
   store64(image+4864,mode);
   let status=0;
   if mode==11{status=windows-protected-run(image,5120);}
   else{status=windows-protected-run-granted(image,5120,authority);}
   let expected=42;
   if mode==1 || mode==2 || mode==3 || mode==4 || mode==6 || mode==7 || mode==8 || mode==9{expected=142;}
   if mode==5{expected=141;}
   if mode==19{expected=0x1234002A;}
   if status!=expected{
    serial-write-cstr(port,"windows-protected: failing mode ");serial-write-dec-wide(port,mode);
    serial-write-cstr(port," result ");serial-write-dec-wide(port,status);serial-nl(port);
    panic("Windows protected execution mismatch");
   }
   if domain-current!=0 || windows-protected-count!=0 || windows-protected-busy!=0 || windows-protected-domain!=0 || windows-protected-authority!=-1 || windows-protected-error!=0{panic("Windows process state leaked");}
   let retired=windows-protected-last-domain;
   if load64(domain-table+retired*24)!=0 || load64(domain-table+retired*24+8)!=DOMAIN-FREE{panic("Windows domain leaked");}
   if load64(other-frame)!=123456 || domain-page-flags(other,0x43000000)==0{panic("Windows other process corrupted");}
   if cap-count!=caps || domain-user-syscall-hook!=0{panic("Windows authority leaked");}
   mode=mode+1;
  }
  if cycle==0{heap=heap-next;free=windows-check-free();domains=domain-count;}
  else{if heap!=heap-next || free!=windows-check-free() || domains!=domain-count{panic("Windows repeated resources leaked");}}
  cycle=cycle+1;
 }
 let pic=inb(0x21);let flags=invoke1(load64(0x4198),0);
 let deadline-heap=heap-next;let deadline-free=windows-check-free();let deadline-domains=domain-count;
 store64(image+4864,24);windows-protected-budget=5;
 if windows-protected-run-granted(image,5120,authority)!=124{panic("Windows infinite guest did not time out");}
 windows-protected-budget=100;store64(image+4864,0);
 if windows-protected-run-granted(image,5120,authority)!=42{panic("Windows fresh guest after timeout failed");}
 if inb(0x21)!=pic || ((invoke1(load64(0x4198),0)^flags)&512)!=0 || user-budget-active!=0 || domain-user-syscall-hook!=0{panic("Windows timeout activation state leaked");}
 if heap-next!=deadline-heap || windows-check-free()!=deadline-free || domain-count!=deadline-domains || windows-protected-count!=0 || windows-protected-busy!=0{panic("Windows timeout resources leaked");}
 serial-write-cstr(port,"windows-protected: infinite guest cancelled 124 then fresh guest PASS");serial-nl(port);
 // Same strict image can execute import-free; no binding mutates source bytes.
 store64(image+4864,0);let imports=load64(image+272);store64(image+272,0);
 if windows-protected-run(image,5120)!=42{panic("Windows import-free image failed");}
 store64(image+272,imports);
 if load64(image+4720)!=0x30B0{panic("Windows source IAT modified");}
 if domain-destroy-user(other)!=0{panic("Windows peer teardown failed");}frame-free(other-frame);cap-revoke(authority);
 serial-write-cstr(port,"windows-protected: PE32+ CPL3 RX RW NX BSS imports errors and CPU denials PASS");serial-nl(port);
 serial-write-cstr(port,"windows-protected: 21 cycles 504 executions stable resources PASS");serial-nl(port);
}
'''
app_admission=''
if a.app:
    app_admission='''let jq-heap=heap-next;let jq-free=free-list;let jq-domains=domain-count;let jq-owned=domain-user-owned;
 if windows-protected-run(0x10000000,APP_SIZE)!=-8 || heap-next!=jq-heap || free-list!=jq-free || domain-count!=jq-domains || domain-user-owned!=jq-owned{panic("Original Windows jq refusal changed state");}
 serial-write-cstr(port,"windows-protected: original jq explicitly unsupported, no admission side effects PASS");serial-nl(port);'''.replace('APP_SIZE',str(a.app.stat().st_size))
source=source.replace('APP_ADMISSION',app_admission)
(out/'kernel.in').write_text(source)
commands = [
    ['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],
    ['nasm','-f','bin',str(ROOT/'fixtures/windows-protected/process.asm'),'-o',str(out/'process.exe')],
    [a.compiler,'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')],
]
with (out/'compile.log').open('w') as log:
    for command in commands:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
kernel=(out/'kernel.bin').read_bytes();payload=(out/'process.exe').read_bytes()
assert len(kernel)<=0x1f0000 and len(payload)==5120
(out/'combined.bin').write_bytes(stage_fixture(kernel,payload,0x2f0000))
received=bytearray();serial=None
with (out/'qemu.log').open('w') as qlog:
    path=out/'serial.sock'
    qemu_command=['qemu-system-x86_64','-kernel',str(out/'combined.bin'),'-m','512M','-display','none','-no-reboot','-serial',f'unix:{path},server=on,wait=on']
    if a.app:qemu_command.extend(['-device',f'loader,file={a.app},addr=0x10000000,force-raw=on'])
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
        assert 'windows-protected: PE32+ CPL3 RX RW NX BSS imports errors and CPU denials PASS' in text,text
        assert 'windows-protected: 21 cycles 504 executions stable resources PASS' in text,text
        assert text.splitlines().count('windows-private-write')==21,text
        assert text.splitlines().count('windows-readonly-input')==21,text
        assert 'windows-protected: infinite guest cancelled 124 then fresh guest PASS' in text,text
        assert 'Xwindows' not in text,text
        if a.app:assert 'windows-protected: original jq explicitly unsupported, no admission side effects PASS' in text,text
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
        report={'status':'passed','cycles':21,'executions':507,'fixture_kind':'original bounded PE32+; not unmodified Windows app','imports':['GetStdHandle','WriteFile','GetCurrentProcessId','ExitProcess','GetLastError'],'compiler':a.compiler,'kernel_sha256':hashlib.sha256(kernel).hexdigest(),'payload_sha256':hashlib.sha256(payload).hexdigest()}
        report.update(compiler_sha256=hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),
                      source_sha256={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in [ROOT/'components/windows-protected.in',ROOT/'components/domain.in',ROOT/'boot/multiboot.asm',ROOT/'fixtures/windows-protected/process.asm']})
        if a.app:report['original_windows_jq']={'sha256':app_metadata['sha256'],'admission':'refused with -8 before allocation','executed':False}
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(f'PASS: protected PE32+ CPU denials, imports and repeated cleanup; {out}')
    finally:
        (out/'serial.log').write_bytes(received)
        if serial:serial.close()
        qemu.terminate()
        try:qemu.wait(timeout=3)
        except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
