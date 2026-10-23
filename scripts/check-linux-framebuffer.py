#!/usr/bin/env python3
"""Original pinned fbv BMP pixels via explicit Linux/native canvas binding."""
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
p.add_argument('--app',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--repeat',type=int,default=21)
a=p.parse_args();out=a.out.resolve();compiler=a.compiler.resolve();app=a.app.resolve()
assert 1<=a.repeat<=100
assert not out.exists() or not any(out.iterdir());out.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((ROOT/'fixtures/applications/fbv-1.1.json').read_text())
assert sha(app)==manifest['apps'][0]['sha256'] and app.stat().st_size==manifest['apps'][0]['size_bytes']
files=[x for d in ['components','kernel','protocol','services'] for x in (ROOT/d).rglob('*.in')]+[ROOT/'boot/multiboot.asm',ROOT/'fixtures/linux-framebuffer/checks.asm',Path(__file__).resolve(),ROOT/'fixtures/applications/fbv-1.1.json']
contents={str(p.relative_to(ROOT)):p.read_bytes() for p in files}
assert all(p.read_bytes()==contents[str(p.relative_to(ROOT))] for p in files)
snapshot=out/'source'
for name,data in contents.items():
 target=snapshot/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
inventory={name:hashlib.sha256(data).hexdigest() for name,data in contents.items()}
(out/'source-hashes.json').write_text(json.dumps(inventory,indent=2)+'\n')
# Test-only native entry interposer: actual renderer/VM code is unchanged.
provider=snapshot/'components/linux-framebuffer.in'
canonical=provider.read_bytes();old=b'linux-process-device-entry=linux-framebuffer-native-entry;'
assert canonical.count(old)==1
compiled=canonical.replace(old,b'linux-process-device-entry=fbc-native-entry;')
assert compiled.replace(b'linux-process-device-entry=fbc-native-entry;',old)==canonical
provider.write_bytes(compiled)
report=dict(status='running',goal_status='OPEN',classification='Original upstream BMP viewer, one explicit native canvas and one mapping; no interactive TTY/X11/general fbdev',application_sha256=sha(app),compiler_sha256=sha(compiler),source_sha256=inventory,root='standard',measured_cycles=a.repeat)
report['test_only_override']={'path':'components/linux-framebuffer.in','canonical_sha256':hashlib.sha256(canonical).hexdigest(),'compiled_sha256':sha(provider),'replacement':'one trusted native entry assignment through real-entry quarantine interposer'}
process=None;serial=None;monitor=None;received=bytearray()
def connect(path):
 deadline=time.monotonic()+10
 while time.monotonic()<deadline:
  c=socket.socket(socket.AF_UNIX);c.settimeout(.2)
  try:c.connect(str(path));return c
  except (FileNotFoundError,ConnectionRefusedError):c.close();time.sleep(.02)
 raise AssertionError('QEMU socket readiness')
def wait(marker):
 deadline=time.monotonic()+120
 while marker not in received:
  assert b'PANIC' not in received,received[-3000:]
  assert process.poll() is None and time.monotonic()<deadline,received[-3000:]
  try:
   block=serial.recv(65536);assert block;received.extend(block)
  except socket.timeout:pass
 (out/'serial.log').write_bytes(received)
try:
 pixels=bytes(c for y in range(4) for x in range(4) for c in ((x+y)*32,y*64,x*64))
 bitmap=struct.pack('<2sIHHI',b'BM',102,0,0,54)+struct.pack('<IiiHHIIiiII',40,4,4,1,24,0,48,2835,2835,0,0)+pixels
 (out/'image.bmp').write_bytes(bitmap)
 subprocess.run(['nasm','-f','elf64',str(snapshot/'fixtures/linux-framebuffer/checks.asm'),'-o',str(out/'checks.o')],check=True,timeout=30)
 subprocess.run(['ld','-static','-z','noexecstack','-o',str(out/'checks.elf'),str(out/'checks.o')],check=True,timeout=30)
 assert (out/'checks.elf').stat().st_size<0x100000
 source=(snapshot/'kernel/kernel-root.in').read_text()
 source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(snapshot/m[1])),source)
 source='import '+json.dumps(str(snapshot/'components/linux-framebuffer.in'))+'\n'+source
 assert source.count('  shell(port)')==1
 source=source.replace('  shell(port)','  framebuffer-check(port)\n  shell(port)')
 setup=''.join(f'store8(bitmap+{i},{b});' for i,b in enumerate(bitmap))
 source+='''
fn fbc-check(want:Int,got:Int)->void{if want!=got{serial-write-cstr(com1(),"framebuffer: expected ");serial-write-dec-wide(com1(),want);serial-write-cstr(com1()," actual ");serial-write-dec-wide(com1(),got);serial-nl(com1());panic("framebuffer contract");}}
var fbc-quarantine:Int=0
var fbc-q-vm:Int=0
var fbc-q-pde:Int=0
var fbc-q-original:Int=0
// Test-only status-returning raw native callback. Always delegates to real entry.
fn fbc-native-entry(request:Int)->Int{
 if fbc-quarantine!=0 && load64(request)==7 && load64(request+8)==linux-framebuffer-address && load64(request+16)==NATIVE-CANVAS-BYTES{
  fbc-quarantine=0;fbc-q-vm=linux-process-vm;
  let address=linux-framebuffer-address;let domain=user-space-domain(fbc-q-vm,linux-process-authority);let root=load64(domain-table+domain*24);
  let pdpt=load64(root+((address>>39)&511)*8)&PAGE-ADDRESS-MASK;let pd=load64(pdpt+((address>>30)&511)*8)&PAGE-ADDRESS-MASK;
  fbc-q-pde=pd+((address>>21)&511)*8;fbc-q-original=load64(fbc-q-pde);store64(fbc-q-pde,fbc-q-original|128);
 }
 return linux-framebuffer-native-entry(request);
}
fn fbc-free()->Int{let frame=free-list;let count=0;while frame!=0 && count<131072{frame=load64(frame);count+=1;}if frame!=0{panic("framebuffer free list");}return count;}
fn framebuffer-check(port:Int)->void{
 fbc-check(-1,dyn-resolve-idx("linux-framebuffer-run"));fbc-check(-1,dyn-resolve-idx("native-canvas-new"));
 if out-set-bga-mode(port,1024,768,100,100)<=0{panic("framebuffer output");}
 let bitmap=alloc(102);
'''+setup+'''
 if fs-write-file("/fbv-test.bmp",bitmap,102)!=0{panic("framebuffer bitmap seed");}
 let auth=cap-mint(root-realm,cap-memory()|cap-serial()|cap-storage());let owner=cap-mint(root-realm,cap-memory()|cap-display());
 let wrong=cap-mint(root-realm,cap-memory());
 let heap=0;let free=0;let domains=0;let caps=cap-count;let objects=obj-arena-next;let owned=domain-user-owned;let caller=current-cap;let fs=rdmsr(0xC0000100);let gs=rdmsr(0xC0000101);
 let cycle=0;while cycle<CYCLES{
 let canvas=native-canvas-new(owner,256,128,64,64);if canvas<=0{panic("framebuffer canvas");}
 dsp-background=0x11161F;dsp-mouse-x=900;dsp-mouse-y=700;
 let beforeheap=heap-next;let beforefree=fbc-free();let beforedomains=domain-count;
 fbc-check(-2,linux-framebuffer-run(0x14000000,APP_SIZE,"/fbv","-cery","/fbv-test.bmp",auth,canvas,wrong));
 fbc-check(-13,linux-framebuffer-run(0x14000000,APP_SIZE,"/fbv","-cery","/fbv-test.bmp",wrong,canvas,owner));
 fbc-check(beforeheap,heap-next);fbc-check(beforefree,fbc-free());fbc-check(beforedomains,domain-count);
 let control=linux-framebuffer-run(0x15000000,CONTROL_SIZE,"/checks","","",auth,canvas,owner);
 fbc-check(42,control);fbc-check(1,linux-framebuffer-presents);fbc-check(1,native-canvas-query(canvas,owner,4));
 let y=0;while y<128{let x=0;while x<256{fbc-check(0x00AABB,load32(fb-addr+(64+y)*fb-pitch+(64+x)*4)&0xFFFFFF);x+=1;}y+=1;}
 fbc-check(0,native-canvas-close(canvas,owner));
 canvas=native-canvas-new(owner,256,128,64,64);if canvas<=0{panic("framebuffer quarantine canvas");}
 fbc-quarantine=1;fbc-check(-5,linux-framebuffer-run(0x15000000,CONTROL_SIZE,"/checks","","",auth,canvas,owner));
 fbc-check(0,fbc-quarantine);fbc-check(1,linux-process-cleanup-failed);fbc-check(canvas,linux-framebuffer-canvas);
 if linux-process-device-entry==0{panic("framebuffer quarantine lost edge lease");}
 fbc-check(-5,linux-framebuffer-end());fbc-check(-16,linux-framebuffer-run(0x15000000,CONTROL_SIZE,"/checks","","",auth,canvas,owner));
 fbc-check(USER-SPACE-QUARANTINED,user-space-phase(fbc-q-vm,auth));fbc-check(0,user-space-refs(fbc-q-vm,auth));fbc-check(0,user-space-constructor-owned(fbc-q-vm,auth));
 fbc-check(0,native-canvas-query(canvas,owner,4));fbc-check(0,linux-framebuffer-presents);
 store64(fbc-q-pde,fbc-q-original);fbc-check(0,linux-process-cleanup-recover());fbc-check(-6,user-space-phase(fbc-q-vm,auth));fbc-check(0,linux-framebuffer-end());fbc-check(0,native-canvas-close(canvas,owner));
 serial-write-cstr(port,"framebuffer: retained VM lease recovery PASS");serial-nl(port);
 let mode=0;while mode<2{
  canvas=native-canvas-new(owner,256,128,64,64);if canvas<=0{panic("framebuffer fault canvas");}
  let argument="fault";let expected=142;if mode==1{argument="deadline";expected=124;linux-process-budget-ticks=10;}
  fbc-check(expected,linux-framebuffer-run(0x15000000,CONTROL_SIZE,"/checks",argument,"",auth,canvas,owner));linux-process-budget-ticks=100;
  fbc-check(0,native-canvas-query(canvas,owner,4));fbc-check(0,linux-framebuffer-presents);fbc-check(0,linux-process-device-entry);fbc-check(0,linux-process-device-busy);
  y=0;while y<128{let x=0;while x<256{fbc-check(0x11161F,load32(fb-addr+(64+y)*fb-pitch+(64+x)*4)&0xFFFFFF);x+=1;}y+=1;}
  fbc-check(0,native-canvas-close(canvas,owner));mode+=1;
 }
 canvas=native-canvas-new(owner,256,128,64,64);if canvas<=0{panic("framebuffer second canvas");}
 linux-process-trace=1;
 let result=linux-framebuffer-run(0x14000000,APP_SIZE,"/fbv","-cery","/fbv-test.bmp",auth,canvas,owner);
 fbc-check(0,result);fbc-check(1,linux-framebuffer-presents);fbc-check(1,native-canvas-query(canvas,owner,4));
 fbc-check(0,linux-process-active);fbc-check(0,domain-current);fbc-check(0,user-context-active);fbc-check(0,user-budget-active);fbc-check(0,linux-framebuffer-canvas);
 if cycle==0{
 serial-write-cstr(port,"framebuffer: original fbv pixels ready");serial-nl(port);
 let remain=100000000;while (inb(port+5)&1)==0 && remain>0{remain-=1;}if remain==0{panic("framebuffer capture wait");}fbc-check(113,inb(port));
 }
 fbc-check(0,native-canvas-close(canvas,owner));
 fbc-check(owned,domain-user-owned);fbc-check(caps,cap-count);fbc-check(objects,obj-arena-next);fbc-check(caller,current-cap);fbc-check(fs,rdmsr(0xC0000100));fbc-check(gs,rdmsr(0xC0000101));
 fbc-check(0,linux-process-pages);fbc-check(0,domain-user-syscall-hook);
 if cycle==0{heap=heap-next;free=fbc-free();domains=domain-count;}else{fbc-check(heap,heap-next);fbc-check(free,fbc-free());fbc-check(domains,domain-count);}
 serial-write-cstr(port,"framebuffer: lifecycle ");serial-write-dec-wide(port,cycle);serial-nl(port);cycle+=1;
 }
 serial-write-cstr(port,"framebuffer: original fbv exited zero and owned presentation PASS");serial-nl(port);
}
'''.replace('APP_SIZE',str(app.stat().st_size)).replace('CONTROL_SIZE',str((out/'checks.elf').stat().st_size)).replace('CYCLES',str(a.repeat+1))
 (out/'kernel.in').write_text(source)
 with (out/'compile.log').open('w') as log:
  subprocess.run(['nasm','-f','bin',str(snapshot/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=30)
  subprocess.run([str(compiler),'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=180)
 metadata=json.loads((out/'kernel.component-metadata.json').read_text());assert metadata['boot_layout']['load_end']<0x14000000
 command=['qemu-system-x86_64','-kernel',str(out/'kernel.bin'),'-m','512M','-cpu','max','-vga','std','-display','none','-no-reboot','-serial',f'unix:{out}/serial.sock,server=on,wait=on','-monitor',f'unix:{out}/monitor.sock,server=on,wait=off','-device',f'loader,file={app},addr=0x14000000,force-raw=on','-device',f'loader,file={out}/checks.elf,addr=0x15000000,force-raw=on']
 report.update(qemu_command=command,kernel_sha256=sha(out/'kernel.bin'),bitmap_sha256=sha(out/'image.bmp'))
 with (out/'qemu.log').open('w') as log:
  process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT);serial=connect(out/'serial.sock');monitor=connect(out/'monitor.sock')
  wait(b'framebuffer: original fbv pixels ready\n')
  frame=out/'pixels.ppm';monitor.sendall(f'screendump {frame}\n'.encode());deadline=time.monotonic()+5
  while (not frame.exists() or frame.stat().st_size<1024*768*3+16) and time.monotonic()<deadline:time.sleep(.02)
  header=frame.read_bytes().split(b'\n',3);assert header[:3]==[b'P6',b'1024 768',b'255']
  expected=bytearray(bytes((0x11,0x16,0x1f))*(1024*768))
  # Independent nearest-neighbor oracle for original -e -r scaling of 4x4 BMP.
  for y in range(128):
   for x in range(256):
    bx=x//64;by=3-y//32;at=((64+y)*1024+64+x)*3
    expected[at:at+3]=bytes((bx*64,by*64,(bx+by)*32))
  for x in range(892,909):expected[(700*1024+x)*3:(700*1024+x)*3+3]=b'\xff'*3
  for y in range(692,709):expected[(y*1024+900)*3:(y*1024+900)*3+3]=b'\xff'*3
  if header[3]!=expected:
   first=next((i for i,(got,want) in enumerate(zip(header[3],expected)) if got!=want),-1);raise AssertionError(('pixels',first,first//3%1024,first//3//1024,len(header[3])))
  serial.sendall(b'q');wait(b'framebuffer: original fbv exited zero and owned presentation PASS\n');wait(b'space> ')
 assert all((ROOT/name).read_bytes()==data for name,data in contents.items()),'source changed'
 assert sha(compiler)==report['compiler_sha256'] and sha(app)==report['application_sha256']
 assert received.count(b'framebuffer: lifecycle ')==a.repeat+1
 assert received.count(b'framebuffer: retained VM lease recovery PASS\n')==a.repeat+1
 assert received.count(b'framebuffer: deadline armed\n')==a.repeat+1
 assert received.count(b'space: guest fault vector 0x000000000000000e')==a.repeat+1
 report.update(status='passed',actual_original_activations=a.repeat+1,synthetic_control_activations=4*(a.repeat+1),actual_retained_vm_recoveries=a.repeat+1,actual_write_pf=a.repeat+1,actual_irq_deadlines=a.repeat+1,control_sha256=sha(out/'checks.elf'),rgb_bytes_checked=len(expected),screenshot_sha256=sha(frame));print(f'PASS original fbv:{a.repeat+1} original launches +{4*(a.repeat+1)} syscall/fault/deadline/quarantine controls, exact full screenshot, exit0,{a.repeat} measured resource cycles (standard)')
except Exception as error:report.update(status='failed',error=str(error));raise
finally:
 (out/'serial.log').write_bytes(received)
 if serial:serial.close()
 if monitor:monitor.close()
 if process:
  process.terminate()
  try:process.wait(timeout=5)
  except subprocess.TimeoutExpired:process.kill();process.wait()
 (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
