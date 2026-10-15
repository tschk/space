#!/usr/bin/env python3
"""Execute the actual Windows wait dispatch branch with isolated handle/process services.

Requires an existing compiler and never builds one. Only synchronous process
completion is tested; timeout, event and scheduler behavior are outside scope.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--in', dest='compiler', required=True)
args = parser.parse_args()
text = (Path(__file__).resolve().parent.parent / 'components/windows.in').read_text()
start = text.index('  if num == WIN-CALL-WAITFORSINGLEOBJECT {')
end = text.index('\n  if num == ', start + 3)
branch = text[start:end]
def function(name):
    start = text.index('fn ' + name + '(')
    return text[start:text.index('\nfn ', start + 3)]
source = '\n'.join(line for line in text.splitlines() if line.startswith('const WIN-'))
source += '''
var win-last-error:Int=0;
var win-last-status:Int=0;
var proc-count:Int=2;
var waits:Int=0;
var exit-code:Int=42;
fn win-handle-type(handle:Int)->Int{if handle==3 || handle==4{return WIN-HANDLE-TYPE-PROCESS;}return WIN-HANDLE-TYPE-FREE;}
fn win-handle-value(handle:Int)->Int{if handle==3{return 1;}return 99;}
fn proc-wait(pid:Int)->Int{waits+=1;return exit-code;}
'''
source += '\n'.join(function(name) for name in ('win-status-from-error', 'win-set-error', 'win-clear-error'))
source += '\nfn wait(handle:Int)->Int{let num=WIN-CALL-WAITFORSINGLEOBJECT;let a0=handle;\n' + branch + '\nreturn -99;}\n'
source += '''
fn main()->Int{
 if wait(-1)!=4294967295{return 1;}
 if win-last-error!=6 || win-last-status!=WIN-STATUS-INVALID-HANDLE || waits!=0{return 2;}
 if wait(4)!=4294967295{return 3;}
 if win-last-error!=6 || win-last-status!=WIN-STATUS-INVALID-HANDLE || waits!=0{return 4;}
 if wait(3)!=0 || waits!=1{return 5;}
 if win-last-error!=0 || win-last-status!=0{return 6;}
 exit-code=-1;
 if wait(3)!=0 || waits!=2{return 7;}
 return 42;
}
'''
with tempfile.TemporaryDirectory(prefix='space-windows-wait-') as directory:
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
        print(f'PASS {profile}: WAIT_FAILED, paired errors and process completion')
