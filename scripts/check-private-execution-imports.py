#!/usr/bin/env python3
"""Prove compiled private execution symbols cannot become raw SCI imports."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import time
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--in',dest='compiler',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
paths=[x for directory in ['components','kernel','protocol','services'] for x in (ROOT/directory).rglob('*.in')]+[ROOT/'boot/multiboot.asm',Path(__file__).resolve()]
contents={str(x.relative_to(ROOT)):x.read_bytes() for x in paths};snapshot=out/'source'
for name,data in contents.items():target=snapshot/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report={'status':'running','scope':__doc__,'original_application_entries':0,'compiler_sha256':sha(a.compiler),'source_sha256':{n:hashlib.sha256(d).hexdigest() for n,d in contents.items()}}
private=['execution-clock-await-interrupt','linux-process-run-vector-input','linux-process-clock-gettime','supervisor-window-init','pe32-process-run','dc-process-run']
process=None;channel=None;received=bytearray()
try:
 artifacts=[]
 for i,name in enumerate(private):
  src=out/f'private-{i}.in';binary=out/f'private-{i}.sci'
  src.write_text('package space.fixture\ninterrupt fn '+name+'(arg:Int)->Int{}\nfn private-entry(info:Int)->Int{store64(0x13000000,42);return '+name+'(info);}\n')
  with (out/f'private-{i}.compile.log').open('w') as log:subprocess.run([str(a.compiler),'compile','--path',str(src),'--entry','private-entry','--emit','sci','--base','0x7a000000','--target','native','--target-triple','x86_64-unknown-none','--out',str(binary)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
  assert 0<binary.stat().st_size<=8192,'private SCI exceeds fixed8-KiB fixture window'
  artifacts.append({'name':name,'path':str(binary),'sha256':sha(binary),'size':binary.stat().st_size})
 source=(snapshot/'kernel/kernel-root.in').read_text();source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(snapshot/m[1])),source)
 for dependency in ['linux-process.in','windows-pe32-process.in','darwin-classic-process.in']:source+='\nimport '+json.dumps(str(snapshot/'components'/dependency))+'\n'
 assert source.count('  shell(port)')==1;source=source.replace('  shell(port)','  private-execution-check(port)\n  shell(port)')
 source+='''
fn private-execution-symbol(name:Int)->Int{
 let table=load64(KERNEL-HEADER+40);if table==0{return 0;}let i=0;while i<load64(table){let r=table+8+i*16;if dyn-str-eq(table+load64(r),name)!=0{return 1;}i+=1;}return 0;
}
fn private-execution-check(port:Int)->void{
 if heap-next>=0x10000000{panic("Private fixture source collision");}heap-end=0x10000000;
 let table=alloc(48);let prior=load64(0x40d0);store64(table,BOOT-IMAGE-TABLE-MAGIC);store64(table+8,1);store64(table+16,254);store64(table+40,0);
'''
 for i,item in enumerate(artifacts):
  name=json.dumps(item['name']);size=item['size'];address=0x10000000+i*8192
  source+='''{
 if private-execution-symbol(NAME)!=1{panic("Private symbol not actually compiled");}
 if dyn-kernel-exportable(NAME)!=0 || dyn-resolve-idx(NAME)!=-1{panic("Private execution export escaped");}
 let i=0;while i<SIZE{store8(0x2fe000+i,load8(ADDRESS+i));i+=1;}
 if load64(0x2fe000)!=SCI-MAGIC-V2 || load64(0x2fe000+24)!=SIZE{panic("Private fixture image staging");}
 store64(table+24,0x2fe000);store64(table+32,SIZE);store64(0x40d0,table);store64(0x13000000,0);
 let heap=heap-next;let free=free-list;let caps=cap-count;let domains=domain-count;let live=runtime-instance-live;let objects=obj-arena-next;let exports=dyn-count;
 if sci-load-runtime-component(port,0x2fe000,"private-execution",1,1,0)!=-1{panic("Private execution SCI entered");}
 if heap-next!=heap || free-list!=free || cap-count!=caps || domain-count!=domains || runtime-instance-live!=live || obj-arena-next!=objects || dyn-count!=exports || load64(0x13000000)!=0{panic("Private execution refusal mutated resources");}
 i=0;while i<SIZE{if load8(0x2fe000+i)!=load8(ADDRESS+i){panic("Private refusal modified original artifact");}i+=1;}
 store64(0x40d0,prior);
}
'''.replace('NAME',name).replace('SIZE',str(size)).replace('ADDRESS',str(address))
 source+='serial-write-cstr(port,"private-execution: six compiled symbols and actual SCI preentry refusals with stable resources PASS");serial-nl(port);}\n'
 (out/'kernel.in').write_text(source)
 with (out/'compile.log').open('w') as log:
  subprocess.run(['nasm','-f','bin',str(snapshot/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],stdout=log,stderr=subprocess.STDOUT,check=True)
  subprocess.run([str(a.compiler),'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
 assert (out/'kernel.bin').stat().st_size+0x100000<=0x2fe000,'kernel overlaps reserved fixture page'
 command=['qemu-system-x86_64','-cpu','max','-kernel',str(out/'kernel.bin'),'-m','512M','-display','none','-no-reboot','-serial','unix:'+str(out/'serial.sock')+',server=on,wait=on']
 for i,item in enumerate(artifacts):command+=['-device',f'loader,file={item["path"]},addr={0x10000000+i*8192:#x},force-raw=on']
 report.update(artifacts=artifacts,qemu_command=command,kernel_sha256=sha(out/'kernel.bin'))
 with (out/'qemu.log').open('w') as log:process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
 deadline=time.monotonic()+10
 while not (out/'serial.sock').exists() and time.monotonic()<deadline:time.sleep(.02)
 channel=socket.socket(socket.AF_UNIX);channel.settimeout(.2);channel.connect(str(out/'serial.sock'));deadline=time.monotonic()+90
 while b'space interactive shell' not in received and time.monotonic()<deadline:
  try:
   block=channel.recv(65536)
   if not block:break
   received+=block;(out/'serial.log').write_bytes(received)
   if b'PANIC' in received and received.endswith(b'\n'):break
  except socket.timeout:
   if process.poll() is not None:break
 text=received.decode(errors='replace')
 assert 'private-execution: six compiled symbols and actual SCI preentry refusals with stable resources PASS' in text,text
 for name in private:assert 'SCI: DENIED unresolved import '+name in text,text
 assert all((ROOT/name).read_bytes()==data for name,data in contents.items()) and sha(a.compiler)==report['compiler_sha256']
 report.update(status='passed',actual_sci_refusals=6,compiled_private_symbols_checked=6)
except Exception as error:report.update(status='failed',error=str(error))
finally:
 if channel:channel.close()
 if process:
  process.terminate()
  try:process.wait(timeout=3)
  except subprocess.TimeoutExpired:process.kill();process.wait()
 (out/'serial.log').write_bytes(received);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['status'].upper()+': '+str(out/'report.json'));raise SystemExit(0 if report['status']=='passed' else 1)
