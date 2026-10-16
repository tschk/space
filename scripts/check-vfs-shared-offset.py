#!/usr/bin/env python3
"""Execute actual VFS/Darwin descriptor functions with isolated storage services."""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--in", dest="compiler", required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]


def extract(file, name):
    text = (root / "components" / file).read_text()
    start = text.index("fn " + name + "(")
    return text[start : text.index("\n}", start) + 2]


source = "\n".join(
    line
    for line in (root / "components/darwin.in").read_text().splitlines()
    if line.startswith("const DARWIN-")
)
source += "\nconst VFS-MAX-FDS=16;\nconst VFS-O-CREAT=64;\nconst VFS-O-RDONLY=0;\nconst VFS-O-WRONLY=1;\nconst VFS-O-RDWR=2;\n"
source += "var heap:[Int]=[" + ",".join(["0"] * 32768) + "];\n"
source += """
var cursor:Int=8;
var vfs-fd-table:Int=0;
var darwin-fd-cloexec:Int=0;
var volume-ready:Int=1;
var sf-disk-ready:Int=1;
var io-result:Int=2;
var io-offset:Int=-1;
var io-read-calls:Int=0;
var io-write-calls:Int=0;
fn alloc(n:Int)->Int{let p=cursor;cursor+=n;return p;}
fn load64(p:Int)->Int{return heap[p];}
fn store64(p:Int,v:Int)->Void{heap[p]=v;}
fn strdup(p:Int)->Int{return p;}
fn volume-rpc-open(path:Int,flags:Int)->Int{return 0;}
fn sf-lookup-path(path:Int)->Int{return 1;}
fn fs-write-file(path:Int,buf:Int,count:Int)->Int{return 0;}
fn vfs-sparkfs-file-size(path:Int)->Int{return 100;}
fn volume-rpc-pread(path:Int,buf:Int,count:Int,offset:Int)->Int{io-read-calls+=1;io-offset=offset;if io-result>0{store8(buf,91);}return io-result;}
fn volume-rpc-pwrite(path:Int,buf:Int,count:Int,offset:Int)->Int{io-write-calls+=1;io-offset=offset;return io-result;}
fn sparkfs-pread(path:Int,buf:Int,count:Int,offset:Int)->Int{io-read-calls+=1;io-offset=offset;if io-result>0{store8(buf,91);}return io-result;}
fn sparkfs-pwrite(path:Int,buf:Int,count:Int,offset:Int)->Int{io-write-calls+=1;io-offset=offset;return io-result;}
fn com1()->Int{return 0;}
fn serial-read(port:Int)->Int{return 10;}
fn serial-put(port:Int,value:Int)->Void{return;}
fn store8(p:Int,value:Int)->Void{heap[p]=value;}
fn load8(p:Int)->Int{return heap[p];}
fn darwin-fd-is-pipe(fd:Int)->Int{return 0;}
fn darwin-pipe-read(fd:Int,buf:Int,count:Int)->Int{return -99;}
fn darwin-pipe-write(fd:Int,buf:Int,count:Int)->Int{return -99;}
fn darwin-pipe-slot(fd:Int)->Int{return 0;}
fn darwin-pipe-end(fd:Int)->Int{return 0;}
fn darwin-pipe-retain(slot:Int,end:Int)->Void{return;}
fn darwin-pipe-release(slot:Int,end:Int)->Void{return;}
"""
# Preserve real stream-aware shared VFS branches while testing regular-file controls.
vfs = (root / "components/vfs.in").read_text()
source += "\n" + "\n".join(
    line for line in vfs.splitlines()
    if line.startswith(("const VFS-FD-STREAM", "const VFS-STREAM-", "var vfs-stream-"))
) + "\n"
for name in ["vfs-stream-pair-valid", "vfs-stream-valid", "vfs-stream-release",
             "vfs-stream-retain", "vfs-stream-publish", "vfs-stream-dup",
             "vfs-stream-read", "vfs-stream-write"]:
    source += extract("vfs.in", name) + "\n"
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
    "vfs-dup-file",
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
 let access-result=access-controls();if access-result!=42{return access-result;}
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
# Exercise the actual Windows duplicate/close dispatch branches too.
windows = (root / "components/windows.in").read_text()
source += "\n" + "\n".join(line for line in windows.splitlines() if line.startswith("const WIN-"))
source += "\nvar win-handles:Int=0;\nvar win-last-error:Int=0;\nvar win-last-status:Int=0;\n"
for name in ["win-ntstatus", "win-dos-error", "win-status-from-error", "win-set-error", "win-set-status", "win-set-error-rc", "win-clear-error"]:
    source += extract("windows.in", name) + "\n"
for name in ["win-handle-base", "win-handle-set", "win-handle-type", "win-handle-value", "win-handle-alloc", "win-handle-alloc-process", "win-handle-free"]:
    source += extract("windows.in", name) + "\n"
for call, function in [("DUPLICATEHANDLE", "duplicate"), ("CLOSEHANDLE", "close")]:
    start = windows.index("  if num == WIN-CALL-" + call + " {")
    end = windows.index("\n  if num == ", start + 3)
    source += f"fn windows-{function}(a0:Int)->Int{{let num=WIN-CALL-{call};\n" + windows[start:end] + "\nreturn -99;}\n"
start = windows.index("  if num == WIN-CALL-SETFILEPOINTER {")
end = windows.index("\n  if num == ", start + 3)
source += "fn windows-seek(a0:Int,a1:Int,a2:Int)->Int{let num=WIN-CALL-SETFILEPOINTER;\n" + windows[start:end] + "\nreturn -99;}\n"
source = source.replace(" return 42;\n}\n", " return windows-lifetime();\n}\n", 1)
source += "\nconst LINUX-ERANGE=-34;\nconst LINUX-EFAULT=-14;\nvar posix-cwd:Int=0;\n"
for name in ["posix-copy-getcwd", "posix-sys-getcwd"]:
    source += extract("posix.in", name) + "\n"
source += extract("darwin.in", "darwin-sys-getcwd") + "\n"
posix = (root / "components/posix.in").read_text()
start = posix.index("  if num == LINUX-SYS-GETCWD {")
end = posix.index("\n  if num == ", start + 3)
source += "const LINUX-SYS-GETCWD=79;\nfn linux-getcwd(a0:Int,a1:Int)->Int{let num=79;\n" + posix[start:end] + "\nreturn -99;}\n"
for name in ["darwin-map-open-flags", "darwin-sys-read", "darwin-sys-write"]:
    source += extract("darwin.in", name) + "\n"
for name in ["posix-sys-read", "posix-sys-write"]:
    source += extract("posix.in", name) + "\n"
for call, function in [("READFILE", "read"), ("WRITEFILE", "write")]:
    start = windows.index("  if num == WIN-CALL-" + call + " {")
    end = windows.index("\n  if num == ", start + 3)
    source += f"fn windows-{function}(a0:Int,a1:Int,a2:Int)->Int{{let port=0;let num=WIN-CALL-{call};\n" + windows[start:end] + "\nreturn -99;}\n"
source += """
fn access-controls()->Int{
 let backend=0;
 while backend<2{
  volume-ready=backend;vfs-fd-table-alloc();
  if darwin-map-open-flags(0)!=0 || darwin-map-open-flags(1)!=1 || darwin-map-open-flags(2)!=2{return 200;}
  let ro=vfs-open(99,64);let wo=vfs-open(99,65);let rw=vfs-open(99,66);
  let rocopy=vfs-dup-file(ro);let wocopy=vfs-dup-file(wo);
  let independent=vfs-open(99,2);
  if ro<3 || wo<3 || rw<3 || rocopy<3 || wocopy<3 || independent<3{return 201;}
  if vfs-lseek(ro,9,0)!=9 || vfs-lseek(wo,11,0)!=11{return 202;}
  let buf=alloc(4);store8(buf,77);store8(buf+1,78);
  io-result=2;io-offset=-1;io-read-calls=0;io-write-calls=0;
  if posix-sys-read(wo,buf,2)!=-9 || vfs-read(wocopy,buf,2)!=-9{return 203;}
  if posix-sys-write(ro,buf,2)!=-9 || vfs-write(rocopy,buf,2)!=-9{return 204;}
  if darwin-sys-read(wo,buf,2)!=-9 || darwin-sys-write(0,ro,buf,2)!=-9{return 217;}
  if io-read-calls!=0 || io-write-calls!=0 || io-offset!=-1{return 205;}
  if load8(buf)!=77 || load8(buf+1)!=78{return 206;}
  if vfs-fd-offset(ro)!=9 || vfs-fd-offset(rocopy)!=9 || vfs-fd-offset(wo)!=11 || vfs-fd-offset(wocopy)!=11{return 207;}
  if vfs-read(rocopy,buf,2)!=2 || vfs-fd-offset(ro)!=11 || load8(buf)!=91{return 208;}
  if vfs-write(wocopy,buf,2)!=2 || vfs-fd-offset(wo)!=13{return 209;}
  if vfs-read(rw,buf,2)!=2 || vfs-write(rw,buf,2)!=2 || vfs-fd-offset(rw)!=4{return 210;}
  if vfs-fd-offset(independent)!=0 || vfs-write(independent,buf,2)!=2{return 211;}
  win-handles=alloc(WIN-MAX-HANDLES*WIN-HANDLE-STRIDE);
  let h=0;while h<WIN-MAX-HANDLES{win-handle-set(h,WIN-HANDLE-TYPE-FREE,0);h+=1;}
  let hro=win-handle-alloc(ro);let hwo=win-handle-alloc(wo);let hrw=win-handle-alloc(rw);
  io-read-calls=0;io-write-calls=0;store8(buf,77);
  if windows-write(hro,buf,2)!=0 || win-last-error!=WIN-ERROR-INVALID-HANDLE || win-last-status!=WIN-STATUS-INVALID-HANDLE{return 212;}
  if windows-read(hwo,buf,2)!=0 || win-last-error!=WIN-ERROR-INVALID-HANDLE || win-last-status!=WIN-STATUS-INVALID-HANDLE{return 213;}
  if io-read-calls!=0 || io-write-calls!=0 || load8(buf)!=77{return 214;}
  if vfs-fd-offset(ro)!=11 || vfs-fd-offset(wo)!=13{return 215;}
  if windows-write(hrw,buf,2)!=2 || win-last-error!=0 || win-last-status!=0{return 216;}
  if vfs-read(0,buf,1)!=1 || load8(buf)!=10 || vfs-write(1,buf,1)!=1 || vfs-write(2,buf,1)!=1{return 218;}
  backend+=1;
 }
 volume-ready=1;
 return 42;
}
fn windows-lifetime()->Int{
 posix-cwd=alloc(2);store8(posix-cwd,47);store8(posix-cwd+1,0);
 let cwdout=alloc(4);store8(cwdout,7);store8(cwdout+1,8);store8(cwdout+2,9);
 if linux-getcwd(cwdout,1)!=-34 || load8(cwdout)!=7 || load8(cwdout+1)!=8{return 140;}
 if linux-getcwd(cwdout,0)!=-34 || linux-getcwd(cwdout,-1)!=-34 || load8(cwdout)!=7{return 141;}
 if linux-getcwd(0,2)!=-14{return 142;}
 if linux-getcwd(cwdout,2)!=2 || load8(cwdout)!=47 || load8(cwdout+1)!=0 || load8(cwdout+2)!=9{return 143;}
 if darwin-sys-getcwd(cwdout,2)!=cwdout || darwin-sys-getcwd(cwdout,1)!=0{return 144;}

 vfs-fd-table-alloc();win-handles=alloc(WIN-MAX-HANDLES*WIN-HANDLE-STRIDE);
 let i=0;while i<WIN-MAX-HANDLES{win-handle-set(i,WIN-HANDLE-TYPE-FREE,0);i+=1;}
 win-handle-set(1,WIN-HANDLE-TYPE-CONSOLE,1);
 win-handle-set(2,WIN-HANDLE-TYPE-CONSOLE,2);
 i=0;while i<40{
  let cloned=windows-duplicate(1);if cloned==WIN-INVALID-HANDLE{return 120;}
  if win-handle-type(cloned)!=WIN-HANDLE-TYPE-CONSOLE || win-handle-value(cloned)!=1{return 121;}
  if windows-close(cloned)!=1 || win-handle-type(cloned)!=WIN-HANDLE-TYPE-FREE{return 122;}
  if windows-close(cloned)!=0 || win-last-error!=WIN-ERROR-INVALID-HANDLE{return 123;}
  if win-handle-type(1)!=WIN-HANDLE-TYPE-CONSOLE || win-handle-type(2)!=WIN-HANDLE-TYPE-CONSOLE{return 124;}
  i+=1;
 }
 if windows-close(1)!=1 || windows-close(2)!=1{return 125;}
 if win-handle-type(1)!=WIN-HANDLE-TYPE-CONSOLE || win-handle-type(2)!=WIN-HANDLE-TYPE-CONSOLE{return 126;}
 let fd=vfs-open(99,2);let original=win-handle-alloc(fd);
 let independent=vfs-open(99,2);let copy=windows-duplicate(original);
 if copy==WIN-INVALID-HANDLE{return 101;}
 let copyfd=win-handle-value(copy);
 if copyfd==fd{return 102;}
 if vfs-lseek(fd,9,0)!=9 || vfs-fd-offset(copyfd)!=9 || vfs-fd-offset(independent)!=0{return 103;}
 // Failed Windows seeks report paired errors without committing the shared offset.
 if windows-seek(copy,0,99)!=-1{return 130;}
 if win-last-error!=WIN-ERROR-INVALID-PARAMETER || win-last-status!=WIN-STATUS-INVALID-PARAMETER{return 131;}
 if vfs-fd-offset(fd)!=9 || vfs-fd-offset(copyfd)!=9 || vfs-fd-offset(independent)!=0{return 132;}
 if windows-seek(copy,-10,1)!=-1{return 133;}
 if win-last-error!=WIN-ERROR-INVALID-PARAMETER || win-last-status!=WIN-STATUS-INVALID-PARAMETER{return 134;}
 if vfs-fd-offset(fd)!=9 || vfs-fd-offset(copyfd)!=9{return 135;}
 if windows-seek(copy,0,1)!=9 || win-last-error!=0 || win-last-status!=0{return 136;}
 if windows-seek(0,0,0)!=-1 || win-last-error!=WIN-ERROR-INVALID-HANDLE || win-last-status!=WIN-STATUS-INVALID-HANDLE{return 137;}
 if windows-seek(original,9,0)!=9 || win-last-error!=0 || win-last-status!=0{return 138;}

 windows-close(original);
 let reused=vfs-open(77,2);if reused!=fd{return 104;}
 if vfs-lseek(reused,55,0)!=55 || vfs-fd-offset(copyfd)!=9{return 105;}
 io-result=2;if vfs-read(copyfd,1,2)!=2 || io-offset!=9{return 106;}
 windows-close(copy);if vfs-fd-valid(reused)!=1{return 107;}
 let other=win-handle-alloc(reused);let sibling=windows-duplicate(other);
 windows-close(sibling);
 if vfs-lseek(reused,12,0)!=12{return 108;}
 if vfs-read(reused,1,2)!=2 || io-offset!=12{return 112;}
 windows-close(other);
 // Exhaust Windows slots: the temporary duplicated descriptor must be released.
 let survivor=win-handle-alloc(independent);
 i=3;while i<WIN-MAX-HANDLES{if win-handle-type(i)==WIN-HANDLE-TYPE-FREE{win-handle-set(i,WIN-HANDLE-TYPE-PROCESS,1);}i+=1;}
 let freefd=vfs-fd-alloc();let refs=load64(vfs-fd-open-file(independent)+8);
 if windows-duplicate(survivor)!=WIN-INVALID-HANDLE || win-last-error!=WIN-ERROR-INVALID-HANDLE{return 109;}
 if vfs-fd-alloc()!=freefd{return 110;}
 if load64(vfs-fd-open-file(independent)+8)!=refs{return 111;}
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
            f"PASS {profile}: shared I/O/seek offsets, independent opens, dup2, close/reuse, table restore, flags, Windows duplicate lifetime/exhaustion, failures, access-mode denial/aliases/adapters"
        )
