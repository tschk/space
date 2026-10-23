#!/usr/bin/env python3
"""Exercise a separate multi-section/high-base protected PE32+ application profile."""
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
source = source.replace('  shell(port)', '  windows-application-check(port)\n  shell(port)')
source += '''
fn windows-application-free()->Int{let n=0;let f=free-list;while f!=0 && n<4096{n=n+1;f=load64(f);}return n;}
fn windows-application-refuse(image:Int,off:Int,value:Int,wide:Int)->void{
 let old=load32(image+off);if wide!=0{old=load64(image+off);}let heap=heap-next;let free=free-list;let domains=domain-count;let owned=domain-user-owned;
 store32(image+off,value);if wide!=0{store64(image+off,value);}let result=windows-application-run(image,5632,-1,-1);
 store32(image+off,old);if wide!=0{store64(image+off,old);}
 if result!=-8 || heap-next!=heap || free-list!=free || domain-count!=domains || domain-user-owned!=owned{serial-write-dec-wide(com1(),off);panic("Windows application malformed image changed state");}
}
fn windows-application-check(port:Int)->void{
 let image=0x280000;
 APP_ADMISSION
 windows-application-refuse(image,134,17,0);
 windows-application-refuse(image,150,0x222E,0);
 windows-application-refuse(image,168,0x2000,0);
 windows-application-refuse(image,176,0x44000000,1);
 windows-application-refuse(image,176,0x800000000000,1);
 windows-application-refuse(image,184,512,0);
 windows-application-refuse(image,208,0x5000,0);
 windows-application-refuse(image,212,1024,0);
 windows-application-refuse(image,222,0x40,0);
 windows-application-refuse(image,288,0x5000,1);
 windows-application-refuse(image,336,0x5000,1);
 windows-application-refuse(image,360,0x1000,0);
 windows-application-refuse(image,364,24,0);
 windows-application-refuse(image,404,0,0);
 windows-application-refuse(image,428,0xE0000020,0);
 windows-application-refuse(image,444,0x1000,0);
 windows-application-refuse(image,468,0xC0000041,0);
 windows-application-refuse(image,480,0x210000,0);
 windows-application-refuse(image,488,0,0);
 windows-application-refuse(image,492,0,0);
 windows-application-refuse(image,4608+64,-1,1);
 windows-application-refuse(image,4608+64,0x3100,1);
 windows-application-refuse(image,4608+96,0x3100,1);
 windows-application-refuse(image,4608+128,0,0);
 windows-application-refuse(image,4608+4,1,0);
 let authority=cap-mint(root-realm,cap-serial());let caps=cap-count;
 let other=domain-create-user();let peer=frame-alloc();store64(peer,123456);domain-map-user-data(other,0x43000000,peer);
 let cycle=0;let heap=0;let free=0;let domains=0;
 while cycle<21{
  let mode=0;while mode<15{
   store64(image+5120,mode);if mode==12{windows-protected-budget=5;}
   let status=windows-application-run(image,5632,authority,-1);windows-protected-budget=100;
   let expected=42;if mode>=1 && mode<=7{expected=142;}if mode==8{expected=141;}if mode==11{expected=0x1234002A;}if mode==12{expected=124;}
   if status!=expected{serial-write-cstr(port,"windows-application: failed mode ");serial-write-dec-wide(port,mode);serial-write-cstr(port," result ");serial-write-dec-wide(port,status);serial-nl(port);panic("Windows application execution mismatch");}
   if windows-protected-count!=0 || windows-protected-busy!=0 || domain-current!=0 || user-budget-active!=0 || domain-user-syscall-hook!=0 || cap-count!=caps || load64(peer)!=123456{panic("Windows application activation leaked");}
   mode=mode+1;
  }
  if cycle==0{heap=heap-next;free=windows-application-free();domains=domain-count;}
  else{if heap-next!=heap || windows-application-free()!=free || domain-count!=domains{panic("Windows application repeated cleanup leak");}}
  cycle=cycle+1;
 }
 // A pure BSS section is a separately exercised mapping, with no raw bytes.
 let old-raw=load64(image+488);let old-flags=load32(image+508);store64(image+488,0);store32(image+508,0xC0000080);
 if windows-application-run(image,5120,authority,-1)!=42{panic("Windows application pure BSS failed");}
 store64(image+488,old-raw);store32(image+508,old-flags);
 store64(image+5120,0);let imp=load64(image+272);let iat=load64(image+360);store64(image+272,0);store64(image+360,0);
 if windows-application-run(image,5632,authority,-1)!=42{panic("Windows application import-free failed");}
 store64(image+272,imp);store64(image+360,iat);
 if load64(image+4608+96)!=0x30A0{panic("Windows application source IAT changed");}
 if domain-destroy-user(other)!=0{panic("Windows application peer cleanup");}frame-free(peer);cap-revoke(authority);
 serial-write-cstr(port,"windows-application: high64 preferred base RX RO RW BSS arbitrary import subset and IAT binding PASS");serial-nl(port);
 serial-write-cstr(port,"windows-application: 317 executions CPU denials budget and stable cleanup PASS");serial-nl(port);
}
'''
app_admission=''
if a.app:
    app_admission='''let structural=windows-application-structure-entry(0x10000000,APP_SIZE);
 if structural!=0x140001400{panic("Original Windows jq structural profile mismatch");}
 serial-write-cstr(port,"windows-application: original jq section layout admitted, runtime directories refused PASS");serial-nl(port);
 let jq-heap=heap-next;let jq-free=free-list;let jq-domains=domain-count;let jq-owned=domain-user-owned;
 if windows-application-run(0x10000000,APP_SIZE,-1,-1)!=-8 || heap-next!=jq-heap || free-list!=jq-free || domain-count!=jq-domains || domain-user-owned!=jq-owned{panic("Original Windows jq refusal changed state");}
 serial-write-cstr(port,"windows-protected: original jq explicitly unsupported, no admission side effects PASS");serial-nl(port);'''.replace('APP_SIZE',str(a.app.stat().st_size))
source=source.replace('APP_ADMISSION',app_admission)
(out/'kernel.in').write_text(source)
commands = [
    ['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],
    ['nasm','-f','bin',str(ROOT/'fixtures/windows-protected/application.asm'),'-o',str(out/'process.exe')],
    [a.compiler,'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')],
]
with (out/'compile.log').open('w') as log:
    for command in commands:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
kernel=(out/'kernel.bin').read_bytes();payload=(out/'process.exe').read_bytes()
assert len(kernel)<=0x180000 and len(payload)==5632
(out/'combined.bin').write_bytes(kernel+bytes(0x180000-len(kernel))+payload)
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
        assert 'windows-application: high64 preferred base RX RO RW BSS arbitrary import subset and IAT binding PASS' in text,text
        assert 'windows-application: 317 executions CPU denials budget and stable cleanup PASS' in text,text
        assert text.splitlines().count('windows-multisection')==21,text
        if a.app:
            assert 'windows-protected: original jq explicitly unsupported, no admission side effects PASS' in text,text
            assert 'windows-application: original jq section layout admitted, runtime directories refused PASS' in text,text
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
        report={'status':'passed','cycles':21,'executions':317,'fixture_kind':'original bounded PE32+; not unmodified Windows app','imports':['GetCurrentProcessId','WriteFile','ExitProcess'],'compiler':a.compiler,'kernel_sha256':hashlib.sha256(kernel).hexdigest(),'payload_sha256':hashlib.sha256(payload).hexdigest()}
        report.update(compiler_sha256=hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),
                      source_sha256={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in [ROOT/'components/windows-protected.in',ROOT/'components/windows-pe-application.in',ROOT/'components/domain.in',ROOT/'boot/multiboot.asm',ROOT/'fixtures/windows-protected/application.asm']})
        if a.app:report['original_windows_jq']={'sha256':app_metadata['sha256'],'admission':'refused with -8 before allocation','executed':False,'structure_entry':'0x140001400','section_layout_validated':True}
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(f'PASS: protected multi-section PE32+ high base, RO data, import subsets and cleanup; {out}')
    finally:
        (out/'serial.log').write_bytes(received)
        if serial:serial.close()
        qemu.terminate()
        try:qemu.wait(timeout=3)
        except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
