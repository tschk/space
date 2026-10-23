#!/usr/bin/env python3
"""Validate original jq image layout in QEMU without claiming application entry."""
import argparse,hashlib,json,re,shutil,struct,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--in',dest='compiler',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--jq',type=Path,required=True);p.add_argument('--lua-dir',type=Path,required=True);p.add_argument('--profile',choices=['default','lean','harden'],default='default');p.add_argument('--control-ignore-unknown',action='store_true',help='Generated-source regression control; must detect an admitted appended command');a=p.parse_args();a.out=a.out.resolve();a.compiler=a.compiler.resolve()
if a.out.exists() and any(a.out.iterdir()):p.error('--out must be new or empty')
a.out.mkdir(parents=True,exist_ok=True)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def pin(path,expected):assert sha(path)==expected['sha256'] and path.stat().st_size==expected['size_bytes'],'unmodified app checksum/size mismatch'
manifest=json.loads((ROOT/'fixtures/applications/jq-1.8.1.json').read_text());pin(a.jq,next(x for x in manifest['apps'] if x['personality']=='darwin'))
lua_manifest=json.loads((ROOT/'fixtures/applications/lua-5.2.4-macos.json').read_text())
for name in ['lua52','luac52']:pin(a.lua_dir/name,next(x for x in lua_manifest['files'] if x['name']==name))
# Independent host parser: decode structures, tables and actual chains directly.
binary=a.jq.read_bytes();magic,cpu,subtype,kind,ncmds,commandbytes,flags,reserved=struct.unpack_from('<8I',binary);assert (magic,cpu,kind)==(0xfeedfacf,0x1000007,2)
commands=[];segments=[];sections=[];off=32
section_kinds={'__text':1,'__stubs':2,'__const':3,'__cstring':4,'__ustring':5,'__unwind_info':6,'__got':7,'__data':8,'__bss':9};segment_kinds={'__PAGEZERO':1,'__TEXT':2,'__DATA_CONST':3,'__DATA':4,'__LINKEDIT':5}
for i in range(ncmds):
 cmd,size=struct.unpack_from('<II',binary,off);assert size>=8 and off+size<=32+commandbytes;commands.append({'offset':off,'command':cmd,'size':size})
 if cmd==0x19:
  name=binary[off+8:off+24].split(b'\0')[0].decode();va,vm,fo,fs,maxprot,prot,nsects,segflags=struct.unpack_from('<QQQQIIII',binary,off+24);segments.append({'command_offset':off,'name':name,'va':va,'vm':vm,'file':fo,'file_size':fs,'maxprot':maxprot,'prot':prot,'first_section':len(sections),'section_count':nsects,'flags':segflags})
  for j in range(nsects):
   s=off+72+j*80;sn=binary[s:s+16].split(b'\0')[0].decode();address,amount,at,align,rel,nrel,attributes,res1,res2,res3=struct.unpack_from('<QQIIIIIIII',binary,s+32);sections.append({'source_offset':s,'name':sn,'va':address,'size':amount,'file':at,'align':align,'flags':attributes,'segment':len(segments)-1,'reserved1':res1,'reserved2':res2})
 off+=size
assert off==32+commandbytes
bykind={x['command']:x for x in commands};entry=struct.unpack_from('<Q',binary,bykind[0x80000028]['offset']+8)[0];fix,fixbytes=struct.unpack_from('<II',binary,bykind[0x80000034]['offset']+8);_,starts,imports,symbols,count,fmt,compressed=struct.unpack_from('<7I',binary,fix);assert fmt==1 and compressed==0
names=[]
for i in range(count):
 word=struct.unpack_from('<I',binary,fix+imports+4*i)[0];names.append(binary[fix+symbols+(word>>9):fix+fixbytes].split(b'\0')[0].decode())
chains=[]
for i,seg in enumerate(segments):
 record=struct.unpack_from('<I',binary,fix+starts+4+i*4)[0]
 if not record:continue
 rec=fix+starts+record;recordbytes,pagebytes,form,offset,maxptr,npages=struct.unpack_from('<IHHQIH',binary,rec);assert pagebytes==4096 and form==6 and offset==seg['va']-0x100000000
 for page in range(npages):
  pos=struct.unpack_from('<H',binary,rec+22+2*page)[0]
  if pos==65535:continue
  while True:
   at=seg['file']+page*4096+pos;raw=struct.unpack_from('<Q',binary,at)[0];bind=bool(raw>>63);chains.append({'offset':at,'bind':bind,'ordinal':raw&0xffffff if bind else None,'target':None if bind else 0x100000000+(raw&((1<<36)-1))});step=((raw>>51)&4095)*4
   if not step:break
   pos+=step;assert pos<4096
plan=bytearray(3840);pages=sum(x['vm']//4096 for x in segments if x['name']!='__PAGEZERO');header=[0x4457504c414e0001,1,len(binary),0x11000000,0x100000000,0x100000000+entry,len(segments),len(sections),ncmds,fix,fixbytes,bykind[12]['offset'],pages,0x100000000,flags,3840];struct.pack_into('<16Q',plan,0,*header)
for i,s in enumerate(segments):struct.pack_into('<10Q',plan,128+i*80,s['command_offset'],s['va'],s['vm'],s['file'],s['file_size'],s['maxprot'],s['prot'],s['first_section'],s['section_count'],segment_kinds[s['name']])
for i,s in enumerate(sections):struct.pack_into('<10Q',plan,768+i*80,s['source_offset'],s['va'],s['size'],s['file'],s['flags'],s['align'],s['segment'],s['reserved1'],s['reserved2'],section_kinds[s['name']])
for i,c in enumerate(commands):struct.pack_into('<QQ',plan,3328+i*16,c['offset'],c['command'])
(a.out/'expected-plan.bin').write_bytes(plan)
snap=a.out/'source';snap.mkdir()
for folder in ['components','kernel','boot','protocol','services']:shutil.copytree(ROOT/folder,snap/folder)
if a.control_ignore_unknown:
 provider=snap/'components/darwin-image-plan.in';text=provider.read_text();needle='else { return -38 }\n    if mark != 0';assert text.count(needle)==1;provider.write_text(text.replace(needle,'else { }\n    if mark != 0'))
hashes={str(f.relative_to(snap)):sha(f) for f in snap.rglob('*') if f.is_file()}
report={'status':'running','profile':a.profile,'compiler':str(a.compiler),'compiler_sha256':sha(a.compiler),'runner_sha256':sha(Path(__file__)),'frozen_source_sha256':hashes,'original_applications':[{'name':q.name,'sha256':sha(q),'executed':False} for q in [a.jq,a.lua_dir/'lua52',a.lua_dir/'luac52']],'oracle':{'segments':segments,'sections':sections,'commands':commands,'imports':names,'chains':chains,'backing_image_pages':pages,'expected_plan_sha256':sha(a.out/'expected-plan.bin')},'source_test_variance':'unknown command rejection removed only in frozen generated control' if a.control_ignore_unknown else None,'commands':[]}
def run(command,log,timeout=180):
 report['commands'].append(command)
 with log.open('w') as f:return subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
try:
 source=(snap/'kernel/kernel-root.in').read_text();source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(snap/m[1])),source);source='import '+json.dumps(str(snap/'components/darwin-image-plan.in'))+'\n'+source;assert source.count('  shell(port)')==1;source=source.replace('  shell(port)','  image-check(port)')
 source+='''
fn image-fill(p:Int,bytes:Int)->void{let n=0;while n<bytes{store8(p+n,165);n+=1;}return;}
fn image-unchanged(p:Int,bytes:Int)->void{let n=0;while n<bytes{if load8(p+n)!=165{panic("image failure published output");}n+=1;}return;}
fn image-refuse(image:Int,plan:Int,offset:Int,value:Int,width:Int,expected:Int)->void{
 let original=load32(image+offset);if width==8{original=load64(image+offset);}if width==1{original=load8(image+offset);}
 image-fill(plan,4096);let heap=heap-next;let free=free-list;let domains=domain-count;let caps=cap-count;
 if width==8{store64(image+offset,value);}else{if width==1{store8(image+offset,value);}else{store32(image+offset,value);}}
 let result=darwin-image-plan(image,IMAGE_SIZE,plan,4096);
 if width==8{store64(image+offset,original);}else{if width==1{store8(image+offset,original);}else{store32(image+offset,original);}}
 if result!=expected{serial-write-cstr(com1(),"image refusal offset ");serial-write-dec-wide(com1(),offset);serial-write-cstr(com1()," result ");serial-write-dec-wide(com1(),result);serial-nl(com1());panic("image malformed classification");}
 image-unchanged(plan,4096);
 if heap-next!=heap||free-list!=free||domain-count!=domains||cap-count!=caps{panic("image refusal allocation");}
}
fn image-chain-refuse(image:Int,plan:Int,offset:Int,value:Int,width:Int,expected:Int)->void{
 let original=load64(image+offset);if width==4{original=load32(image+offset);}if width==2{original=load16(image+offset);}
 if width==8{store64(image+offset,value);}else{if width==4{store32(image+offset,value);}else{store16(image+offset,value);}}
 let layout=darwin-image-plan(image,IMAGE_SIZE,plan,4096);let result=layout;if layout==0{result=darwin-image-import-preflight(plan);}
 if width==8{store64(image+offset,original);}else{if width==4{store32(image+offset,original);}else{store16(image+offset,original);}}
 if result!=expected{serial-write-cstr(com1(),"image chain offset ");serial-write-dec-wide(com1(),offset);serial-write-cstr(com1()," result ");serial-write-dec-wide(com1(),result);serial-nl(com1());panic("image malformed chain classification");}
}
fn image-appended-refuse(image:Int,plan:Int,command:Int)->void{
 let count=load32(image+16);let extent=load32(image+20);let at=image+32+extent;let saved=load64(at);
 image-fill(plan,4096);store32(image+16,count+1);store32(image+20,extent+8);store32(at,command);store32(at+4,8);
 let result=darwin-image-plan(image,IMAGE_SIZE,plan,4096);store32(image+16,count);store32(image+20,extent);store64(at,saved);
 if result!= -38{serial-write-cstr(com1(),"image appended unknown command admitted");serial-nl(com1());outb(0xF4,17);return;}
 image-unchanged(plan,4096);return;
}
fn image-check(port:Int)->void{
 // Original closed-profile baseline is tested before the new planning path.
 if dyn-kernel-exportable("darwin-image-plan")!=0||dyn-kernel-exportable("darwin-image-import-preflight")!=0||dyn-resolve-idx("darwin-image-plan")!=-1{panic("raw image planner exported");}
 let image=0x11000000;let plan=alloc(4096);let copy=alloc(IMAGE_SIZE);let n=0;while n<IMAGE_SIZE{store8(copy+n,load8(image+n));n+=1;}
 let heap=heap-next;let free=free-list;let domains=domain-count;let caps=cap-count;
 image-fill(plan,4096);if darwin-image-import-preflight(0)!=-8||darwin-image-import-preflight(plan)!=-8||darwin-image-unknown-import(0)!=0{panic("invalid plan header accepted");}
 if darwin-heap-run(image,IMAGE_SIZE,0,0,DARWIN-HEAP-IDENTITY,-1,-1,-1,1000)!=-8{panic("original jq old-profile baseline");}
 if darwin-heap-run(0x12000000,LUA_SIZE,0,0,DARWIN-HEAP-IDENTITY,-1,-1,-1,1000)!=-8||darwin-heap-run(0x13000000,LUAC_SIZE,0,0,DARWIN-HEAP-IDENTITY,-1,-1,-1,1000)!=-8{panic("original Lua old-profile baseline");}
 let cycle=0;
 while cycle<21{
  image-fill(plan,4096);let result=darwin-image-plan(image,IMAGE_SIZE,plan,4096);
  if result!=0{serial-write-cstr(port,"image plan result ");serial-write-dec-wide(port,result);serial-nl(port);panic("original jq layout refused");}
  n=0;while n<3840{if load8(plan+n)!=load8(0x14000000+n){serial-write-dec-wide(port,n);panic("native plan differs from independent host oracle");}n+=1;}
  n=3840;while n<4096{if load8(plan+n)!=165{panic("plan overwrote caller tail");}n+=1;}
  if darwin-image-import-preflight(plan)!=-38{panic("original jq unavailable imports did not refuse");}
  let unknown=darwin-image-unknown-import(plan);
  if darwin-image-string(unknown,unknown+256,"__DefaultRuneLocale")==0{panic("wrong original jq unsupported dependency diagnostic");}
  if heap-next!=heap||free-list!=free||domain-count!=domains||cap-count!=caps||domain-current!=0||darwin-protected-busy!=0||darwin-protected-count!=0||domain-user-syscall-hook!=0||user-context-active!=0{panic("planning changed execution ownership");}
  cycle+=1;
 }
 image-appended-refuse(image,plan,0x80000077);image-appended-refuse(image,plan,0x7777);
 image-fill(plan,4096);
 if darwin-image-plan(0x12000000,LUA_SIZE,plan,4096)!=-38||darwin-image-plan(0x13000000,LUAC_SIZE,plan,4096)!=-38{panic("classic Lua profile not refused");}image-unchanged(plan,4096);
 if darwin-image-plan(image,IMAGE_SIZE,plan,3839)!=-14||darwin-image-plan(image,IMAGE_SIZE,image,4096)!=-14||darwin-image-plan(0,IMAGE_SIZE,plan,4096)!=-8{panic("plan pointer/size refusal");}image-unchanged(plan,4096);
 // POSITIVE_IMPORT_CONTROL
 // MUTATIONS
 // CHAIN_MUTATIONS
 n=0;while n<IMAGE_SIZE{if load8(image+n)!=load8(copy+n){panic("original image modified");}n+=1;}
 if heap-next!=heap||free-list!=free||domain-count!=domains||cap-count!=caps{panic("malformed controls changed allocation");}
 serial-write-cstr(port,"darwin-image: original jq 21 validated plans, unavailable imports refused; original applications never entered PASS");serial-nl(port);outb(0xF4,16);
}
'''
 source=source.replace('IMAGE_SIZE',str(len(binary))).replace('LUA_SIZE',str((a.lua_dir/'lua52').stat().st_size)).replace('LUAC_SIZE',str((a.lua_dir/'luac52').stat().st_size))
 mutations=[(16,0,4,-8),(20,4097,4,-8),(24,0,4,-8),(36,88,4,-8),(64,0,8,-8),(136,0,8,-8),(128,0x100000001,8,-8),(128,0x1000c4000,8,-8),(152,len(binary)+1,8,-8),(172,1,4,-38),(112,ord('!'),1,-38),(160,7,4,-38),(176,ord('!'),1,-38),(240,9,4,-38),(240,0x11,4,-38),(232,1,4,-8),(224,len(binary),4,-8),(216,0x200000,8,-8),(208,0,8,-8),(1440,0,8,-8),(1456,0x80000077,4,-38),(1360,0x7777,4,-38),(1384,0x80000077,4,-38),(1480,ord('!'),1,-38),(1476,0,4,-38),(1404,2,4,-38),(1336,13,4,-38),(1232,len(binary),4,-8),(1240,len(binary),4,-8),(1264,2,4,-8),(1280,1,4,-38),(bykind[38]['offset']+12,1,4,-8)]
 # Malformed actual descriptive export trie: self-cycle and missing terminator.
 export,exportbytes=struct.unpack_from('<II',binary,bykind[0x80000033]['offset']+8);mutations.append((export+22,0,1,-8));mutations.append((bykind[0x80000033]['offset']+12,1,4,-8))
 source=source.replace('// MUTATIONS','\n'.join(f'image-refuse(image,plan,{off},{value},{width},{expected});' for off,value,width,expected in mutations))
 bind=next(c['offset'] for c in chains if c['bind']);rebase=next(c['offset'] for c in chains if not c['bind']);badordinal=(struct.unpack_from('<Q',binary,bind)[0]&~0xffffff)|count
 chainmut=[(fix,1,4,-8),(fix+4,33,4,-8),(fix+16,257,4,-8),(fix+20,2,4,-8),(fix+24,1,4,-8),(fix+32,6,4,-8),(fix+imports,2,4,-8),(bind,badordinal,8,-8),(rebase,0x1fffff,8,-8),(fix+56+6,2,2,-8)]
 def signed(v):return v if v<1<<63 else v-(1<<64)
 source=source.replace('// CHAIN_MUTATIONS','\n'.join(f'image-chain-refuse(image,plan,{off},{signed(value)},{width},{expected});' for off,value,width,expected in chainmut))
 # Generated-source owning-function control only: retain actual original chain
 # geometry while pointing every import at one genuine implemented API. This
 # is never entered and never counted as original application execution.
 known=names.index('___error');knownword=struct.unpack_from('<I',binary,fix+imports+known*4)[0]
 source=source.replace('// POSITIVE_IMPORT_CONTROL',f'let item=0;while item<{count}{{store32(image+{fix+imports}+item*4,{knownword});item+=1;}}if darwin-image-plan(image,{len(binary)},plan,4096)!=0||darwin-image-import-preflight(plan)!=0{{panic("supported import owner control refused");}}item=0;while item<{count}{{store32(image+{fix+imports}+item*4,load32(copy+{fix+imports}+item*4));item+=1;}}')
 report['positive_import_control']='generated import table points to existing ___error; chain geometry unchanged; not executed or counted as original application coverage'
 report['layout_refusal_cases']=len(mutations);report['chain_refusal_cases']=len(chainmut);(a.out/'kernel.in').write_text(source)
 for command in [['nasm','-f','bin',str(snap/'boot/multiboot.asm'),'-o',str(a.out/'trampoline.bin')],[str(a.compiler),'compile','--path',str(a.out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(a.out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--profile',a.profile,'--out',str(a.out/'kernel.bin')]]:assert run(command,a.out/('compile.log' if command[0]!='nasm' else 'nasm.log')).returncode==0,(a.out/'compile.log').read_text()[-5000:]
 assert (a.out/'kernel.bin').stat().st_size<0xff00000
 command=['qemu-system-x86_64','-kernel',str(a.out/'kernel.bin'),'-m','512M','-display','none','-no-reboot','-serial','file:'+str(a.out/'serial.log'),'-device','isa-debug-exit,iobase=0xf4,iosize=0x04']
 for path,address in [(a.jq,0x11000000),(a.lua_dir/'lua52',0x12000000),(a.lua_dir/'luac52',0x13000000),(a.out/'expected-plan.bin',0x14000000)]:command+=['-device',f'loader,file={path.resolve()},addr={hex(address)},force-raw=on']
 result=run(command,a.out/'qemu.log',75);serial=(a.out/'serial.log').read_text()
 if a.control_ignore_unknown:assert result.returncode==35 and 'image appended unknown command admitted' in serial,serial[-5000:]
 else:assert result.returncode==33 and 'original applications never entered PASS' in serial,serial[-5000:]
 report['frozen_source_changed_during_run']=[name for name,digest in hashes.items() if sha(snap/name)!=digest];assert not report['frozen_source_changed_during_run'];report.update(status='passed',cycles=21,original_application_executions=0,jq_layout='validated',jq_imports='unsupported',first_unavailable_import=names[0],kernel_sha256=sha(a.out/'kernel.bin'),negative_control_detected=a.control_ignore_unknown,old_profile_admission=-8,lua_layout_admission=-38);print('PASS regression control caught appended unknown command' if a.control_ignore_unknown else 'PASS original jq actual layout, independent plan oracle and import refusal; no application entry',flush=True)
except Exception as error:report.update(status='failed',error=str(error));print('FAIL',error,flush=True)
finally:(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='passed' else 1)
