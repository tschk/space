#!/usr/bin/env python3
"""Boot the native HPET provider and prove hardware progress with IRQs masked."""
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
tracked=[ROOT/'components/counter.in',ROOT/'kernel/kernel-root.in',ROOT/'boot/multiboot.asm',ROOT/'components/sci-loader.in',ROOT/'components/object.in',ROOT/'components/memory.in',ROOT/'components/time.in',Path(__file__).resolve()]
hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in tracked}
base=(ROOT/'kernel/kernel-root.in').read_text()
base=re.sub(r'import "\.\./([^\"]+)"',lambda m:'import '+json.dumps(str(ROOT/m.group(1))),base)
if 'counter.in' not in base:base='import '+json.dumps(str(ROOT/'components/counter.in'))+'\n'+base
if '  counter-init(mb-info)' not in base:base=base.replace('  discover-memory(mb-info)','  discover-memory(mb-info)\n  counter-init(mb-info)')
assert base.count('  shell(port)')==1
base=base.replace('  shell(port)','  counter-hardware-proof(port)\n  shell(port)')
base+='''
fn counter-hardware-proof(port:Int)->void{
 let flags=invoke1(load64(0x4198),0);
 let timer=cap-mint(root-realm,cap-timer());let wrong=cap-mint(root-realm,cap-serial());
 if timer<0 || wrong<0{panic("counter test authority unavailable");}
 let heap=heap-next;let caps=cap-count;
 cli();let tick=ticks;
 if (invoke1(load64(0x4198),0)&512)!=0{panic("counter proof interrupts not masked");}
 if EXPECT==1{
  if counter-ready!=1 || counter-base!=0xFED00000 || counter-rsdp==0 || counter-hpet-table==0{panic("actual HPET ACPI discovery failed");}
  let hz=counter-frequency();let period=(load64(counter-base)>>32)&0xFFFFFFFF;
  if hz<=0 || period<=0 || 1000000000000000%period!=0 || hz!=1000000000000000/period{panic("counter hardware frequency is not exact");}
  let first=counter-read();let last=first;let read=0;
  if first<0{panic("counter initial read unavailable");}
  while read<10000{let next=counter-read();if next<last{panic("counter went backwards");}last=next;read=read+1;}
  if last<=first || ticks!=tick || (invoke1(load64(0x4198),0)&512)!=0{panic("counter did not progress independently of IRQ ticks");}
  if counter-frequency-authorized(timer)!=hz || counter-read-authorized(timer)<last{panic("counter borrowed timer authority failed");}
  let published=counter-last;
  if counter-read-authorized(-1)!=-13 || counter-frequency-authorized(wrong)!=-13 || counter-last!=published{panic("counter denied call touched hardware state");}
  let registry-read=dyn-resolve-idx("counter-service-read");let registry-frequency=dyn-resolve-idx("counter-service-frequency");
  if registry-read<0 || registry-frequency<0 || dyn-resolve-idx("counter-read")!=-1 || dyn-resolve-idx("counter-init")!=-1 || dyn-resolve-idx("counter-read-authorized")!=-1{panic("counter actual native import registry mismatch");}
  let caller=current-cap;current-cap=wrong;
  let denied=invoke1(load64(dyn-fn-tab+registry-read*8),0);current-cap=timer;
  let granted=invoke1(load64(dyn-fn-tab+registry-frequency*8),0);current-cap=caller;
  if denied!=-13 || granted!=hz{panic("counter native current grant mismatch");}
  cap-revoke(timer);published=counter-last;
  if counter-read-authorized(timer)!=-13 || counter-last!=published{panic("counter live revocation failed");}
  serial-write-cstr(port,"counter-hardware: Hz ");serial-write-dec-wide(port,hz);serial-write-cstr(port," period-fs ");serial-write-dec-wide(port,period);
  serial-write-cstr(port," delta ");serial-write-dec-wide(port,last - first);serial-nl(port);
 }else{
  if counter-ready!=0 || counter-frequency()!=-1 || counter-read()!=-1 || counter-read-authorized(timer)!=-1{panic("counter absent hardware fabricated success");}
  cap-revoke(timer);
 }
 if dyn-kernel-exportable("counter-init")!=0 || dyn-kernel-exportable("counter-read")!=0 || dyn-kernel-exportable("counter-read-authorized")!=0 || dyn-kernel-exportable("counter-memory-map")!=0 || dyn-kernel-exportable("counter-service-read")!=1 || dyn-kernel-exportable("counter-service-frequency")!=1{panic("counter private helper registry exposed");}
 if heap-next!=heap || cap-count!=caps{panic("counter read resources grew");}
 if time-wallclock()<0{panic("counter changed independent RTC service");}
 cap-revoke(wrong);
 if (flags&512)!=0{
  sti();
  if EXPECT==1{
   let next=counter-read();
   if next<0 || (invoke1(load64(0x4198),0)&512)==0{panic("counter native IF1 caller state not restored");}
  }
 }
 serial-write-cstr(port,"counter-hardware: actual IF0 monotonic HPET or explicit absence and scoped authority PASS");serial-nl(port);
 outb(0xF4,16);
}
'''
report={'status':'running','compiler':str(a.compiler),'compiler_sha256':hashlib.sha256(a.compiler.read_bytes()).hexdigest(),'source_sha256':hashes,'boots':[]}
try:
 subprocess.run(['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(a.out/'trampoline.bin')],check=True,timeout=30)
 for name,machine,expect in [('pc','pc',1),('q35','q35',1),('no-hpet','pc,hpet=off',0)]:
  target=a.out/name;target.mkdir();(target/'kernel.in').write_text(base.replace('EXPECT',str(expect)))
  command=[str(a.compiler),'compile','--path',str(target/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(a.out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(target/'kernel.bin')]
  with (target/'compile.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
  command=['qemu-system-x86_64','-machine',machine,'-kernel',str(target/'kernel.bin'),'-m','512M','-display','none','-no-reboot','-serial','file:'+str(target/'serial.log'),'-device','isa-debug-exit,iobase=0xf4,iosize=0x04']
  with (target/'qemu.log').open('w') as log:result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=60)
  serial=(target/'serial.log').read_text()
  assert result.returncode==33 and 'counter-hardware: actual IF0 monotonic HPET or explicit absence and scoped authority PASS' in serial,serial
  samples=re.findall(r'counter-hardware: Hz (\d+) period-fs (\d+) delta (\d+)',serial)
  assert bool(samples)==bool(expect),serial
  for hz,period,delta in samples:assert int(hz)*int(period)==10**15 and int(delta)>0
  report['boots'].append({'name':name,'status':'passed','available':bool(expect),'samples':samples,'command':command,'kernel_sha256':hashlib.sha256((target/'kernel.bin').read_bytes()).hexdigest()})
  print(f'PASS {name}: actual HPET IF0 advance and exact Hz' if expect else 'PASS no-hpet: explicit unavailable; independent RTC retained',flush=True)
 report['source_changed_during_run']=[name for name,digest in hashes.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest]
 report['status']='passed'
except Exception as error:
 report.update(status='failed',error=str(error));print('FAIL:',error,flush=True)
finally:(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='passed' else 1)
