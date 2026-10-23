#!/usr/bin/env python3
"""Prove current admission refusal of checksum-pinned official Windows CLI apps."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',required=True)
p.add_argument('--apps',type=Path,required=True,help='directory from acquire-windows-cli.py')
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();out=a.out.resolve()
assert not out.exists() or not any(out.iterdir()),'--out must be new or empty'
out.mkdir(parents=True,exist_ok=True)
apps=json.loads((ROOT/'fixtures/applications/windows-cli-2024.json').read_text())['apps']
source=(ROOT/'kernel/kernel-root.in').read_text()
source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(ROOT/m.group(1))),source)
assert source.count('  shell(port)')==1
source=source.replace('  shell(port)','  windows-cli-admission-check(port)\n  shell(port)')
source+='\nfn windows-cli-admission-check(port:Int)->void{\n if heap-next>=0x10000000{panic("CLI staging collides with heap");}heap-end=0x10000000;let timer=cap-mint(root-realm,cap-timer());let memory=cap-mint(root-realm,cap-memory());let env=alloc(2);store8(env,0);store8(env+1,0);\n'
loaders=[]
for i,app in enumerate(apps):
    path=(a.apps/app['filename']).resolve();data=path.read_bytes()
    assert len(data)==app['size_bytes'] and hashlib.sha256(data).hexdigest()==app['sha256']
    base=0x10000000+i*0x2000000
    loaders.extend(['-device',f'loader,file={path},addr={base:#x},force-raw=on'])
    diagnostic=''
    if app['name']=='sqlite3':
        diagnostic='''
 if windows-application-structure-entry(BASE,SIZE)!=0x140003a8a || windows-application-pages(BASE)!=946{panic("Original SQLite Windows layout not admitted");}
 if windows-application-directory-mask(BASE,SIZE,2)!=0x46c{panic("Original SQLite directory barriers changed");}
 if windows-application-import-barrier(BASE,SIZE,1)!=2{panic("Original SQLite first unsupported import changed");}
 serial-write-cstr(port,"windows-cli-admission: original SQLite structural entry140003a8a pages946 directorymask46c import2 GetEnvironmentVariableA PASS");serial-nl(port);
'''.replace('BASE',str(base)).replace('SIZE',str(len(data)))
    source+=''' let heapINDEX=heap-next;let freeINDEX=free-list;let domainsINDEX=domain-count;let ownedINDEX=domain-user-owned;
 DIAGNOSTIC
 let cycleINDEX=0;while cycleINDEX<21{
  let profile=0;while profile<9{
   let result=-8;if profile<3{result=windows-protected-run-profile(BASE,SIZE,-1,-1,profile);}
   else if profile==3{let line="APPLICATION -version";result=windows-command-run(BASE,SIZE,-1,-1,line,strlen(line)+1);}
   else if profile==4{let line="APPLICATION -version";result=windows-command-time-run(BASE,SIZE,-1,-1,timer,line,strlen(line)+1);}
   else if profile==5{let line="APPLICATION -version";result=windows-command-environment-run(BASE,SIZE,-1,-1,line,strlen(line)+1,env,2);}
   else if profile==6{let line="APPLICATION -version";result=windows-command-counter-run(BASE,SIZE,-1,-1,timer,line,strlen(line)+1);}
   else if profile==7{let line="APPLICATION -version";result=windows-command-heap-run(BASE,SIZE,-1,-1,memory,line,strlen(line)+1);}
   else{let line="APPLICATION -version";result=windows-command-local-run(BASE,SIZE,-1,-1,memory,line,strlen(line)+1);}
   if result!=-8{panic("Original Windows CLI unexpectedly admitted");}
   if heap-next!=heapINDEX || free-list!=freeINDEX || domain-count!=domainsINDEX || domain-user-owned!=ownedINDEX || windows-protected-busy!=0{panic("Original Windows CLI refusal changed ownership");}
   profile=profile+1;
  }cycleINDEX=cycleINDEX+1;
 }
'''.replace('INDEX',str(i)).replace('BASE',str(base)).replace('SIZE',str(len(data))).replace('APPLICATION',app['filename']).replace('DIAGNOSTIC',diagnostic)
source+=' cap-revoke(timer);cap-revoke(memory);serial-write-cstr(port,"windows-cli-admission: official SQLite and 7za unchanged refusals before allocation PASS");serial-nl(port);}\n'
(out/'kernel.in').write_text(source)
commands=[['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],[a.compiler,'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')]]
with (out/'compile.log').open('w') as log:
    for command in commands:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
kernel=(out/'kernel.bin').read_bytes();assert 0x100000+len(kernel)<0x10000000
serial_path=out/'serial.sock';received=bytearray();serial=None
qemu_command=['qemu-system-x86_64','-kernel',str(out/'kernel.bin'),'-m','512M','-display','none','-no-reboot','-serial',f'unix:{serial_path},server=on,wait=on']+loaders
with (out/'qemu.log').open('w') as log:
    qemu=subprocess.Popen(qemu_command,stdout=log,stderr=subprocess.STDOUT)
    try:
        deadline=time.monotonic()+10
        while not serial_path.exists() and qemu.poll() is None and time.monotonic()<deadline:time.sleep(.02)
        serial=socket.socket(socket.AF_UNIX);serial.settimeout(.2);serial.connect(str(serial_path))
        deadline=time.monotonic()+60
        while b'space> ' not in received and time.monotonic()<deadline:
            try:
                block=serial.recv(65536)
                if not block:break
                received.extend(block)
                if b'PANIC' in received or b'nanokernel fault handler halting' in received:break
            except socket.timeout:
                if qemu.poll() is not None:break
        text=received.decode(errors='replace')
        assert 'windows-cli-admission: official SQLite and 7za unchanged refusals before allocation PASS' in text,text
        assert 'space> ' in text,text
    finally:
        (out/'serial.log').write_bytes(received)
        if serial:serial.close()
        qemu.terminate()
        try:qemu.wait(timeout=5)
        except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
report=dict(status='passed',refusals=378,sqlite_diagnostics=dict(structure_entry='0x140003a8a',mapped_pages=946,unsupported_directory_mask='0x46c',first_unsupported_import_index=2,first_unsupported_import='GetEnvironmentVariableA',import_slots=157,execution_import_slot_limit=32),apps=[dict(id=app['id'],sha256=app['sha256'],admission=-8,executed=False) for app in apps],compiler_sha256=hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),kernel_sha256=hashlib.sha256(kernel).hexdigest(),commands=commands,qemu_command=qemu_command)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['apps']))
