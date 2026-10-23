#!/usr/bin/env python3
"""Execute the actual bounded GUI file API with isolated authority/FS models."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', required=True)
a = p.parse_args()
source = (root/'components/gui-note-store.in').read_text()
source = source.replace('package space.kernel', '')
for name in ('cap-require', 'cap-check'):
    text = (root/'components/object.in').read_text()
    start = text.index('fn '+name+'(')
    source += '\n'+text[start:text.index('\n}', start)+2]
source = '''var memory:[Int]=['''+','.join(['0']*5000)+'''];
const DOMAIN-ACTIVE=1;const COMP-HEAP-VIRT=0x80000000;
const COMP-HEAP-SIZE=0x200000;const SF-ST-SIZE=8;
var domain-count:Int=2;var domain-table:Int=1000;var current-cap:Int=0;
var cap-count:Int=1;var cap-table-base:Int=2000;var current:Int=1;
var nvme-ready:Int=1;var sf-mem-disk:Int=0;var sf-disk-ready:Int=1;
var calls:Int=0;var writes:Int=0;var allocated:Int=0;var file-size:Int=3;
fn domain-get-current()->Int{return current;}
fn cap-storage()->Int{return 32;}
fn load64(p:Int)->Int{return memory[p];}
fn store64(p:Int,v:Int)->Void{memory[p]=v;return;}
fn alloc(n:Int)->Int{allocated+=1;return 3000;}
fn fs-stat(path:Int,buffer:Int)->Int{calls+=1;store64(buffer+8,file-size);return 0;}
fn fs-read-file(path:Int,buffer:Int,size:Int)->Int{calls+=1;return file-size;}
fn fs-write-file(path:Int,buffer:Int,size:Int)->Int{calls+=1;writes+=1;return 0;}
'''+source+'''
fn main()->Int{
 store64(domain-table+32,1);store64(domain-table+40,0);
 store64(cap-table-base,123);store64(cap-table-base+8,20);
 if gui-note-write(0,9)!=-13 || gui-note-read(0,8)!=-13{return 1;}
 if calls!=0 || writes!=0 || allocated!=0 || gui-note-store-epoch!=0{return 2;}
 store64(cap-table-base+8,52);
 current=0;if gui-note-write(COMP-HEAP-VIRT,3)!=-13{return 3;}current=1;
 store64(domain-table+32,0);if gui-note-write(COMP-HEAP-VIRT,3)!=-13{return 4;}store64(domain-table+32,1);
 current-cap=-1;if gui-note-write(COMP-HEAP-VIRT,3)!=-13{return 5;}current-cap=0;
 store64(cap-table-base,0);if gui-note-write(COMP-HEAP-VIRT,3)!=-13{return 6;}store64(cap-table-base,123);
 if gui-note-write(COMP-HEAP-VIRT,9)!=-22 || gui-note-write(COMP-HEAP-VIRT,-1)!=-22{return 7;}
 if gui-note-write(COMP-HEAP-VIRT - 1,1)!=-22 || gui-note-write(COMP-HEAP-VIRT+COMP-HEAP-SIZE,1)!=-22{return 8;}
 if gui-note-read(COMP-HEAP-VIRT,7)!=-22{return 9;}
 nvme-ready=0;if gui-note-write(COMP-HEAP-VIRT,3)!=-19{return 10;}nvme-ready=1;
 sf-mem-disk=1;if gui-note-read(COMP-HEAP-VIRT,8)!=-19{return 11;}sf-mem-disk=0;
 sf-disk-ready=0;if gui-note-write(COMP-HEAP-VIRT,0)!=-19{return 12;}sf-disk-ready=1;
 if calls!=0 || writes!=0 || allocated!=0 || gui-note-store-epoch!=0{return 13;}
 if gui-note-write(COMP-HEAP-VIRT,0)!=0 || writes!=1 || calls!=1 || gui-note-store-epoch!=1{return 14;}
 if gui-note-read(COMP-HEAP-VIRT,8)!=3 || calls!=3 || allocated!=1 || gui-note-store-epoch!=2{return 15;}
 file-size=9;if gui-note-read(COMP-HEAP-VIRT,8)!=-27 || calls!=4 || allocated!=1{return 16;}
 return 42;
}
'''
with tempfile.TemporaryDirectory(prefix='space-gui-store-') as directory:
    fixture = Path(directory)/'store.in'; fixture.write_text(source)
    for profile in ('default','lean','harden'):
        run = subprocess.run([a.compiler,'compile','--path',str(fixture),'--target','jit','--profile',profile,'--out',str(Path(directory)/profile),'--json'],capture_output=True,text=True,check=True,timeout=30)
        report = json.loads(run.stdout)
        assert report.get('success') and report.get('eval_result')=={'Int':42},report
        print(f'PASS {profile}: actual GUI file API authority/bounds/backend guards before FS/allocation; zero save/read/oversize refusal')
