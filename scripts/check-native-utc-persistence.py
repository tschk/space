#!/usr/bin/env python3
"""Independent UTC metadata across three real NVMe boots; raw disk byte oracle."""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import re
import selectors
import struct
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();out=a.out.resolve();compiler=a.compiler.resolve()
assert not out.exists() or not any(out.iterdir());out.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=[p for directory in ['components','kernel','protocol','services','fixtures/native-utc-metadata'] for p in (ROOT/directory).rglob('*.in')]+[ROOT/'boot/multiboot.asm',ROOT/'scripts/pack-sci-image.py',Path(__file__).resolve()]
contents={str(p.relative_to(ROOT)):p.read_bytes() for p in files};assert all(p.read_bytes()==contents[str(p.relative_to(ROOT))] for p in files)
snapshot=out/'source'
for name,data in contents.items():
 target=snapshot/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
inventory={name:hashlib.sha256(data).hexdigest() for name,data in contents.items()};(out/'source-hashes.json').write_text(json.dumps(inventory,indent=2)+'\n')
report=dict(status='running',goal_status='OPEN',classification='Native UTC metadata, actual owned NVMe and readonly raw oracle; zero Windows application entries',source_sha256=inventory,compiler_sha256=sha(compiler),boots=[],malformed_controls=[])
disk=out/'owned.raw'
with disk.open('xb') as f:f.truncate(64*1024*1024)
process=None
try:
 subprocess.run(['nasm','-f','bin',str(snapshot/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],check=True,timeout=30)
 with (out/'volume-compile.log').open('w') as log:subprocess.run([str(compiler),'compile','--path',str(snapshot/'components/volume.in'),'--entry','volume-entry','--emit','sci','--base','0x60000000','--target','native','--target-triple','x86_64-unknown-none','--out',str(out/'volume.sci')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)

 previous=None;records=[]
 for stage in range(7):
  boot=out/f'boot-{stage+1}';boot.mkdir()
  bootdisk=disk
  if stage>=3:
   bootdisk=out/f'malformed-{stage-2}.raw'
   with disk.open('rb') as src,bootdisk.open('xb') as dst:
    while chunk:=src.read(65536):
     if chunk==bytes(len(chunk)):dst.seek(len(chunk),1)
     else:dst.write(chunk)
    dst.truncate(disk.stat().st_size)
   changes=[(4,3,4,'unknown-version'),(8,512,4,'wrong-block-size'),(40,1,8,'overlapping-inode-table'),(48,0xFFFFFFFFFFFFFFFF,8,'outside-data-start')]
   offset,value,width,control=changes[stage-3]
   with bootdisk.open('r+b') as f:f.seek(offset);f.write(value.to_bytes(width,'little'))

  source=(snapshot/'kernel/kernel-root.in').read_text();source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(snapshot/m[1])),source)
  source='const FUN-STAGE = '+str(stage)+'\nimport '+json.dumps(str(snapshot/'fixtures/native-utc-metadata/nvme.in'))+'\n'+source
  assert source.count('  shell(port)')==1;source=source.replace('  shell(port)','  native-utc-nvme-check(port)\n  shell(port)');(boot/'kernel.in').write_text(source)
  with (boot/'compile.log').open('w') as log:subprocess.run([str(compiler),'compile','--path',str(boot/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(boot/'kernel.bin')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
  subprocess.run(['python3',str(snapshot/'scripts/pack-sci-image.py'),str(boot/'kernel.bin'),str(boot/'combined.bin'),'254:'+str(out/'volume.sci')],stdout=subprocess.DEVNULL,check=True,timeout=30)
  base=datetime(2026,10,24,tzinfo=timezone.utc)+timedelta(days=stage)
  command=['qemu-system-x86_64','-kernel',str(boot/'combined.bin'),'-m','512M','-cpu','max','-vga','std','-display','none','-no-reboot','-rtc','base='+base.strftime('%Y-%m-%dT%H:%M:%S')+',clock=vm','-serial','stdio','-monitor','none','-drive',f'file={bootdisk},format=raw,if=none,id=owned,cache=writethrough','-device','nvme,drive=owned,serial=space-utc-metadata']
  before=sha(bootdisk);serial=bytearray();process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);select=selectors.DefaultSelector();select.register(process.stdout,selectors.EVENT_READ);deadline=time.monotonic()+60
  try:
   while b'native-utc-nvme: boot PASS\n' not in serial or b'space> ' not in serial:
    assert b'PANIC' not in serial,serial[-2000:]
    assert process.poll() is None and time.monotonic()<deadline,serial[-2000:]
    for key,_ in select.select(.1):
     chunk=key.fileobj.read1(65536);assert chunk;serial.extend(chunk)
  finally:
   process.terminate()
   try:rest,_=process.communicate(timeout=5)
   except subprocess.TimeoutExpired:process.kill();rest,_=process.communicate()
   serial.extend(rest);select.close();process=None;(boot/'serial.log').write_bytes(serial)
  assert b'nvme: storage component ready' in serial and b'PANIC' not in serial
  if stage>=3:
   assert b'native-utc-nvme: malformed volume refused\n' in serial and sha(bootdisk)==before
   report['malformed_controls'].append(dict(control=control,qemu_command=command,kernel_sha256=sha(boot/'kernel.bin'),combined_sha256=sha(boot/'combined.bin'),disk_before_sha256=before,disk_after_sha256=sha(bootdisk)))
   (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(f'PASS UTC NVMe refusal:{control}; disk unchanged',flush=True);continue
  match=re.search(rb'native-utc-nvme: record ([0-9a-f]{256})\n',serial);assert match;record=bytes.fromhex(match[1].decode());records.append(record);(boot/'record.bin').write_bytes(record)
  raw=disk.read_bytes();u32=lambda o:struct.unpack_from('<I',raw,o)[0];u64=lambda o:struct.unpack_from('<Q',raw,o)[0]
  assert (u32(0),u32(4),u32(8))==(0x53504146,2,4096)
  total,count,table=u64(12),u32(20),u64(40);assert total==16384 and count==2048 and table*4096+count*256<len(raw)
  identity=struct.unpack_from('<Q',record,40)[0];inode=identity-1;assert 0<inode<count;at=table*4096+inode*256
  assert u32(at)==1 and u32(at+4)==0o644 and u64(at+16)==8 and u32(at+176)==1
  expected=b'boot-one' if stage==0 else b'boot-two';assert raw[at+64:at+72]==expected
  times=(u64(at+32),u64(at+48),u64(at+40));assert times==struct.unpack_from('<3Q',record,96)
  first=int(datetime(2026,10,24,tzinfo=timezone.utc).timestamp());assert first<=times[0]<=first+60
  sample=first if stage==0 else first+86400;assert all(sample<=t<=sample+60 for t in times[1:])
  if previous is not None:
   assert times[0]==previous[0]
   assert raw[65536*512:65536*512+4096]==raw[:4096],'Volume probe must see the actual UTC header at its own reserved backing offset'
   assert b'volume: unsupported backing refused before activation' in serial and b'native-utc-nvme: Volume v2 denial stable ownership' in serial
  if stage==2:assert records[2]==records[1] and sha(disk)==before,'readonly reboot changed record/disk bytes'
  previous=times
  report['boots'].append(dict(stage=stage+1,qemu_command=command,kernel_sha256=sha(boot/'kernel.bin'),combined_sha256=sha(boot/'combined.bin'),disk_before_sha256=before,disk_after_sha256=sha(disk),record_sha256=sha(boot/'record.bin'),timestamps=times,payload_sha256=hashlib.sha256(expected).hexdigest()))
  (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(f'PASS UTC NVMe boot{stage+1}: raw inode/content/epoch verified',flush=True)
 assert all((ROOT/name).read_bytes()==data for name,data in contents.items()),'source changed';assert sha(compiler)==report['compiler_sha256']
 report.update(status='passed',actual_nvme_boots=7,valid_metadata_boots=3,malformed_refusal_boots=4,readonly_complete_disk_unchanged=True)
except Exception as error:report.update(status='failed',error=str(error));raise
finally:
 if process:process.kill();process.wait()
 (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
