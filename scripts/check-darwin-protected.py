#!/usr/bin/env python3
"""Boot private Mach-O fixtures at CPL3 and test CPU denial and reclamation."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import time

root = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--app', type=Path, help='Also check allocation-free refusal of pinned original macOS jq')
p.add_argument('--imports', action='store_true', help='also exercise bounded classic dyld _write/_exit imports')
a = p.parse_args()
out = a.out.resolve()
if out.exists() and any(out.iterdir()):
    p.error('--out must be new or empty')
out.mkdir(parents=True, exist_ok=True)
tracked_sources=sorted(set(root.glob('components/*.in')) | set(root.glob('boot/*.asm')) | set(root.glob('kernel/*.in')) | set((root/'fixtures/darwin-protected').glob('*.asm')))
source_hashes={str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in tracked_sources}
app_metadata=None
if a.app:
    a.app=a.app.resolve()
    app_metadata=next(row for row in json.loads((root/'fixtures/applications/jq-1.8.1.json').read_text())['apps'] if row['personality']=='darwin')
    assert hashlib.sha256(a.app.read_bytes()).hexdigest()==app_metadata['sha256'], 'original macOS jq checksum mismatch'
source = (root/'kernel/kernel-root.in').read_text()
source = re.sub(r'import "\.\./([^"]+)"', lambda m: 'import '+json.dumps(str(root/m.group(1))), source)
source='import '+json.dumps(str(root/'components/darwin-protected.in'))+'\n'+source
assert source.count('  shell(port)') == 1
source = source.replace('  shell(port)', '  protected-process-check(port)\n  shell(port)')
source += '''
fn protected-refuse(image:Int,size:Int,offset:Int,value:Int,wide:Int)->void{
 let saved=load32(image+offset);if wide!=0{saved=load64(image+offset);}
 let heap=heap-next;let free=free-list;let domains=domain-count;let owned=domain-user-owned;
 store32(image+offset,value);if wide!=0{store64(image+offset,value);}
 let result=darwin-protected-run(image,size);
 store32(image+offset,saved);if wide!=0{store64(image+offset,saved);}
 if result!=-8 || heap-next!=heap || free-list!=free || domain-count!=domains || domain-user-owned!=owned{panic("protected malformed image changed state");}
}
fn protected-free-frames()->Int{
 let n=0;let frame=free-list;
 while frame!=0 && n<1024{n=n+1;frame=load64(frame);}
 return n;
}
fn protected-process-check(port:Int)->void{
 let image=0x10000000;let size=8192;
 if heap-next+0x100000>=image{panic("protected fixture overlaps allocation reserve");}
 let other=domain-create-user();let other-frame=frame-alloc();
 store64(other-frame,123456);domain-map-user-data(other,0x43000000,other-frame);
 let before=heap-next;let before-domains=domain-count;let before-free=free-list;let before-owned=domain-user-owned;
 let saved=load64(image+16);store64(image+16,0);
 if darwin-protected-run(image,size)!=-8{panic("protected malformed accepted");}
 store64(image+16,saved);
 if heap-next!=before || domain-count!=before-domains{panic("protected refusal allocated");}
 let saved-va=load64(image+128);store64(image+128,0x41000000);
 if darwin-protected-run(image,size)!=-8{panic("protected overlap accepted");}
 store64(image+128,saved-va);
 let saved-size=load64(image+136);store64(image+136,-4096);
 if darwin-protected-run(image,size)!=-8{panic("protected overflow accepted");}
 store64(image+136,saved-size);
 let saved-prot=load64(image+160);store64(image+160,0x700000007);
 if darwin-protected-run(image,size)!=-8{panic("protected RWX accepted");}
 store64(image+160,saved-prot);
 if heap-next!=before || domain-count!=before-domains || free-list!=before-free || domain-user-owned!=before-owned{panic("protected refusal changed state");}
 protected-refuse(image,size,0,0,0);
 protected-refuse(image,size,4,16777228,0);
 protected-refuse(image,size,8,0,0);
 protected-refuse(image,size,12,6,0);
 protected-refuse(image,size,16,2,0);
 protected-refuse(image,size,20,200,0);
 protected-refuse(image,size,24,2097153,0);
 protected-refuse(image,size,28,1,0);
 protected-refuse(image,size,32,0,0);
 protected-refuse(image,size,36,64,0);
 protected-refuse(image,size,56,1048576,1);
 protected-refuse(image,size,64,0,1);
 protected-refuse(image,size,72,4096,1);
 protected-refuse(image,size,80,199,1);
 protected-refuse(image,size,88,7,0);
 protected-refuse(image,size,92,7,0);
 protected-refuse(image,size,96,1,0);
 protected-refuse(image,size,100,1,0);
 protected-refuse(image,size,128,1090519040,1);
 protected-refuse(image,size,136,-4096,1);
 protected-refuse(image,size,144,8193,1);
 protected-refuse(image,size,152,4097,1);
 protected-refuse(image,size,160,7,0);
 protected-refuse(image,size,164,7,0);
 protected-refuse(image,size,168,1,0);
 protected-refuse(image,size,176,0,0);
 protected-refuse(image,size,180,16,0);
 protected-refuse(image,size,184,0,1);
 protected-refuse(image,size,184,4096,1);
 protected-refuse(image,size,192,1,1);

 if domain-destroy-user(0)!=-1{panic("protected kernel tree teardown accepted");}
 let other-root=load64(domain-table+other*24);let other-pdpt=load64(other-root)&PAGE-ADDRESS-MASK;
 let other-pd=load64(other-pdpt)&PAGE-ADDRESS-MASK;let old-pde=load64(other-pd);
 store64(other-pd,131);let control-free=free-list;
 if domain-destroy-user(other)!=-1 || free-list!=control-free || load64(domain-table+other*24)!=other-root{panic("protected huge-page teardown changed state");}
 store64(other-pd,old-pde);
 domain-current=other;
 if domain-destroy-user(other)!=-1{panic("protected active tree teardown accepted");}
 domain-current=0;
 let authority=cap-mint(root-realm,cap-serial());let stable-caps=cap-count;
 let cycle=0;let stable-heap=0;let stable-free=0;let stable-domains=0;
 while cycle<21{
  let mode=0;
  while mode<=19{
   if mode!=8{
    store64(image+4096,mode);
    let result=0;
    if mode>=12{result=darwin-protected-run-granted(image,size,authority);}
    else{result=darwin-protected-run(image,size);}
    let expected=42;
    if mode==1 || mode==2 || mode==3 || mode==4 || mode==7 || mode==11{expected=142;}
    if mode==5{expected=141;}
    if mode==9{expected=42;}
    if result!=expected{
      serial-write-cstr(port,"protected: failing mode ");serial-write-dec-wide(port,mode);
      serial-write-cstr(port," result ");serial-write-dec-wide(port,result);serial-nl(port);
      panic("protected execution mismatch");
    }
    if load64(other-frame)!=123456 || domain-page-flags(other,0x43000000)==0{panic("protected other domain corrupted");}
    let retired=darwin-protected-last-domain;
    if domain-current!=0 || darwin-protected-count!=0 || darwin-protected-busy!=0{panic("protected live state leaked");}
    if load64(domain-table+retired*24)!=0 || load64(domain-table+retired*24+8)!=DOMAIN-FREE{panic("protected domain leaked");}
   }
   mode=mode+1;
  }
  if cap-count!=stable-caps || domain-user-syscall-hook!=0{panic("protected authority leaked");}
  if cycle==0{stable-heap=heap-next;stable-free=protected-free-frames();stable-domains=domain-count;}
  else{if heap-next!=stable-heap || protected-free-frames()!=stable-free || domain-count!=stable-domains{panic("protected repeated resources leaked");}}
  cycle=cycle+1;
 }
 cap-revoke(authority);
 if domain-destroy-user(other)!=0{panic("protected other domain teardown");}
 frame-free(other-frame);
 serial-write-cstr(port,"protected: private Mach-O RX/RW BSS CPL3 IOPL0 denial and cleanup PASS");serial-nl(port);
 serial-write-cstr(port,"protected: 21 cycles, 399 executions, stable frames and domain slots PASS");serial-nl(port);
}
'''
if a.imports:
    source=source.replace('mode<=19', 'mode<=23').replace('if mode>=12{', 'if mode==23{result=darwin-protected-run-budgeted(image,size,authority,10);}else if mode>=12 && mode!=22{').replace('let expected=42;', 'let expected=42;if mode==23{expected=124;}').replace('399 executions', '483 executions')
    refusals='''
 protected-refuse(image,size,204,40,0);
 protected-refuse(image,size,208,1,0);
 protected-refuse(image,size,216,8193,0);
 protected-refuse(image,size,220,0,0);
 protected-refuse(image,size,220,129,0);
 protected-refuse(image,size,256,25,0);
 protected-refuse(image,size,260,1,0);
 protected-refuse(image,size,272,0,0);
 let program=load32(image+216);
 protected-refuse(image,size,program,18,0);
 protected-refuse(image,size,program+2,1684103775,0);
 protected-refuse(image,size,program+9,82,0);
 protected-refuse(image,size,program+11,24,0);
 protected-refuse(image,size,program+21,32,0);
 protected-refuse(image,size,program+23,144,0);
'''
    source=source.replace(' if domain-destroy-user(0)', refusals+'\n if domain-destroy-user(0)')
if a.app:
    refusal=f'''let admission-heap=heap-next;let admission-free=free-list;let admission-domains=domain-count;
 if darwin-protected-run(0x10200000,{a.app.stat().st_size})!=-8{{panic("unsupported original macOS jq admitted");}}
 if heap-next!=admission-heap || free-list!=admission-free || domain-count!=admission-domains{{panic("original macOS jq refusal allocated");}}
 '''
    source=source.replace('let image=0x10000000;',refusal+'let image=0x10000000;')
(out/'kernel.in').write_text(source)
with (out/'compile.log').open('w') as log:
    for command in [
        ['nasm','-f','bin',str(root/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],
        ['nasm','-f','bin',str(root/'fixtures/darwin-protected'/('process-imports.asm' if a.imports else 'process.asm')),'-o',str(out/'process.macho')],
        [a.compiler,'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')],
    ]:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180,cwd=root)
kernel=(out/'kernel.bin').read_bytes();payload=(out/'process.macho').read_bytes()
# Multiboot loads at 1 MiB; the fixture is a separate QEMU loader region.
# Keep explicit non-overlap even when the compiler relocates boot data.
assert len(kernel)<0x0FF00000 and len(payload)==8192
received=bytearray();serial=None
with (out/'qemu.log').open('w') as qlog:
    path=out/'serial.sock'
    qemu_args=['qemu-system-x86_64','-kernel',str(out/'kernel.bin'),'-device',f'loader,file={out / "process.macho"},addr=0x10000000,force-raw=on','-m','512M','-display','none','-no-reboot','-serial',f'unix:{path},server=on,wait=on']
    if a.app:qemu_args += ['-device',f'loader,file={a.app},addr=0x10200000,force-raw=on']
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
                if b'nanokernel fault handler halting' in received or b'PANIC' in received:break
            except socket.timeout:
                if qemu.poll() is not None:break
        text=received.decode(errors='replace')
        assert 'protected: private Mach-O RX/RW BSS CPL3 IOPL0 denial and cleanup PASS' in text,text
        executions=483 if a.imports else 399
        assert f'protected: 21 cycles, {executions} executions, stable frames and domain slots PASS' in text,text
        assert text.count('darwin-import-write\n')==(21 if a.imports else 0),text
        assert text.count('darwin-private-write\n')==21,text
        assert '^' not in text,text
        assert 'space interactive shell' in text,text
        serial.sendall(b'halt\n')
        report={'status':'passed','executions':executions,'imports':a.imports,'original_macos_jq':{'sha256':app_metadata['sha256'],'status':'refused','executed':False} if app_metadata else None,'cycles':21,'compiler':a.compiler,'compiler_sha256':hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),'source_sha256':source_hashes,'source_changed_during_run':[str(path.relative_to(root)) for path in tracked_sources if hashlib.sha256(path.read_bytes()).hexdigest()!=source_hashes[str(path.relative_to(root))]],'kernel_sha256':hashlib.sha256(kernel).hexdigest(),'payload_sha256':hashlib.sha256(payload).hexdigest()}
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(f'PASS: protected Mach-O execution, hardware denial and repeated cleanup; {out}')
    finally:
        (out/'serial.log').write_bytes(received)
        if serial:serial.close()
        qemu.terminate()
        try:qemu.wait(timeout=3)
        except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
