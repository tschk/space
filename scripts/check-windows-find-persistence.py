#!/usr/bin/env python3
"""Real PE Find imports across an owned NVMe reboot, with raw inode/time oracles."""
import argparse,hashlib,json,struct,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--in',dest='compiler',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();assert not out.exists() or not any(out.iterdir());out.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sources={str(p):sha(p) for p in [Path(__file__).resolve(),ROOT/'scripts/check-windows-find.py']}
compiler=a.compiler.resolve();disk=out/'owned.raw';report=dict(source_sha256=sources,status='running',goal_status='OPEN',boots=[],compiler_sha256=sha(compiler),original_windows_application_entries=0)
try:
 previous=None
 for stage in range(2):
  boot=out/f'boot-{stage+1}';command=[sys.executable,str(ROOT/'scripts/check-windows-find.py'),'--in',str(compiler),'--out',str(boot),'--nvme-disk',str(disk)]
  if stage:command.append('--reopen')
  with (out/f'boot-{stage+1}.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
  receipt=json.loads((boot/'report.json').read_text());assert receipt['status']=='passed';raw=disk.read_bytes();u32=lambda at:struct.unpack_from('<I',raw,at)[0];u64=lambda at:struct.unpack_from('<Q',raw,at)[0]
  assert (u32(0),u32(4),u32(8),u64(12),u32(20))==(0x53504146,2,4096,16384,2048)
  table=u64(40)*4096;root=table+u32(56)*256;block=u64(root+64)*4096;directory_size=u64(root+16);entries={}
  for offset in range(0,directory_size,32):
   inode=u32(block+offset)
   if inode:entries[raw[block+offset+8:block+offset+8+raw[block+offset+4]].decode()]=inode
  assert set(entries)=={'alpha.txt','é😀'},entries
  times=[]
  for name,kind,size in [('alpha.txt',1,3),('é😀',2,0)]:
   at=table+entries[name]*256;assert u32(at)==kind and u64(at+16)==size and u32(at+4)==(0o644 if kind==1 else 0o755)
   times.extend([u64(at+32),u64(at+40),u64(at+48)])
   if kind==1:assert raw[at+64:at+67]==b'abc' and u32(at+176)==1
  assert times==receipt['native_utc_seconds'];assert times[0]<times[1]<times[2]
  if stage:assert previous==sha(disk) and times==report['boots'][0]['timestamps']
  if stage:assert receipt['source_sha256']==json.loads((out/'boot-1/report.json').read_text())['source_sha256'],'sources differ across boots'
  previous=sha(disk);report['boots'].append(dict(command=command,report_sha256=sha(boot/'report.json'),fixture_activations=receipt['fixture_activations'],disk_sha256=previous,timestamps=times));print('PASS Find NVMe boot',stage+1,flush=True)
 assert all(sha(Path(name))==value for name,value in sources.items()),'checker changed'
 assert sha(compiler)==report['compiler_sha256']
 report.update(status='passed',actual_nvme_boots=2,fixture_activations=sum(b['fixture_activations'] for b in report['boots']),readonly_reboot_complete_disk_unchanged=True)
except Exception as error:report.update(status='failed',error=str(error));raise
finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
