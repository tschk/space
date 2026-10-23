#!/usr/bin/env python3
"""Actual revision2 Mach-O owned-heap C ABI calls and bounded cleanup."""
import argparse,hashlib,json,re,shutil,struct,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--in',dest='compiler',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--app',type=Path);a=p.parse_args();a.out=a.out.resolve();a.compiler=a.compiler.resolve()
if a.out.exists() and any(a.out.iterdir()):p.error('--out must be new or empty')
a.out.mkdir(parents=True,exist_ok=True)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
snap=a.out/'source';snap.mkdir()
for folder in ['components','kernel','boot','protocol','services']:shutil.copytree(ROOT/folder,snap/folder)
shutil.copytree(ROOT/'fixtures/darwin-heap',snap/'fixtures/darwin-heap')
provider=snap/'components/darwin-owned-heap.in';s=provider.read_text();assert s.count('domain-user-syscall-hook = darwin-heap-dispatch')==1;provider.write_text(s.replace('domain-user-syscall-hook = darwin-heap-dispatch','domain-user-syscall-hook = heap-test-dispatch'))
hashes={str(f.relative_to(snap)):sha(f) for f in snap.rglob('*') if f.is_file()}
report={'status':'running','compiler':str(a.compiler),'compiler_sha256':sha(a.compiler),'runner_sha256':sha(Path(__file__)),'frozen_source_sha256':hashes,'source_test_variance':'only owned-heap dispatcher assignment routes through test-only actual memory-cap revocation and inaccessible metadata-address probe controls','commands':[]}
def run(cmd,log,timeout=180):
 report['commands'].append(cmd)
 with log.open('w') as f:return subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
try:
 command=['nasm','-f','bin',str(snap/'fixtures/darwin-heap/process.asm'),'-o',str(a.out/'process.macho')];assert run(command,a.out/'nasm.log').returncode==0
 binary=(a.out/'process.macho').read_bytes();size=len(binary);assert struct.unpack_from('<II',binary,232)==(0x20000,0x20000)
 fix,extent=struct.unpack_from('<II',binary,208);_,starts,imports,symbols,count,fmt,_=struct.unpack_from('<7I',binary,fix);assert count==12 and fmt==1
 names=[]
 for i in range(count):
  word=struct.unpack_from('<I',binary,fix+imports+4*i)[0];names.append(binary[fix+symbols+(word>>9):].split(b'\0')[0].decode())
 assert names==['_write','_exit','___error','_open','_read','_close','_lseek','_malloc','_calloc','_realloc','_free','_malloc']
 report['fixture']={'sha256':sha(a.out/'process.macho'),'imports':names,'size':size,'descriptor_revision':2}
 source=(snap/'kernel/kernel-root.in').read_text();source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(snap/m[1])),source)
 source='import '+json.dumps(str(snap/'components/darwin-owned-heap.in'))+'\n'+source
 assert source.count('  shell(port)')==1;source=source.replace('  shell(port)','  heap-check(port)')
 source+='''
fn heap-test-dispatch(frame:Int)->Int{
 if load64(frame+112)==0x2FFFFFE{
  if domain-current!=darwin-heap-owner || darwin-heap-active==0{panic("heap revoke owner");}
  cap-revoke(darwin-heap-authority);store64(frame+112,0);store64(frame+136,load64(frame+136)&-2);return 1;
 }
 if load64(frame+112)==0x2FFFFFD{
  if domain-current!=darwin-heap-owner || darwin-heap-active==0{panic("heap metadata owner");}
  store64(frame+112,darwin-heap-metadata);return 1;
 }
 return darwin-heap-dispatch(frame);
}
fn heap-free-count()->Int{let f=free-list;let n=0;while f!=0&&n<4096{n+=1;f=load64(f);}return n;}
fn heap-invoke(image:Int,input:Int,serial:Int,storage:Int,memory:Int,budget:Int)->Int{return darwin-heap-run(image,IMAGE_SIZE,input,1024,DARWIN-HEAP-IDENTITY,serial,storage,memory,budget);}
fn heap-refuse(image:Int,input:Int,serial:Int,storage:Int,memory:Int,offset:Int,value:Int,width:Int)->void{
 let old=load32(image+offset);if width==8{old=load64(image+offset);}let heap=heap-next;let free=free-list;let domains=domain-count;let caps=cap-count;
 if width==8{store64(image+offset,value);}else{store32(image+offset,value);}
 let result=heap-invoke(image,input,serial,storage,memory,1000);
 if width==8{store64(image+offset,old);}else{store32(image+offset,old);}
 if result!=-8 || heap-next!=heap || free-list!=free || domain-count!=domains || cap-count!=caps{panic("heap malformed mutated state");}
}
fn heap-check(port:Int)->void{
 if dyn-kernel-exportable("darwin-heap-run")!=0 || dyn-kernel-exportable("darwin-heap-malloc")!=0 || dyn-resolve-idx("darwin-heap-run")!=-1{panic("heap raw provider registry");}
 let image=0x10000000;let input=alloc(1024);
 store64(input,0);store64(input+8,input+64);store64(input+16,0);store64(input+24,input+80);store64(input+32,0);store64(input+40,input+96);
 store64(input+64,0);store64(input+80,0);store64(input+96,0);
 if fs-write-file("heap-host.txt","sentinel",8)!=0{panic("heap host seed");}
 let host=vfs-open("heap-host.txt",0);if host<3{panic("heap host open");}let first=vfs-fd-alloc();let host-path=load64(vfs-fd-table+host*32);
 let serial=cap-mint(root-realm,cap-serial());let storage=cap-mint(root-realm,cap-storage());let memory=cap-mint(root-realm,cap-memory());let caps=cap-count;
 let source-copy=alloc(IMAGE_SIZE);let n=0;while n<IMAGE_SIZE{store8(source-copy+n,load8(image+n));n+=1;}
 let held=alloc(96*8);let hold=0;while hold<96{store64(held+hold*8,frame-alloc());hold+=1;}hold=0;while hold<96{frame-free(load64(held+hold*8));hold+=1;}
 let saved-end=heap-end;let cold=heap-next;let cold-free=free-list;let cold-domains=domain-count;
 heap-end=heap-next;let refused=heap-invoke(image,input,serial,storage,memory,1000);heap-end=saved-end;
 if refused!=-12 || heap-next!=cold || free-list!=cold-free || domain-count!=cold-domains || darwin-heap-context!=0 || darwin-heap-metadata!=0{panic("heap firstuse zero-bump refusal");}
 let last=free-list;let idx=1;while idx<95{last=load64(last);idx+=1;}let rest=load64(last);store64(last,0);heap-end=heap-next+10160;let short=heap-invoke(image,input,serial,storage,memory,1000);heap-end=saved-end;store64(last,rest);
 if short!=-12 || heap-next!=cold || free-list!=cold-free || domain-count!=cold-domains{panic("heap insufficient real frames refusal");}
 heap-end=heap-next+10160;let recovered=heap-invoke(image,input,serial,storage,memory,1000);heap-end=saved-end;
 if recovered!=42 || heap-next!=cold+10160{serial-write-dec-wide(port,recovered);panic("heap exact retained recovery");}
 let heap=heap-next;let free=heap-free-count();let domains=domain-count;let cycle=0;let executions=1;
 while cycle<21{
  let mode=0;
  while mode<14{
   if mode!=10{
    store64(image+4096,mode);let budget=1000;if mode==6{budget=3;}
    let result=heap-invoke(image,input,serial,storage,memory,budget);let expected=42;
    if mode>=1&&mode<=4{expected=134;}if mode==5||mode==7||mode==8||mode==9||mode==12{expected=142;}if mode==6{expected=124;}
    if result!=expected{serial-write-cstr(port,"heap mode ");serial-write-dec-wide(port,mode);serial-write-cstr(port," result ");serial-write-dec-wide(port,result);serial-nl(port);panic("heap guest mismatch");}
    if heap-next!=heap || heap-free-count()!=free || domain-count!=domains || cap-count!=caps || domain-current!=0 || darwin-heap-active!=0 || darwin-heap-owner!=0 || darwin-heap-metadata!=0 || darwin-heap-authority!=-1 || darwin-protected-count!=0 || darwin-protected-busy!=0 || user-context-active!=0 || domain-user-syscall-hook!=0{panic("heap resource cleanup");}
    if vfs-fd-alloc()!=first || vfs-fd-valid(host)==0 || vfs-fd-offset(host)!=0 || load64(vfs-fd-table+host*32)!=host-path{panic("heap ambient descriptor changed");}
    n=0;while n<IMAGE_SIZE{if n<4096||n>=4104{if load8(image+n)!=load8(source-copy+n){panic("heap caller image changed");}}n+=1;}
    executions+=1;
   }
   mode+=1;
  }
  cycle+=1;
 }
 let old=heap-next;let head=free-list;
 if heap-invoke(image,input,serial,storage,-1,1000)!=-13 || heap-invoke(image,input,serial,storage,serial,1000)!=-13 || heap-next!=old || free-list!=head{panic("heap launch capability refusal");}
 // MALFORMED
 // ORIGINAL_APP
 let revocable=cap-mint(root-realm,cap-memory());store64(image+4096,10);
 if heap-invoke(image,input,serial,storage,revocable,1000)!=42 || cap-check(revocable,cap-memory())!=0 || heap-next!=heap || heap-free-count()!=free || domain-count!=domains{panic("heap actual revocation cleanup");}
 if vfs-close(host)!=0{panic("heap host close");}
 serial-write-cstr(port,"darwin-heap: 275 CPL3 executions 21 stable cycles PASS");serial-nl(port);outb(0xF4,16);
}
'''.replace('IMAGE_SIZE',str(size))
 mutations=[(4,0x2000007,4),(232,0x10000,4),(236,0x10000,4),(200,0x80000022,4),(fix+16,17,4),(fix+20,2,4),(fix+imports,2,4),(4352,0x800000000000000c,8)]
 unknown=binary.index(b'_unknown\0')-(fix+symbols);mutations.append((fix+imports+44,1|(unknown<<9),4))
 source=source.replace('// MALFORMED','\n'.join(f'heap-refuse(image,input,serial,storage,memory,{off},{value if value<(1<<63) else value-(1<<64)},{width});' for off,value,width in mutations))
 report['malformed_cases']=len(mutations)
 if a.app:
  import importlib.util
  spec=importlib.util.spec_from_file_location('requirements',ROOT/'scripts/inspect-darwin-application.py');inspector=importlib.util.module_from_spec(spec);spec.loader.exec_module(inspector);report['original_application']=inspector.inspect(a.app)
  source=source.replace('// ORIGINAL_APP',f'if darwin-heap-run(0x11000000,{a.app.stat().st_size},input,1024,DARWIN-HEAP-IDENTITY,serial,storage,memory,1000)!=-8 || heap-next!=old || free-list!=head || domain-count!=domains{{panic("original jq heap admission");}}')
 (a.out/'kernel.in').write_text(source)
 for command in [['nasm','-f','bin',str(snap/'boot/multiboot.asm'),'-o',str(a.out/'trampoline.bin')],[str(a.compiler),'compile','--path',str(a.out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(a.out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(a.out/'kernel.bin')]]:
  assert run(command,a.out/('compile.log' if command[0]!='nasm' else 'trampoline.log')).returncode==0,(a.out/'compile.log').read_text()[-4000:]
 assert (a.out/'kernel.bin').stat().st_size<0xff00000
 report['kernel_sha256']=sha(a.out/'kernel.bin')
 command=['qemu-system-x86_64','-kernel',str(a.out/'kernel.bin'),'-m','512M','-display','none','-no-reboot','-serial','file:'+str(a.out/'serial.log'),'-device','isa-debug-exit,iobase=0xf4,iosize=0x04','-device',f'loader,file={a.out/"process.macho"},addr=0x10000000,force-raw=on']
 if a.app:command+=['-device',f'loader,file={a.app.resolve()},addr=0x11000000,force-raw=on']
 result=run(command,a.out/'qemu.log',90);serial=(a.out/'serial.log').read_text();assert result.returncode==33 and '275 CPL3 executions 21 stable cycles PASS' in serial,serial[-5000:]
 report['frozen_source_changed_during_run']=[name for name,digest in hashes.items() if sha(snap/name)!=digest];assert not report['frozen_source_changed_during_run'];report.update(status='passed',executions=275,cycles=21);print('PASS actual owned Darwin heap 275 CPL3 executions',flush=True)
except Exception as error:report.update(status='failed',error=str(error));print('FAIL',error,flush=True)
finally:(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='passed' else 1)
