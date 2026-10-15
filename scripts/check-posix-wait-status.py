#!/usr/bin/env python3
"""Execute the real wait4 translator with isolated process/memory services.

IN selects an existing compiler; this check never builds one. Memory service
stubs record the four byte writes so adjacent bytes and null/error paths remain
observable. This is service-level execution, not a scheduler or QEMU test.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--in', dest='compiler', required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
text = (root / 'components/posix.in').read_text()
start = text.index('fn posix-sys-wait4(')
end = text.index('\nfn ', start + 3)
function = text[start:end]
source = '''
const LINUX-ECHILD:Int=-10;
var proc-count:Int=2;
var code:Int=42;
var waits:Int=0;
var writes:Int=0;
var bytes:[Int]=[99,99,99,99,99,99,99,99];
fn proc-wait(pid:Int)->Int{waits+=1;return code;}
fn store32(p:Int,value:Int)->void{
 writes+=1;let i=0;while i<4{bytes[p+i]=(value>>(i*8))&255;i+=1;}
}
''' + function + '''
fn main()->Int{
 if posix-sys-wait4(1,2,0,0)!=1{return 1;}
 if bytes[2]!=0 || bytes[3]!=42 || bytes[4]!=0 || bytes[5]!=0{return 2;}
 if bytes[1]!=99 || bytes[6]!=99 || writes!=1{return 3;}
 if posix-sys-wait4(1,0,0,0)!=1 || writes!=1{return 4;}
 if posix-sys-wait4(-1,2,0,0)!=LINUX-ECHILD{return 5;}
 if posix-sys-wait4(2,2,0,0)!=LINUX-ECHILD{return 6;}
 if writes!=1 || waits!=2{return 7;}
 code=298;posix-sys-wait4(0,2,0,0);
 if bytes[3]!=42 || bytes[2]!=0{return 8;}
 code=-1;posix-sys-wait4(0,2,0,0);
 if bytes[3]!=255 || bytes[2]!=0{return 9;}
 return 42;
}
'''
with tempfile.TemporaryDirectory(prefix='space-posix-wait-') as directory:
    path = Path(directory) / 'wait.in'
    path.write_text(source)
    for profile in ('default', 'lean', 'harden'):
        run = subprocess.run([args.compiler, 'compile', '--path', str(path),
                              '--out', str(Path(directory) / 'out'), '--target',
                              'jit', '--entry', 'main', '--profile', profile,
                              '--json'], capture_output=True, text=True)
        report = json.loads(run.stdout)
        if not report.get('success') or report.get('eval_result') != {'Int': 42}:
            raise SystemExit(f'FAIL {profile}: {run.stdout}\n{run.stderr}')
        print(f'PASS {profile}: wait status encoding, width, null and invalid pid')
