#!/usr/bin/env python3
"""Observe production native SCI teardown during real apps and emitted aborts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--cycles',type=int,default=70)
a=p.parse_args();root=Path(__file__).resolve().parents[1];out=a.out.resolve()
if a.cycles<65:p.error('--cycles must exceed 64 to prove more than 128 real app activations')
if out.exists() and any(out.iterdir()):p.error('--out must be new or empty')
out.mkdir(parents=True,exist_ok=True);a.compiler=a.compiler.resolve()
env=dict(os.environ,IN=str(a.compiler),BUILD_DIR=str(out/'build'))
def run(command,log,**kwargs):
 with (out/log).open('w') as stream:subprocess.run([str(v) for v in command],cwd=root,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=180,**kwargs)
run(['bash',root/'scripts/build-images.sh','--variant','standard'],'build.log',env=env)
def imports(source,directory):
 return re.sub(r'(?m)^import "([^"]+)"',lambda m:'import '+json.dumps(str((directory/m.group(1)).resolve())),source)
loader=imports((root/'components/sci-loader.in').read_text(),root/'components')
loader=loader.replace('fn sci-load-runtime-component(', 'fn sci-load-runtime-component-implementation(',1)
loader+=r'''
var lifecycle-observing=0
var lifecycle-count=0
var lifecycle-aborts=0
var lifecycle-stale-cap=-1
var lifecycle-heap=0
var lifecycle-free=0
var lifecycle-domains=0
var lifecycle-caps=0
var lifecycle-objects=0
var lifecycle-exports=0
var lifecycle-clones=0
fn lifecycle-free-count()->Int{
 let frame=free-list;let count=0;
 while frame!=0 && count<10000{count=count+1;frame=load64(frame);}
 if frame!=0{panic("lifecycle free-list cycle");}return count;
}
fn lifecycle-difference(port:Int,label:Int,actual:Int,expected:Int)->void{
 if actual!=expected{serial-write-cstr(port,"lifecycle delta ");serial-write-cstr(port,label);serial-write-cstr(port," actual ");serial-write-hex(port,actual);serial-write-cstr(port," expected ");serial-write-hex(port,expected);serial-nl(port);}
}
fn lifecycle-observe(port:Int)->void{
 if runtime-instance-live!=0 || domain-current!=0 || current-cap!=load64(domain-table+16){panic("lifecycle live state");}
 if cap-check(lifecycle-stale-cap,cap-serial())!=0{panic("lifecycle generic stale cap regained authority");}
 if runtime-instance-cap-free==0{panic("lifecycle private cap not released");}
 let private=runtime-instance-cap-free - 1;
 if private==lifecycle-stale-cap || cap-check(private,cap-serial())!=0{panic("lifecycle private cap release");}
 if lifecycle-count==16{
  lifecycle-heap=heap-next;lifecycle-free=lifecycle-free-count();lifecycle-domains=domain-count;
  lifecycle-caps=cap-count;lifecycle-objects=obj-arena-next;lifecycle-exports=dyn-count;lifecycle-clones=domain-clone-owned;
 }
 if lifecycle-count>16{
  if heap-next!=lifecycle-heap || lifecycle-free-count()!=lifecycle-free || domain-count!=lifecycle-domains || cap-count!=lifecycle-caps || obj-arena-next!=lifecycle-objects || dyn-count!=lifecycle-exports || domain-clone-owned!=lifecycle-clones{
   lifecycle-difference(port,"heap",heap-next,lifecycle-heap);lifecycle-difference(port,"free",lifecycle-free-count(),lifecycle-free);
   lifecycle-difference(port,"domains",domain-count,lifecycle-domains);lifecycle-difference(port,"caps",cap-count,lifecycle-caps);
   lifecycle-difference(port,"objects",obj-arena-next,lifecycle-objects);lifecycle-difference(port,"exports",dyn-count,lifecycle-exports);
   lifecycle-difference(port,"clones",domain-clone-owned,lifecycle-clones);panic("lifecycle resources grew after warmup");}
 }
 serial-write-cstr(port,"lifecycle: observed ");serial-write-dec-wide(port,lifecycle-count);
 serial-write-cstr(port," aborts ");serial-write-dec-wide(port,lifecycle-aborts);serial-nl(port);
}
fn sci-load-runtime-component(port:Int,image:Int,name:Int,grants:Int,sync:Int,args:Int)->Int{
 let result=sci-load-runtime-component-implementation(port,image,name,grants,sync,args);
 if sync==1 && lifecycle-observing!=0{
  lifecycle-count=lifecycle-count+1;
  if lifecycle-count>=16{
   if sci-load-runtime-component-implementation(port,boot-image-find(250),"allocation-control",1,1,0)!=134{panic("lifecycle emitted abort outcome");}
   lifecycle-aborts=lifecycle-aborts+1;
  }
  lifecycle-observe(port);
 }
 return result;
}
fn lifecycle-registry-capacity(port:Int)->void{
 let saved=dyn-count;let phys=lib-phys;let entry=lib-entry;let size=lib-size;let registered=lib-registered;
 let library=boot-image-find(7);let exports=load64(library+SCI-V2-EXPORT-COUNT);
 if exports<2{panic("lifecycle library capacity fixture");}
 dyn-count=DYN-MAX-EXPORTS - 1;
 let tail=load64(dyn-name-tab+dyn-count*8);
 if sci-register-library(port,library)!=-1 || dyn-count!=DYN-MAX-EXPORTS - 1 || load64(dyn-name-tab+dyn-count*8)!=tail || lib-phys!=phys || lib-entry!=entry || lib-size!=size || lib-registered!=registered{panic("lifecycle partial library readiness");}
 if dyn-register-image-exports(port,boot-image-find(250),0x7d000040,4096)!=-1 || dyn-count!=DYN-MAX-EXPORTS - 1{panic("lifecycle partial image exports");}
 if dyn-register-kernel-exports(port)!=-1 || dyn-count!=DYN-MAX-EXPORTS - 1{panic("lifecycle partial kernel exports");}
 dyn-count=DYN-MAX-EXPORTS;
 if dyn-add(0,0,0,0,0)!=-1 || dyn-count!=DYN-MAX-EXPORTS{panic("lifecycle full registry accepted");}
 let start=DYN-MAX-EXPORTS - exports;dyn-count=start;
 if sci-register-library(port,library)!=0 || dyn-count!=DYN-MAX-EXPORTS || load64(dyn-prov-phys+start*8)!=library || load64(dyn-prov-phys+(DYN-MAX-EXPORTS - 1)*8)!=library{panic("lifecycle exact-fit library incomplete");}
 let i=start;
 while i<DYN-MAX-EXPORTS{store64(dyn-name-tab+i*8,0);store64(dyn-fn-tab+i*8,0);store64(dyn-prov-phys+i*8,0);store64(dyn-prov-base+i*8,0);store64(dyn-prov-size+i*8,0);i=i+1;}
 dyn-count=saved;lib-phys=phys;lib-entry=entry;lib-size=size;lib-registered=registered;
 serial-write-cstr(port,"lifecycle: registry capacity refusal and exact-fit provider PASS");serial-nl(port);
}
fn lifecycle-start(port:Int)->void{
 lifecycle-registry-capacity(port);
 lifecycle-stale-cap=cap-mint(root-realm,cap-serial());cap-revoke(lifecycle-stale-cap);
 if runtime-instance-release-cap(lifecycle-stale-cap,root-realm)!=-1{panic("lifecycle borrowed cap recycled");}
 if domain-destroy-clone-owned(0)!=-1{panic("lifecycle kernel tree accepted");}
 let user=domain-create-user();let root=load64(domain-table+user*24);let free=free-list;
 if domain-destroy-clone-owned(user)!=-1 || free-list!=free || load64(domain-table+user*24)!=root{panic("lifecycle user tree accepted");}
 if domain-destroy-user(user)!=0{panic("lifecycle user control teardown");}
 if dyn-resolve-idx("runtime-instance-cap")!=-1 || dyn-resolve-idx("sci-load-retained-component")!=-1 || dyn-resolve-idx("domain-destroy-clone-owned")!=-1 || dyn-resolve-idx("domain-restore-service-context")!=-1{panic("lifecycle private authority exported");}
 let denied-image=boot-image-find(251);
 if load64(denied-image+8)!=1 || load64(denied-image+16)!=0x7e000040{panic("lifecycle private fixture identity");}
 if sci-load-runtime-component-implementation(port,denied-image,"private-import",1,1,0)!=-1{panic("lifecycle private import accepted");}
 if sci-load-runtime-component-implementation(port,boot-image-find(253),"private-foreign-import",1,1,0)!=-1{panic("lifecycle private foreign import accepted");}
 if sci-load-runtime-component-implementation(port,boot-image-find(256),"private-startup-import",1,1,0)!=-1{panic("lifecycle private startup import accepted");}
 if runtime-instance-live!=0{panic("lifecycle refused import retained state");}
 if sci-load-runtime-component-implementation(port,boot-image-find(252),"allocator-control",1,1,0)!=42{panic("lifecycle allocator ABI");}
 if sci-load-runtime-component-implementation(port,boot-image-find(254),"fresh-global-first",1,1,0)!=1 || sci-load-runtime-component-implementation(port,boot-image-find(254),"fresh-global-second",1,1,0)!=1{panic("ephemeral initialized globals shared");}
 serial-write-cstr(port,"lifecycle: fresh initialized globals PASS");serial-nl(port);
 lifecycle-observing=1;
}
'''
(out/'loader.in').write_text(loader)
hub=imports((root/'components/runtime-hub.in').read_text(),root/'components')
hub=hub.replace(json.dumps(str(root/'components/sci-loader.in')),json.dumps(str(out/'loader.in')))
(out/'hub.in').write_text(hub)
source=imports((root/'kernel/kernel-root.in').read_text(),root/'kernel')
source=source.replace(json.dumps(str(root/'components/runtime-hub.in')),json.dumps(str(out/'hub.in')))
assert source.count('  shell(port)')==1
source=source.replace('  shell(port)','  lifecycle-start(port)\n  shell(port)')
(out/'kernel.in').write_text(source)
run([a.compiler,'compile','--path',out/'kernel.in','--entry','kernel-entry','--emit','boot','--trampoline',out/'build/trampoline.bin','--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',out/'kernel.bin'],'kernel.log')
for source,entry,base,name in [('private-startup-import.in','private-entry','0x79000000','private-startup-import'),('global-state.in','fresh-entry','0x7b000000','global-state'),('allocation.in','failure-entry','0x7d000000','allocation'),('private-import.in','private-entry','0x7e000000','private-import'),('allocator.in','allocator-entry','0x7f000000','allocator'),('private-foreign-import.in','private-entry','0x7c000000','private-foreign-import')]:
 run([a.compiler,'compile','--path',root/'fixtures/runtime-failure'/source,'--entry',entry,'--target','native','--target-triple','x86_64-unknown-none','--emit','sci','--base',base,'--out',out/f'{name}.sci'],name+'.log')
image=(out/'build/standard.bin').read_bytes();table=struct.unpack_from('<Q',image,0xf00)[0]-0x100000
magic,count=struct.unpack_from('<QQ',image,table);assert magic==0x5350414345424f4f
specs=[]
for index in range(count):
 kind,physical,size,_=struct.unpack_from('<QQQQ',image,table+16+index*32)
 path=out/f'kind-{kind}.sci';path.write_bytes(image[physical-0x100000:physical-0x100000+size]);specs.append(f'{kind}:{path}')
specs += [f'256:{out}/private-startup-import.sci',f'254:{out}/global-state.sci',f'250:{out}/allocation.sci',f'251:{out}/private-import.sci',f'252:{out}/allocator.sci',f'253:{out}/private-foreign-import.sci']
run(['python3',root/'scripts/pack-sci-image.py',out/'kernel.bin',out/'combined.bin',*specs],'pack.log')
result=subprocess.run([sys.executable,str(root/'scripts/check-native-applications.py'),'--image',str(out/'combined.bin'),'--out',str(out/'applications'),'--repeat-cycles',str(a.cycles),'--allow-boot-denial'],cwd=root)
serial=(out/'applications/serial.log').read_bytes();observations=re.findall(rb'lifecycle: observed ([0-9]+) aborts ([0-9]+)',serial)
report={'status':'failed','compiler_sha256':hashlib.sha256(a.compiler.read_bytes()).hexdigest(),'image_sha256':hashlib.sha256((out/'combined.bin').read_bytes()).hexdigest(),'cycles':a.cycles,'driver_status':result.returncode,'observations':len(observations),'last_observation':[int(v) for v in observations[-1]] if observations else None,'original_source_sha256':hashlib.sha256((root/'components/sci-loader.in').read_bytes()).hexdigest(),'instrumented_loader_sha256':hashlib.sha256(loader.encode()).hexdigest()}
report['registry_capacity_refusals']=serial.count(b'SCI: DENIED export registry capacity')
report['registry_exact_fit_verified']=b'lifecycle: registry capacity refusal and exact-fit provider PASS' in serial
report['private_import_refused_before_entry']=b'DENIED unresolved import runtime-instance-cap' in serial and b'DENIED unresolved import darwin-protected-run' in serial and b'DENIED unresolved import windows-startup-entry' in serial and b'INVALID' not in serial
report['allocator_abi_verified']=b'SCI: allocator-control exited 0x000000000000002a' in serial
report['fresh_initialized_globals_verified']=b'lifecycle: fresh initialized globals PASS' in serial
report['resource_invariants']=['heap-next','free-frame count','domain-count','cap-count','object-arena high water','export-count','clone ownership','revoked generic capability denial']
if result.returncode==0 and observations and int(observations[-1][1])>128 and report['registry_capacity_refusals']>=3 and report['registry_exact_fit_verified'] and report['private_import_refused_before_entry'] and report['allocator_abi_verified'] and report['fresh_initialized_globals_verified']:
 report['status']='passed'
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(f"{report['status'].upper()}: actual native lifecycle; {out/'report.json'}")
sys.exit(0 if report['status']=='passed' else 1)
