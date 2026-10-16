#!/usr/bin/env python3
"""Execute actual bounded SCI resume guards with isolated domain/entry services."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--in', dest='compiler', required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
functions = []
for filename, names in [('channel.in', ['chan-page-frame-header-valid']), ('sci-loader.in', ['sci-display-cap-info', 'sci-sync-pixels', 'sci-sync-restore-info', 'sci-resume-sync'])]:
    text = (root/'components'/filename).read_text()
    for name in names:
        start = text.index('fn '+name+'(')
        functions.append(text[start:text.index('\n}', start)+2])
source = 'var memory:[Int]=[' + ','.join(['0']*8192) + '];\n' + '''
const COMP-HEAP-VIRT=0x80000000;
const COMP-HEAP-SIZE=0x200000;
const COMP-SHARED-VIRT=0x70000000;
const COMP-PIXEL-VIRT=0x70001000;
const SCI-V2-HEADER=64;
const DOMAIN-ACTIVE=1;
var domain-count:Int=2;
var domain-table:Int=1500;
var cap-count:Int=1;
var cap-table-base:Int=1904;
var sci-sync-domain:Int=1;
var sci-sync-grants:Int=20;
var sci-sync-pixel-phys:Int=8192;
var sci-sync-pixel-size:Int=4096;
var sci-sync-pixel-pool:Int=0;
var sci-sync-entry:Int=0x48000040;
var sci-sync-code-start:Int=0x48000000;
var sci-sync-code-end:Int=0x48001000;
var sci-sync-info:Int=1800;
var sci-sync-cap:Int=0;
var sci-sync-object:Int=77;
var sci-sync-page:Int=4096;
var current:Int=0;
var invoked:Int=0;
var fail-switch:Int=0;
fn cap-memory()->Int{return 4;}
fn cap-display()->Int{return 16;}
fn load64(p:Int)->Int{return memory[p];}
fn store64(p:Int,v:Int)->Void{memory[p]=v;}
fn domain-get-current()->Int{return current;}
fn domain-switch(id:Int)->Void{if fail-switch==0 || (fail-switch==2 && id!=0){current=id;}return;}
fn invoke1(entry:Int,info:Int)->Int{
 invoked+=1;
 if entry!=0x48000040 || info!=1800{return 1;}
 if load64(info)!=20 || load64(info+8)!=0 || load64(info+16)!=COMP-HEAP-VIRT || load64(info+24)!=COMP-HEAP-SIZE{return 2;}
 if load64(info+32)!=COMP-SHARED-VIRT || load64(info+40)!=1 || load64(info+48)!=800 || load64(info+56)!=600 || load64(info+64)!=55{return 3;}
 if load64(info+72)!=COMP-PIXEL-VIRT || load64(info+80)!=4096 || load64(info+88)!=0{return 4;}
 if current!=1 || load64(4096)!=12 || load64(4104)!=12{return 5;}
 return 42;
}
''' + '\n'.join(functions) + '''
fn setup()->Void{
 domain-count=2;cap-count=1;current=0;fail-switch=0;
 sci-sync-domain=1;sci-sync-grants=20;sci-sync-cap=0;sci-sync-object=77;
 sci-sync-pixel-phys=8192;sci-sync-pixel-size=4096;sci-sync-pixel-pool=0;
 sci-sync-entry=0x48000040;sci-sync-code-start=0x48000000;sci-sync-code-end=0x48001000;
 sci-sync-info=1800;sci-sync-page=4096;
 store64(domain-table,4096);store64(domain-table+8,1);
 store64(domain-table+24,8192);store64(domain-table+32,1);store64(domain-table+40,0);
 store64(cap-table-base,77);store64(cap-table-base+8,20);
 store64(4096,12);store64(4104,12);store64(4112,508);store64(4120,8);
 // Every descriptor word is hostile; resume must rebuild all of them.
 let i=0;while i<96{store64(1800+i,-1);i+=8;}
 return;
}
fn main()->Int{
 setup();
 if sci-resume-sync(1,55)!=42 || invoked!=1 || current!=0 || domain-count!=2 || cap-count!=1{return 6;}
'''
mutations = [
    ('sci-sync-domain=0;', 1), ('', 0), ('', 2),
    ('store64(domain-table+32,0);', 1), ('store64(domain-table+24,0);', 1),
    ('sci-sync-cap=-1;', 1), ('sci-sync-cap=1;', 1),
    ('store64(domain-table+40,1);', 1), ('store64(cap-table-base,0);', 1),
    ('store64(cap-table-base+8,4);', 1), ('sci-sync-entry=0x48000000;', 1),
    ('sci-sync-entry=0x48001000;', 1), ('sci-sync-code-end=0x48000000;', 1),
    ('sci-sync-code-end=0x100001000;', 1), ('sci-sync-info=1801;', 1),
    ('sci-sync-page=0;', 1), ('sci-sync-page=4097;', 1),
    ('store64(4112,512);', 1), ('store64(4120,4);', 1),
    ('store64(4104,16);', 1), ('store64(4104,14);', 1),
    ('sci-sync-pixel-size=4095;', 1), ('sci-sync-pixel-phys=0;', 1), ('store64(domain-table,0);', 1),
]
for index, (mutation, domain) in enumerate(mutations, 10):
    source += f'setup();{mutation}\nif sci-resume-sync({domain},55)!=-1 || invoked!=1 || current!=0 || load64(1800)!=-1{{return {index};}}\n'
source += '''
 setup();fail-switch=1;
 if sci-resume-sync(1,55)!=-1 || invoked!=1 || current!=0{return 40;}
 setup();fail-switch=2;
 if sci-resume-sync(1,55)!=-1 || invoked!=2 || current!=1{return 41;}
 current=0;
 return 42;
}
'''
with tempfile.TemporaryDirectory(prefix='space-sci-resume-') as directory:
    path = Path(directory)/'resume.in'
    path.write_text(source)
    for profile in ('default', 'lean', 'harden'):
        result = subprocess.run([args.compiler, 'compile', '--path', str(path), '--target', 'jit', '--profile', profile, '--out', str(Path(directory)/'out'), '--json'], capture_output=True, text=True, check=True, timeout=30)
        report = json.loads(result.stdout)
        assert report.get('success') and report.get('eval_result') == {'Int': 42}, report
        print(f'PASS {profile}: same-instance resume, full descriptor reconstruction, guarded rejection and domain restoration')
