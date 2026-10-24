#!/usr/bin/env python3
"""Record actual unchanged revision1 refusal of jq's four allocator imports."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--in',dest='compiler',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--app',type=Path,required=True)
a=p.parse_args();a.out=a.out.resolve();a.compiler=a.compiler.resolve()
if a.out.exists() and any(a.out.iterdir()):p.error('--out must be new or empty')
a.out.mkdir(parents=True,exist_ok=True)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
report={'status':'running','executions':0,'compiler':str(a.compiler),'compiler_sha256':sha(a.compiler)}
try:
 spec=importlib.util.spec_from_file_location('requirements',ROOT/'scripts/inspect-darwin-application.py');inspector=importlib.util.module_from_spec(spec);spec.loader.exec_module(inspector);requirements=inspector.inspect(a.app)
 names=['_malloc','_calloc','_realloc','_free'];assert set(names)<=set(requirements['chained_fixups']['import_names'])
 snapshot=a.out/'source';snapshot.mkdir()
 for directory in ['components','kernel','boot','protocol','services']:shutil.copytree(ROOT/directory,snapshot/directory)
 shutil.copytree(ROOT/'fixtures/darwin-eager',snapshot/'fixtures/darwin-eager')
 subprocess.run(['nasm','-f','bin',str(snapshot/'fixtures/darwin-eager/process.asm'),'-o',str(a.out/'process.macho')],check=True,timeout=30)
 binary=(a.out/'process.macho').read_bytes();fix=struct.unpack_from('<I',binary,208)[0];imports,pool=struct.unpack_from('<II',binary,fix+8);unknown=binary.index(b'_unknown\0');nameoffset=unknown-fix-pool
 tracked=sorted(f for f in snapshot.rglob('*') if f.is_file());hashes={str(f.relative_to(snapshot)):sha(f) for f in tracked}
 report.update(original_application=requirements,symbols=names,profile='unchanged finite seven-service revision1',fixture_sha256=sha(a.out/'process.macho'),frozen_source_sha256=hashes)
 source=(snapshot/'kernel/kernel-root.in').read_text();source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(snapshot/m[1])),source);assert source.count('  shell(port)')==1;source=source.replace('  shell(port)','  heap-import-baseline(port)')
 source+='''
fn heap-import-unknown(image:Int,size:Int,name:Int,pool:Int)->void{
 let i=0;while i<9{store8(image+pool+i,0);i+=1;}
 i=0;let c=-1;while c!=0{c=load8(name+i);store8(image+pool+i,c);i+=1;}
 let heap=heap-next;let free=free-list;let domains=domain-count;let caps=cap-count;
 if darwin-eager-symbol(image,pool,size)!=0 || darwin-eager-run(image,size,0,0,DARWIN-EAGER-IDENTITY,-1,-1,1000)!=-8{panic("revision1 unexpectedly provided heap import");}
 if heap-next!=heap || free-list!=free || domain-count!=domains || cap-count!=caps || darwin-protected-busy!=0 || darwin-protected-count!=0{panic("unknown heap import mutated execution resources");}
 serial-write-cstr(com1(),"heap-import-baseline: unknown ");serial-write-cstr(com1(),name);serial-nl(com1());
}
fn heap-import-baseline(port:Int)->void{
 let image=0x10000000;
'''
 source+=f' store32(image+{fix+imports+28},{1|(nameoffset<<9)});\n'
 for name in names:source+=f' heap-import-unknown(image,{len(binary)},{json.dumps(name)},{unknown});\n'
 source+=' serial-write-cstr(port,"heap-import-baseline:4 allocation-free unknown imports BLOCKED");serial-nl(port);outb(0xF4,16);\n}\n'
 (a.out/'kernel.in').write_text(source)
 commands=[['nasm','-f','bin',str(snapshot/'boot/multiboot.asm'),'-o',str(a.out/'trampoline.bin')],[str(a.compiler),'compile','--path',str(a.out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(a.out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(a.out/'kernel.bin')]]
 report['compile_commands']=commands
 with (a.out/'compile.log').open('w') as log:
  for command in commands:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
 command=['qemu-system-x86_64','-kernel',str(a.out/'kernel.bin'),'-m','512M','-display','none','-no-reboot','-serial','file:'+str(a.out/'serial.log'),'-device','isa-debug-exit,iobase=0xf4,iosize=0x04','-device',f'loader,file={a.out/"process.macho"},addr=0x10000000,force-raw=on'];report['qemu_command']=command
 with (a.out/'qemu.log').open('w') as log:run=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=45)
 serial=(a.out/'serial.log').read_text();assert run.returncode==33 and 'heap-import-baseline:4 allocation-free unknown imports BLOCKED' in serial,serial[-5000:]
 report['frozen_source_changed_during_run']=[name for name,digest in hashes.items() if sha(snapshot/name)!=digest];assert not report['frozen_source_changed_during_run'];report.update(status='passed',admission='blocked')
 print('BLOCKED actual revision1 Mach-O allocator imports: malloc/calloc/realloc/free, no guest execution or execution allocation',flush=True)
except Exception as error:report.update(status='failed',error=str(error));print('FAIL:',error,flush=True)
finally:(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='passed' else 1)
