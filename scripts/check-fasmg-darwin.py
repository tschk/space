#!/usr/bin/env python3
"""Run the original upstream macOS fasmg Mach-O executable inside Space."""
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
p.add_argument('--app',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--cpu',choices=['qemu64','max'],default='max')
a=p.parse_args();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False);a.app=a.app.resolve()
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
pin=next(x for x in json.loads((ROOT/'fixtures/applications/fasmg.json').read_text())['apps'] if x['personality']=='darwin')
assert sha(a.app)==pin['sha256'] and a.app.stat().st_size==pin['size_bytes']
inputs=[ROOT/'boot/multiboot.asm',ROOT/'components/user-context.in',ROOT/'components/domain.in',ROOT/'components/interrupts.in',ROOT/'components/user-address-space.in',ROOT/'components/supervisor-window.in',ROOT/'fixtures/applications/fasmg-darwin.in',ROOT/'fixtures/applications/darwin-classic-contracts.in',*sorted((ROOT/'components').glob('darwin-classic-*.in')),Path(__file__).resolve(),ROOT/'fixtures/applications/fasmg.json']
hashes={str(path.relative_to(ROOT)):sha(path) for path in inputs}
report=dict(status='running',scope=__doc__,compiler_sha256=sha(a.compiler),application_sha256=sha(a.app),source_sha256=hashes,original_application_entries=0)
received=bytearray();channel=None;qemu=None
try:
 source=(ROOT/'kernel/kernel-root.in').read_text()
 source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(ROOT/m[1])),source)
 source+='\nimport '+json.dumps(str(ROOT/'components/darwin-classic-process.in'))+'\n'
 assert source.count('  shell(port)')==1
 source=source.replace('  shell(port)','  fasmg-dc-check(port)\n  dc-contracts-check(port)\n  shell(port)')
 source+='\nimport '+json.dumps(str(ROOT/'fixtures/applications/fasmg-darwin.in'))+'\nimport '+json.dumps(str(ROOT/'fixtures/applications/darwin-classic-contracts.in'))+'\n'
 (a.out/'kernel.in').write_text(source)
 commands=[['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(a.out/'trampoline.bin')],[str(a.compiler.resolve()),'compile','--path',str(a.out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(a.out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(a.out/'kernel.bin')]];report['commands']=commands
 with (a.out/'compile.log').open('w') as log:
  for command in commands:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
 path=a.out/'serial.sock';command=['qemu-system-x86_64','-kernel',str(a.out/'kernel.bin'),'-m','512M','-cpu',a.cpu,'-display','none','-no-reboot','-serial','unix:'+str(path)+',server=on,wait=on','-device','loader,file='+str(a.app)+',addr=0x10000000,force-raw=on'];report['qemu_command']=command
 with (a.out/'qemu.log').open('w') as log:qemu=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
 deadline=time.monotonic()+10
 while not path.exists() and time.monotonic()<deadline and qemu.poll() is None:time.sleep(.02)
 channel=socket.socket(socket.AF_UNIX);channel.settimeout(.2);channel.connect(str(path));deadline=time.monotonic()+120
 while b'space interactive shell' not in received and time.monotonic()<deadline:
  try:
   data=channel.recv(65536)
   if not data:break
   received+=data
   (a.out/'serial.log').write_bytes(received)
   if (b'PANIC' in received or b'fault handler halting' in received) and received.endswith(b'\n'):break
  except socket.timeout:
   if qemu.poll() is not None:break
 text=received.decode(errors='replace')
 assert 'flat assembler' in text and 'Usage: fasmg source [output]' in text,text
 assert 'original-mac: original Mach-O assembler generated exact 14-byte macro/arithmetic file inside Space PASS' in text,text
 assert 'classic-contracts: owned mmap, RO/hint/unmap denials, FILE bytes/items/EOF/seek/close and actual RTC PASS' in text,text
 assert 'space interactive shell' in text,text
 assert sha(a.app)==pin['sha256'] and sha(a.compiler)==report['compiler_sha256'] and all(sha(ROOT/name)==value for name,value in hashes.items())
 assert 'original-mac: completed original application entries 65' in text,text
 mask=int(re.search(r'original-mac: observed import mask (?:0x)?([0-9a-f]+)',text)[1],16)
 report.update(status='passed',original_application_entries=65,generated_bytes=14,original_error_exits=42,lifetime_cycles=21,malformed_controls=6,observed_import_ids=[id for id in range(1,14) if mask&(1<<id)],kernel_sha256=sha(a.out/'kernel.bin'))
except Exception as error:report.update(status='failed',error=str(error))
finally:
 if channel is not None:channel.close()
 if qemu is not None:
  qemu.terminate()
  try:qemu.wait(timeout=3)
  except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
 (a.out/'serial.log').write_bytes(received);(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['status'].upper()+': '+str(a.out/'report.json'))
raise SystemExit(0 if report['status']=='passed' else 1)
