#!/usr/bin/env python3
"""Run finite Windows Find imports through genuine captured CPL3 execution."""
import argparse,hashlib,json,re,socket,struct,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--in',dest='compiler',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--nvme-disk',type=Path);p.add_argument('--reopen',action='store_true');a=p.parse_args()
out=a.out.resolve();compiler=a.compiler.resolve();assert not out.exists() or not any(out.iterdir());out.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=[p for d in ['components','kernel','protocol','services','fixtures/windows-find'] for p in (ROOT/d).rglob('*') if p.is_file() and p.suffix in ['.in','.asm']]+[ROOT/'boot/multiboot.asm',Path(__file__).resolve(),ROOT/'scripts/check-windows-find-persistence.py']
contents={str(p.relative_to(ROOT)):p.read_bytes() for p in files};snapshot=out/'source'
for name,data in contents.items():
 target=snapshot/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
assert not a.reopen or a.nvme_disk is not None
if a.nvme_disk is not None:
 a.nvme_disk=a.nvme_disk.resolve()
 if a.reopen:assert a.nvme_disk.is_file() and a.nvme_disk.stat().st_size==64*1024*1024
 else:
  with a.nvme_disk.open('xb') as disk:disk.truncate(64*1024*1024)
report=dict(status='running',goal_status='OPEN',classification='Owned PE fixture, no original Windows application coverage',source_sha256={k:hashlib.sha256(v).hexdigest() for k,v in contents.items()},compiler_sha256=sha(compiler))
try:
 protected=snapshot/'components/windows-protected.in';canonical=protected.read_text();needle='domain-user-syscall-hook = windows-protected-dispatch';assert canonical.count(needle)==1;compiled=canonical.replace(needle,'domain-user-syscall-hook = wft-dispatch');protected.write_text(compiled);assert compiled.replace('domain-user-syscall-hook = wft-dispatch',needle)==canonical;report['test_hook']={'kind':'one callback installation; genuine original dispatch and captured context','canonical_sha256':hashlib.sha256(canonical.encode()).hexdigest(),'compiled_sha256':sha(protected)}
 find=snapshot/'components/windows-process-find.in';find_canonical=find.read_text();find_needle='let got=fs-directory-details-into(';assert find_canonical.count(find_needle)==1;find_compiled=find_canonical.replace(find_needle,'let got=wft-details(');find.write_text(find_compiled);assert find_compiled.replace('let got=wft-details(',find_needle)==find_canonical;report['native_read_hook']={'kind':'one call site; always performs original native directory read, then actual grant mutation','canonical_sha256':hashlib.sha256(find_canonical.encode()).hexdigest(),'compiled_sha256':sha(find)}
 source=(snapshot/'kernel/kernel-root.in').read_text();source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(snapshot/m[1])),source)
 private=out/'private.sci'
 with (out/'private.log').open('w') as log:subprocess.run([str(compiler),'compile','--path',str(snapshot/'fixtures/windows-find/private.in'),'--entry','private-entry','--emit','sci','--base','0x7a000000','--target','native','--target-triple','x86_64-unknown-none','--out',str(private)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
 report['private_sci_sha256']=sha(private)
 source='const WFT-NVME = '+str(int(a.nvme_disk is not None))+'\nconst WFT-REOPEN = '+str(int(a.reopen))+'\nconst WFT-PRIVATE-SIZE = '+str(private.stat().st_size)+'\n'+'import '+json.dumps(str(snapshot/'fixtures/windows-find/checks.in'))+'\n'+source
 assert source.count('  shell(port)')==1;source=source.replace('  shell(port)','  windows-find-check(port)\n  shell(port)');(out/'kernel.in').write_text(source)
 commands=[['nasm','-f','bin',str(snapshot/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],['nasm','-f','bin',str(snapshot/'fixtures/windows-find/checks.asm'),'-o',str(out/'process.exe')],[str(compiler),'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')]]
 compiled_inventory={name:sha(snapshot/name) for name in contents};report['compiled_source_sha256']=compiled_inventory
 report['commands']=commands
 with (out/'compile.log').open('w') as log:
  for command in commands:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
 assert (out/'process.exe').stat().st_size==11776
 assert json.loads((out/'kernel.component-metadata.json').read_text())['boot_layout']['load_end']<=0x2f0000
 path=out/'serial.sock';command=['qemu-system-x86_64','-kernel',str(out/'kernel.bin'),'-m','512M','-display','none','-no-reboot','-rtc','base=2026-10-24T00:00:00,clock=vm','-serial',f'unix:{path},server=on,wait=on','-device',f'loader,file={out}/process.exe,addr=0x10000000,force-raw=on','-device',f'loader,file={out}/private.sci,addr=0x2f0000,force-raw=on']
 if a.nvme_disk is not None:
  command.extend(['-drive',f'file={a.nvme_disk},format=raw,if=none,id=owned,cache=writethrough','-device','nvme,drive=owned,serial=space-windows-find'])
  report['disk_before_sha256']=sha(a.nvme_disk)
  if a.reopen:command[command.index('-rtc')+1]='base=2026-10-25T00:00:00,clock=vm'
 report.update(qemu_command=command,kernel_sha256=sha(out/'kernel.bin'),fixture_sha256=sha(out/'process.exe'));received=bytearray();serial=None
 with (out/'qemu.log').open('w') as log:
  qemu=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
  try:
   deadline=time.monotonic()+10
   while not path.exists() and qemu.poll() is None and time.monotonic()<deadline:time.sleep(.02)
   serial=socket.socket(socket.AF_UNIX);serial.settimeout(.5);serial.connect(str(path))
   def until(marker,seconds=120):
    deadline=time.monotonic()+seconds;start=len(received)
    while marker not in received[start:]:
     assert time.monotonic()<deadline,'serial timeout '+str(received[-1000:])
     try:
      block=serial.recv(65536);assert block,'serial EOF';received.extend(block)
      (out/'serial.log').write_bytes(received)
      assert b'PANIC' not in received and b'nanokernel fault handler halting' not in received,received[-2000:]
     except socket.timeout:assert qemu.poll() is None,'QEMU stopped'
   until(b'windows-find-ready\n')
   times=list(map(int,re.search(rb'windows-find-times:((?: [0-9]+){6})',received)[1].split()));report['native_utc_seconds']=times
   assert all(1792800000<=t<=1792800060 for t in times)
   assert times[0]<times[1]<times[2],times
   assert b'DENIED unresolved import windows-find-run' in received
   payload=bytearray()
   cases=[dict(name='enumerate-'+str(mode),mode=mode) for mode in range(7)]
   def denied(name,path=None,error=50,output=0,wide=0,source=0):
    cases.append(dict(name=name,mode=7,path=path,error=error,output=output,wide=wide,source=source))
   denied('null-source',error=87)
   denied('bad-source',error=998,source=0x70000000)
   denied('bad-output','C:\\*',998,0x70000000)
   denied('readonly-output','C:\\*',998,0x140003400)
   denied('cross-unmapped-output','C:\\*',998,0x140006fff)
   denied('unsupported-wildcard','C:\\a?')
   denied('nested-root-only','C:\\dir\\*')
   denied('root-no-pattern','C:\\',2)
   denied('trailing-literal-slash','C:\\alpha.txt\\',2)
   denied('missing-literal','C:\\missing',2)
   denied('unicode-case-unproven','C:\\É😀',50,wide=1)
   denied('bad-drive','D:\\*',15)
   denied('device','C:\\NUL',123)
   denied('invalid-UTF16',b'\x00\xd8\x00\x00',1113,wide=1)
   cases.append(dict(name='service-quota',mode=8))
   cases.extend([dict(name='literal-ASCII-fold',mode=13,path='C:\\ALPHA.TXT'),dict(name='literal-Unicode-A',mode=13,path='C:\\é😀',unicode=True),dict(name='literal-Unicode-W',mode=14,path='C:\\é😀',unicode=True),dict(name='literal-ExW-sensitive-basic',mode=15,path='C:\\é😀',unicode=True)])
   cases.extend([dict(name='stale-prior-activation',mode=16),dict(name='FLS-callback-refusal',mode=17)])
   regular=len(cases)
   cases.extend(dict(name=name,mode=mode) for mode,name in [(9,'Storage-revoked'),(10,'Memory-revoked'),(11,'Storage-retargeted'),(12,'Memory-retargeted')])
   cases.extend(dict(name=name,mode=7,path='C:\\*',error=5,trigger=trigger) for trigger,name in [(16,'Memory-after-native-read'),(17,'Storage-after-native-read'),(18,'Memory-retarget-after-native-read'),(19,'Storage-retarget-after-native-read')])
   (out/'cases.json').write_text(json.dumps(cases,indent=2,default=lambda v:v.hex())+'\n')
   for case in cases:
    mode=case['mode']
    wide=mode in [1,2,14,15];width=592 if wide else 320;raw=bytearray(4096);struct.pack_into('<2Q',raw,0,mode,width)
    pattern=((case.get('path') if isinstance(case.get('path'),str) else 'C:\\*')+'\0').encode('utf-16-le' if wide else 'utf-8');raw[256:256+len(pattern)]=pattern
    if mode==7:
     pathvalue=case.get('path');encoded=pathvalue if isinstance(pathvalue,bytes) else (pathvalue+'\0').encode('utf-16-le' if case.get('wide') else 'utf-8') if pathvalue is not None else b''
     raw[256:256+len(encoded)]=encoded
     struct.pack_into('<5Q',raw,16,0x140005100 if pathvalue is not None else case.get('source',0),case['error'],case.get('trigger',0),case.get('output',0),case.get('wide',0))
    for i,(name,size,attributes) in enumerate([('alpha.txt',3,128),('é😀',0,16)]):
     record=bytearray(width);struct.pack_into('<I',record,0,attributes)
     # Native inode fields are ctime,mtime,atime; Windows is creation,access,write.
     c,m,access=times[i*3:i*3+3]
     struct.pack_into('<3Q',record,4,*[(v+11644473600)*10000000 for v in [c,access,m]])
     struct.pack_into('<2I',record,28,size>>32,size&0xffffffff)
     encoded=(name+'\0').encode('utf-16-le' if wide else 'utf-8');record[44:44+len(encoded)]=encoded
     raw[2048+i*1024:2048+i*1024+width]=record
    if mode>=13:
     if case.get('unicode'):raw[2048:2048+width]=raw[3072:3072+width]
     raw[3072:3072+width]=raw[2048:2048+width]
    payload.extend(raw)
   payload=struct.pack('<2Q',len(cases),regular)+payload
   (out/'oracles.bin').write_bytes(payload);report['oracle_sha256']=sha(out/'oracles.bin')
   for at in range(0,len(payload),8):serial.sendall(payload[at:at+8]);until(b'.',10)
   until(b'space> ',240)
   assert b'windows-find: actual A W Ex records EOF stale fault deadline21 cycles PASS' in received
  finally:
   (out/'serial.log').write_bytes(received)
   if serial:serial.close()
   qemu.terminate()
   try:qemu.wait(timeout=5)
   except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
 if a.nvme_disk is not None:
  report['disk_after_sha256']=sha(a.nvme_disk)
  assert b'nvme: storage component ready' in received
  if a.reopen:assert report['disk_before_sha256']==report['disk_after_sha256'],'readonly Find boot changed disk'
 report['rtc_preentry_refusals']=int(re.search(rb'windows-find-clock-refusals: ([0-9]+)',received)[1])
 assert all((ROOT/name).read_bytes()==data for name,data in contents.items()),'source changed'
 assert all(sha(snapshot/name)==value for name,value in compiled_inventory.items()),'compiled source changed'
 assert sha(compiler)==report['compiler_sha256']
 report.update(status='passed',fixture_activations=22*regular+8,cold_preentry_refusals=4,unique_regular_cases=regular,measured_resource_cycles=21,original_windows_application_entries=0)
 print('PASS Windows Find:',22*regular+8,'actual CPL3 fixture activations,21 stable cycles')
except Exception as error:report.update(status='failed',error=str(error));raise
finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
