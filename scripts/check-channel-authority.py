#!/usr/bin/env python3
"""Exercise channel syscalls with two isolated callers and recycled channels."""
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
text = (root / 'components/syscall.in').read_text()
functions = []
for match in re.finditer(r'^fn sys-chan-[\w-]+\(', text, re.MULTILINE):
    start = match.start()
    functions.append(text[start:text.index('\n}', start) + 2])
declarations = '\n'.join(line for line in text.splitlines()
                         if line.startswith(('const SYS-CHAN-', 'var sys-chan-')))
source = 'var memory:[Int]=[' + ','.join(['0'] * 10000) + '];\n' + declarations + '\n' + '''
var domain-current:Int=1;
var current-cap:Int=1;
var next:Int=100;
var last-channel:Int=0;
var sends:Int=0;
var frees:Int=0;
var allowed:Int=1;
fn alloc(n:Int)->Int{let p=next;next+=n;return p;}
fn load64(p:Int)->Int{return memory[p];}
fn store64(p:Int,v:Int)->Void{memory[p]=v;}
fn cap-graph()->Int{return 8;}
fn cap-require(rights:Int)->Int{return allowed;}
fn chan-new(cap:Int)->Int{last-channel=9000;return last-channel;}
fn chan-send(ch:Int,msg:Int)->Void{sends+=1;return;}
fn chan-recv(ch:Int)->Int{return 73;}
fn chan-heap-free(ch:Int)->Void{frees+=1;return;}
''' + '\n'.join(functions) + '''
fn main()->Int{
 let first=sys-chan-create(2);
 if first==0{return 1;}
 domain-current=2;current-cap=2;
 if sys-chan-send(first,42)!=-1 || sends!=0{return 2;}
 if sys-chan-recv(first)!=-1{return 3;}
 if sys-chan-close(first)!=-1 || frees!=0{return 4;}
 domain-current=1;current-cap=1;
 if sys-chan-send(first,42)!=0 || sends!=1{return 5;}
 if sys-chan-recv(first)!=73{return 6;}
 if sys-chan-close(first)!=0 || frees!=1{return 7;}
 let second=sys-chan-create(2);
 if second==0{return 8;}
 if sys-chan-send(first,42)!=-1 || sends!=1{return 9;}
 if sys-chan-send(last-channel,42)!=-1 || sends!=1{return 10;}
 if sys-chan-send(second,42)!=0 || sends!=2{return 11;}
 current-cap=2;
 if sys-chan-send(second,42)!=-1 || sends!=2{return 12;}
 current-cap=1;allowed=0;
 if sys-chan-send(second,42)!=-1 || sys-chan-create(2)!=0{return 13;}
 allowed=1;
 if sys-chan-close(second)!=0 || frees!=2{return 14;}
 return 42;
}
'''
with tempfile.TemporaryDirectory(prefix='space-channel-authority-') as temporary:
    path = Path(temporary) / 'test.in'
    path.write_text(source)
    for profile in ('default', 'lean', 'harden'):
        run = subprocess.run([args.compiler, 'compile', '--path', str(path), '--target', 'jit',
                              '--profile', profile, '--out', str(Path(temporary) / 'out'), '--json'],
                             capture_output=True, text=True, timeout=30)
        try:
            report = json.loads(run.stdout)
        except ValueError:
            raise SystemExit(f'FAIL {profile}: {run.stdout}\n{run.stderr}')
        if not report.get('success') or report.get('eval_result') != {'Int': 42}:
            raise SystemExit(f'FAIL {profile}: {run.stdout}\n{run.stderr}')
        print(f'PASS {profile}: cross-domain, stale and raw channel handles denied')
