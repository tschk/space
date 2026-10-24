#!/usr/bin/env python3
"""Boot the native RTC service against fixed QEMU UTC hardware clocks."""
import argparse
from datetime import datetime, timezone
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
# Read the immutable owning source once; this tiny hardware bootstrap imports no
# desktop/filesystem/personality policy and performs actual RTC port operations.
provider=(ROOT/'components/time.in').read_text()
(a.out/'time.in').write_text(provider)
source='import '+json.dumps(str(a.out/'time.in'))+'\n'+r'''
fn clock-put(ch:Int)->void {while (inb(0x3fd)&32)==0{pause();}outb(0x3f8,ch);return;}
fn clock-print(text:Int)->void {let i=0;while load8(text+i)!=0{clock-put(load8(text+i));i=i+1;}return;}
fn clock-number(number:Int)->void {if number>=10{clock-number(number/10);}clock-put(48+number%10);return;}
fn clock-sample(value:Int)->void {
 clock-print("time-sample: ");clock-number(value);clock-put(32);
 clock-number(time-component-y);clock-put(32);clock-number(time-component-mo);clock-put(32);
 clock-number(time-component-d);clock-put(32);clock-number(time-component-h);clock-put(32);
 clock-number(time-component-mi);clock-put(32);clock-number(time-component-s);clock-put(10);return;
}
fn clock-fail()->Int {clock-print("time-rtc: FAIL\n");outb(0xf4,0x11);return 1;}
fn clock-check(mb:Int)->Int {
 cli();outb(0x3f9,0);outb(0x3fb,128);outb(0x3f8,3);outb(0x3f9,0);outb(0x3fb,3);outb(0x3fa,0xc7);outb(0x3fc,11);
 let first=time-component-wallclock();
 if first<MIN-TIME || first>MIN-TIME+10{return clock-fail();}
 clock-sample(first);
 let last=first;let reads=0;
 while last - first<2 && reads<2000000 {
  let next=time-component-wallclock();
  if next<0{if time-component-ts!=last{return clock-fail();}reads=reads+1;continue;}
  if next<last || next>first+10{clock-print("progress mismatch: ");clock-sample(next);return clock-fail();}
  last=next;reads=reads+1;
 }
 if last - first<2{clock-print("progress limit: ");clock-sample(last);return clock-fail();}
 clock-sample(last);
 let old=time-component-rtc-read(0x0b);
 outb(0x70,0x0b);outb(0x71,old|128);
 if time-component-wallclock()!=-1 || time-component-ts!=last{return clock-fail();}
 outb(0x70,0x0b);outb(0x71,old);
 clock-print("time-rtc: actual RTC UTC progress coherent sample and SET refusal PASS\n");
 outb(0xf4,0x10);return 0;
}
'''
trampoline=a.out/'trampoline.bin'
subprocess.run(['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(trampoline)],check=True,timeout=30)
report={'status':'running','compiler_sha256':hashlib.sha256(a.compiler.read_bytes()).hexdigest(),'provider_sha256':hashlib.sha256(provider.encode()).hexdigest(),'trampoline_sha256':hashlib.sha256(trampoline.read_bytes()).hexdigest(),'boots':[]}
try:
 for base in ['1970-01-01T00:00:00','2000-02-28T23:59:59','2100-02-28T23:59:59','2026-12-31T23:59:59']:
  target=a.out/base.replace(':','-');target.mkdir()
  epoch=int(datetime.fromisoformat(base).replace(tzinfo=timezone.utc).timestamp())
  fixture=target/'kernel.in';fixture.write_text(source+'\nconst MIN-TIME='+str(epoch)+'\n')
  kernel=target/'kernel.bin'
  command=[str(a.compiler),'compile','--path',str(fixture),'--entry','clock-check','--emit','boot','--trampoline',str(trampoline),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(kernel)]
  with (target/'compile.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
  command=['qemu-system-x86_64','-kernel',str(kernel),'-m','64M','-display','none','-no-reboot','-rtc','base='+base+',clock=vm','-serial','file:'+str(target/'serial.log'),'-device','isa-debug-exit,iobase=0xf4,iosize=0x04']
  with (target/'qemu.log').open('w') as log:result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=45)
  log=(target/'serial.log').read_text()
  assert result.returncode==33 and 'SET refusal PASS' in log,log
  samples=[]
  for match in re.finditer(r'^time-sample: (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)$',log,re.MULTILINE):
   stamp,*fields=map(int,match.groups())
   parsed=datetime.fromtimestamp(stamp,tz=timezone.utc)
   assert fields==[parsed.year,parsed.month,parsed.day,parsed.hour,parsed.minute,parsed.second]
   samples.append(stamp)
  assert len(samples)==2 and epoch<=samples[0]<=epoch+10 and 2<=samples[1]-samples[0]<=10
  report['boots'].append({'base_utc':base,'samples':samples,'passed':True,'kernel_sha256':hashlib.sha256(kernel.read_bytes()).hexdigest(),'command':command})
  (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
  print('PASS: actual RTC '+base+' UTC calendar, clock progress and SET refusal')
 report['source_changed_during_run']=provider!=(ROOT/'components/time.in').read_text()
 report['status']='passed'
except Exception as error:
 report.update(status='failed',error=str(error));raise
finally:
 (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
