#!/usr/bin/env python3
"""Execute actual Darwin pipe functions with isolated VFS/memory services.

This checks translator descriptor ownership, not hardware or scheduler behavior.
Select an existing compiler explicitly; no compiler build is performed.
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
text = (root / 'components/darwin.in').read_text()
names = ['darwin-pipe-table-init', 'darwin-fd-is-pipe', 'darwin-pipe-slot',
         'darwin-pipe-end', 'darwin-pipe-release', 'darwin-sys-close',
         'darwin-pipe-write', 'darwin-pipe-read', 'darwin-sys-dup',
         'darwin-sys-dup2', 'darwin-sys-pipe', 'darwin-sys-lseek']
if 'fn darwin-pipe-retain(' in text:
    names.append('darwin-pipe-retain')
functions = []
for name in names:
    start = text.index('fn ' + name + '(')
    following = re.search(r'\nfn ', text[start + 3:])
    end = start + 3 + following.start() if following else len(text)
    functions.append(text[start:end])
source = '\n'.join(line for line in text.splitlines()
                   if line.startswith('const DARWIN-'))
source += '\nvar heap:[Int]=[' + ','.join(['0'] * 32768) + '];\n'
source += '''
const VFS-MAX-FDS=16;
var cursor:Int=8;
var darwin-pipe-table:Int=0;
var darwin-fd-cloexec:Int=0;
var vfs-fd-table:Int=0;
var seek-calls:Int=0;
fn vfs-lseek(fd:Int,offset:Int,whence:Int)->Int{seek-calls+=1;return 17;}
fn alloc(n:Int)->Int{let p=cursor;cursor+=n;return p;}
fn load64(p:Int)->Int{return heap[p];}
fn store64(p:Int,v:Int)->void{heap[p]=v;}
fn load32(p:Int)->Int{return heap[p];}
fn store32(p:Int,v:Int)->void{heap[p]=v;}
fn load8(p:Int)->Int{return heap[p];}
fn store8(p:Int,v:Int)->void{heap[p]=v;}
fn vfs-close(fd:Int)->Int{vfs-fd-clear(fd);return 0;}
'''
vfs = (root / 'components/vfs.in').read_text()
for name in ('vfs-fd-valid', 'vfs-fd-clear', 'vfs-fd-alloc', 'vfs-fd-open-file', 'vfs-fd-table-alloc'):
    start = vfs.index('fn ' + name + '(')
    following = re.search(r'\nfn ', vfs[start + 3:])
    end = start + 3 + following.start() if following else len(vfs)
    functions.append(vfs[start:end])
source += '\n'.join(functions) + '''
fn pipe-seek-preserved(fd:Int)->Int{
 let row=vfs-fd-table+fd*32;
 let slot=load64(row+8);let end=load64(row+16);
 let base=darwin-pipe-table+slot*DARWIN-PIPE-SLOT;
 let buffer=load64(base+DARWIN-PIPE-OFF-BUF);
 let head=load64(base+DARWIN-PIPE-OFF-HEAD);
 let count=load64(base+DARWIN-PIPE-OFF-COUNT);
 let readers=load64(base+DARWIN-PIPE-OFF-ROPEN);
 let writers=load64(base+DARWIN-PIPE-OFF-WOPEN);
 let whence=0;
 while whence<3{
  if darwin-sys-lseek(fd,42,whence)!=DARWIN-ESPIPE{return 0;}
  if seek-calls!=0 || load64(row+8)!=slot || load64(row+16)!=end{return 0;}
  if load64(base+DARWIN-PIPE-OFF-BUF)!=buffer || load64(base+DARWIN-PIPE-OFF-HEAD)!=head{return 0;}
  if load64(base+DARWIN-PIPE-OFF-COUNT)!=count || load8(buffer+head)!=42{return 0;}
  if load64(base+DARWIN-PIPE-OFF-ROPEN)!=readers || load64(base+DARWIN-PIPE-OFF-WOPEN)!=writers{return 0;}
  whence+=1;
 }
 return 1;
}
fn main()->Int{
 vfs-fd-table-alloc();
 let pair=alloc(8);if darwin-sys-pipe(pair)!=0{return 1;}
 let r=load32(pair);let w=load32(pair+4);let idx=darwin-pipe-slot(r);
 let r2=darwin-sys-dup(r);let w2=darwin-sys-dup(w);
 if r2<0 || w2<0{return 2;}
 let probe=alloc(1);store8(probe,42);
 if darwin-pipe-write(w,probe,1)!=1{return 15;}
 if pipe-seek-preserved(r)!=1 || pipe-seek-preserved(w)!=1 || pipe-seek-preserved(r2)!=1 || pipe-seek-preserved(w2)!=1{return 16;}
 if darwin-pipe-read(r,probe,1)!=1 || load8(probe)!=42{return 17;}
 // Non-pipe inputs remain owned by VFS validation/seek handling.
 if darwin-sys-lseek(99,0,0)!=17 || seek-calls!=1{return 18;}
 seek-calls=0;

 darwin-sys-close(r);darwin-sys-close(w);
 let bytes=alloc(1);store8(bytes,42);
 if darwin-pipe-write(w2,bytes,1)!=1{return 3;}
 if darwin-pipe-read(r2,bytes,1)!=1 || load8(bytes)!=42{return 4;}
 // Replace another descriptor to the same endpoint, then close the source.
 let r3=darwin-sys-dup(r2);
 if darwin-sys-dup2(r2,r3)!=r3{return 5;}
 if darwin-sys-dup2(r2,r2)!=r2{return 6;}
 darwin-sys-close(r2);
 if darwin-pipe-write(w2,bytes,1)!=1{return 7;}
 if darwin-pipe-read(r3,bytes,1)!=1{return 8;}
 // Replacing the final reader with a writer must release only the reader.
 if darwin-sys-dup2(w2,r3)!=r3{return 9;}
 darwin-sys-close(w2);
 if load64(darwin-pipe-table+idx*DARWIN-PIPE-SLOT+DARWIN-PIPE-OFF-USED)!=1{return 10;}
 darwin-sys-close(r3);
 if load64(darwin-pipe-table+idx*DARWIN-PIPE-SLOT+DARWIN-PIPE-OFF-USED)!=0{return 11;}
 if darwin-sys-pipe(pair)!=0 || darwin-pipe-slot(load32(pair))!=idx{return 12;}
 darwin-sys-close(load32(pair));darwin-sys-close(load32(pair+4));
 // Only one free descriptor: writer allocation must undo reader reservation.
 let fd=3;while fd<15{store64(vfs-fd-table+fd*32,0);fd+=1;}
 if darwin-sys-pipe(pair)!=DARWIN-ENOMEM{return 13;}
 if vfs-fd-valid(15)!=0{return 14;}
 return 42;
}
'''
with tempfile.TemporaryDirectory(prefix='space-darwin-pipe-') as directory:
    path = Path(directory) / 'pipe.in'
    path.write_text(source)
    for profile in ('default', 'lean', 'harden'):
        run = subprocess.run([args.compiler, 'compile', '--path', str(path),
                              '--out', str(Path(directory) / 'out'), '--target',
                              'jit', '--entry', 'main', '--profile', profile,
                              '--json'], capture_output=True, text=True)
        report = json.loads(run.stdout)
        if not report.get('success') or report.get('eval_result') != {'Int': 42}:
            raise SystemExit(f'FAIL {profile}: {run.stdout}\n{run.stderr}')
        print(f'PASS {profile}: pipe seek refusal/state preservation, duplicated endpoints, dup2 replacement, final close/reuse')
