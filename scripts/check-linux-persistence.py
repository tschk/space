#!/usr/bin/env python3
"""Run the original SQLite ELF over an owned NVMe disk across three QEMU boots.

Only Space formats/writes the guest disk. Host SQLite is a separate reference
and a read-only oracle for database bytes extracted after each stopped boot.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--app',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--qemu',default='qemu-system-x86_64')
p.add_argument('--timeout',type=int,default=120)
a=p.parse_args();a.out=a.out.resolve();a.compiler=a.compiler.resolve();a.app=a.app.resolve()
if a.out.exists() and any(a.out.iterdir()):p.error('--out must be new or empty')
a.out.mkdir(parents=True,exist_ok=True)
live=ROOT
paths=[]
for directory in ['components','kernel','protocol','services','fixtures']:
    paths+=list((live/directory).rglob('*.in'))
paths+=list((live/'fixtures/applications').glob('*.json'))
paths+=[live/'boot/multiboot.asm',Path(__file__).resolve(),live/'scripts/check-native-persistence.py']
for attempt in range(3):
    captured={path.relative_to(live):path.read_bytes() for path in paths}
    if all(path.read_bytes()==captured[path.relative_to(live)] for path in paths):break
else:raise RuntimeError('source changed while capturing persistence inputs')
ROOT=a.out/'source';receipt={}
for name,data in captured.items():
    target=ROOT/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);target.chmod(0o444)
    receipt[str(name)]=hashlib.sha256(data).hexdigest()
(ROOT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
spec=importlib.util.spec_from_file_location('native_persistence_oracle',ROOT/'scripts/check-native-persistence.py')
oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
manifest=json.loads((ROOT/'fixtures/applications/sqlite-3.46.1.json').read_text())
assert oracle.sha(a.app)==manifest['apps'][0]['sha256'],'SQLite binary differs from pinned reproducible release'
queries=[
 'create table t(x,b);begin immediate;insert into t values(42,zeroblob(9000));commit;select x,length(b) from t;',
 'pragma integrity_check;select x,length(b) from t;begin immediate;update t set x=x+1;commit;select x,length(b) from t;',
 'pragma integrity_check;select x,length(b) from t;begin immediate;update t set x=99;rollback;select x,length(b) from t;']
expected=['42|9000\n','ok\n42|9000\n43|9000\n','ok\n43|9000\n43|9000\n']
reference=[]
for query,output in zip(queries,expected):
    result=subprocess.run(['/sqlite3',str(a.out/'host-reference.db'),query],executable=str(a.app),env={'LC_ALL':'C','HOME':'/'},cwd='/',umask=0o22,capture_output=True,text=True,timeout=15)
    assert (result.returncode,result.stdout,result.stderr)==(0,output,''),result
    reference.append({'query':query,'stdout':result.stdout,'stderr':result.stderr,'exit':result.returncode})
source=(ROOT/'kernel/kernel-root.in').read_text()
source=re.sub(r'import "\.\./([^\"]+)"',lambda m:'import '+json.dumps(str(ROOT/m.group(1))),source)
source='import '+json.dumps(str(ROOT/'components/linux-process.in'))+'\nimport '+json.dumps(str(ROOT/'fixtures/linux-process/checks.in'))+'\n'+source
assert source.count('  shell(port)')==1
source=source.replace('  shell(port)','  linux-persist-check(port)\n  shell(port)')
source+='''
fn linux-persist-check(port:Int)->void{
 let image=0x10000000;let mode=load64(0x18000000);
 if mode<0 || mode>2{panic("SQLite persistence stage invalid");}
 if heap-next>=image{panic("SQLite payload overlaps heap");}heap-end=image;
 if nvme-ready!=1 || sf-mem-disk!=0 || volume-ready!=0{panic("SQLite persistence requires real direct NVMe");}
 if mode==0{linux-check(0,fs-format());}
 linux-check(1,sf-disk-ready);
 let authority=cap-mint(root-realm,cap-memory()|cap-serial()|cap-storage());
 if authority<0{panic("SQLite persistence authority");}
 let caller-fs=rdmsr(0xC0000100);let caller-gs=rdmsr(0xC0000101);
 wrmsr64(0xC0000100,0x400000);wrmsr64(0xC0000101,0x400000);
 let descriptors=vfs-fd-alloc();
 let flushes=nvme-flush-completions;
 serial-write-cstr(port,"linux-persist: transaction begins");serial-nl(port);
 let query=QUERY0;
 if mode==1{query=QUERY1;}else if mode==2{query=QUERY2;}
 linux-check(0,linux-process-run(image,APP_SIZE,"/sqlite3","/sqlite.db",query,authority));
 serial-write-cstr(port,"linux-persist: transaction ends");serial-nl(port);
 if mode<2 && nvme-flush-completions<=flushes{panic("SQLite commit did not consume checked NVMe FLUSH");}
 serial-write-cstr(port,"linux-persist: checked FLUSH completions ");serial-write-dec-wide(port,nvme-flush-completions - flushes);serial-nl(port);
 if linux-process-active!=0 || linux-process-pages!=0 || linux-process-domain!=0 || domain-user-syscall-hook!=0 || fs-range-count!=0 || domain-current!=0 || user-budget-active!=0{panic("SQLite transaction owned cleanup");}
 linux-check(descriptors,vfs-fd-alloc());
 // Warm once, then prove repeated distinct read processes retain no resources.
 let check="select x,length(b) from t;";
 linux-check(0,linux-process-run(image,APP_SIZE,"/sqlite3","/sqlite.db",check,authority));
 let heap=heap-next;let free=linux-check-free-count();let domains=domain-count;let owned=domain-user-owned;let blocks=linux-check-fs-used();
 let i=0;
 while i<3{
  linux-check(0,linux-process-run(image,APP_SIZE,"/sqlite3","/sqlite.db",check,authority));
  linux-check(heap,heap-next);linux-check(free,linux-check-free-count());
  linux-check(domains,domain-count);linux-check(owned,domain-user-owned);linux-check(blocks,linux-check-fs-used());
  linux-check(descriptors,vfs-fd-alloc());linux-check(0,fs-range-count);
  linux-check(0x400000,rdmsr(0xC0000100));linux-check(0x400000,rdmsr(0xC0000101));
  linux-check(0,linux-process-active);linux-check(0,linux-process-pages);linux-check(0,domain-user-syscall-hook);
  i=i+1;
 }
 wrmsr64(0xC0000100,caller-fs);wrmsr64(0xC0000101,caller-gs);cap-revoke(authority);
 serial-write-cstr(port,"linux-persist: actual SQLite NVMe stage ");serial-write-dec-wide(port,mode);serial-write-cstr(port," PASS");serial-nl(port);
}
'''
for index,query in enumerate(queries):source=source.replace('QUERY'+str(index),json.dumps(query))
source=source.replace('APP_SIZE',str(a.app.stat().st_size))
(a.out/'kernel.in').write_text(source)
compiler_sha=oracle.sha(a.compiler)
with (a.out/'compile.log').open('w') as log:
    for command in [
      ['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(a.out/'trampoline.bin')],
      [str(a.compiler),'compile','--path',str(a.out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(a.out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(a.out/'kernel.bin')]]:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
assert oracle.sha(a.compiler)==compiler_sha,'compiler changed during compilation'
disk=a.out/'owned-nvme.img'
with disk.open('xb') as file:file.truncate(64*1024*1024)
report={'status':'running','classification':'actual original SQLite ELF, direct native NVMe, separate QEMU processes','compiler':str(a.compiler),'compiler_sha256':compiler_sha,'application':str(a.app),'application_sha256':oracle.sha(a.app),'kernel_sha256':oracle.sha(a.out/'kernel.bin'),'source_receipt_sha256':oracle.sha(ROOT/'receipt.json'),'environment':{'LC_ALL':'C','HOME':'/'},'working_directory':'/','umask':'022','reference':reference,'boots':[]}
boot=None
try:
    for mode,name in enumerate(['A-transaction','B-reopen-update','C-reopen-rollback']):
        row={'name':name,'mode':mode,'status':'running','formatted':mode==0,'disk_before_sha256':oracle.sha(disk)};report['boots'].append(row)
        config=a.out/f'{name}.config';config.write_bytes(struct.pack('<Q',mode))
        wrapper=a.out/f'qemu-{name}.sh'
        wrapper.write_text('#!/bin/sh\nexec '+shlex.quote(a.qemu)+' -cpu max -device '+shlex.quote(f'loader,file={a.app},addr=0x10000000,force-raw=on')+' -device '+shlex.quote(f'loader,file={config},addr=0x18000000,force-raw=on')+' "$@"\n');wrapper.chmod(0o700)
        boot=oracle.Boot(a.out/'kernel.bin',disk,a.out/name,str(wrapper),a.timeout,row)
        text=bytes(boot.log).decode(errors='replace')
        assert f'linux-persist: actual SQLite NVMe stage {mode} PASS' in text,text
        body=text.split('linux-persist: transaction begins\n',1)[1].split('linux-persist: transaction ends\n',1)[0]
        assert body==expected[mode],{'expected':expected[mode],'actual':body}
        boot.halt();boot=None
        metadata,content=oracle.read_disk_file(disk,'sqlite.db')
        assert content.startswith(b'SQLite format 3\x00') and len(content)>=12288
        try:oracle.read_disk_file(disk,'sqlite.db-journal')
        except AssertionError as error:
            assert 'missing from persisted root directory' in str(error),error
        else:raise AssertionError('SQLite journal remains after completed transaction')
        extracted=a.out/f'{name}.read-only-oracle.db';extracted.write_bytes(content)
        check=subprocess.run(['/sqlite3',str(extracted),'pragma integrity_check;select x,length(b) from t;'],executable=str(a.app),env={'LC_ALL':'C','HOME':'/'},cwd='/',umask=0o22,capture_output=True,text=True,timeout=15)
        assert (check.returncode,check.stdout,check.stderr)==(0,f'ok\n{42 if mode==0 else 43}|9000\n',''),check
        assert oracle.sha(extracted)==hashlib.sha256(content).hexdigest(),'host verification mutated extracted database'
        flushes=re.search(r'linux-persist: checked FLUSH completions (\d+)',text)
        assert flushes is not None
        row.update(status='passed',guest_output=body,persisted_file=metadata,disk_after_sha256=oracle.sha(disk),raw_database_host_oracle=check.stdout,actual_application_activations=5,checked_nvme_flush_completions=int(flushes[1]))
    assert report['boots'][1]['persisted_file']['sha256']==report['boots'][2]['persisted_file']['sha256'],'rollback changed persisted database bytes'
    assert oracle.sha(a.compiler)==compiler_sha and oracle.sha(a.app)==manifest['apps'][0]['sha256'],'input artifact changed during persistence gate'
    report['status']='passed'
    print(f'PASS: original SQLite transaction/update/rollback across three real NVMe QEMU boots; {a.out}')
except Exception as error:
    report.update(status='failed',error=f'{type(error).__name__}: {error}');raise
finally:
    if boot:boot.close()
    report['disk_final_sha256']=oracle.sha(disk)
    (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
