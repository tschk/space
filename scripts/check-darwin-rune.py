#!/usr/bin/env python3
"""Independent C-table oracle, actual native data model and high-VA CPL3 objects.

These are owned ABI fixtures, never original macOS application execution.
"""
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
p.add_argument('--root',choices=['standard','minimal'],default='standard')
p.add_argument('--model-only',action='store_true')
a=p.parse_args();out=a.out.resolve();compiler=a.compiler.resolve()
assert not out.exists() or not any(out.iterdir()),'preserve earlier evidence'
out.mkdir(parents=True,exist_ok=True)
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
paths=[path for group in ('components','kernel','protocol','services') for path in (ROOT/group).rglob('*.in')]
paths += [ROOT/name for name in ('fixtures/darwin-mapped/process.asm','boot/multiboot.asm',
           'assets/darwin/rune/table.c','assets/darwin/rune/provenance.json')]+[Path(__file__)]
snapshot=out/'source';frozen={str(path.relative_to(ROOT)):path.read_bytes() for path in paths}
for name,data in frozen.items():
    path=snapshot/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
report=dict(status='running',goal_status='OPEN',scope='C-locale data ABI fixtures only; zero original application entries',
            compiler_sha256=sha(compiler),root=a.root,source_sha256={name:hashlib.sha256(data).hexdigest() for name,data in frozen.items()})
def run(command,name,timeout=180):
    with (out/name).open('w') as log:
        result=subprocess.run(list(map(str,command)),stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
    assert result.returncode==0,(name,(out/name).read_text()[-4000:])
try:
    # Compile the actual unchanged upstream cache initializer. Adapt only host
    # headers/Mach-O section spelling; cache values are evaluated by C itself.
    upstream=(snapshot/'assets/darwin/rune/table.c').read_text().split('struct xlocale_ctype')[0]
    upstream=re.sub(r'^#include[^\n]+','',upstream,flags=re.M)
    upstream=upstream.replace('__attribute__((section("__DATA,__constrw")))','')
    macros=dict(A=0x100,C=0x200,D=0x400,G=0x800,L=0x1000,P=0x2000,S=0x4000,U=0x8000,
                X=0x10000,B=0x20000,R=0x40000,I=0x80000,T=0x100000,Q=0x200000,
                SW0=0x20000000,SW1=0x40000000,SW2=0x80000000,SW3=0xc0000000)
    prelude='''#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#define __FBSDID(x)
#define _RUNE_MAGIC_A "RuneMagA"
typedef struct { int32_t count; void *ranges; } Range;
typedef struct { char magic[8],encoding[32]; void *deprecated[2]; int32_t invalid;
 uint32_t classes[256]; int32_t lower[256],upper[256];Range extensions[3];
 void *variable;int32_t length,class_count;void *class_data; } _RuneLocale;
_Static_assert(sizeof(_RuneLocale)==3208,"Darwin object size");
_Static_assert(offsetof(_RuneLocale,classes)==60,"classes offset");
_Static_assert(offsetof(_RuneLocale,lower)==1084,"lower offset");
_Static_assert(offsetof(_RuneLocale,upper)==2108,"upper offset");
'''+''.join(f'#define _CTYPE_{name} {value}u\n' for name,value in macros.items())
    oracle=out/'oracle.c';oracle.write_text(prelude+upstream+'''
int main(void){unsigned char page[4096]={0};uint64_t current=0x130002000ULL;
 memcpy(page,&_DefaultRuneLocale,sizeof(_DefaultRuneLocale));memcpy(page+3216,&current,8);
 return fwrite(page,1,4096,stdout)==4096?0:1;}
''')
    run(['cc','-std=c11','-O2',oracle,'-o',out/'oracle'],'oracle-build.log')
    with (out/'oracle.bin').open('wb') as output:subprocess.run([str(out/'oracle')],stdout=output,check=True)
    expected=(out/'oracle.bin').read_bytes();assert len(expected)==4096
    native='\n'.join(line for line in (snapshot/'components/darwin-rune.in').read_text().splitlines() if not line.startswith('package '))
    model='''var memory:[Int]=[ZEROS];var escaped=0;var writes=0;
fn store8(p:Int,v:Int)->void{if p<16 || p>=4112{escaped=1;return;}memory[p]=v&255;writes+=1;}
fn store32(p:Int,v:Int)->void{let i=0;while i<4{store8(p+i,(v>>(i*8))&255);i+=1;}}
fn store64(p:Int,v:Int)->void{let i=0;while i<8{store8(p+i,(v>>(i*8))&255);i+=1;}}
'''.replace('ZEROS',','.join(['0']*4128))+native
    model+='\nvar expected:[Int]=['+','.join(map(str,expected))+'];\nfn main()->Int{\n'
    model+='if darwin-rune-populate(0,4096,0x130002000)!=-22 || darwin-rune-populate(16,4095,0x130002000)!=-22 || darwin-rune-populate(16,4096,1)!=-22 || writes!=0{return 1;}\n'
    model+='let cycle=0;while cycle<22{if darwin-rune-populate(16,4096,0x130002000)!=0{return 2;}let i=0;while i<4096{if memory[16+i]!=expected[i]{return 100+i;}i+=1;}if escaped!=0 || memory[15]!=0 || memory[4112]!=0{return 3;}cycle+=1;}return 42;}\n'
    (out/'model.in').write_text(model)
    for profile in ('default','lean','harden'):
        result=subprocess.run([str(compiler),'compile','--path',str(out/'model.in'),'--target','jit','--profile',profile,'--out',str(out/profile),'--json'],capture_output=True,text=True,timeout=120)
        (out/(profile+'.json')).write_text(result.stdout);(out/(profile+'.stderr')).write_text(result.stderr)
        actual=json.loads(result.stdout);assert result.returncode==0 and actual.get('eval_result')=={'Int':42},actual
    report.update(native_model_profiles=3,oracle_bytes=4096,oracle_sha256=sha(out/'oracle.bin'))
    if not a.model_only:
        # The modern five-segment Mach-O skeleton is Space's own fixture.
        # Replace its test program and extend two real data bindings.
        source=(snapshot/'fixtures/darwin-mapped/process.asm').read_text()
        digest=0xcbf29ce484222325
        for byte in expected[60:3132]:digest=((digest^byte)*1099511628211)&((1<<64)-1)
        entry='''entry:
 mov r12,[rel got_rune]
 mov rax,0x130002000
 cmp r12,rax
 jne fail
 mov r13,[rel got_current]
 mov rax,0x130002c90
 cmp r13,rax
 jne fail
 cmp [r13],r12
 jne fail
 mov rax,0x4167614d656e7552
 cmp [r12],rax
 jne fail
 cmp dword[r12+8],0x454e4f4e
 jne fail
 cmp dword[r12+56],65533
 jne fail
 cmp qword[r12+40],0
 jne fail
 cmp qword[r12+48],0
 jne fail
 lea rsi,[r12+60]
 mov ecx,3072
 mov rax,0xcbf29ce484222325
 mov rdx,1099511628211
cache_loop:
 movzx r8d,byte[rsi]
 xor rax,r8
 imul rax,rdx
 inc rsi
 loop cache_loop
 mov rdx,CACHE_DIGEST
 cmp rax,rdx
 jne fail
 mov rax,0x100003000
 mov rax,[rax]
 cmp eax,1
 je write_object
 cmp eax,2
 je execute_object
 cmp eax,3
 je write_pointer
 cmp eax,4
 je execute_pointer
 cmp eax,5
 je write_padding
 cmp eax,6
 je read_outside
 cmp eax,7
 je write_fixup
 mov eax,42
 ret
write_object: mov byte[r12],0
 jmp fail
execute_object: call r12
 jmp fail
write_pointer: mov qword[r13],0
 jmp fail
execute_pointer: call r13
 jmp fail
write_padding: mov byte[r12+4095],0
 jmp fail
read_outside: mov rax,[r12+4096]
 jmp fail
write_fixup: mov byte[rel got_rune],0
fail: mov eax,99
 ret
code_end:
'''.replace('CACHE_DIGEST',str(digest))
        source=source[:source.index('entry:\n')]+entry+source[source.index(' times 0x1800-'):]
        source=source.replace("0x100002000,24,8192","0x100002000,40,8192").replace('0x100002018,8,8216','0x100002028,8,8232')
        source=source.replace('got_error: dq 0x8010000000000002','got_error: dq 0x8010000000000002\ngot_rune: dq 0x8010000000000003\ngot_current: dq 0x8010000000000004')
        source=source.replace('pool-fixups,3,1,0,0','pool-fixups,5,1,0,0')
        source=source.replace('1|((name_error-pool)<<9)','1|((name_error-pool)<<9),1|((name_rune-pool)<<9),1|((name_current-pool)<<9)')
        source=source.replace("name_error: db '___error',0","name_error: db '___error',0\nname_rune: db '__DefaultRuneLocale',0\nname_current: db '__CurrentRuneLocale',0")
        # The indirect symbol table describes three function stubs and five GOT
        # entries. All five undefined names remain real Mach-O symbol records.
        source=source.replace('dd symtab-image,4,','dd symtab-image,6,').replace('dd 0,0,0,1,1,3','dd 0,0,0,1,1,5').replace('dd indirect-image,6,','dd indirect-image,8,')
        source=source.replace(' undef symbol_error',' undef symbol_error\n undef symbol_rune\n undef symbol_current')
        source=source.replace('indirect: dd 1,2,3,1,2,3','indirect: dd 1,2,3,1,2,3,4,5')
        source=source.replace("symbol_error: db '___error',0","symbol_error: db '___error',0\nsymbol_rune: db '__DefaultRuneLocale',0\nsymbol_current: db '__CurrentRuneLocale',0")
        (out/'rune.asm').write_text(source)
        run(['nasm','-f','bin',out/'rune.asm','-o',out/'rune.macho'],'fixture-build.log')
        kernel=(snapshot/'kernel'/('kernel-root.in' if a.root=='standard' else 'kernel-root-minimal.in')).read_text()
        kernel=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(snapshot/m[1])),kernel)
        kernel='import '+json.dumps(str(snapshot/'components/darwin-mapped-process.in'))+'\n'+kernel
        assert kernel.count('  shell(port)')==1;kernel=kernel.replace('  shell(port)','  rune-check(port)')
        kernel+='''
fn rune-free()->Int{let page=free-list;let count=0;while page!=0&&count<131072{count+=1;page=load64(page);}if page!=0{panic("rune free chain");}return count;}
fn rune-check(port:Int)->void{
 let state=alloc(20480);cpu-mem-fill64(state,0,2560);let input=alloc(1024);cpu-mem-fill64(input,0,128);
 store64(input+8,input+64);store64(input+24,input+64);store64(input+40,input+64);
 let memory=cap-mint(root-realm,cap-memory());let serial=cap-mint(root-realm,cap-serial());
 let caps=cap-count;let caller=current-cap;let fs=rdmsr(0xc0000100);let gs=rdmsr(0xc0000101);
 let heap=0;let free=0;let domains=0;let cycle=0;
 while cycle<23{
  let mode=0;while mode<8{
   store64(0x11003000,mode);
   let result=darwin-mapped-prepare(0x11000000,IMAGE_SIZE,state,20480,DARWIN-MAPPED-IDENTITY);
   if result!=0{serial-write-dec-wide(port,result);panic("rune image prepare");}
   let digest=darwin-mapped-digest(0x11000000,IMAGE_SIZE);
   result=darwin-mapped-run(state,input,1024,DARWIN-MAPPED-IDENTITY,serial,memory,1000);
   let expected=142;if mode==0{expected=42;}
   if result!=expected{serial-write-dec-wide(port,mode);serial-put(port,32);serial-write-dec-wide(port,result);panic("rune protected result");}
   if mode!=0{
    let error=7;if mode==2||mode==4{error=21;}if mode==6{error=4;}
    if load64(state+4096+696)!=14 || load64(state+4096+704)!=error || load64(state+160)!=USER-CONTEXT-FAULT{panic("rune hardware permissions");}
   }
   if darwin-mapped-digest(0x11000000,IMAGE_SIZE)!=digest || load64(state+56)!=0 || load64(state+64)!=0 || load64(state+48)!=3{panic("rune immutable source and lifetime");}
   if domain-current!=0||user-context-active!=0||domain-user-syscall-hook!=0||darwin-mapped-active!=0||current-cap!=caller||rdmsr(0xc0000100)!=fs||rdmsr(0xc0000101)!=gs{panic("rune supervisor context");}
   if cycle>0 && (heap-next!=heap||rune-free()!=free||domain-count!=domains||cap-count!=caps){panic("rune stable resources");}
   mode+=1;
  }
  if cycle==0{heap=heap-next;free=rune-free();domains=domain-count;}
  cycle+=1;
 }
 serial-write-cstr(port,"darwin-rune:184 actual CPL3 data/cache/RO/NX/lifetime fixtures PASS");serial-nl(port);outb(0xf4,16);
}
'''.replace('IMAGE_SIZE',str((out/'rune.macho').stat().st_size))
        (out/'kernel.in').write_text(kernel)
        run(['nasm','-f','bin',snapshot/'boot/multiboot.asm','-o',out/'trampoline.bin'],'trampoline.log')
        run([compiler,'compile','--path',out/'kernel.in','--entry','kernel-entry','--emit','boot','--trampoline',out/'trampoline.bin','--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',out/'kernel.bin'],'kernel-build.log')
        command=['qemu-system-x86_64','-cpu','max','-kernel',str(out/'kernel.bin'),'-m','512M','-display','none','-no-reboot','-serial','file:'+str(out/'serial.log'),'-device','isa-debug-exit,iobase=0xf4,iosize=0x04','-device',f'loader,file={out}/rune.macho,addr=0x11000000,force-raw=on']
        with (out/'qemu.log').open('w') as log:result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        serial=(out/'serial.log').read_text();assert result.returncode==33 and '184 actual CPL3' in serial,serial[-4000:]
        report.update(own_cpl3_entries=184,original_application_entries=0,kernel_sha256=sha(out/'kernel.bin'),fixture_sha256=sha(out/'rune.macho'))
    assert all((ROOT/name).read_bytes()==data for name,data in frozen.items()),'source changed during test'
    report['status']='passed';print('PASS Darwin rune data model'+(' and184 actual protected fixtures' if not a.model_only else ''),flush=True)
except Exception as error:
    report.update(status='failed',error=str(error));raise
finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
