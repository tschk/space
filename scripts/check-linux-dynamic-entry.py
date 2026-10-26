#!/usr/bin/env python3
"""Run original glibc ET_DYN entry and record actual original browser refusals.

Passing this prerequisite gate never means a browser executed successfully.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import struct
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--loader',type=Path,required=True)
p.add_argument('--firefox',type=Path,required=True)
p.add_argument('--helium',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--root',choices=['standard','minimal'],default='standard')
a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
artifacts={'loader':a.loader.resolve(),'firefox':a.firefox.resolve(),'helium':a.helium.resolve()}
pins={'loader':json.loads((ROOT/'fixtures/applications/glibc-2.41-loader.json').read_text())['apps'][0]}
pins.update({x['id']:x for x in json.loads((ROOT/'fixtures/applications/original-browsers.json').read_text())['apps']})
for name,path in artifacts.items():assert sha(path)==pins[name]['sha256'] and path.stat().st_size==pins[name]['size_bytes'],name
report={'status':'running','goal_status':'OPEN','scope':__doc__,'root':a.root,'compiler_sha256':sha(a.compiler),'original_loader_entries':0,'successful_browser_entries':0,'artifacts':{name:{'path':str(path),'sha256':sha(path),'size_bytes':path.stat().st_size} for name,path in artifacts.items()}}
paths=[x for directory in ['components','kernel','protocol','services','fixtures/linux-process'] for x in (ROOT/directory).rglob('*') if x.suffix in ['.in','.asm']]
paths += [ROOT/'boot/multiboot.asm',ROOT/'fixtures/applications/glibc-2.41-loader.json',ROOT/'fixtures/applications/original-browsers.json',Path(__file__).resolve()]
contents={str(path.relative_to(ROOT)):path.read_bytes() for path in paths}
snapshot=out/'source'
for name,data in contents.items():
 path=snapshot/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
report['source_sha256']={name:hashlib.sha256(data).hexdigest() for name,data in contents.items()}
references={}
for option in ['--help','--version','--space-invalid-option']:
 r=subprocess.run(['/ld.so',option],executable=str(a.loader.resolve()),env={'LC_ALL':'C','HOME':'/'},capture_output=True,timeout=10)
 references[option]={'output':(r.stdout+r.stderr).decode(),'exit':r.returncode}
report['host_reference']=references
for name,path in artifacts.items():
 metadata=subprocess.run(['readelf','-l','-d',str(path)],capture_output=True,text=True,check=True,timeout=15).stdout
 report['artifacts'][name]['elf_metadata']=metadata
 report['artifacts'][name]['needed_libraries']=re.findall(r'Shared library: \[(.*?)\]',metadata)
 report['artifacts'][name]['interpreter']=re.findall(r'Requesting program interpreter: (.*?)\]',metadata)
# Exact declared QEMU max/Space CPU profile: no enabled AVX XSAVE state.
# Retain the unmodified host reference; only these CPU-dependent labels differ.
expected={option:dict(value) for option,value in references.items()}
expected['--help']['output']=expected['--help']['output'].replace('  x86-64-v4 (supported, searched)\n','  x86-64-v4\n').replace('  x86-64-v3 (supported, searched)\n','  x86-64-v3\n')
report['space_expected']=expected
report['cpu_profile']='QEMU max; Space startup has no enabled AVX XSAVE state; glibc-hwcaps v2 only'
qemu=None;channel=None;received=bytearray()
try:
 with (out/'build.log').open('w') as log:
  subprocess.run(['nasm','-f','elf64',str(snapshot/'fixtures/linux-process/dynamic-entry.asm'),'-o',str(out/'probe.o')],check=True,stdout=log,stderr=subprocess.STDOUT)
  subprocess.run(['ld','-pie','--no-dynamic-linker','-z','noexecstack','-o',str(out/'probe.elf'),str(out/'probe.o')],check=True,stdout=log,stderr=subprocess.STDOUT)
 own=out/'probe.elf';report['own_cpu_fixture_sha256']=sha(own)
 data=a.loader.read_bytes();assert len(data)%8==0;phoff=struct.unpack_from('<Q',data,32)[0];count=struct.unpack_from('<H',data,56)[0]
 headers=[(i,struct.unpack_from('<II6Q',data,phoff+i*56)) for i in range(count)]
 dynamic=next(phoff+i*56 for i,h in headers if h[0]==2)
 load=next(phoff+i*56 for i,h in headers if h[0]==1)
 rx=next(phoff+i*56 for i,h in headers if h[0]==1 and h[1]==5)
 note=next(phoff+i*56 for i,h in headers if h[0]==4)
 dynoff=struct.unpack_from('<Q',data,dynamic+8)[0]
 mutations=[('wrong-type',[(16,2,1)]),('bad-phdr',[(32,8,0)]),('negative-entry',[(24,8,2**64-1)]),('non-executable-entry',[(24,8,0)]),('overflow-va',[(rx+16,8,2**63-1)]),('writable-executable',[(rx+4,4,7)]),('bad-alignment',[(rx+48,8,3)]),('unmapped-phdr',[(load+32,8,0)]),('overlap',[(rx+16,8,0)]),('interpreter',[(dynamic,4,3)]),('needed-library',[(dynoff,8,1)]),('unterminated-dynamic',[(dynamic+32,8,16),(dynamic+40,8,16),(dynoff,8,7)]),('dynamic-file-bounds',[(dynamic+8,8,len(data))]),('dynamic-va-mismatch',[(dynamic+16,8,1)]),('duplicate-dynamic',[]),('dynamic-stride',[(dynamic+32,8,17),(dynamic+40,8,17)])]
 tests=[]
 for index,(name,edits) in enumerate(mutations):
  if name=='duplicate-dynamic':
   blob=data[dynamic:dynamic+56];edits=[(note+i,1,byte) for i,byte in enumerate(blob)]
  patch=''.join('store'+str(width*8)+'(copy+'+str(offset)+','+str(value if value<2**63 else value-2**64)+');' for offset,width,value in edits)
  tests.append('cpu-mem-copy64(copy,0x10000000,'+str(len(data)//8)+');'+patch+'if linux-process-elf-entry(copy,'+str(len(data))+')!=-8{panic("ET_DYN malformed '+name+'");}')
 report['malformed_controls']=[name for name,_ in mutations]
 body='''
fn dynamic-entry-free()->Int{let n=0;let p=free-list;while p!=0 && n<131072{n+=1;p=load64(p);}if p!=0{panic("ET_DYN free-list cycle");}return n;}
fn dynamic-entry-run(port:Int)->void{
 if heap-next>=0x10000000{panic("ET_DYN source collision");}heap-end=0x10000000;
 let copy=alloc(LOADER_SIZE);let authority=cap-mint(root-realm,cap-memory()|cap-serial()|cap-storage()|cap-timer());
 let heap=heap-next;let free=dynamic-entry-free();let domains=domain-count;let caps=cap-count;
 MUTATIONS
 if linux-process-run-counted-input(0x10000000,LOADER_SIZE,"/ld.so","--version","",-1,-1,2)!=-13{panic("ET_DYN denied grant");}
 if heap-next!=heap || dynamic-entry-free()!=free || domain-count!=domains || cap-count!=caps{panic("ET_DYN preflight mutated ownership");}
 let calls=linux-process-syscalls;
 if linux-process-run-counted-input(0x12000000,FIREFOX_SIZE,"/firefox","--version","",authority,-1,2)!=-8{panic("Firefox actual entry result changed");}
 if linux-process-run-counted-input(0x20000000,HELIUM_SIZE,"/helium","--version","",authority,-1,2)!=-8{panic("Helium actual entry result changed");}
 if linux-process-syscalls!=calls || heap-next!=heap || domain-count!=domains || dynamic-entry-free()!=free{panic("Browser refusal entered or allocated");}
 serial-write-cstr(port,"browser-entry: original Firefox and Helium refused before execution");serial-nl(port);
 let fs=rdmsr(0xc0000100);let gs=rdmsr(0xc0000101);let cap=current-cap;
 let cycle=0;while cycle<21{
  let which=0;while which<3{
   let option="--help";let expected=0;if which==1{option="--version";}if which==2{option="--space-invalid-option";expected=1;}
   serial-write-cstr(port,"ld-entry: begin ");serial-write-dec-wide(port,cycle);serial-put(port,32);serial-write-dec-wide(port,which);serial-nl(port);
   let status=linux-process-run-counted-input(0x10000000,LOADER_SIZE,"/ld.so",option,"",authority,-1,2);
   serial-write-cstr(port,"ld-entry: end ");serial-write-dec-wide(port,cycle);serial-put(port,32);serial-write-dec-wide(port,which);serial-put(port,32);serial-write-dec-wide(port,status);serial-nl(port);
   if status!=expected{panic("Original runtime linker status");}which+=1;
  }
  if linux-process-run-counted-input(0x14000000,OWN_SIZE,"/probe","first","",authority,-1,2)!=42{panic("ET_DYN auxv self-exec and writev control");}
  if domain-current!=0 || user-context-active!=0 || user-budget-active!=0 || domain-user-syscall-hook!=0 || rdmsr(0xc0000100)!=fs || rdmsr(0xc0000101)!=gs || current-cap!=cap || linux-process-active!=0 || linux-process-cleanup-failed!=0 || cap-count!=caps{panic("ET_DYN supervisor restoration");}
  if cycle==0{heap=heap-next;free=dynamic-entry-free();domains=domain-count;}else if heap-next!=heap || dynamic-entry-free()!=free || domain-count!=domains{panic("ET_DYN repeated ownership growth");}cycle+=1;
 }
 serial-write-cstr(port,"ld-entry: 63 original loader entries and 42 own auxv/exec/writev entries PASS");serial-nl(port);
}
'''.replace('MUTATIONS','\n'.join(tests)).replace('LOADER_SIZE',str(len(data))).replace('OWN_SIZE',str(own.stat().st_size)).replace('FIREFOX_SIZE',str(a.firefox.stat().st_size)).replace('HELIUM_SIZE',str(a.helium.stat().st_size))
 source=(snapshot/('kernel/kernel-root.in' if a.root=='standard' else 'kernel/kernel-root-minimal.in')).read_text()
 source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(snapshot/m[1])),source)
 source='import '+json.dumps(str(snapshot/'components/linux-process.in'))+'\n'+source
 assert source.count('  shell(port)')==1
 source=source.replace('  shell(port)','  dynamic-entry-run(port)\n  shell(port)')+body
 (out/'kernel.in').write_text(source)
 with (out/'build.log').open('a') as log:
  commands=[['nasm','-f','bin',str(snapshot/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],[str(a.compiler.resolve()),'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')]]
  for command in commands:subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=180)
 report['kernel_sha256']=sha(out/'kernel.bin')
 sock=out/'serial.sock';command=['qemu-system-x86_64','-kernel',str(out/'kernel.bin'),'-m','1G','-cpu','max','-display','none','-no-reboot','-serial','unix:'+str(sock)+',server=on,wait=on']
 for path,address in [(artifacts['loader'],0x10000000),(artifacts['firefox'],0x12000000),(artifacts['helium'],0x20000000),(own,0x14000000)]:command+=['-device',f'loader,file={path},addr={address:#x},force-raw=on']
 report['qemu_command']=command
 with (out/'qemu.log').open('w') as log:qemu=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
 deadline=time.monotonic()+20
 while not sock.exists() and qemu.poll() is None and time.monotonic()<deadline:time.sleep(.02)
 channel=socket.socket(socket.AF_UNIX);channel.settimeout(.2);channel.connect(str(sock));deadline=time.monotonic()+240
 while b'space interactive shell' not in received and time.monotonic()<deadline:
  try:
   block=channel.recv(65536)
   if not block:break
   received.extend(block);(out/'serial.log').write_bytes(received)
   if b'PANIC' in received or b'CPU EXCEPTION' in received:break
  except socket.timeout:
   if qemu.poll() is not None:break
 text=received.decode(errors='replace');assert 'space interactive shell' in text,text[-3000:]
 for cycle in range(21):
  for index,option in enumerate(expected):
   match=re.search(r'ld-entry: begin '+str(cycle)+' '+str(index)+r'\r?\n(.*?)ld-entry: end '+str(cycle)+' '+str(index)+' '+str(expected[option]['exit'])+r'\r?\n',text,re.S)
   assert match and match[1].replace('\r\n','\n')==expected[option]['output'],(cycle,option,match[1] if match else text[-3000:])
 assert 'ld-entry: 63 original loader entries and 42 own auxv/exec/writev entries PASS' in text
 assert all(sha(path)==report['artifacts'][name]['sha256'] for name,path in artifacts.items()) and sha(a.compiler)==report['compiler_sha256']
 assert all((ROOT/name).read_bytes()==data for name,data in contents.items())
 report.update(status='passed',original_loader_entries=63,own_cpu_entries=42,lifetime_cycles=21,exact_original_output=True,integrity_status='passed',browser_status={'firefox':{'status':'loader-refusal','execution_started':False,'return':-8},'helium':{'status':'loader-refusal','execution_started':False,'return':-8}})
except Exception as error:report.update(status='failed',error=str(error))
finally:
 if channel is not None:channel.close()
 if qemu is not None:
  qemu.terminate()
  try:qemu.wait(timeout=3)
  except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
 (out/'serial.log').write_bytes(received);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['status'].upper()+': '+str(out/'report.json'))
raise SystemExit(0 if report['status']=='passed' else 1)
