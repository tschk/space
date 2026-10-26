#!/usr/bin/env python3
"""Prove native Unicode mechanics and actual bounded Win64 conversion semantics."""
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
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();a.compiler=a.compiler.resolve();out=a.out.resolve()
assert not out.exists() or not any(out.iterdir()),'--out must be new or empty'
out.mkdir(parents=True,exist_ok=True)
SRC=0x140005100;DST=0x140005400;PRESERVE=0x12345678
cases=[]
def case(name,mode=0,cp=65001,flags=0,data=b'',count=None,capacity=256,result=0,error=PRESERVE,source=SRC,output=DST,expected=b'',default=0,used=0,fill=0,control=0):
    if count is None:count=len(data)//(2 if mode==1 else 1)
    row=[mode,cp,flags,count,capacity,result,error,source,output,len(data),len(expected),control,0,default,used,fill]
    # source bytes at128, expected bytes at512, fixed1024-byte independent vector.
    assert len(data)<=256 or fill and len(data)<=8192
    assert len(expected)<=256
    raw=struct.pack('<16Q',*(x&0xffffffffffffffff for x in row))+data[:256]
    raw=raw.ljust(512,b'\0')+expected
    cases.append(dict(name=name,fields=row,source_hex=data[:256].hex(),expected_hex=expected.hex(),raw=raw.ljust(1024,b'\0')))

def conversion(name,text,wide=False,terminated=False):
    source=text.encode('utf-16-le' if wide else 'utf-8')
    expected=text.encode('utf-8' if wide else 'utf-16-le')
    unit=2 if wide else 1;needed=len(expected)//(1 if wide else 2)
    for cp in [65001,0,1]:
        for strict in [0,128 if wide else 8]:
            case(f'{name}-cp{cp}-flags{strict}',mode=int(wide),cp=cp,flags=strict,data=source,count=-1 if terminated else len(source)//unit,result=needed,expected=expected)
    case(name+'-query',mode=int(wide),flags=128 if wide else 8,data=source,count=-1 if terminated else len(source)//unit,capacity=0,output=0,result=needed)
    if needed>1:case(name+'-short',mode=int(wide),data=source,count=-1 if terminated else len(source)//unit,capacity=needed-1,error=122)

for name,text in [('ascii','hello'),('empty-terminated','\0'),('terminated','A€😀\0'),('embedded-nul','A\0€😀Z'),('boundaries','\x7f\x80߿ࠀ\ud7ff\ue000\uffff𐀀\U0010ffff'),('noncharacters','\ufdd0\ufffe\U0001fffe')]:
    conversion('mb-'+name,text,terminated=name in ['empty-terminated','terminated'])
    conversion('wc-'+name,text,wide=True,terminated=name in ['empty-terminated','terminated'])
malformed=[b'\x80',b'\xbf',b'\xc0\xaf',b'\xc1\xbf',b'\xf5\x80\x80\x80',b'\xff',b'\xe0\x80\x80',b'\xed\xa0\x80',b'\xf4\x90\x80\x80',b'\xe1',b'\xe1\x80',b'\xe1\x80A',b'\xf0',b'\xf0\x90',b'\xf0\x90\x80',b'\xf0\x90\x80A',b'A\xe2\x82B',b'\xc2A',b'\xe0\xa0A',b'\xed\x9fA',b'\xf4\x8f\x80A']
for i,data in enumerate(malformed):
    expected=data.decode('utf-8','replace').encode('utf-16-le')
    case(f'malformed-utf8-{i}-strict',flags=8,data=data,error=1113)
    case(f'malformed-utf8-{i}-replace',data=data,result=len(expected)//2,expected=expected)
    case(f'malformed-utf8-{i}-query-replace',data=data,capacity=0,output=0,result=len(expected)//2)
for i,units in enumerate([[0xd800],[0xdc00],[0xdbff],[0xd800,65],[0xd800,0xd800,0xdc00],[0xdc00,0xdc00],[65,0xdfff,0]]):
    data=struct.pack('<'+'H'*len(units),*units);expected=data.decode('utf-16-le','replace').encode('utf-8')
    case(f'malformed-utf16-{i}-strict',mode=1,flags=128,data=data,error=1113)
    case(f'malformed-utf16-{i}-replace',mode=1,data=data,result=len(expected),expected=expected)
for mode in [0,1]:
    data=b'A\0' if mode else b'A';width=1 if mode else 2
    case(f'{mode}-null-source',mode=mode,count=1,source=0,error=87)
    case(f'{mode}-zero-count',mode=mode,data=data,count=0,error=87)
    case(f'{mode}-bad-source',mode=mode,data=data,count=1,source=0x70000000,error=998)
    case(f'{mode}-overflow-source',mode=mode,data=data,count=1,source=0x7fffffffffffffff,error=998)
    case(f'{mode}-null-output',mode=mode,data=data,output=0,error=87)
    case(f'{mode}-negative-capacity',mode=mode,data=data,capacity=-1,error=87)
    case(f'{mode}-zero-query-ignores-output',mode=mode,data=data,output=0x7fffffffffffffff,capacity=0,result=1)
    case(f'{mode}-unknown-cp',mode=mode,cp=1252,data=data,error=87)
    case(f'{mode}-flags',mode=mode,flags=1,data=data,error=1004)
    case(f'{mode}-readonly-output',mode=mode,data=data,output=0x140003400,error=998)
    case(f'{mode}-bad-output',mode=mode,data=data,output=0x70000000,error=998)
    case(f'{mode}-cross-unmapped-output',mode=mode,data=data,capacity=2,output=0x140006fff,error=998)
    case(f'{mode}-overlap',mode=mode,data=data,output=SRC,capacity=2,error=87)
    case(f'{mode}-source-count-bound',mode=mode,data=data,count=4097,error=8)
    case(f'{mode}-output-count-bound',mode=mode,data=data,capacity=16385,error=8)
    case(f'{mode}-int32-count',mode=mode,data=data,count=0x100000001,result=1,expected=b'A' if mode else b'A\0')
    case(f'{mode}-negative2-terminated',mode=mode,data=data+b'\0'*width,count=-2,result=2,expected=b'A\0' if mode else b'A\0\0\0')
case('mb-cross-page-unit',data=b'\xe2\x82\xac',source=0x140005fff,output=0x140006101,result=1,expected=b'\xac\x20')
case('mb-cross-page-output',data=b'A',output=0x140005fff,capacity=1,result=1,expected=b'A\0')
case('wc-cross-page-source',mode=1,data=b'A\0',source=0x140005fff,result=1,expected=b'A')
case('wc-supplementary-cross-page-source',mode=1,data=struct.pack('<HH',0xd83d,0xde00),source=0x140005fff,result=4,expected='😀'.encode())
case('wc-default-pointer',mode=1,data=b'A\0',default=SRC,error=87)
case('wc-used-pointer',mode=1,data=b'A\0',used=DST+64,error=87)
case('mb-maximum-query',data=b'A'*4096,source=0x140006000,count=4096,capacity=0,output=0,result=4096,fill=1)
case('mb-unterminated-bound',data=b'A'*4096,source=0x140006000,count=-1,capacity=0,output=0,error=8,fill=1)
case('wc-large-query',mode=1,data=b'A\0'*2048,source=0x140006000,count=2048,capacity=0,output=0,result=2048,fill=2)
for cp in [65001,0,1]:case(f'cpinfo-{cp}',mode=2,cp=cp,result=1,expected=struct.pack('<I',4)+b'?'+bytes(15))
case('cpinfo-unknown',mode=2,cp=1252,error=87)
case('cpinfo-null',mode=2,output=0,error=87)
case('cpinfo-readonly',mode=2,output=0x140003400,error=998)
for mode in [3,4]:case('acp' if mode==3 else 'oem',mode=mode,result=65001)
for cp in [0,1,2,3,65001,65000,1252,0xffffffff]:case(f'valid-{cp}',mode=5,cp=cp,result=int(cp==65001))
case('mb-max4096-full-output',data=b'A'*4096,source=0x4d000000,count=4096,capacity=4096,output=0x4d004000,result=4096,fill=1,control=2)
case('wc-max4096-full-capacity',mode=1,data=b'A\0'*4096,source=0x4d000000,count=4096,capacity=16384,output=0x4d004000,result=4096,fill=2,control=2)
case('mb-sixth-stackarg-unmapped',mode=6,data=b'A',count=1,error=998)
case('wc-eighth-stackarg-unmapped',mode=7,data=b'A\0',count=1,error=998)
normal_count=len(cases)
for mode in range(6):case(f'live-memory-revoke-{mode}',mode=mode,data=b'A\0' if mode else b'A',count=1,error=5,control=1)

models=[]
def model(values):models.append(struct.pack('<8Q',*(x&0xffffffffffffffff for x in values)))
scalars=sorted(set(range(0,0x110000,997))|{0,0x7f,0x80,0x7ff,0x800,0xd7ff,0xe000,0xffff,0x10000,0x10ffff})
for scalar in scalars:
    if 0xd800<=scalar<=0xdfff:continue
    data=chr(scalar).encode();b=list(data.ljust(4,b'\0'))
    model([0,len(data),*b,(len(data)<<32)|scalar,0])
    model([2,scalar,int.from_bytes(data,'little'),len(data),0,0,0,0])
    w=chr(scalar).encode('utf-16-le');units=list(struct.unpack('<'+'H'*(len(w)//2),w));model([1,len(units),units[0],units[1] if len(units)>1 else 0,0,0,((len(w)//2)<<32)|scalar,0])
for data in malformed:
    b=list(data[:4].ljust(4,b'\0'));model([0,min(len(data),4),*b,-1,0])
for first,second,units in [(0xd800,0,1),(0xdc00,0,1),(0xdbff,65,2),(0xd800,0xd800,2)]:model([1,units,first,second,0,0,-1,0])
for data,consume in [(b'\xf0',1),(b'\xf0\x90',2),(b'\xf0\x90\x80',3),(b'\xe1',1),(b'\xe1\x80',2),(b'\xe1\x80A',2),(b'\xe0\x80',1),(b'\xed\xa0',1),(b'\xf4\x90',1),(b'\x80',1)]:
    b=list(data.ljust(3,b'\0'));model([3,len(data),*b,0,consume,0])
# A-leading malformed whole string has a valid first scalar; scalar oracle
# only checks the first sequence, unlike the actual whole-string Win64 corpus.
for i,data in enumerate(malformed):
    if data.startswith(b'A'):
        row=[0,min(len(data),4),*list(data[:4].ljust(4,b'\0')),(1<<32)|65,0]
        models[sum(3 for s in scalars if not 0xd800<=s<=0xdfff)+i]=struct.pack('<8Q',*row)
modeloff=(4096+len(cases)*1024+4095)&-4096
payload=struct.pack('<4Q',len(cases),len(models),modeloff,normal_count).ljust(4096,b'\0')+b''.join(c['raw'] for c in cases)
payload=payload.ljust(modeloff,b'\0')+b''.join(models)
(out/'oracles.bin').write_bytes(payload)
(out/'cases.json').write_text(json.dumps([{k:v for k,v in c.items() if k!='raw'} for c in cases],indent=2)+'\n')

def absolute_imports(source):return re.sub(r'import "([^"]+)"',lambda m:'import '+json.dumps(str((ROOT/'components'/m.group(1)).resolve())),source)
protected=absolute_imports((ROOT/'components/windows-protected.in').read_text());assert protected.count('domain-user-syscall-hook = windows-protected-dispatch')==1
protected=protected.replace('domain-user-syscall-hook = windows-protected-dispatch','domain-user-syscall-hook = windows-unicode-test-dispatch');(out/'windows-protected.in').write_text(protected)
hub=absolute_imports((ROOT/'components/personality-hub.in').read_text()).replace(json.dumps(str(ROOT/'components/windows-protected.in')),json.dumps(str(out/'windows-protected.in')));(out/'personality-hub.in').write_text(hub)
source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(ROOT/m.group(1))),(ROOT/'kernel/kernel-root.in').read_text()).replace(json.dumps(str(ROOT/'components/personality-hub.in')),json.dumps(str(out/'personality-hub.in')))
assert source.count('  shell(port)')==1;source=source.replace('  shell(port)','  windows-unicode-check(port)\n  shell(port)')
source+=r'''
var windows-unicode-test-row:Int=0
var windows-unicode-test-first:Int=0
var windows-unicode-test-scratch:Int=0
fn windows-unicode-test-output-bytes(row:Int)->Int{let n=load64(row+32);if load64(row)==0{n=n*2;}if n>512 && n<=16384{return n;}return 512;}
fn windows-unicode-test-dispatch(frame:Int)->Int{
 let row=windows-unicode-test-row;
 if windows-protected-profile!=11 || windows-protected-count!=87{panic("Unicode profile owner mismatch");}
 if windows-unicode-test-first==0{
  windows-unicode-test-first=1;let output=load64(row+64);let i=0;
  while i<windows-unicode-test-output-bytes(row){let p=windows-protected-physical(output+i);if p!=0 && (domain-page-flags(windows-protected-domain,output+i)&7)==7{store8(p,90);}i=i+1;}
  let input=load64(row+56);let bytes=load64(row+72);i=0;while i<bytes{
   let p=windows-protected-physical(input+i);if p!=0{
    let value=0;let fill=load64(row+120);if fill==0{value=load8(row+128+i);}else{value=65;if fill==2 && (i&1)!=0{value=0;}}
    store8(p,value);
   }i=i+1;
  }
  if load64(row+88)==1{cap-revoke(windows-parameters-heap-authority);}
 }
 let num=load64(frame+112);let observing=0;if num>=0x10002b && num<=0x100030{observing=1;}
 let output=load64(row+64);if observing!=0{let i=0;while i<windows-unicode-test-output-bytes(row){let value=0;let p=windows-protected-physical(output+i);if p!=0{value=load8(p);}store8(windows-unicode-test-scratch+i,value);i=i+1;}}
 let control=windows-protected-dispatch(frame);
 if observing!=0 && load64(frame+112)==0{let i=0;while i<windows-unicode-test-output-bytes(row){let p=windows-protected-physical(output+i);if p!=0 && load8(p)!=load8(windows-unicode-test-scratch+i){panic("Unicode failure partially wrote guest output");}i=i+1;}}
 return control;
}
fn windows-unicode-test-free()->Int{let f=free-list;let n=0;while f!=0 && n<4096{n=n+1;f=load64(f);}return n;}
fn windows-unicode-test-clean()->void{
 if windows-protected-busy!=0 || windows-protected-count!=0 || windows-parameters-active!=0 || windows-parameters-composed-active!=0 || windows-parameters-composed-data!=0 || windows-parameters-env-active!=0 || windows-parameters-env-data!=0 || windows-parameters-heap-active!=0 || windows-parameters-heap-records!=0 || windows-parameters-local-data!=0 || windows-parameters-critical-data!=0 || windows-parameters-time-active!=0 || domain-user-syscall-hook!=0 || user-context-active!=0 || user-budget-active!=0 || domain-current!=0{panic("Unicode activation ownership leaked");}
}
fn windows-unicode-check(port:Int)->void{
 let image=0x10000000;if heap-next>=image{panic("Unicode fixture collision");}heap-end=image;
 let oracle=0x12000000;let model=oracle+load64(oracle+16);let i=0;
 while i<load64(oracle+8){let row=model+i*64;let kind=load64(row);let value=0;
  if kind==0{value=unicode-utf8-decode(load64(row+16),load64(row+24),load64(row+32),load64(row+40),load64(row+8));}
  if kind==1{value=unicode-utf16-decode(load64(row+16),load64(row+24),load64(row+8));}
  if kind==2{let scalar=load64(row+8);let width=unicode-utf8-width(scalar);if width!=load64(row+24){panic("Unicode scalar width oracle mismatch");}let j=0;while j<width{if unicode-utf8-byte(scalar,j)!=((load64(row+16)>>(j*8))&255){panic("Unicode encoded byte oracle mismatch");}j=j+1;}value=load64(row+48);}
  if kind==3{value=unicode-utf8-invalid-prefix(load64(row+16),load64(row+24),load64(row+32),load64(row+8));}
  if value!=load64(row+48){serial-write-dec-wide(port,i);panic("Unicode pure scalar oracle mismatch");}i=i+1;
 }
 serial-write-cstr(port,"windows-unicode-model: independent scalar encoding decoding malformed maximalprefix PASS");serial-nl(port);
 if dyn-resolve-idx("windows-command-unicode-run")!=-1 || dyn-resolve-idx("windows-parameters-unicode-dispatch")!=-1{panic("Unicode private policy exported");}
 let config=alloc(96);let env=alloc(2);store8(env,0);store8(env+1,0);windows-unicode-test-scratch=alloc(16384);
 let memory=cap-mint(root-realm,cap-memory());let weak=cap-mint(root-realm,cap-serial());
 store64(config,1);store64(config+8,96);store64(config+16,-1);store64(config+24,-1);store64(config+32,memory);store64(config+40,-1);
 windows-unicode-test-line(config,"sqlite3.exe");store64(config+64,env);store64(config+72,2);store64(config+80,0);store64(config+88,0);
 let before=heap-next;let free=free-list;let domains=domain-count;
 if windows-command-composed-run(image,9728,config)!=-8 || heap-next!=before || free-list!=free || domain-count!=domains{panic("Old composed profile admitted Unicode/allocated");}
 store64(config+32,weak);if windows-command-unicode-run(image,9728,config)!=-13 || heap-next!=before || free-list!=free || domain-count!=domains{panic("Unicode weak memory admission mutated");}store64(config+32,memory);windows-unicode-test-clean();
 let fs=rdmsr(0xc0000100);let gs=rdmsr(0xc0000101);let pic=inb(0x21);let caller=current-cap;let caps=cap-count;let heap=0;let pool=0;
 let cycle=0;while cycle<21{let n=0;while n<load64(oracle+24){
  let row=oracle+4096+n*1024;windows-unicode-test-row=row;windows-unicode-test-first=0;
  i=0;while i<128{store8(image+7680+i,load8(row+i));i=i+1;}
  i=0;while i<load64(row+80){store8(image+7680+1536+i,load8(row+512+i));i=i+1;}
  let result=windows-command-unicode-run(image,9728,config);
  if result!=42{serial-write-dec-wide(port,n);serial-put(port,32);serial-write-dec-wide(port,result);panic("Unicode actual Windows case mismatch");}windows-unicode-test-clean();
  if rdmsr(0xc0000100)!=fs || rdmsr(0xc0000101)!=gs || inb(0x21)!=pic || current-cap!=caller || cap-count!=caps{panic("Unicode caller context changed");}n=n+1;
 }
 if cycle==0{heap=heap-next;pool=windows-unicode-test-free();domains=domain-count;}else{if heap-next!=heap || pool!=windows-unicode-test-free() || domains!=domain-count{panic("Unicode repeat cleanup leaked");}}cycle=cycle+1;}
 let n=load64(oracle+24);while n<load64(oracle){let live=cap-mint(root-realm,cap-memory());store64(config+32,live);let row=oracle+4096+n*1024;windows-unicode-test-row=row;windows-unicode-test-first=0;
  i=0;while i<128{store8(image+7680+i,load8(row+i));i=i+1;}
  if windows-command-unicode-run(image,9728,config)!=42 || cap-check(live,cap-memory())!=0{panic("Unicode actual live grant denial mismatch");}windows-unicode-test-clean();n=n+1;
 }
 store64(config+32,memory);windows-unicode-test-row=oracle+4096;windows-unicode-test-first=0;i=0;while i<128{store8(image+7680+i,load8(oracle+4096+i));i=i+1;}i=0;while i<load64(oracle+4096+80){store8(image+7680+1536+i,load8(oracle+4096+512+i));i=i+1;}
 if windows-command-unicode-run(image,9728,config)!=42{panic("Unicode fresh activation failed");}windows-unicode-test-clean();
 if heap-next!=heap || pool!=windows-unicode-test-free() || domains!=domain-count{panic("Unicode revoke fresh cleanup leaked");}
 cap-revoke(memory);cap-revoke(weak);
 serial-write-cstr(port,"windows-unicode: actual UTF8 UTF16 metadata query count strict replacement pointers stackargs revoke no partial writes cleanup PASS");serial-nl(port);
}
fn windows-unicode-test-line(config:Int,line:Int)->void{store64(config+48,line);store64(config+56,12);}
'''
names=['components/text-unicode.in','components/windows-process-unicode.in','components/windows-process-composed.in','components/windows-process-local.in','components/windows-protected.in','components/windows-process-parameters.in','components/windows-pe-startup.in','components/windows-pe-application.in','fixtures/windows-protected/unicode.asm']
source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names};(out/'kernel.in').write_text(source)
commands=[['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],['nasm','-f','bin',str(ROOT/'fixtures/windows-protected/unicode.asm'),'-o',str(out/'process.exe')],[str(a.compiler),'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')]]
with (out/'compile.log').open('w') as log:
 for command in commands:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
assert (out/'process.exe').stat().st_size==9728 and 0x100000+(out/'kernel.bin').stat().st_size<0x10000000
path=out/'serial.sock';received=bytearray();serial=None
command=['qemu-system-x86_64','-kernel',str(out/'kernel.bin'),'-m','512M','-display','none','-no-reboot','-serial',f'unix:{path},server=on,wait=on','-device',f'loader,file={out/"process.exe"},addr=0x10000000,force-raw=on','-device',f'loader,file={out/"oracles.bin"},addr=0x12000000,force-raw=on']
with (out/'qemu.log').open('w') as log:
 qemu=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
 try:
  deadline=time.monotonic()+10
  while not path.exists() and qemu.poll() is None and time.monotonic()<deadline:time.sleep(.02)
  serial=socket.socket(socket.AF_UNIX);serial.settimeout(.2);serial.connect(str(path));deadline=time.monotonic()+240
  while b'space> ' not in received and time.monotonic()<deadline:
   try:
    block=serial.recv(65536)
    if not block:break
    received.extend(block)
    if b'PANIC' in received or b'nanokernel fault handler halting' in received:break
   except socket.timeout:
    if qemu.poll() is not None:break
  text=received.decode(errors='replace');assert 'windows-unicode-model: independent scalar encoding decoding malformed maximalprefix PASS' in text,text
  assert 'windows-unicode: actual UTF8 UTF16 metadata query count strict replacement pointers stackargs revoke no partial writes cleanup PASS' in text and 'space> ' in text,text
 finally:
  (out/'serial.log').write_bytes(received)
  if serial:serial.close()
  qemu.terminate()
  try:qemu.wait(timeout=5)
  except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
report=dict(status='passed',executions=normal_count*21+len(cases)-normal_count+1,unique_regular_cases=normal_count,live_revoke_cases=len(cases)-normal_count,scalar_model_cases=len(models),compiler_sha256=hashlib.sha256(a.compiler.read_bytes()).hexdigest(),kernel_sha256=hashlib.sha256((out/'kernel.bin').read_bytes()).hexdigest(),fixture_sha256=hashlib.sha256((out/'process.exe').read_bytes()).hexdigest(),oracle_sha256=hashlib.sha256(payload).hexdigest(),source_sha256=source_hashes,source_changed=[name for name,value in source_hashes.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=value],commands=commands,qemu_command=command)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS Windows Unicode',report['executions'],'actual activations,',len(models),'independent scalar models')
