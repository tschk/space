#!/usr/bin/env python3
"""Run the real SCI v2 import/export table code against hostile manifests.

The loader patches `call rel32` sites named by an image's import table. Every
offset in that table is untrusted: a record must never make the kernel write
outside the image's own code, read a name outside the image, or leave a denied
image partially patched. Memory is modelled byte by byte so stray writes are
counted wherever they land.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--in', dest='compiler', required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
loader = (root / 'components/sci-loader.in').read_text()
names = ['dyn-str-eq', 'dyn-resolve-idx', 'dyn-ensure-tables', 'dyn-add', 'dyn-map-provider',
         'dyn-register-image-exports', 'sci-bind-imports']
names += [n for n in ('sci-v2-table-valid', 'sci-v2-name-valid', 'sci-v2-exports-valid')
          if 'fn ' + n + '(' in loader]
functions = []
for name in names:
    start = loader.index('fn ' + name + '(')
    body = loader[start:loader.index('\n}', start) + 2]
    # Diagnostics only; the harness observes return values and memory.
    functions.append(re.sub(r'^\s*serial-[\w-]+\(.*\)\s*$\n', '', body, flags=re.MULTILINE))

source = 'var memory:[Int]=[' + ','.join(['0'] * 12288) + '];\n' + '''
const MEM=12288;
const SCI-MAGIC-V2=0x5343490000000002;
const SCI-V2-HEADER=64;
const SCI-V2-EXPORT-COUNT=32;
const SCI-V2-EXPORT-TABLE=40;
const SCI-V2-IMPORT-COUNT=48;
const SCI-V2-IMPORT-TABLE=56;
const DYN-MAX-EXPORTS=8;
const IMG=1024;
const SIZE=1024;
const ENTRY=0x40000040;
const KFN=0x101234;
var dyn-name-tab:Int=0;
var dyn-fn-tab:Int=0;
var dyn-prov-phys:Int=0;
var dyn-prov-base:Int=0;
var dyn-prov-size:Int=0;
var dyn-count:Int=0;
var heap:Int=8192;
var stray:Int=0;
var mapped:Int=0;
fn load8(p:Int)->Int{if p<0 || p>=MEM{return 0;}return memory[p];}
fn store8(p:Int,v:Int)->Void{if p<0 || p>=MEM{stray+=1;return;}memory[p]=v&255;return;}
fn load64(p:Int)->Int{let v=0;let i=7;while i>=0{v=(v<<8)|load8(p+i);i-=1;}return v;}
fn store64(p:Int,v:Int)->Void{let i=0;while i<8{store8(p+i,(v>>(i*8))&255);i+=1;}return;}
// The only legitimate patch target is the image's code, after the header.
fn store32(p:Int,v:Int)->Void{
 if p<IMG+SCI-V2-HEADER || p+4>IMG+SIZE{stray+=1;}
 let i=0;while i<4{store8(p+i,(v>>(i*8))&255);i+=1;}return;
}
fn alloc(n:Int)->Int{let p=heap;heap+=n;return p;}
fn domain-map-user-code(d:Int,v:Int,p:Int)->Void{mapped+=1;return;}
''' + '\n'.join(functions) + '''
fn put-str(p:Int,s:Int)->Void{
 // "foo" or "bar" by selector, NUL-terminated.
 if s==0{store8(p,102);store8(p+1,111);store8(p+2,111);}else{store8(p,98);store8(p+1,97);store8(p+2,114);}
 store8(p+3,0);return;
}
fn setup(count:Int,table:Int)->Void{
 let i=0;while i<8192{memory[i]=0;i+=1;}
 heap=8192;dyn-name-tab=0;dyn-count=0;stray=0;mapped=0;
 dyn-ensure-tables();
 put-str(6000,0);
 dyn-add(6000,KFN,0,0,0);
 store64(IMG,SCI-MAGIC-V2);store64(IMG+16,ENTRY);store64(IMG+24,SIZE);
 store64(IMG+SCI-V2-IMPORT-COUNT,count);store64(IMG+SCI-V2-IMPORT-TABLE,table);
 put-str(IMG+200,0);put-str(IMG+208,1);
 return;
}
fn rec(i:Int,name:Int,site:Int)->Void{store64(IMG+512+i*16,name);store64(IMG+520+i*16,site);return;}
fn patched(site:Int)->Int{return load8(IMG+65+site)|(load8(IMG+66+site)<<8)|(load8(IMG+67+site)<<16)|(load8(IMG+68+site)<<24);}
fn deny(code:Int)->Int{
 if sci-bind-imports(1,IMG,7,ENTRY)!=-1 || stray!=0{return code;}
 return 0;
}
fn main()->Int{
 store64(100,-200);if load64(100)!=-200{return 1;}
 // A well-formed import is patched with its rel32 displacement.
 setup(1,512);rec(0,200,100);
 if sci-bind-imports(1,IMG,7,ENTRY)!=0 || stray!=0 || mapped!=0{return 2;}
 if patched(100)!=((KFN - ENTRY - 100 - 5)&0xFFFFFFFF){return 3;}
 // The last whole 5-byte call slot is accepted.
 setup(1,512);rec(0,200,SIZE - SCI-V2-HEADER - 5);
 if sci-bind-imports(1,IMG,7,ENTRY)!=0 || stray!=0{return 4;}
 // Call sites outside the image code: arbitrary kernel writes before the fix.
 setup(1,512);rec(0,200,4096);let r=deny(10);if r!=0{return r;}
 setup(1,512);rec(0,200,-200);r=deny(11);if r!=0{return r;}
 setup(1,512);rec(0,200,SIZE - SCI-V2-HEADER - 4);r=deny(12);if r!=0{return r;}
 setup(1,512);rec(0,200,5000 - IMG - SCI-V2-HEADER - 1);r=deny(13);if r!=0{return r;}
 // Malformed tables.
 setup(40,512);rec(0,200,100);r=deny(20);if r!=0{return r;}
 setup(1,-8);r=deny(21);if r!=0{return r;}
 setup(1<<40,512);r=deny(22);if r!=0{return r;}
 setup(1,SIZE);r=deny(23);if r!=0{return r;}
 setup(-1,512);r=deny(24);if r!=0{return r;}
 // Names outside the image or unterminated before its end.
 setup(1,512);rec(0,5000,100);r=deny(30);if r!=0{return r;}
 setup(1,512);rec(0,8,100);r=deny(31);if r!=0{return r;}
 setup(1,512);let i=IMG+1000;while i<IMG+SIZE{store8(i,65);i+=1;}rec(0,1000,100);r=deny(32);if r!=0{return r;}
 // A later bad record leaves earlier sites untouched.
 setup(2,512);rec(0,200,100);rec(1,200,4096);r=deny(40);if r!=0{return r;}
 if patched(100)!=0{return 41;}
 setup(2,512);rec(0,200,100);rec(1,208,140);r=deny(42);if r!=0{return r;}
 if patched(100)!=0{return 43;}
 // Export tables: registry entries may only point into the image.
 setup(0,512);store64(IMG+SCI-V2-EXPORT-COUNT,1);store64(IMG+SCI-V2-EXPORT-TABLE,512);rec(0,208,0);
 if dyn-register-image-exports(1,IMG,ENTRY,SIZE)!=0 || dyn-count!=2{return 50;}
 setup(0,512);store64(IMG+SCI-V2-EXPORT-COUNT,1);store64(IMG+SCI-V2-EXPORT-TABLE,512);rec(0,5000,0);
 if dyn-register-image-exports(1,IMG,ENTRY,SIZE)!=-1 || dyn-count!=1{return 51;}
 setup(0,512);store64(IMG+SCI-V2-EXPORT-COUNT,1);store64(IMG+SCI-V2-EXPORT-TABLE,512);rec(0,208,SIZE - SCI-V2-HEADER);
 if dyn-register-image-exports(1,IMG,ENTRY,SIZE)!=-1 || dyn-count!=1{return 52;}
 setup(0,512);store64(IMG+SCI-V2-EXPORT-COUNT,9);store64(IMG+SCI-V2-EXPORT-TABLE,SIZE - 16);rec(0,208,0);
 if dyn-register-image-exports(1,IMG,ENTRY,SIZE)!=-1 || dyn-count!=1{return 53;}
 return 42;
}
'''

with tempfile.TemporaryDirectory(prefix='space-sci-imports-') as directory:
    path = Path(directory) / 'imports.in'
    path.write_text(source)
    for profile in ('default', 'lean', 'harden'):
        result = subprocess.run([args.compiler, 'compile', '--path', str(path), '--target', 'jit', '--profile', profile,
                                 '--out', str(Path(directory) / 'out'), '--json'], capture_output=True, text=True, timeout=60)
        try:
            report = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise SystemExit(f'FAIL {profile}: compiler did not emit JSON\n{result.stdout}\n{result.stderr}')
        if not report.get('success') or report.get('eval_result') != {'Int': 42}:
            raise SystemExit(f"FAIL {profile}: eval_result={report.get('eval_result')} error={report.get('error')}")
        print(f'PASS {profile}: SCI v2 import/export tables cannot reach outside the image')
