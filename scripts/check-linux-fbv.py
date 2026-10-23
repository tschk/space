#!/usr/bin/env python3
"""Execute pinned upstream fbv CLI entry in protected Space; GUI remains open."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', type=Path, required=True)
p.add_argument('--app', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--root', choices=['standard','minimal'], default='standard')
p.add_argument('--repeat', type=int, default=21)
a = p.parse_args()
a.compiler = a.compiler.resolve(); a.app = a.app.resolve(); out = a.out.resolve()
assert not out.exists() or not any(out.iterdir()), '--out must be new or empty'
assert 1 <= a.repeat <= 100
out.mkdir(parents=True, exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest_path = ROOT/'fixtures/applications/fbv-1.1.json'
manifest = json.loads(manifest_path.read_text()); app = manifest['apps'][0]
assert sha(a.app) == app['sha256'] and a.app.stat().st_size == app['size_bytes'], 'pinned fbv mismatch'
report = dict(status='running',goal_status='OPEN',classification='Original fbv CLI entry only; no GUI rendering/interaction coverage',
              gui_status='not-executed',execution_started=False,root=a.root,repeat=a.repeat,application_sha256=sha(a.app),
              compiler_sha256=sha(a.compiler),manifest_sha256=sha(manifest_path),cases=[])
files = [x for d in ['components','kernel','protocol','services'] for x in (ROOT/d).rglob('*.in')]
files += [ROOT/'boot/multiboot.asm',ROOT/'fixtures/linux-counted/startup.asm',manifest_path,Path(__file__).resolve()]
contents = {str(x.relative_to(ROOT)):x.read_bytes() for x in files}
assert all(x.read_bytes()==contents[str(x.relative_to(ROOT))] for x in files), 'source changed during snapshot'
snapshot = out/'source';inventory={}
for name, data in contents.items():
    target=snapshot/name; target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    inventory[name]=hashlib.sha256(data).hexdigest()
(out/'source-hashes.json').write_text(json.dumps(inventory,indent=2)+'\n')
report['source_inventory_sha256']=sha(out/'source-hashes.json')
try:
    for case in manifest['cli_oracles']:
        got=subprocess.run(case['argv'],executable=str(a.app),cwd='/',env={'HOME':'/','LC_ALL':'C'},umask=0o22,capture_output=True,timeout=10)
        assert got.returncode==case['exit']
        assert hashlib.sha256(got.stdout).hexdigest()==case['stdout_sha256']
        assert hashlib.sha256(got.stderr).hexdigest()==case['stderr_sha256']
        merged=subprocess.run(case['argv'],executable=str(a.app),cwd='/',env={'HOME':'/','LC_ALL':'C'},umask=0o22,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=10)
        assert merged.returncode==got.returncode
        report['cases'].append(dict(argv=case['argv'],exit=got.returncode,stdout=got.stdout.decode(),stderr=got.stderr.decode(),merged_serial_order=merged.stdout.decode()))
    report['startup_host']=[]
    for count in (1,2,3):
        obj=out/f'argc{count}.o';binary=out/f'argc{count}.elf'
        subprocess.run(['nasm','-f','elf64',f'-DARGC={count}',str(snapshot/'fixtures/linux-counted/startup.asm'),'-o',str(obj)],check=True,timeout=30)
        subprocess.run(['ld','-static','-z','noexecstack','-o',str(binary),str(obj)],check=True,timeout=30)
        argv=['/high-source','hello-from-high-source','third-high-source'][:count]
        host=subprocess.run(argv,executable=str(binary),cwd='/',env={'LC_ALL':'C','HOME':'/'},capture_output=True,timeout=10)
        assert host.returncode==42 and not host.stdout and not host.stderr,(count,host.returncode)
        report['startup_host'].append(dict(argc=count,status=42,sha256=sha(binary)))
    arguments=bytearray(4096)
    for offset,text in [(0,b'/high-source\0'),(256,b'hello-from-high-source\0'),(512,b'third-high-source\0')]:arguments[offset:offset+len(text)]=text
    (out/'high-arguments.bin').write_bytes(arguments)
    source=(snapshot/('kernel/kernel-root.in' if a.root=='standard' else 'kernel/kernel-root-minimal.in')).read_text()
    source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(snapshot/m[1])),source)
    source='import '+json.dumps(str(snapshot/'components/linux-process.in'))+'\n'+source
    assert source.count('  shell(port)')==1
    source=source.replace('  shell(port)','  fbv-cli-check(port)\n  shell(port)')
    source+='''
fn fbv-cli-free()->Int{let page=free-list;let count=0;while page!=0 && count<131072{count+=1;page=load64(page);}return count;}
fn fbv-cli-check(port:Int)->void{
 let authority=cap-mint(root-realm,cap-memory()|cap-serial());
 if authority<0{panic("fbv authority");}
 linux-process-trace=1;
 let cycle=0;let heap=0;let free=0;let domains=0;
 let previous-end=heap-end;heap-end=0x10000000;
 let refusal-heap=heap-next;let refusal-free=fbv-cli-free();let refusal-domains=domain-count;
 if linux-process-run-counted-input(0,0,0,0,0,authority,-1,0)!=-22 || linux-process-run-counted-input(0,0,0,0,0,authority,-1,4)!=-22 || linux-process-run-counted-input(0,0,0,0,0,authority,-1,0x7fffffffffffffff)!=-22{panic("counted argc refusal");}
 if heap-next!=refusal-heap || fbv-cli-free()!=refusal-free || domain-count!=refusal-domains{panic("counted argc refusal allocated");}
 let caps=cap-count;let owned=domain-user-owned;let caller=current-cap;
 let fs=rdmsr(0xC0000100);let gs=rdmsr(0xC0000101);
 while cycle<CYCLES{
  let test=0;while test<2{
   serial-write-cstr(port,"fbv-cli: begin ");serial-write-dec-wide(port,cycle);serial-put(port,32);serial-write-dec-wide(port,test);serial-nl(port);
   let argument=0;let count=1;if test==0{argument="-h";count=2;}
   let result=linux-process-run-counted-input(0x10000000,APP_SIZE,"/fbv",argument,-1,authority,-1,count);
   serial-write-cstr(port,"fbv-cli: end ");serial-write-dec-wide(port,cycle);serial-put(port,32);serial-write-dec-wide(port,test);serial-put(port,32);serial-write-dec-wide(port,result);serial-put(port,32);serial-write-dec-wide(port,linux-process-syscalls);serial-nl(port);
   if domain-current!=0 || domain-user-syscall-hook!=0 || user-budget-active!=0 || linux-process-active!=0 || linux-process-pages!=0 || cap-count!=caps || domain-user-owned!=owned || current-cap!=caller || rdmsr(0xC0000100)!=fs || rdmsr(0xC0000101)!=gs{panic("fbv owner or caller leak");}
   if cycle>0 && (heap-next!=heap || fbv-cli-free()!=free || domain-count!=domains){panic("fbv resource leak");}
   test+=1;
  }
  let count=1;while count<=3{
   let fixture=0x12000000+(count - 1)*0x200000;let size=STARTUP_SIZE;
   if count==2{size=STARTUP_SIZE2;}if count==3{size=STARTUP_SIZE3;}
   let second=-1;let third=-1;
   if count>1{second=0x13000100;}if count>2{third=0x13000200;}
   let result=linux-process-run-counted-input(fixture,size,0x13000000,second,third,authority,-1,count);
   if result!=42{panic("counted argc argv environment auxv mismatch");}
   if cycle>0 && (heap-next!=heap || fbv-cli-free()!=free || domain-count!=domains){panic("counted argc resource leak");}
   if domain-current!=0 || domain-user-syscall-hook!=0 || user-budget-active!=0 || linux-process-active!=0 || linux-process-pages!=0 || cap-count!=caps || domain-user-owned!=owned || current-cap!=caller || rdmsr(0xC0000100)!=fs || rdmsr(0xC0000101)!=gs{panic("counted argc owner leak");}
   serial-write-cstr(port,"fbv-cli: startup argc PASS ");serial-write-dec-wide(port,count);serial-nl(port);
   count+=1;
  }
  if cycle==0{heap=heap-next;free=fbv-cli-free();domains=domain-count;}
  cycle+=1;
 }
 heap-end=previous-end;
 serial-write-cstr(port,"fbv-cli: completed unchanged ownership cycles PASS");serial-nl(port);
}
'''.replace('CYCLES',str(a.repeat+1)).replace('APP_SIZE',str(a.app.stat().st_size)).replace('STARTUP_SIZE3',str((out/'argc3.elf').stat().st_size)).replace('STARTUP_SIZE2',str((out/'argc2.elf').stat().st_size)).replace('STARTUP_SIZE',str((out/'argc1.elf').stat().st_size))
    (out/'kernel.in').write_text(source)
    commands=[['nasm','-f','bin',str(snapshot/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],
              [str(a.compiler),'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')]]
    with (out/'compile.log').open('w') as log:
        for command in commands:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    command=['qemu-system-x86_64','-cpu','max','-kernel',str(out/'kernel.bin'),'-m','512M','-display','none','-no-reboot','-serial','file:'+str(out/'serial.log'),'-device',f'loader,file={a.app},addr=0x10000000,force-raw=on']
    for count in (1,2,3):
        command += ['-device',f'loader,file={out}/argc{count}.elf,addr={0x12000000+(count-1)*0x200000},force-raw=on']
    command += ['-device',f'loader,file={out}/high-arguments.bin,addr=0x13000000,force-raw=on']
    report['qemu_command']=command; report['kernel_sha256']=sha(out/'kernel.bin')
    with (out/'qemu.log').open('w') as log:
        process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                serial=(out/'serial.log').read_bytes() if (out/'serial.log').exists() else b''
                if b'fbv-cli: completed unchanged ownership cycles PASS' in serial or b'PANIC' in serial or process.poll() is not None:break
                time.sleep(.05)
        finally:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait()
    serial=(out/'serial.log').read_text(errors='replace')
    runs=re.findall(r'fbv-cli: begin (\d+) (\d+)\n(.*?)fbv-cli: end \1 \2 (-?\d+) (\d+)\n',serial,re.S)
    report['actual_entries_with_syscalls']=sum(int(row[4])>0 for row in runs)
    report['execution_started']=report['actual_entries_with_syscalls']>0
    report['observations']=[]
    for index,(cycle,test,body,status,syscalls) in enumerate(runs):
        case=report['cases'][int(test)]
        cleaned=re.sub(r'linux-process: (?:(?:syscall|result|suspended) -?\d+|completed \d+ \d+ -?\d+)\n','',body)
        report['observations'].append(dict(cycle=int(cycle),case=int(test),status=int(status),syscalls=int(syscalls),output=cleaned))
        assert (int(cycle),int(test))==divmod(index,2)
        assert int(status)==case['exit'] and int(syscalls)>0,(cycle,test,status,cleaned[-1000:])
        # The serial ABI merges fd1/fd2. Compare a genuine host merged pipe;
        # stdio buffering can flush the stderr diagnostic before stdout help.
        # Never reorder guest bytes or concatenate separate host captures.
        assert cleaned==case['merged_serial_order'],(cycle,test,cleaned[-1000:])
    assert serial.count('fbv-cli: startup argc PASS ')==3*(a.repeat+1)
    report['startup_fixture_activations']=3*(a.repeat+1)
    assert len(runs)==2*(a.repeat+1) and 'fbv-cli: completed unchanged ownership cycles PASS' in serial and 'PANIC' not in serial
    assert all((ROOT/name).read_bytes()==data for name,data in contents.items()),'source changed during run'
    assert sha(a.compiler)==report['compiler_sha256'] and sha(a.app)==report['application_sha256']
    report.update(status='passed',actual_cli_activations=len(runs),GUI_coverage_claim=False)
    print('PASS original fbv CLI only:',len(runs),'protected entries;',a.root,'; GUI remains OPEN')
except Exception as error:
    report.update(status='failed',error=str(error));raise
finally:
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
