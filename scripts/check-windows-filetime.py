#!/usr/bin/env python3
"""Prove protected Windows FILETIME against four real QEMU UTC RTC clocks."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import socket
import struct
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();out=a.out.resolve();a.compiler=a.compiler.resolve()
assert not out.exists() or not any(out.iterdir()),'--out must be new or empty'
out.mkdir(parents=True,exist_ok=True)
def absolute_imports(source):
    return re.sub(r'import "([^"]+)"',lambda m:'import '+json.dumps(str((ROOT/'components'/m.group(1)).resolve())),source)
# Test-only scope: the owning Windows provider still invokes the real native RTC
# service. Counting those calls proves denied buffers/grants do not touch it.
# One supervisor hook can revoke the borrowed grant or set actual RTC SET mode;
# it also inspects the guest's owned frames after dispatch, before teardown.
provider=(ROOT/'components/windows-process-time.in').read_text()
assert provider.count('time-component-wallclock()')==2
(out/'windows-process-time.in').write_text(provider.replace('time-component-wallclock()','windows-time-test-wallclock()'))
parameters=absolute_imports((ROOT/'components/windows-process-parameters.in').read_text())
parameters=parameters.replace(json.dumps(str(ROOT/'components/windows-process-time.in')),json.dumps(str(out/'windows-process-time.in')))
(out/'windows-process-parameters.in').write_text(parameters)
protected=absolute_imports((ROOT/'components/windows-protected.in').read_text())
protected=protected.replace(json.dumps(str(ROOT/'components/windows-process-parameters.in')),json.dumps(str(out/'windows-process-parameters.in')))
assert protected.count('domain-user-syscall-hook = windows-protected-dispatch')==1
protected=protected.replace('domain-user-syscall-hook = windows-protected-dispatch','domain-user-syscall-hook = windows-time-test-dispatch')
(out/'windows-protected.in').write_text(protected)
hub=absolute_imports((ROOT/'components/personality-hub.in').read_text())
hub=hub.replace(json.dumps(str(ROOT/'components/windows-protected.in')),json.dumps(str(out/'windows-protected.in')))
(out/'personality-hub.in').write_text(hub)
source=(ROOT/'kernel/kernel-root.in').read_text()
source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(ROOT/m.group(1))),source)
source=source.replace(json.dumps(str(ROOT/'components/personality-hub.in')),json.dumps(str(out/'personality-hub.in')))
assert source.count('  shell(port)')==1
source=source.replace('  shell(port)','  windows-filetime-check(port)\n  shell(port)')
source+='''
var windows-time-test-samples:Int=0
var windows-time-test-first:Int=0
var windows-time-test-last:Int=0
var windows-time-test-rb:Int=-1
var windows-time-test-observed:Int=0
var windows-time-test-value:Int=0
var windows-time-test-mode:Int=0
var windows-time-test-admission-transients:Int=0
var windows-time-test-runtime-transients:Int=0
fn windows-time-test-wallclock()->Int{
 let value=time-component-wallclock();windows-time-test-samples=windows-time-test-samples+1;
 if windows-time-test-samples==1{windows-time-test-first=value;}
 windows-time-test-last=value;return value;
}
fn windows-time-test-restore()->void{
 if windows-time-test-rb>=0{outb(0x70,0x0b);outb(0x71,windows-time-test-rb);windows-time-test-rb=-1;}
}
fn windows-time-test-dispatch(frame:Int)->Int{
 let num=load64(frame+112);
 if num==0x100100{
  if domain-current!=windows-protected-domain || windows-protected-busy==0{panic("Windows time control wrong owner");}
  if load64(frame+96)==0{cap-revoke(windows-parameters-time-authority);}
  else{windows-time-test-rb=time-component-rtc-read(0x0b);outb(0x70,0x0b);outb(0x71,windows-time-test-rb|128);}
  store64(frame+112,0);return 1;
 }
 let output=load64(frame+96);let control=windows-protected-dispatch(frame);
 if num==0x100011{
  windows-time-test-observed=windows-time-test-observed+1;
  let i=248;while i<280{
   if control==0 || 0x140005000+i<output || 0x140005000+i>=output+8{
    if load8(windows-protected-physical(0x140005000+i))!=90{panic("Windows FILETIME partial/out-of-span write");}
   }i=i+1;
  }
  i=4090;while i<4106{
   if control==0 || 0x140005000+i<output || 0x140005000+i>=output+8{if load8(windows-protected-physical(0x140005000+i))!=90{panic("Windows FILETIME cross-page span corrupted");}}i=i+1;
  }
  i=8186;while i<8192{if load8(windows-protected-physical(0x140005000+i))!=90{panic("Windows FILETIME crossing write");}i=i+1;}
  if control!=0{
   windows-time-test-value=windows-protected-load64(output);
   if windows-time-test-value!=(windows-time-test-last+11644473600)*10000000{panic("Windows FILETIME native conversion mismatch");}
   if windows-time-test-mode==0{
    serial-write-cstr(com1(),"windows-time-sample: ");serial-write-dec-wide(com1(),windows-time-test-last);serial-put(com1(),32);serial-write-dec-wide(com1(),windows-time-test-value);serial-nl(com1());
   }
  }
 }
 return control;
}
fn windows-time-test-free()->Int{let n=0;let f=free-list;while f!=0 && n<4096{n=n+1;f=load64(f);}return n;}
fn windows-time-test-reset()->void{windows-time-test-samples=0;windows-time-test-observed=0;windows-time-test-value=0;}
fn windows-time-test-refuse(image:Int,timer:Int,line:Int,bytes:Int,expected:Int,samples:Int)->void{
 windows-time-test-reset();let heap=heap-next;let free=free-list;let domains=domain-count;let owned=domain-user-owned;let stamp=time-component-ts;
 let result=windows-command-time-run(image,7168,-1,-1,timer,line,bytes);
 if result!=expected || windows-time-test-samples!=samples || windows-time-test-observed!=0 || heap-next!=heap || free-list!=free || domain-count!=domains || domain-user-owned!=owned || time-component-ts!=stamp{panic("Windows time admission refusal changed state");}
 if windows-parameters-time-active!=0 || windows-parameters-time-authority!=-1 || windows-parameters-time-anchor!=0{panic("Windows time refusal retained authority");}
}
fn windows-time-test-run(image:Int,timer:Int,line:Int,bytes:Int)->Int{
 let attempt=0;
 while attempt<32{
  windows-time-test-reset();let heap=heap-next;let free=free-list;let domains=domain-count;let owned=domain-user-owned;let stamp=time-component-ts;
  let result=windows-command-time-run(image,7168,-1,-1,timer,line,bytes);windows-time-test-restore();
  if result==-11{
   if windows-time-test-samples!=1 || windows-time-test-observed!=0 || heap-next!=heap || free-list!=free || domain-count!=domains || domain-user-owned!=owned || time-component-ts!=stamp{panic("Transient RTC admission mutated activation");}
   windows-time-test-admission-transients=windows-time-test-admission-transients+1;
  }else{
   if result!=125 || (windows-time-test-mode!=0 && windows-time-test-mode!=5 && windows-time-test-mode!=8 && windows-time-test-mode!=10){return result;}
   if windows-time-test-samples!=2 || windows-time-test-observed!=1 || windows-time-test-last!=-1 || time-component-ts!=windows-time-test-first{panic("Natural RTC failure returned a fake sample");}
   windows-time-test-runtime-transients=windows-time-test-runtime-transients+1;
  }
  if windows-parameters-time-active!=0 || windows-parameters-time-authority!=-1 || windows-parameters-time-anchor!=0 || windows-protected-busy!=0 || windows-protected-count!=0 || user-budget-active!=0 || domain-current!=0 || domain-user-syscall-hook!=0{panic("Transient RTC failure leaked scope");}
  attempt=attempt+1;pause();
 }
 panic("Bounded coherent RTC retry exhausted");return -11;
}
fn windows-filetime-check(port:Int)->void{
 let image=0x10000000;if heap-next>=image{panic("Windows time staging collides with heap");}heap-end=image;
 let initial=time-component-wallclock();let minimum=load64(image+5128)/10000000 - 11644473600;
 if initial<minimum || initial>minimum+60{panic("Windows time fixed RTC base mismatch");}
 let timer=cap-mint(root-realm,cap-timer());let weak=cap-mint(root-realm,cap-serial());let revoked=cap-mint(root-realm,cap-timer());cap-revoke(revoked);
 let line="sqlite3.exe -version";let bytes=strlen(line)+1;
 if windows-command-run(image,7168,-1,-1,line,bytes)!=-8 || windows-startup-entry(image,7168)!=-8 || windows-application-entry(image,7168)!=-8{panic("Existing Windows profiles widened time imports");}
 windows-time-test-rb=time-component-rtc-read(0x0b);outb(0x70,0x0b);outb(0x71,windows-time-test-rb|128);
 windows-time-test-refuse(image,-1,line,bytes,-13,0);windows-time-test-refuse(image,weak,line,bytes,-13,0);windows-time-test-refuse(image,revoked,line,bytes,-13,0);
 windows-time-test-refuse(image,timer,line,0,-22,0);
 let old=load32(image);store32(image,0);windows-time-test-refuse(image,timer,line,bytes,-8,0);store32(image,old);
 windows-time-test-refuse(image,timer,line,bytes,-11,1);windows-time-test-restore();
 let caller-fs=rdmsr(0xc0000100);let caller-gs=rdmsr(0xc0000101);
 wrmsr64(0xc0000100,0x140005000);wrmsr64(0xc0000101,0x23456000);
 let cycle=0;let heap=0;let free=0;let domains=0;let caps=cap-count;
 while cycle<21{
  let mode=0;while mode<11{
   if mode!=7{
    store64(image+5120,mode);windows-time-test-mode=mode;windows-time-test-reset();if mode==8{windows-protected-budget=10;}
    let status=windows-time-test-run(image,timer,line,bytes);windows-protected-budget=100;windows-time-test-restore();
    let expected=42;if mode>=1 && mode<=4{expected=142;}if mode==6{expected=125;}if mode==8{expected=124;}if mode==9{expected=142;}
    let samples=1;if mode==0 || mode==5 || mode==6 || mode==8 || mode==10{samples=2;}
    if status!=expected || windows-time-test-samples!=samples || windows-time-test-observed!=1{serial-write-dec-wide(port,mode);serial-write-dec-wide(port,status);panic("Windows FILETIME result/sample mismatch");}
    if mode==6 || mode==9{if time-component-ts!=windows-time-test-first{panic("Unavailable RTC published stale/fake value");}}
    if rdmsr(0xc0000100)!=0x140005000 || rdmsr(0xc0000101)!=0x23456000 || windows-protected-count!=0 || windows-protected-busy!=0 || windows-protected-profile!=0 || domain-current!=0 || user-budget-active!=0 || domain-user-syscall-hook!=0 || cap-count!=caps{panic("Windows FILETIME execution scope leaked");}
    if windows-parameters-active!=0 || windows-parameters-time-active!=0 || windows-parameters-time-authority!=-1 || windows-parameters-time-anchor!=0 || cap-check(timer,cap-timer())==0{panic("Windows FILETIME borrowed grant leaked/revoked");}
   }mode=mode+1;
  }
  if cycle==0{heap=heap-next;free=windows-time-test-free();domains=domain-count;}
  else{if heap-next!=heap || windows-time-test-free()!=free || domain-count!=domains{panic("Windows FILETIME repeated cleanup leak");}}
  cycle=cycle+1;
 }
 store64(image+5120,7);windows-time-test-mode=7;windows-time-test-reset();
 if windows-command-time-run(image,7168,-1,-1,weak,line,bytes)!=-13 || windows-time-test-samples!=0{panic("Windows weak timer grant acquired clock");}
 let live=cap-mint(root-realm,cap-timer());
 if windows-time-test-run(image,live,line,bytes)!=126 || cap-check(live,cap-timer())!=0 || windows-time-test-samples!=1 || windows-time-test-observed!=1{panic("Windows live timer revoke did not stop void API");}
 store64(image+5120,0);windows-time-test-mode=0;windows-time-test-reset();
 if windows-time-test-run(image,timer,line,bytes)!=42 || windows-time-test-samples!=2 || windows-time-test-observed!=1{panic("Windows fresh clock after terminal failure failed");}
 if heap-next!=heap || windows-time-test-free()!=free || domain-count!=domains{panic("Windows FILETIME revoke/fresh cleanup leak");}
 wrmsr64(0xc0000100,caller-fs);wrmsr64(0xc0000101,caller-gs);cap-revoke(timer);cap-revoke(weak);
 serial-write-cstr(port,"windows-time-transients: ");serial-write-dec-wide(port,windows-time-test-admission-transients);serial-put(port,32);serial-write-dec-wide(port,windows-time-test-runtime-transients);serial-nl(port);
 serial-write-cstr(port,"windows-filetime: 212 execution cases real RTC conversion pointer grant live revoke SET terminal failure no partial writes stable cleanup PASS");serial-nl(port);
}
'''
(out/'kernel.in').write_text(source)
commands=[['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],['nasm','-f','bin',str(ROOT/'fixtures/windows-protected/filetime.asm'),'-o',str(out/'process.exe')],[str(a.compiler),'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')]]
with (out/'compile.log').open('w') as log:
    for command in commands:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
kernel=(out/'kernel.bin').read_bytes();payload=(out/'process.exe').read_bytes()
assert 0x100000+len(kernel)<0x10000000 and len(payload)==7168
source_files=['components/windows-process-time.in','components/windows-process-parameters.in','components/windows-protected.in','components/windows-pe-application.in','components/time.in','fixtures/windows-protected/filetime.asm','boot/multiboot.asm']
report=dict(status='running',compiler_sha256=hashlib.sha256(a.compiler.read_bytes()).hexdigest(),kernel_sha256=hashlib.sha256(kernel).hexdigest(),source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in source_files},commands=commands,boots=[])
try:
    for base in ['1970-01-01T00:00:00','2000-02-29T12:34:56','2100-03-01T00:00:00','2026-12-31T23:59:59']:
        target=out/base.replace(':','-');target.mkdir()
        epoch=int(datetime.fromisoformat(base).replace(tzinfo=timezone.utc).timestamp())
        fixture=bytearray(payload);struct.pack_into('<QQ',fixture,5128,(epoch+11644473600)*10000000,(epoch+11644473600+60)*10000000)
        image=target/'process.exe';image.write_bytes(fixture)
        serial_path=target/'serial.sock';received=bytearray();serial=None
        command=['qemu-system-x86_64','-kernel',str(out/'kernel.bin'),'-m','512M','-display','none','-no-reboot','-rtc','base='+base+',clock=vm','-serial',f'unix:{serial_path},server=on,wait=on','-device',f'loader,file={image},addr=0x10000000,force-raw=on']
        with (target/'qemu.log').open('w') as log:
            qemu=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
            try:
                deadline=time.monotonic()+10
                while not serial_path.exists() and qemu.poll() is None and time.monotonic()<deadline:time.sleep(.02)
                serial=socket.socket(socket.AF_UNIX);serial.settimeout(.2);serial.connect(str(serial_path))
                deadline=time.monotonic()+120
                while b'space> ' not in received and time.monotonic()<deadline:
                    try:
                        block=serial.recv(65536)
                        if not block:break
                        received.extend(block)
                        if b'PANIC' in received or b'nanokernel fault handler halting' in received:break
                    except socket.timeout:
                        if qemu.poll() is not None:break
                text=received.decode(errors='replace')
                assert 'windows-filetime: 212 execution cases real RTC conversion pointer grant live revoke SET terminal failure no partial writes stable cleanup PASS' in text,text
                assert 'space> ' in text,text
            finally:
                (target/'serial.log').write_bytes(received)
                if serial:serial.close()
                qemu.terminate()
                try:qemu.wait(timeout=5)
                except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
        samples=[]
        for sec,value in re.findall(r'^windows-time-sample: (\d+) (\d+)$',text,re.MULTILINE):
            sec=int(sec);value=int(value)
            delta=datetime.fromtimestamp(sec,tz=timezone.utc)-datetime(1601,1,1,tzinfo=timezone.utc)
            expected=(delta.days*86400+delta.seconds)*10000000
            assert epoch<=sec<=epoch+60 and value==expected
            samples.append(dict(unix_seconds=sec,filetime=value))
        assert len(samples)==22 and samples[-1]['unix_seconds']>=samples[0]['unix_seconds']+1,samples
        transient=re.search(r'^windows-time-transients: (\d+) (\d+)$',text,re.MULTILINE);assert transient,text
        admission_transients,runtime_transients=map(int,transient.groups())
        report['boots'].append(dict(base_utc=base,execution_cases=212,executions=212+runtime_transients,admission_refusals=7+admission_transients,transient_admission_refusals=admission_transients,natural_runtime_unavailable=runtime_transients,samples=samples,status='passed',fixture_sha256=hashlib.sha256(fixture).hexdigest(),command=command))
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print('PASS: Windows FILETIME actual RTC '+base+' 212 cases; transients admission='+str(admission_transients)+' runtime='+str(runtime_transients))
    report['status']='passed';report['execution_cases']=848;report['executions']=sum(boot['executions'] for boot in report['boots'])
except Exception as error:
    report.update(status='failed',error=str(error));raise
finally:
    report['source_changed_during_run']=any(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest for name,digest in report['source_sha256'].items())
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
