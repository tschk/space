#!/usr/bin/env python3
"""Execute actual VFS/Darwin descriptor functions with isolated storage services."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--in", dest="compiler", required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]


def extract(file, name):
    text = (root / "components" / file).read_text()
    start = text.index("fn " + name + "(")
    following = re.search(r"\nfn ", text[start + 3 :])
    return text[start : start + 3 + following.start()] if following else text[start:]


source = "\n".join(
    line
    for line in (root / "components/darwin.in").read_text().splitlines()
    if line.startswith("const DARWIN-")
)
source += "\nconst VFS-MAX-FDS=16;\nconst VFS-O-CREAT=64;\n"
source += "var heap:[Int]=[" + ",".join(["0"] * 32768) + "];\n"
source += """
var cursor:Int=8;
var vfs-fd-table:Int=0;
var darwin-fd-cloexec:Int=0;
var volume-ready:Int=1;
var sf-disk-ready:Int=1;
var io-result:Int=2;
var io-offset:Int=-1;
fn alloc(n:Int)->Int{let p=cursor;cursor+=n;return p;}
fn load64(p:Int)->Int{return heap[p];}
fn store64(p:Int,v:Int)->Void{heap[p]=v;}
fn strdup(p:Int)->Int{return p;}
fn volume-rpc-open(path:Int,flags:Int)->Int{return 0;}
fn sf-lookup-path(path:Int)->Int{return 1;}
fn fs-write-file(path:Int,buf:Int,count:Int)->Int{return 0;}
fn vfs-sparkfs-file-size(path:Int)->Int{return 100;}
fn volume-rpc-pread(path:Int,buf:Int,count:Int,offset:Int)->Int{io-offset=offset;return io-result;}
fn volume-rpc-pwrite(path:Int,buf:Int,count:Int,offset:Int)->Int{io-offset=offset;return io-result;}
fn sparkfs-pread(path:Int,buf:Int,count:Int,offset:Int)->Int{io-offset=offset;return io-result;}
fn sparkfs-pwrite(path:Int,buf:Int,count:Int,offset:Int)->Int{io-offset=offset;return io-result;}
fn com1()->Int{return 0;}
fn serial-read(port:Int)->Int{return 10;}
fn serial-put(port:Int,value:Int)->Void{return;}
fn store8(p:Int,value:Int)->Void{heap[p]=value;}
fn load8(p:Int)->Int{return heap[p];}
fn darwin-fd-is-pipe(fd:Int)->Int{return 0;}
fn darwin-pipe-slot(fd:Int)->Int{return 0;}
fn darwin-pipe-end(fd:Int)->Int{return 0;}
fn darwin-pipe-retain(slot:Int,end:Int)->Void{return;}
fn darwin-pipe-release(slot:Int,end:Int)->Void{return;}
"""
for name in [
    "vfs-fd-table-alloc",
    "vfs-fd-clear",
    "vfs-fd-open-file",
    "vfs-fd-offset",
    "vfs-fd-set-offset",
    "vfs-fd-alloc",
    "vfs-fd-valid",
    "vfs-open",
    "vfs-close",
    "vfs-read",
    "vfs-write",
    "vfs-lseek",
]:
    source += extract("vfs.in", name) + "\n"
for name in [
    "darwin-sys-dup",
    "darwin-sys-dup2",
    "darwin-sys-close",
    "darwin-sys-fcntl",
]:
    source += extract("darwin.in", name) + "\n"
source += """
fn main()->Int{
 vfs-fd-table-alloc();
 let original=vfs-open(99,2);let independent=vfs-open(99,2);
 let copy=darwin-sys-dup(original);
 if original!=3 || independent!=4 || copy!=5{return 1;}
 if vfs-lseek(original,9,0)!=9 || vfs-lseek(copy,0,1)!=9{return 2;}
 if vfs-lseek(independent,0,1)!=0{return 3;}
 if vfs-read(copy,1,2)!=2 || io-offset!=9 || vfs-fd-offset(original)!=11{return 4;}
 if vfs-write(original,1,2)!=2 || io-offset!=11 || vfs-fd-offset(copy)!=13{return 5;}
 io-result=-1;
 if vfs-read(copy,1,2)!=-5 || vfs-fd-offset(original)!=13{return 6;}
 if vfs-write(copy,1,2)!=-5 || vfs-fd-offset(original)!=13{return 7;}
 if vfs-lseek(copy,-1,0)!=-22 || vfs-fd-offset(copy)!=13{return 8;}
 darwin-sys-fcntl(original,DARWIN-F-SETFD,1);
 if darwin-sys-fcntl(copy,DARWIN-F-GETFD,0)!=0{return 9;}
 darwin-sys-fcntl(independent,DARWIN-F-SETFD,1);
 if darwin-sys-dup2(original,independent)!=independent{return 10;}
 if darwin-sys-fcntl(independent,DARWIN-F-GETFD,0)!=0{return 11;}
 if vfs-lseek(independent,19,0)!=19 || vfs-fd-offset(copy)!=19{return 12;}
 if darwin-sys-dup2(original,original)!=original || darwin-sys-fcntl(original,DARWIN-F-GETFD,0)!=1{return 13;}
 if darwin-sys-dup2(original,copy)!=copy || vfs-fd-offset(copy)!=19{return 14;}
 // F_SETFD consumes FD_CLOEXEC bit zero, not boolean truthiness.
 darwin-sys-fcntl(copy,DARWIN-F-SETFD,1);
 darwin-sys-fcntl(copy,DARWIN-F-SETFD,2);
 if darwin-sys-fcntl(copy,DARWIN-F-GETFD,0)!=0 || darwin-sys-fcntl(original,DARWIN-F-GETFD,0)!=1{return 20;}
 darwin-sys-fcntl(copy,DARWIN-F-SETFD,3);
 if darwin-sys-fcntl(copy,DARWIN-F-GETFD,0)!=1{return 21;}
 darwin-sys-fcntl(copy,DARWIN-F-SETFD,0);
 darwin-sys-close(original);
 if darwin-sys-fcntl(original,DARWIN-F-GETFD,0)!=DARWIN-EBADF || vfs-fd-offset(copy)!=19{return 15;}
 let reopened=vfs-open(99,2);if reopened!=3 || vfs-fd-offset(reopened)!=0{return 16;}
 let table=vfs-fd-table;vfs-fd-table-alloc();let temporary=vfs-open(77,2);
 vfs-lseek(temporary,55,0);vfs-fd-table=table;
 if vfs-fd-offset(copy)!=19 || vfs-fd-offset(reopened)!=0{return 17;}
 let fd=vfs-open(99,2);while fd>=0{fd=vfs-open(99,2);}
 if darwin-sys-dup(copy)!=DARWIN-ENOSYS || vfs-fd-offset(copy)!=19{return 18;}
 darwin-sys-close(copy);darwin-sys-close(independent);
 let i=0;while i<40{let fresh=vfs-open(88,2);if fresh<0{return 19;}vfs-lseek(fresh,33,0);darwin-sys-close(fresh);i+=1;}
 return 42;
}
"""
with tempfile.TemporaryDirectory(prefix="space-vfs-offset-") as directory:
    path = Path(directory) / "offset.in"
    path.write_text(source)
    for profile in ["default", "lean", "harden"]:
        run = subprocess.run(
            [
                a.compiler,
                "compile",
                "--path",
                str(path),
                "--out",
                str(Path(directory) / "out"),
                "--target",
                "jit",
                "--entry",
                "main",
                "--profile",
                profile,
                "--json",
            ],
            capture_output=True,
            text=True,
        )
        report = json.loads(run.stdout)
        if not report.get("success") or report.get("eval_result") != {"Int": 42}:
            raise SystemExit(f"FAIL {profile}: {run.stdout}\n{run.stderr}")
        print(
            f"PASS {profile}: shared I/O/seek offsets, independent opens, dup2, close/reuse, table restore, flags, failures"
        )
