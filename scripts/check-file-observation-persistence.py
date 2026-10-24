#!/usr/bin/env python3
"""Execute original fbv from native storage across NVMe boots; no ELF loader on reopen."""
import argparse,hashlib,json,struct,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--utc',action='store_true');p.add_argument('--in',dest='compiler',type=Path,required=True);p.add_argument('--app',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();assert not out.exists() or not any(out.iterdir());out.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
compiler=a.compiler.resolve();app=a.app.resolve();disk=out/'owned.raw';sources={str(p):sha(p) for p in [Path(__file__).resolve(),ROOT/'scripts/check-linux-framebuffer.py']};report=dict(status='running',goal_status='OPEN',application_sha256=sha(app),compiler_sha256=sha(compiler),source_sha256=sources,boots=[])
try:
 previous_inode=None
 for stage in range(2):
  boot=out/f'boot-{stage+1}';command=[sys.executable,str(ROOT/'scripts/check-linux-framebuffer.py'),'--in',str(compiler),'--app',str(app),'--out',str(boot),'--file-source','--nvme-disk',str(disk)]
  if stage:command.append('--reopen')
  if a.utc:command.append('--utc')
  with (out/f'boot-{stage+1}.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
  receipt=json.loads((boot/'report.json').read_text());assert receipt['status']=='passed' and receipt['accepted_source_sha256']==sha(app)
  raw=disk.read_bytes();u32=lambda at:struct.unpack_from('<I',raw,at)[0];u64=lambda at:struct.unpack_from('<Q',raw,at)[0];assert (u32(0),u32(4),u32(8))==(0x53504146,2 if a.utc else 1,4096)
  total,table,bitmap=u64(12),u64(40)*4096,u64(24)*4096;root=table+u32(56)*256;block=u64(root+64)*4096;entries={}
  for offset in range(0,u64(root+16),32):
   inode=u32(block+offset)
   if inode:entries[raw[block+offset+8:block+offset+8+raw[block+offset+4]].decode()]=inode
  assert 'fbv-copy' in entries and 'fbv-test.bmp' in entries and 'original-fbv' not in entries
  inode=table+entries['fbv-copy']*256;size=u64(inode+16);assert u32(inode)==1 and u32(inode+4)==0o644 and u32(inode+176)==0 and size==app.stat().st_size
  payload=bytearray();blocks=set()
  for index in range((size+4095)//4096):
   data=u64(inode+64+index*8) if index<12 else u64(u64(inode+160)*4096+(index-12)*8)
   assert u64(48)<=data<total and raw[bitmap+data//8]&(1<<(data&7)) and data not in blocks
   blocks.add(data);payload.extend(raw[data*4096:(data+1)*4096])
  assert hashlib.sha256(payload[:size]).hexdigest()==sha(app)
  original_inode=raw[inode:inode+256]
  if stage:
   assert original_inode==previous_inode,'readonly executable observation changed its inode'
   assert not any(f'loader,file={app},' in arg for arg in receipt['qemu_command']),'reopen staged the original executable again'
   first=json.loads((out/'boot-1/report.json').read_text());assert receipt['source_sha256']==first['source_sha256']
  previous_inode=original_inode;report['boots'].append(dict(command=command,report_sha256=sha(boot/'report.json'),original_activations=receipt['actual_original_activations'],control_activations=receipt['synthetic_control_activations'],accepted_source_sha256=receipt['accepted_source_sha256'],disk_sha256=sha(disk),executable_inode_sha256=hashlib.sha256(original_inode).hexdigest(),screenshot_sha256=receipt['screenshot_sha256']));print('PASS native stored fbv boot',stage+1,flush=True)
 assert all(sha(Path(path))==value for path,value in sources.items()) and sha(compiler)==report['compiler_sha256'] and sha(app)==report['application_sha256']
 report.update(filesystem_version=2 if a.utc else 1,status='passed',actual_nvme_boots=2,actual_original_activations=44,synthetic_control_activations=176,readonly_executable_inode_unchanged=True,reopen_without_executable_loader=True)
except Exception as error:report.update(status='failed',error=str(error));raise
finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
