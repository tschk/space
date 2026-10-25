#!/usr/bin/env python3
"""Run the original upstream Windows fasmg PE32 executable inside Space."""
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
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--app',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--cpu',choices=['qemu64','max'],default='max')
a=p.parse_args();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False);a.app=a.app.resolve()
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
pin=next(x for x in json.loads((ROOT/'fixtures/applications/fasmg.json').read_text())['apps'] if x['personality']=='windows')
assert sha(a.app)==pin['sha256'] and a.app.stat().st_size==pin['size_bytes']
inputs=[ROOT/'boot/multiboot.asm',ROOT/'components/user-context.in',*sorted((ROOT/'components').glob('windows-pe32-*.in')),Path(__file__).resolve(),ROOT/'fixtures/applications/fasmg.json']
hashes={str(path.relative_to(ROOT)):sha(path) for path in inputs}
report=dict(status='running',scope=__doc__,compiler_sha256=sha(a.compiler),application_sha256=sha(a.app),source_sha256=hashes,original_application_entries=0)
received=bytearray();channel=None;qemu=None
try:
 source=(ROOT/'kernel/kernel-root.in').read_text()
 source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(ROOT/m[1])),source)
 source+='\nimport '+json.dumps(str(ROOT/'components/windows-pe32-process.in'))+'\n'
 assert source.count('  shell(port)')==1
 source=source.replace('  shell(port)','  fasmg-windows-check(port)\n  shell(port)')
 source+='''
fn fasmg-windows-free()->Int{let count=0;let p=free-list;while p!=0 && count<32768{count+=1;p=load64(p);}return count;}
fn fasmg-windows-denied(state:Int,image:Int,size:Int,offset:Int,value:Int,expected:Int,serial:Int,storage:Int,memory:Int,timer:Int)->void{
 let before=load32(image+offset);let heap=heap-next;let free=free-list;let domains=domain-count;let caps=cap-count;
 store32(image+offset,value);let line="fasmg";let status=pe32-process-run(state,image,size,line,strlen(line)+1,serial,storage,memory,timer,1000);store32(image+offset,before);
 if status!=expected || heap-next!=heap || free-list!=free || domain-count!=domains || cap-count!=caps{panic("PE32 refused metadata changed resources");}
}
fn fasmg-windows-check(port:Int)->void{
 if heap-next>=0x10000000{panic("Original app source collision");}heap-end=0x10000000;
 let state=alloc(32768);cpu-mem-fill64(state,0,4096);
 let serial=cap-mint(root-realm,cap-serial());let storage=cap-mint(root-realm,cap-storage());let memory=cap-mint(root-realm,cap-memory());let timer=cap-mint(root-realm,cap-timer());
 let image=0x10000000;let size=APP_SIZE;
 let entry=pe32-image-check(image,size);serial-write-cstr(port,"original-win: entry ");serial-write-hex(port,entry);serial-nl(port);
 if entry<0{panic("Original Windows PE32 was not admitted");}
 let line="fasmg";
 serial-write-cstr(port,"original-win: BEGIN help");serial-nl(port);
 let status=pe32-process-run(state,image,size,line,strlen(line)+1,serial,storage,memory,timer,1000);
 serial-write-cstr(port,"original-win: END help status ");serial-write-dec-wide(port,status);serial-nl(port);
 if status!=1{serial-write-cstr(port,"original-win: stopped syscall ");serial-write-hex(port,load64(state+256+112));serial-write-cstr(port," calls ");serial-write-dec-wide(port,load64(state+168));serial-nl(port);panic("Original Windows help failed");}
 let seen=load64(state+176);
 let input="db 'Space',10\nrepeat 4\n dw % * 257\nend repeat\n";
 if fs-write-file("/input.asm",input,strlen(input))!=0{panic("Original Windows source file seed");}
 line="fasmg input.asm output.bin";
 serial-write-cstr(port,"original-win: BEGIN assemble");serial-nl(port);
 status=pe32-process-run(state,image,size,line,strlen(line)+1,serial,storage,memory,timer,1000);
 serial-write-cstr(port,"original-win: END assemble status ");serial-write-dec-wide(port,status);serial-nl(port);
 if status!=0{serial-write-cstr(port,"original-win: stopped syscall ");serial-write-hex(port,load64(state+256+112));serial-write-cstr(port," calls ");serial-write-dec-wide(port,load64(state+168));serial-nl(port);panic("Original Windows assembler failed");}
 seen=seen|load64(state+176);
 let buffer=alloc(4096);if fs-read-file("/output.bin",buffer,4096)!=14{panic("Original Windows generated file length");}
 let expected="Space\n";let i=0;while i<6{if load8(buffer+i)!=load8(expected+i){panic("Original Windows generated text bytes");}i+=1;}
 i=0;while i<4{if load16(buffer+6+i*2)!=(i+1)*257{panic("Original Windows macro arithmetic output");}i+=1;}
 let invalid="this_is_not_an_instruction\n";if fs-write-file("/bad.asm",invalid,strlen(invalid))!=0{panic("Original Windows invalid source seed");}
 let specimen=alloc(size);i=0;while i<size{store8(specimen+i,load8(image+i));i+=1;}
 let pe=load32(specimen+60);let opt=pe+24;let section=opt+224;
 fasmg-windows-denied(state,specimen,size,pe+4,0x38664,-8,serial,storage,memory,timer);
 fasmg-windows-denied(state,specimen,size,opt,0x20b,-8,serial,storage,memory,timer);
 fasmg-windows-denied(state,specimen,size,section+36,0xe0000020,-8,serial,storage,memory,timer);
 fasmg-windows-denied(state,specimen,size,opt+16,load32(specimen+section+40+12),-8,serial,storage,memory,timer);
 let desc=pe32-import-descriptor(specimen,size);let lookup=load32(specimen+desc);if lookup==0{lookup=load32(specimen+desc+16);}
 let lookupoff=pe32-rva(specimen,size,lookup,4);let symbol=load32(specimen+lookupoff);let symboloff=pe32-rva(specimen,size,symbol+2,4);
 fasmg-windows-denied(state,specimen,size,symboloff,0x78787878,-38,serial,storage,memory,timer);
 fasmg-windows-denied(state,specimen,size,lookupoff,0x80000001,-8,serial,storage,memory,timer);
 let heap=heap-next;let free=fasmg-windows-free();let domains=domain-count;let caps=cap-count;let firstfd=vfs-fd-alloc();let entries=2;
 let cycle=0;while cycle<21{
  let mode=0;while mode<3{
   let command="fasmg input.asm output.bin";let expectedstatus=0;
   if mode==1{command="fasmg bad.asm rejected.bin";expectedstatus=2;}if mode==2{command="fasmg missing.asm missing.bin";expectedstatus=2;}
   status=pe32-process-run(state,image,size,command,strlen(command)+1,serial,storage,memory,timer,1000);
   if status!=expectedstatus{serial-write-dec-wide(port,status);panic("Original Windows compiler success/error exit");}
   if load64(state+168)<=0 || load64(state+256+128)!=0x3b{panic("Original Windows activation not observed");}entries+=1;
   seen=seen|load64(state+176);
   if mode==0{
    if fs-read-file("/output.bin",buffer,4096)!=14{panic("Original Windows repeated output size");}
    i=0;while i<6{if load8(buffer+i)!=load8(expected+i){panic("Original Windows repeated text output");}i+=1;}
    i=0;while i<4{if load16(buffer+6+i*2)!=(i+1)*257{panic("Original Windows repeated macro output");}i+=1;}
   }else{
    let path="/rejected.bin";if mode==2{path="/missing.bin";}if fs-stat(path,buffer)>=0{panic("Original Windows failed assembly produced a file");}
   }
   if heap-next!=heap || fasmg-windows-free()!=free || domain-count!=domains || cap-count!=caps || vfs-fd-alloc()!=firstfd || pe32-active!=0 || domain-user-syscall-hook!=0 || user-context-active!=0 || user-budget-active!=0 || user-space-quarantined(memory)!=0{panic("Original Windows repeated activation leaked ownership");}
   mode+=1;
  }cycle+=1;
 }
 serial-write-cstr(port,"original-win: completed original application entries ");serial-write-dec-wide(port,entries);serial-nl(port);
 serial-write-cstr(port,"original-win: observed import mask ");serial-write-hex(port,seen);serial-nl(port);
 cap-revoke(timer);cap-revoke(memory);cap-revoke(storage);cap-revoke(serial);
 serial-write-cstr(port,"original-win: upstream PE32 compiler produced exact 14-byte macro/arithmetic file in Space PASS");serial-nl(port);
}
'''.replace('APP_SIZE',str(pin['size_bytes']))
 (a.out/'kernel.in').write_text(source)
 commands=[['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(a.out/'trampoline.bin')],[str(a.compiler.resolve()),'compile','--path',str(a.out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(a.out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(a.out/'kernel.bin')]];report['commands']=commands
 with (a.out/'compile.log').open('w') as log:
  for command in commands:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
 path=a.out/'serial.sock';command=['qemu-system-x86_64','-kernel',str(a.out/'kernel.bin'),'-m','512M','-cpu',a.cpu,'-display','none','-no-reboot','-serial','unix:'+str(path)+',server=on,wait=on','-device','loader,file='+str(a.app)+',addr=0x10000000,force-raw=on'];report['qemu_command']=command
 with (a.out/'qemu.log').open('w') as log:qemu=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
 deadline=time.monotonic()+10
 while not path.exists() and time.monotonic()<deadline and qemu.poll() is None:time.sleep(.02)
 channel=socket.socket(socket.AF_UNIX);channel.settimeout(.2);channel.connect(str(path));deadline=time.monotonic()+120
 while b'space interactive shell' not in received and time.monotonic()<deadline:
  try:
   data=channel.recv(65536)
   if not data:break
   received+=data
   if (b'PANIC' in received or b'fault handler halting' in received) and received.endswith(b'\n'):break
  except socket.timeout:
   if qemu.poll() is not None:break
 text=received.decode(errors='replace')
 assert 'flat assembler' in text and 'Usage: fasmg source [output]' in text,text
 assert 'original-win: upstream PE32 compiler produced exact 14-byte macro/arithmetic file in Space PASS' in text,text
 assert 'original-win: completed original application entries 65' in text,text
 assert 'space interactive shell' in text,text
 assert sha(a.app)==pin['sha256'] and sha(a.compiler)==report['compiler_sha256'] and all(sha(ROOT/name)==value for name,value in hashes.items())
 mask=int(re.search(r'original-win: observed import mask (?:0x)?([0-9a-f]+)',text)[1],16)
 report.update(status='passed',original_application_entries=65,generated_bytes=14,observed_import_ids=[id for id in range(1,20) if mask&(1<<id)],malformed_controls=6,lifetime_cycles=21,original_error_exits=42,kernel_sha256=sha(a.out/'kernel.bin'))
except Exception as error:report.update(status='failed',error=str(error))
finally:
 if channel is not None:channel.close()
 if qemu is not None:
  qemu.terminate()
  try:qemu.wait(timeout=3)
  except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
 (a.out/'serial.log').write_bytes(received);(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['status'].upper()+': '+str(a.out/'report.json'))
raise SystemExit(0 if report['status']=='passed' else 1)
