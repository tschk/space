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
for filename, names in [('runtime-retained.in', ['runtime-instance-kernel-context','runtime-instance-record','runtime-instance-resume']), ('runtime-pixels.in', ['runtime-instance-pixel-bytes']), ('domain.in', ['domain-restore-service-context']), ('channel.in', ['chan-page-frame-header-valid']), ('sci-loader.in', ['sci-display-cap-info', 'sci-sync-pixels', 'sci-sync-restore-info', 'sci-resume-sync', 'sci-resume-sync-unit', 'sci-sync-provenance-valid', 'sci-sync-enter', 'sci-admit-input-sync', 'sci-resume-input-sync'])]:
    text = (root/'components'/filename).read_text()
    for name in names:
        start = text.index('fn '+name+'(')
        functions.append(text[start:text.index('\n}', start)+2])
text = (root/'protocol/input.in').read_text()
for name in ('input-page-header-valid', 'input-page-send', 'input-page-recv'):
    start = text.index('fn '+name+'(')
    functions.append(text[start:text.index('\n}', start)+2])
source = 'var memory:[Int]=[' + ','.join(['0']*20000) + '];\n' + '''
const RUNTIME-INSTANCE-CATALOG-SLOTS=64;const RUNTIME-INSTANCE-LIVE=0x52554e54494d4531;
const RUNTIME-INSTANCE-PIXEL-PAGES=288;const SCI-CANVAS-BYTES=1179648;
var runtime-instance-catalog:Int=16000;var runtime-instance-active:Int=0;var runtime-aborted:Int=0;
var sci-sync-handle:Int=257;var current-cap:Int=0;var model-root:Int=4096;
const COMP-HEAP-VIRT=0x80000000;
const COMP-HEAP-SIZE=0x200000;
const COMP-SHARED-VIRT=0x70000000;
const COMP-PIXEL-VIRT=0x70001000;
const SCI-V2-HEADER=64;
const SCI-INPUT-GRANTS=3;
const DOMAIN-ACTIVE=1;
var domain-count:Int=2;
var domain-table:Int=1500;
var cap-count:Int=1;
var cap-table-base:Int=1904;
var sci-sync-ring-unit:Int=4;
var sci-sync-domain:Int=1;
var sci-sync-grants:Int=20;
var sci-sync-pixel-phys:Int=8192;
var sci-sync-pixel-size:Int=4096;
var sci-sync-pixel-pool:Int=0;
var sci-sync-entry:Int=0x48000040;
var sci-sync-code-start:Int=0x48000000;
var sci-sync-code-end:Int=0x48001000;
var sci-sync-info:Int=13528;
var sci-sync-cap:Int=0;
var sci-sync-object:Int=14600;
var sci-sync-page:Int=4096;
var domain-current:Int=0;
var invoked:Int=0;
var fail-switch:Int=0;
fn cap-memory()->Int{return 4;}
fn cap-display()->Int{return 16;}
fn load64(p:Int)->Int{return memory[p];}
fn store64(p:Int,v:Int)->Void{memory[p]=v;}
fn cr3-read()->Int{return model-root;}
fn cr3-write(root:Int)->Void{if fail-switch==2 && root==4096{return;}model-root=root;return;}
fn runtime-invoke-entry(entry:Int,info:Int)->Int{return invoke1(entry,info);}
fn domain-get-current()->Int{return domain-current;}
fn domain-switch(id:Int)->Void{if fail-switch==0 || (fail-switch==2 && id!=0){domain-current=id;model-root=load64(domain-table+id*24);current-cap=load64(domain-table+id*24+16);}return;}
fn invoke1(entry:Int,info:Int)->Int{
 invoked+=1;
 if entry!=0x48000040 || info!=13528{return 1;}
 if load64(info)!=20 || load64(info+8)!=0 || load64(info+16)!=COMP-HEAP-VIRT || load64(info+24)!=COMP-HEAP-SIZE{return 2;}
 if load64(info+32)!=COMP-SHARED-VIRT || load64(info+40)!=1 || load64(info+48)!=800 || load64(info+56)!=600 || load64(info+64)!=55{return 3;}
 if load64(info+72)!=COMP-PIXEL-VIRT || load64(info+80)!=4096 || load64(info+88)!=0{return 4;}
 if domain-current!=1 || load64(4096)!=12 || load64(4104)!=12{return 5;}
 return 42;
}
''' + '\n'.join(functions) + '''
fn setup()->Void{
 model-root=4096;runtime-instance-active=0;runtime-aborted=0;sci-sync-handle=257;
 store64(13400,1);store64(13408,14600);store64(13416,0);store64(13432,4096);store64(13440,8192);store64(13512,0);store64(13704,1);
 store64(13656,RUNTIME-INSTANCE-LIVE);store64(13680,257);store64(13688,0x48000040);store64(13696,0);
 store64(14600,101);store64(14608,5);store64(14616,0x48000040);store64(14640,1);
 store64(16000,13400);store64(16008,1);store64(16016,101);store64(16024,14600);store64(16032,0);store64(16040,1);store64(16048,1);
 sci-sync-ring-unit=4;domain-count=2;cap-count=1;domain-current=0;fail-switch=0;
 sci-sync-domain=1;sci-sync-grants=20;sci-sync-cap=0;sci-sync-object=14600;
 sci-sync-pixel-phys=8192;sci-sync-pixel-size=4096;sci-sync-pixel-pool=0;
 sci-sync-entry=0x48000040;sci-sync-code-start=0x48000000;sci-sync-code-end=0x48001000;
 sci-sync-info=13528;sci-sync-page=4096;
 store64(domain-table,4096);store64(domain-table+8,1);
 store64(domain-table+24,8192);store64(domain-table+32,1);store64(domain-table+40,0);
 store64(cap-table-base,14600);store64(cap-table-base+8,20);
 store64(4096,12);store64(4104,12);store64(4112,508);store64(4120,8);
 // Every descriptor word is hostile; resume must rebuild all of them.
 let i=0;while i<96{store64(13528+i,-1);i+=8;}
 return;
}
fn main()->Int{
 setup();
 if sci-resume-sync(1,55)!=42 || invoked!=1 || domain-current!=0 || domain-count!=2 || cap-count!=1{return 6;}
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
    source += f'setup();{mutation}\nif sci-resume-sync({domain},55)!=-1 || invoked!=1 || domain-current!=0 || load64(13528)!=-1{{return {index};}}\n'
source += '''
 setup();fail-switch=1;
 if sci-resume-sync(1,55)!=-1 || invoked!=1 || domain-current!=0{return 40;}
 setup();fail-switch=2;
 if sci-resume-sync(1,55)!=-1 || invoked!=2 || domain-current!=1{return 41;}
 domain-current=0;
 setup();domain-current=1;
 if sci-resume-sync-unit(1,55,4)!=-1 || invoked!=2 || domain-current!=1 || load64(13528)!=-1{return 48;}
 // Admission cannot be requested by the input domain, even with valid provenance.
 sci-sync-grants=3;store64(cap-table-base+8,3);
 sci-sync-code-start=0x50000000;sci-sync-code-end=0x50001000;sci-sync-entry=0x50000040;
 sci-sync-pixel-phys=0;sci-sync-pixel-size=0;store64(13440,0);store64(13704,0);store64(13688,0x50000040);store64(14616,0x50000040);store64(4096,1);store64(4104,1);
 if sci-admit-input-sync(1)!=0 || sci-sync-ring-unit!=4 || invoked!=2 || domain-current!=1 || load64(13528)!=-1{return 49;}
 domain-current=0;
 // Unit-one role admission is private and cannot weaken ordinary SPDP entry.
 setup();sci-sync-grants=3;store64(cap-table-base+8,3);
 sci-sync-code-start=0x50000000;sci-sync-code-end=0x50001000;sci-sync-entry=0x50000040;
 sci-sync-pixel-phys=0;sci-sync-pixel-size=0;store64(13440,0);store64(13704,0);store64(13688,0x50000040);store64(14616,0x50000040);
 store64(4096,1);store64(4104,1);
 if sci-admit-input-sync(1)!=1 || sci-sync-ring-unit!=1{return 50;}
 if sci-resume-sync(1,55)!=-1 || invoked!=2 || load64(13528)!=-1{return 51;}
 store64(4112,0);
 if sci-resume-input-sync(1)!=-1 || invoked!=2 || domain-current!=0{return 52;}
 setup();
 if sci-admit-input-sync(1)!=0 || sci-sync-ring-unit!=4{return 53;}
 // Empty/full/wrap and rejection never consume partial or malformed state.
 store64(4096,0);store64(4104,0);store64(4112,3);store64(4120,8);store64(2000,777);
 if input-page-recv(4096,2000)!=0 || load64(2000)!=777{return 54;}
 if input-page-send(4096,97)!=1 || input-page-send(4096,98)!=1 || input-page-send(4096,99)!=0{return 55;}
 if input-page-recv(4096,2000)!=1 || load64(2000)!=97{return 56;}
 if input-page-send(4096,99)!=1 || load64(4096)!=0{return 57;}
 if input-page-recv(4096,2000)!=1 || load64(2000)!=98{return 58;}
 if input-page-recv(4096,2000)!=1 || load64(2000)!=99 || input-page-recv(4096,2000)!=0{return 59;}
 let bad=0;
 while bad<6 {
   store64(4096,0);store64(4104,0);store64(4112,3);store64(4120,8);store64(2000,777);
   if bad==0{store64(4112,0);}if bad==1{store64(4112,509);}if bad==2{store64(4096,-1);}
   if bad==3{store64(4096,3);}if bad==4{store64(4104,3);}if bad==5{store64(4120,4);}
   let head=load64(4096);let tail=load64(4104);
   if input-page-send(4096,42)!=-1 || input-page-recv(4096,2000)!=-1{return 60;}
   if load64(4096)!=head || load64(4104)!=tail || load64(2000)!=777{return 61;}
   bad+=1;
 }
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
