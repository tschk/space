#!/usr/bin/env python3
"""Boot the actual native EOF/discard descriptor implementation without storage."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();a.out=a.out.resolve();a.compiler=a.compiler.resolve()
if a.out.exists() and any(a.out.iterdir()):p.error('--out must be new or empty')
a.out.mkdir(parents=True,exist_ok=True)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
tracked=[ROOT/'components/vfs.in',ROOT/'components/sci-loader.in',ROOT/'kernel/kernel-root.in',ROOT/'fixtures/vfs-discard/check.in',Path(__file__).resolve()]
hashes={str(path.relative_to(ROOT)):sha(path) for path in tracked}
base=(ROOT/'kernel/kernel-root.in').read_text()
base=re.sub(r'import "\.\./([^\"]+)"',lambda m:'import '+json.dumps(str(ROOT/m.group(1))),base)
base='import '+json.dumps(str(ROOT/'fixtures/vfs-discard/check.in'))+'\n'+base
assert base.count('  shell(port)')==1
base=base.replace('  shell(port)','''  if dyn-kernel-exportable("vfs-discard-open") != 0 || dyn-kernel-exportable("vfs-discard-stat") != 0 || dyn-kernel-exportable("vfs-dup-file-into") != 0 || dyn-resolve-idx("vfs-discard-open") != -1 || dyn-resolve-idx("vfs-dup-file-into") != -1 { panic("discard raw native provider exported") }
  discard-runtime-proof(port)''')
(a.out/'kernel.in').write_text(base)
report={'status':'running','compiler':str(a.compiler),'compiler_sha256':sha(a.compiler),'source_sha256':hashes}
try:
 subprocess.run(['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(a.out/'trampoline.bin')],check=True,timeout=30)
 command=[str(a.compiler),'compile','--path',str(a.out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(a.out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(a.out/'kernel.bin')]
 report['compile_command']=command
 with (a.out/'compile.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
 command=['qemu-system-x86_64','-kernel',str(a.out/'kernel.bin'),'-m','512M','-display','none','-no-reboot','-serial','file:'+str(a.out/'serial.log'),'-device','isa-debug-exit,iobase=0xf4,iosize=0x04']
 report['qemu_command']=command
 with (a.out/'qemu.log').open('w') as log:result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=60)
 serial=(a.out/'serial.log').read_text()
 assert result.returncode==33 and 'discard: result 42' in serial and 'discard: actual native EOF sink lifetime PASS' in serial,serial[-5000:]
 report['source_changed_during_run']=[name for name,digest in hashes.items() if sha(ROOT/name)!=digest]
 assert not report['source_changed_during_run'],report['source_changed_during_run']
 report.update(status='passed',kernel_sha256=sha(a.out/'kernel.bin'))
 print('PASS actual QEMU native EOF/discard, stat, shared descriptions, full-pool replacement and 63-cycle no heap/reference drift',flush=True)
except Exception as error:
 report.update(status='failed',error=str(error));print('FAIL:',error,flush=True)
finally:(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='passed' else 1)
