#!/usr/bin/env python3
"""Exercise relocated supervisor windows and explicit low native VM views; no app credit."""
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
p.add_argument('--out',type=Path,required=True)
p.add_argument('--cpu',choices=['qemu64','max'],default='max')
a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
paths=[ROOT/'boot/multiboot.asm',ROOT/'components/user-context.in',ROOT/'components/domain.in',ROOT/'components/interrupts.in',ROOT/'components/user-address-space.in',ROOT/'components/supervisor-window.in',ROOT/'fixtures/user-space/low.in',ROOT/'fixtures/user-space/low.asm']
hashes={str(x.relative_to(ROOT)):sha(x) for x in paths}
report=dict(status='running',scope=__doc__,source_sha256=hashes,compiler_sha256=sha(a.compiler),cpu=a.cpu)
qemu=None;channel=None;received=bytearray()
try:
 source=(ROOT/'kernel/kernel-root.in').read_text()
 source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(ROOT/m[1])),source)
 source+='\nimport '+json.dumps(str(ROOT/'components/user-address-space.in'))+'\nimport '+json.dumps(str(ROOT/'fixtures/user-space/low.in'))+'\n'
 assert source.count('  shell(port)')==1
 source=source.replace('  shell(port)','  low-view-check(port)\n  shell(port)')
 (out/'kernel.in').write_text(source)
 commands=[['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],['nasm','-f','bin',str(ROOT/'fixtures/user-space/low.asm'),'-o',str(out/'controls.bin')],[str(a.compiler.resolve()),'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')]]
 report['commands']=commands
 with (out/'compile.log').open('w') as log:
  for command in commands:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
 path=out/'serial.sock';command=['qemu-system-x86_64','-kernel',str(out/'kernel.bin'),'-m','512M','-cpu',a.cpu,'-display','none','-no-reboot','-serial','unix:'+str(path)+',server=on,wait=on','-device','loader,file='+str(out/'controls.bin')+',addr=0x10000000,force-raw=on'];report['qemu_command']=command
 with (out/'qemu.log').open('w') as log:qemu=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
 deadline=time.monotonic()+10
 while not path.exists() and time.monotonic()<deadline and qemu.poll() is None:time.sleep(.02)
 channel=socket.socket(socket.AF_UNIX);channel.settimeout(.2);channel.connect(str(path));deadline=time.monotonic()+90
 while b'space interactive shell' not in received and time.monotonic()<deadline:
  try:
   block=channel.recv(65536)
   if not block:break
   received+=block
   (out/'serial.log').write_bytes(received)
   if (b'PANIC' in received or b'fault handler halting' in received) and received.endswith(b'\n'):break
  except socket.timeout:
   if qemu.poll() is not None:break
 text=received.decode(errors='replace')
 assert 'low-view: 80 native CPU activations, 4103 owned pages, low shadow isolation, high denial, null/RX, deadlines and repeated cleanup PASS' in text,text
 assert 'space interactive shell' in text,text
 assert all(sha(ROOT/name)==value for name,value in hashes.items()) and sha(a.compiler)==report['compiler_sha256']
 report.update(status='passed',native_control_entries=80,owned_page_peak=4103,original_application_entries=0,kernel_sha256=sha(out/'kernel.bin'))
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
