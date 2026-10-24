#!/usr/bin/env python3
"""Original fbv, BusyBox and Lua from native NVMe files across two protected boots."""
import argparse,hashlib,json,re,socket,struct,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--in',dest='compiler',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--utc',action='store_true')
for name in ['fbv','busybox','lua']:p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();out=a.out.resolve();compiler=a.compiler.resolve();assert not out.exists() or not any(out.iterdir());out.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
subprocess.run(['nasm','-f','elf64',str(ROOT/'fixtures/file-observation/named.asm'),'-o',str(out/'named.o')],check=True,timeout=30)
subprocess.run(['ld','-static','-z','noexecstack','-o',str(out/'named.elf'),str(out/'named.o')],check=True,timeout=30)
apps=[];payload=struct.pack('<2Q',3,(out/'named.elf').stat().st_size).ljust(4096,b'\0')
for i,(name,version,argv) in enumerate([('fbv','1.1',['fbv','--help']),('busybox','1.36.1',['busybox','echo','stored-file']),('lua','5.4.7',['lua','-v'])]):
 app=getattr(a,name).resolve();manifest=ROOT/f'fixtures/applications/{name}-{version}.json';data=json.loads(manifest.read_text());assert sha(app)==data['apps'][0]['sha256'] and app.stat().st_size==data['apps'][0]['size_bytes']
 reference=subprocess.run(argv,executable=str(app),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=True,timeout=10).stdout;assert len(reference)<7168
 raw=bytearray(8192);struct.pack_into('<4Q',raw,0,app.stat().st_size,len(argv),len(reference),0);path=f'/stored-{name}'.encode()+b'\0';raw[64:64+len(path)]=path
 for j,arg in enumerate(argv):encoded=arg.encode()+b'\0';raw[256+j*256:256+j*256+len(encoded)]=encoded
 raw[1024:1024+len(reference)]=reference;payload+=raw;apps.append(dict(name=name,path=str(app),sha256=sha(app),size=app.stat().st_size,argv=argv,reference_sha256=hashlib.sha256(reference).hexdigest(),reference_bytes=len(reference)))
(out/'oracles.bin').write_bytes(payload)
files=[p for d in ['components','kernel','protocol','services','fixtures/file-observation'] for p in (ROOT/d).rglob('*.in')]+[ROOT/'boot/multiboot.asm',ROOT/'fixtures/file-observation/named.asm',Path(__file__).resolve()]+[ROOT/f'fixtures/applications/{name}-{version}.json' for name,version in [('fbv','1.1'),('busybox','1.36.1'),('lua','5.4.7')]]
contents={str(p.relative_to(ROOT)):p.read_bytes() for p in files};snapshot=out/'source'
for name,data in contents.items():target=snapshot/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
original=snapshot/'components/linux-process.in';canonical=original.read_text();needle='domain-user-syscall-hook = linux-process-dispatch';assert canonical.count(needle)==1;compiled=canonical.replace(needle,'domain-user-syscall-hook = fsa-dispatch');original.write_text(compiled);assert compiled.replace('domain-user-syscall-hook = fsa-dispatch',needle)==canonical
inventory={k:hashlib.sha256(v).hexdigest() for k,v in contents.items()};compiled_inventory={k:sha(snapshot/k) for k in contents}
report=dict(status='running',goal_status='OPEN',filesystem_version=2 if a.utc else 1,applications=apps,compiler_sha256=sha(compiler),source_sha256=inventory,compiled_source_sha256=compiled_inventory,boots=[],oracle_sha256=sha(out/'oracles.bin'),test_hook='one actual protected dispatcher installation; exact reverse verified')
disk=out/'owned.raw'
with disk.open('xb') as f:f.truncate(64*1024*1024)
try:
 subprocess.run(['nasm','-f','bin',str(snapshot/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],check=True,timeout=30)
 for stage in range(2):
  boot=out/f'boot-{stage+1}';boot.mkdir();source=(snapshot/'kernel/kernel-root.in').read_text();source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(snapshot/m[1])),source)
  source=f'const FSA-REOPEN = {stage}\nconst FSA-UTC = {int(a.utc)}\nimport '+json.dumps(str(snapshot/'fixtures/file-observation/apps.in'))+'\n'+source;assert source.count('  shell(port)')==1;source=source.replace('  shell(port)','  file-apps-check(port)\n  shell(port)');(boot/'kernel.in').write_text(source)
  with (boot/'compile.log').open('w') as log:subprocess.run([str(compiler),'compile','--path',str(boot/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(boot/'kernel.bin')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
  command=['qemu-system-x86_64','-kernel',str(boot/'kernel.bin'),'-m','512M','-cpu','max','-display','none','-no-reboot','-serial',f'unix:{boot}/serial.sock,server=on,wait=on','-monitor',f'unix:{boot}/monitor.sock,server=on,wait=off','-rtc','base=2026-10-'+('24' if stage==0 else '25')+'T00:00:00,clock=vm','-drive',f'file={disk},format=raw,if=none,id=owned,cache=writethrough','-device','nvme,drive=owned,serial=space-file-apps','-device',f'loader,file={out}/oracles.bin,addr=0x13000000,force-raw=on']
  if stage==0:
   command.extend(['-device',f'loader,file={out}/named.elf,addr=0x17000000,force-raw=on'])
   for i,app in enumerate(apps):command.extend(['-device',f'loader,file={app["path"]},addr={0x14000000+i*0x1000000:#x},force-raw=on'])
  before=sha(disk);received=bytearray();serial=None;monitor=None
  def connect(path):
   deadline=time.monotonic()+10
   while time.monotonic()<deadline:
    sock=socket.socket(socket.AF_UNIX);sock.settimeout(.2)
    try:sock.connect(str(path));return sock
    except (FileNotFoundError,ConnectionRefusedError):sock.close();time.sleep(.02)
   raise AssertionError('socket readiness')
  with (boot/'qemu.log').open('w') as log:
   qemu=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
   try:
    serial=connect(boot/'serial.sock');monitor=connect(boot/'monitor.sock')
    def wait(marker):
     deadline=time.monotonic()+120
     matches=lambda:marker.search(received) if hasattr(marker,'search') else marker in received
     while not matches():
      assert qemu.poll() is None and time.monotonic()<deadline,received[-3000:]
      if b'PANIC' in received:raise AssertionError(received[-3000:])
      try:
       block=serial.recv(65536);assert block;received.extend(block);(boot/'serial.log').write_bytes(received)
      except socket.timeout:pass
     return matches()
    for i,app in enumerate(apps):
     match=wait(re.compile(rb'file-apps: accepted '+str(i).encode()+rb' ([0-9]+) ([0-9]+)\n'))
     assert match,received[-500:];pointer,size=map(int,match.groups());assert size==app['size'];capture=boot/f'{app["name"]}.elf';monitor.sendall(f'pmemsave {pointer:#x} {size:#x} {json.dumps(str(capture))}\n'.encode());deadline=time.monotonic()+10
     while (not capture.exists() or capture.stat().st_size!=size) and time.monotonic()<deadline:time.sleep(.02)
     assert sha(capture)==app['sha256'];serial.sendall(b'k')
    wait(b'file-apps: three original programs from native storage, exact output and21 stable cycles PASS\n');wait(b'space> ')
   finally:
    (boot/'serial.log').write_bytes(received)
    if serial:serial.close()
    if monitor:monitor.close()
    qemu.terminate()
    try:qemu.wait(timeout=5)
    except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
  assert b'file-apps: real named argc argv auxv readlink proof and ten preentry refusals PASS' in received
  assert len(re.findall(rb'file-apps: executed [0-9]+ [0-2] [1-9][0-9]*\n',received))==66 and b'PANIC' not in received
  scope=int(re.search(rb'file-apps: actual active-scope refusal pairs ([0-9]+)',received)[1]);assert scope>=66
  after=sha(disk)
  if stage:assert before==after,'readonly original CLI boot changed disk'
  report['boots'].append(dict(qemu_command=command,kernel_sha256=sha(boot/'kernel.bin'),serial_sha256=sha(boot/'serial.log'),actual_original_activations=66,actual_active_scope_refusal_pairs=scope,disk_before_sha256=before,disk_after_sha256=after,reopen_without_executable_loaders=bool(stage)));(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS three stored original apps boot',stage+1,flush=True)
 assert all((ROOT/name).read_bytes()==data for name,data in contents.items()) and all(sha(snapshot/name)==value for name,value in compiled_inventory.items())
 assert sha(compiler)==report['compiler_sha256'] and all(sha(Path(app['path']))==app['sha256'] for app in apps)
 report.update(named_fixture_sha256=sha(out/'named.elf'),actual_named_fixture_entries=2,native_preentry_refusals=20,status='passed',actual_original_activations=132,actual_nvme_boots=2,measured_resource_cycles_per_boot=21,readonly_reboot_complete_disk_unchanged=True)
except Exception as error:report.update(status='failed',error=str(error));raise
finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
