#!/usr/bin/env python3
"""Actual native UTC file metadata, coherent RTC refusal and immutable snapshots."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();out=a.out.resolve();compiler=a.compiler.resolve()
assert not out.exists() or not any(out.iterdir());out.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=[p for directory in ['components','kernel','protocol','services','fixtures/native-utc-metadata'] for p in (ROOT/directory).rglob('*.in')]+[ROOT/'boot/multiboot.asm',Path(__file__).resolve()]
contents={str(p.relative_to(ROOT)):p.read_bytes() for p in files};assert all(p.read_bytes()==contents[str(p.relative_to(ROOT))] for p in files)
snapshot=out/'source'
for name,data in contents.items():
 target=snapshot/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
inventory={name:hashlib.sha256(data).hexdigest() for name,data in contents.items()};(out/'source-hashes.json').write_text(json.dumps(inventory,indent=2)+'\n')
report=dict(status='running',goal_status='OPEN',classification='Private native UTC filesystem prototype; no Windows Find API/original Windows execution',source_sha256=inventory,compiler_sha256=sha(compiler))
try:
 private=out/'private.in';private.write_text('package space.fixture\ninterrupt fn fs-metadata-format-utc(total:Int,count:Int,storage:Int,timer:Int)->Int{}\nfn private-entry(info:Int)->Int{return fs-metadata-format-utc(256,256,info,info); }\n')
 with (out/'private.log').open('w') as log:subprocess.run([str(compiler),'compile','--path',str(private),'--entry','private-entry','--emit','sci','--base','0x7a000000','--target','native','--target-triple','x86_64-unknown-none','--out',str(out/'private.sci')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
 private_size=(out/'private.sci').stat().st_size;assert 0<private_size<=65536
 source=(snapshot/'kernel/kernel-root.in').read_text();source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(snapshot/m[1])),source)
 source='const FUM-PRIVATE-SIZE = '+str(private_size)+'\nimport '+json.dumps(str(snapshot/'fixtures/native-utc-metadata/checks.in'))+'\n'+source
 assert source.count('  shell(port)')==1;source=source.replace('  shell(port)','  native-utc-check(port)\n  shell(port)');(out/'kernel.in').write_text(source)
 with (out/'compile.log').open('w') as log:
  subprocess.run(['nasm','-f','bin',str(snapshot/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=30)
  subprocess.run([str(compiler),'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
 metadata=json.loads((out/'kernel.component-metadata.json').read_text());assert metadata['boot_layout']['load_end']<=0x2f0000
 command=['qemu-system-x86_64','-kernel',str(out/'kernel.bin'),'-m','512M','-cpu','max','-vga','std','-display','none','-no-reboot','-rtc','base=2026-10-24T00:00:00,clock=vm','-serial','stdio','-monitor','none','-device',f'loader,file={out}/private.sci,addr=0x2f0000,force-raw=on']
 report.update(qemu_command=command,kernel_sha256=sha(out/'kernel.bin'))
 # The guest returns to shell; preserve its completed serial before killing only
 # this owned QEMU process at a bounded external timeout.
 try:result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=15);serial=result.stdout
 except subprocess.TimeoutExpired as error:serial=error.stdout or b''
 (out/'serial.log').write_bytes(serial)
 assert b'PANIC' not in serial,serial[-2000:]
 assert b'DENIED unresolved import fs-metadata-format-utc' in serial
 report['private_sci_sha256']=sha(out/'private.sci')
 assert b'native-utc: UTC creation/access/modification, clock denial and21 stable observations PASS\n' in serial and b'space> ' in serial,serial[-2000:]
 match=re.search(rb'native-utc: record ([0-9a-f]{256})\n',serial);assert match
 record=bytes.fromhex(match[1].decode());(out/'record.bin').write_bytes(record)
 magic,mount,count,width=struct.unpack_from('<4Q',record);assert magic==0x5346444952530002 and mount>0 and count==1 and width==96
 kind,inode,size,length=struct.unpack_from('<4Q',record,32);assert kind==1 and inode>0 and size==3 and length==4 and record[64:69]==b'file\0' and record[69:96]==bytes(27)
 created,accessed,modified,mode=struct.unpack_from('<4Q',record,96);base=int(datetime(2026,10,24,tzinfo=timezone.utc).timestamp());assert base<=created<=base+60 and created<=accessed<=base+60 and created<modified<=base+60 and mode==0o644
 assert all((ROOT/name).read_bytes()==data for name,data in contents.items()),'source changed'
 assert sha(compiler)==report['compiler_sha256']
 report.update(status='passed',observations=22,measured_resource_cycles=21,creation_utc_seconds=created,access_utc_seconds=accessed,modification_utc_seconds=modified,record_sha256=sha(out/'record.bin'))
 print('PASS native UTC metadata: real coherent RTC, clock/grant refusal, exact directory record,21 stable observations')
except Exception as error:report.update(status='failed',error=str(error));raise
finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
