#!/usr/bin/env python3
"""Exercise actual local-stream and file-adapter functions with isolated memory.

This checks descriptor ownership and byte-ring behavior; the foreign syscall
QEMU fixture separately verifies execution against real kernel memory.
"""
import argparse, json, subprocess, hashlib
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--in", dest="compiler", required=True)
p.add_argument("--build-dir", type=Path, required=True)
a = p.parse_args()
r = a.build_dir
r.mkdir(parents=True, exist_ok=True)
s = Path(__file__).resolve().parents[1]


def extract(file, name):
    t = (s / "components" / file).read_text()
    i = t.index("fn " + name + "(")
    # Outer function braces are column-zero in these sources. Stop at the
    # function's own close, rather than copying constants between functions
    # a second time after the separately collected top-level declarations.
    j = t.index("\n}", i) + 2
    return t[i:j]


v = (s / "components/vfs.in").read_text()
record = v[v.index("struct VfsStreamPair {") : v.index("\n}", v.index("struct VfsStreamPair {")) + 2]
source = "\n".join(x for x in v.splitlines() if x.startswith(("const ", "var "))) + "\n"
source += record + "\n"
source += "var memory:[Int]=[" + ",".join(["0"] * 50000) + "];\n"
source += """var cursor:Int=8;
fn alloc(n:Int)->Int{let p=cursor;cursor+=n;return p;}
fn load64(p:Int)->Int{return memory[p];}
fn store64(p:Int,v:Int)->Void{memory[p]=v;}
fn load32(p:Int)->Int{return memory[p];}
fn store32(p:Int,v:Int)->Void{memory[p]=v;}
fn load8(p:Int)->Int{return memory[p];}
fn store8(p:Int,v:Int)->Void{memory[p]=v;}
"""
for name in [
    "vfs-fd-table-alloc",
    "vfs-fd-clear",
    "vfs-fd-alloc",
    "vfs-fd-valid",
    "vfs-fd-open-file",
    "vfs-fd-offset",
    "vfs-discard-tagged",
    "vfs-discard-valid",
    "vfs-close",
] + [x.split("(")[0][3:] for x in v.splitlines() if x.startswith("fn vfs-stream-")]:
    source += extract("vfs.in", name) + "\n"
source += (
    "\n".join(
        x
        for x in (s / "components/darwin.in").read_text().splitlines()
        if x.startswith("const DARWIN-")
    )
    + "\n"
)
source += """var darwin-fd-cloexec:Int=0;
fn darwin-fd-is-pipe(fd:Int)->Int{return 0;}
fn darwin-pipe-slot(fd:Int)->Int{return 0;}
fn darwin-pipe-end(fd:Int)->Int{return 0;}
fn darwin-pipe-retain(slot:Int,end:Int)->Void{return;}
fn darwin-pipe-release(slot:Int,end:Int)->Void{return;}
"""
for name in ["darwin-sys-dup", "darwin-sys-dup2", "darwin-sys-close"]:
    source += extract("darwin.in", name) + "\n"
source += """fn main()->Int{
 vfs-fd-table-alloc();let result=alloc(8);let buf=alloc(4200);let out=alloc(4200);
 store32(result,91);
 if vfs-stream-pair(2,1,0,result)!=-97 || load32(result)!=91{return 1;}
 if vfs-stream-pair(1,2,0,result)!=-22 || load32(result)!=91{return 2;}
 if vfs-stream-pair(1,1,0,result)!=0{return 3;}
 let a=load32(result);let b=load32(result+4);
 // Private handles are bounded indices, not raw metadata/payload addresses.
 let row=vfs-fd-table+a*32;let handle=load64(row);store8(out,91);
 store64(row,0);if vfs-stream-valid(a)!=0 || vfs-stream-read(a,out,1)!=-9 || load8(out)!=91{return 29;}
 store64(row,VFS-STREAM-MAX+1);if vfs-stream-valid(a)!=0 || vfs-stream-write(a,buf,1)!=-9{return 30;}
 store64(row,handle);
 if a!=3 || b!=4 || vfs-stream-read(b,out,1)!=-11{return 4;}
 if vfs-stream-read(b,out,-1)!=-22 || vfs-stream-write(a,buf,-1)!=-22{return 5;}
 if vfs-stream-read(b,0,0)!=0 || vfs-stream-write(a,0,0)!=0{return 6;}
 let i=0;while i<4200{store8(buf+i,i%251);i+=1;}
 if vfs-stream-write(a,buf,4200)!=4096 || vfs-stream-write(a,buf,1)!=-11{return 7;}
 if vfs-stream-read(b,out,3000)!=3000{return 8;}
 i=0;while i<3000{if load8(out+i)!=i%251{return 9;}i+=1;}
 if vfs-stream-write(a,buf,3000)!=3000 || vfs-stream-read(b,out,4200)!=4096{return 10;}
 i=0;while i<1096{if load8(out+i)!=(i+3000)%251{return 11;}i+=1;}
 i=0;while i<3000{if load8(out+1096+i)!=i%251{return 12;}i+=1;}
 let copy=darwin-sys-dup(a);if copy!=5{return 13;}
 if darwin-sys-dup2(copy,copy)!=copy || darwin-sys-dup2(copy,a)!=a{return 21;}
 // Replacement target is the same shared endpoint; retain must precede release.
 if darwin-sys-dup2(copy,0)!=DARWIN-ENOSYS{return 22;}

 darwin-sys-close(a);if vfs-stream-read(b,out,1)!=-11{return 14;}
 if vfs-stream-write(copy,buf,12)!=12{return 15;}
 darwin-sys-close(copy);if vfs-stream-read(b,out,20)!=12 || vfs-stream-read(b,out,1)!=0{return 16;}
 if vfs-stream-write(b,buf,1)!=-32{return 17;}
 vfs-close(b);if vfs-stream-read(b,out,1)!=-9{return 18;}
 i=0;while i<20{if vfs-stream-pair(1,1,0,result)!=0{return 19;}vfs-close(load32(result));vfs-close(load32(result+4));i+=1;}
 // Two independently opened pairs cannot observe each other's bytes.
 if vfs-stream-pair(1,1,0,result)!=0{return 23;}
 let first=load32(result);let peer=load32(result+4);
 if vfs-stream-pair(1,1,0,result)!=0{return 24;}
 let other=load32(result);let otherpeer=load32(result+4);
 if vfs-stream-write(first,buf,1)!=1 || vfs-stream-read(otherpeer,out,1)!=-11{return 25;}
 if vfs-stream-read(peer,out,1)!=1{return 26;}
 vfs-close(first);vfs-close(peer);vfs-close(other);vfs-close(otherpeer);
 // Pair-pool exhaustion does not consume descriptor rows or output words.
 i=0;while i<4{if vfs-stream-pair(1,1,0,result)!=0{return 27;}i+=1;}
 let free=vfs-fd-alloc();store32(result,91);
 if vfs-stream-pair(1,1,0,result)!=-23 || vfs-fd-alloc()!=free || load32(result)!=91{return 28;}
 i=3;while i<11{vfs-close(i);i+=1;}
 // Leave only one descriptor free: no partial publication or output mutation.
 i=3;while i<15{store64(vfs-fd-table+i*32,99);i+=1;}
 store32(result,91);if vfs-stream-pair(1,1,0,result)!=-24 || load32(result)!=91 || vfs-fd-alloc()!=15{return 20;}
 return 42;
}
"""
source = source.replace("fn main()->Int{", "fn stream-controls()->Int{", 1)
posix = (s / "components/posix.in").read_text()
windows = (s / "components/windows.in").read_text()
source += (
    "\n"
    + "\n".join(
        line
        for line in posix.splitlines()
        if line.startswith(("const LINUX-", "const POSIX-MMAP-", "var posix-map-"))
    )
    + "\n"
)
source += (
    "\n"
    + "\n".join(line for line in windows.splitlines() if line.startswith("const WIN-"))
    + "\n"
)
source += """var volume-ready:Int=0;var heap-next:Int=46000;var heap-end:Int=49000;
var io-calls:Int=0;var fake-vfd:Int=0;var win-last-error:Int=0;
const SF-ST-SIZE=0;
fn posix-fd-valid(fd:Int)->Int{return vfs-fd-valid(fd);}
fn volume-rpc-stat(path:Int,out:Int)->Int{io-calls+=1;return -1;}
fn sparkfs-stat(path:Int,out:Int)->Int{io-calls+=1;return -1;}
fn fs-stat(path:Int,out:Int)->Int{io-calls+=1;return -1;}
fn sf-lookup-path(path:Int)->Int{io-calls+=1;return -1;}
fn vfs-sparkfs-file-size(path:Int)->Int{io-calls+=1;return -1;}
fn volume-rpc-pread(path:Int,out:Int,n:Int,off:Int)->Int{io-calls+=1;return -1;}
fn sparkfs-pread(path:Int,out:Int,n:Int,off:Int)->Int{io-calls+=1;return -1;}
fn vfs-open(path:Int,flags:Int)->Int{io-calls+=1;return -1;}
fn vfs-read(fd:Int,out:Int,n:Int)->Int{io-calls+=1;return -1;}
fn fs-write-file(path:Int,out:Int,n:Int)->Int{io-calls+=1;return -1;}
fn win-handle-type(h:Int)->Int{return WIN-HANDLE-TYPE-FILE;}
fn win-handle-value(h:Int)->Int{return fake-vfd;}
fn win-set-error(error:Int)->Void{win-last-error=error;}
fn win-clear-error()->Void{win-last-error=0;}
"""
for file, name in [
    ("posix.in", "posix-sys-fstat"),
    ("posix.in", "posix-sys-mmap"),
    ("darwin.in", "darwin-sys-fstat"),
]:
    source += extract(file, name) + "\n"
for call, function in [
    ("GETFILESIZE", "size"),
    ("SETENDOFFILE", "truncate"),
    ("GETFILETYPE", "kind"),
]:
    start = windows.index("  if num == WIN-CALL-" + call + " {")
    end = (
        windows.index("\n  if num == ", start + 3)
        if call != "SETENDOFFILE"
        else (
            windows.index("\n  return 0;\n}", start)
            if "\n  return 0;\n}" in windows[start:]
            else windows.index("\n  return 0\n}", start)
        )
    )
    source += (
        "fn windows-"
        + function
        + "(a0:Int)->Int{let num=WIN-CALL-"
        + call
        + ";\n"
        + windows[start:end]
        + "\nreturn -99;}\n"
    )
source += """fn main()->Int{
 if stream-controls()!=42{return 80;}
 vfs-fd-table-alloc();let pair=alloc(8);let out=alloc(256);
 if vfs-stream-pair(1,1,0,pair)!=0{return 81;}
 let fd=load32(pair);store8(out,91);let before=cursor;let beforeheap=heap-next;
 if posix-sys-fstat(fd,out)!=LINUX-EBADF || load8(out)!=91 || cursor!=before || io-calls!=0{return 82;}
 if darwin-sys-fstat(fd,out)!=DARWIN-EBADF || load8(out)!=91 || cursor!=before || io-calls!=0{return 83;}
 if posix-sys-mmap(0,4096,3,2,fd,0)!=LINUX-EBADF || heap-next!=beforeheap || posix-map-starts[0]!=0 || io-calls!=0{return 84;}
 fake-vfd=fd;
 if windows-size(3)!=0 || win-last-error!=WIN-ERROR-INVALID-HANDLE || cursor!=before || io-calls!=0{return 85;}
 if windows-truncate(3)!=0 || win-last-error!=WIN-ERROR-INVALID-HANDLE || cursor!=before || io-calls!=0{return 86;}
 if windows-kind(3)!=WIN-FILE-TYPE-UNKNOWN || win-last-error!=WIN-ERROR-INVALID-HANDLE || io-calls!=0{return 87;}
 vfs-close(fd);vfs-close(load32(pair+4));return 42;
}
"""
(r / "extracted.in").write_text(source)
results = []
for profile in ["default", "lean", "harden"]:
    cmd = [
        a.compiler,
        "compile",
        "--path",
        str(r / "extracted.in"),
        "--target",
        "jit",
        "--profile",
        profile,
        "--json",
        "--out",
        str(r / ("extracted-" + profile)),
    ]
    q = subprocess.run(cmd, text=True, capture_output=True, timeout=60)
    (r / (profile + ".stdout")).write_text(q.stdout)
    (r / (profile + ".stderr")).write_text(q.stderr)
    data = json.loads(q.stdout)
    results.append(
        {
            "profile": profile,
            "success": data.get("success"),
            "eval_result": data.get("eval_result"),
        }
    )
    if data.get("success") is not True or data.get("eval_result") != {"Int": 42}:
        raise SystemExit(str(results))
(r / "extracted-results.json").write_text(
    json.dumps(
        {
            "compiler_sha256": hashlib.sha256(
                Path(a.compiler).read_bytes()
            ).hexdigest(),
            "results": results,
        },
        indent=2,
    )
)
print(results)
