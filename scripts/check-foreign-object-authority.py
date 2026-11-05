#!/usr/bin/env python3
"""Check that foreign file access requires authority over the storage realm."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--in', dest='compiler', required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent


def function(path, name):
    text = (root / path).read_text()
    start = text.index('fn ' + name + '(')
    return text[start:text.index('\n}', start) + 2]


source = 'var memory:[Int]=[' + ','.join(['0'] * 512) + '];\n' + '''
var cap-table-base:Int=16;
var cap-count:Int=1;
var root-realm:Int=100;
var foreign-storage-cap:Int=0;
var foreign-image:Int=200;
var foreign-size:Int=100;
var foreign-fds:Int=8;
var volume-ready:Int=0;
var sf-mem-disk:Int=1;
const VFS-MAX-FDS=64;
fn load64(p:Int)->Int{return memory[p];}
fn store64(p:Int,v:Int)->Void{memory[p]=v;}
fn cap-storage()->Int{return 32;}
fn vfs-read(fd:Int,buf:Int,len:Int)->Int{return 42;}
''' + '\n'.join(function(path, name) for path, name in [
    ('components/object.in', 'cap-has-rights'),
    ('components/object.in', 'cap-check'),
    ('components/foreign-exec.in', 'foreign-buffer-valid'),
    ('components/foreign-exec.in', 'foreign-fd-owned'),
    ('components/foreign-exec.in', 'foreign-file-read'),
]) + '''
fn main()->Int{
 store64(cap-table-base,101);store64(cap-table-base+8,32);
 if foreign-file-read(3,200,1)!=-13{return 1;}
 store64(cap-table-base,root-realm);
 if foreign-file-read(3,200,1)!=42{return 2;}
 store64(cap-table-base+8,0);
 if foreign-file-read(3,200,1)!=-13{return 3;}
 return 42;
}
'''
with tempfile.TemporaryDirectory(prefix='space-foreign-object-') as temporary:
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
        print(f'PASS {profile}: foreign file access checks its storage realm and rights')
