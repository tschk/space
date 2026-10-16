#!/usr/bin/env python3
"""Execute actual fixed SCI snapshot/seat guards with isolated numeric memory."""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--in", dest="compiler", required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
functions = []
for filename, names in [
    (
        "components/channel.in",
        [
            "chan-page-frame-header-valid",
            "chan-page-send-frame",
            "chan-page-recv-frame",
        ],
    ),
    ("protocol/input.in", ["input-page-header-valid"]),
    ("protocol/display.in", ["spdp-seat-key"]),
    (
        "components/sci-loader.in",
        [
            "sci-display-cap-info",
            "sci-sync-pixels",
            "sci-sync-restore-info",
            "sci-sync-provenance-valid",
            "sci-sync-enter",
            "sci-resume-sync",
            "sci-resume-sync-unit",
            "sci-resume-input-sync",
            "sci-proof-capture",
            "sci-proof-restore",
            "sci-proof-capture-input",
            "sci-proof-capture-app",
            "sci-proof-poll-input",
            "sci-proof-fail-app",
            "sci-proof-deliver-key",
        ],
    ),
]:
    text = (root / filename).read_text()
    for name in names:
        start = text.index("fn " + name + "(")
        functions.append(text[start : text.index("\n}", start) + 2])
source = (
    "var memory:[Int]=["
    + ",".join(["0"] * 20000)
    + "];\n"
    + """
const SCI-INPUT-GRANTS=3;const SCI-V2-HEADER=64;const DOMAIN-ACTIVE=1;
const COMP-HEAP-VIRT=0x80000000;const COMP-HEAP-SIZE=0x200000;
const COMP-SHARED-VIRT=0x70000000;const COMP-PIXEL-VIRT=0x70001000;
const SPDP-OBJ-SEAT=4;const SPDP-SEAT-KEYBOARD-KEY=4;
var domain-count:Int=3;var cap-count:Int=2;
var domain-table:Int=1500;var cap-table-base:Int=1904;
var sci-sync-ring-unit:Int=4;var sci-sync-page:Int=0;var sci-sync-domain:Int=0;
var sci-sync-grants:Int=0;var sci-sync-pixel-phys:Int=0;var sci-sync-pixel-size:Int=0;
var sci-sync-pixel-pool:Int=0;var sci-sync-entry:Int=0;var sci-sync-code-start:Int=0;
var sci-sync-code-end:Int=0;var sci-sync-info:Int=0;var sci-sync-cap:Int=-1;var sci-sync-object:Int=0;
var sci-proof-input:[Int]=[0,0,0,0,0,0,0,0,0,0,0,0,0];
var sci-proof-app:[Int]=[0,0,0,0,0,0,0,0,0,0,0,0,0];
var current:Int=0;var invoked:Int=0;var mode:Int=0;var fail-switch:Int=0;
fn load64(p:Int)->Int{return memory[p];}
fn store64(p:Int,v:Int)->Void{memory[p]=v;return;}
fn cap-memory()->Int{return 4;}
fn cap-display()->Int{return 16;}
fn domain-get-current()->Int{return current;}
fn domain-switch(id:Int)->Void{if (fail-switch==1 && id!=0) || (fail-switch==2 && id==0){return;}current=id;return;}
fn invoke1(entry:Int,info:Int)->Int{
 invoked+=1;
 if current==1 {if entry!=0x50000040 || info!=1800{return -1;}return 0;}
 if current!=2 || entry!=0x48000040 || info!=2000{return -1;}
 if load64(info)!=20 || load64(info+8)!=0 || load64(info+16)!=COMP-HEAP-VIRT || load64(info+32)!=COMP-SHARED-VIRT || load64(info+40)!=2 || load64(info+64)!=0 || load64(info+72)!=COMP-PIXEL-VIRT || load64(info+80)!=4096{return -1;}
 if mode==1{return 42;}
 if chan-page-recv-frame(8192,3000)!=1{return -1;}
 if load64(3000)!=4 || load64(3008)!=4 || load64(3016)!=7 || load64(3024)!=spdp-seat-key(97,1){return -1;}
 if mode==2{store64(8192,(load64(8192)+4)%508);return 42;}
 if mode==3{store64(8208,0);return 42;}
 if mode==4{return 7;}
 let i=0;while i<96{store64(info+i,-1);i+=8;}
 if chan-page-send-frame(8192,2,1,0,0)!=1 || chan-page-send-frame(8192,2,2,0,0)!=1 || chan-page-send-frame(8192,2,3,0,0)!=1{return -1;}
 return 42;
}
"""
    + "\n".join(functions)
    + """
fn setup()->Int{
 current=0;invoked=0;mode=0;fail-switch=0;sci-proof-input[0]=0;sci-proof-app[0]=0;
 store64(domain-table,4096);store64(domain-table+8,1);
 store64(domain-table+24,8192);store64(domain-table+32,1);store64(domain-table+40,0);
 store64(domain-table+48,12288);store64(domain-table+56,1);store64(domain-table+64,1);
 store64(cap-table-base,77);store64(cap-table-base+8,3);
 store64(cap-table-base+16,88);store64(cap-table-base+24,20);
 sci-sync-ring-unit=1;sci-sync-page=4096;sci-sync-domain=1;sci-sync-grants=3;
 sci-sync-pixel-phys=0;sci-sync-pixel-size=0;sci-sync-pixel-pool=0;
 sci-sync-entry=0x50000040;sci-sync-code-start=0x50000000;sci-sync-code-end=0x50001000;
 sci-sync-info=1800;sci-sync-cap=0;sci-sync-object=77;
 store64(4096,1);store64(4104,1);store64(4112,508);store64(4120,8);
 if sci-proof-capture-input()!=1{return 0;}
 sci-sync-ring-unit=4;sci-sync-page=8192;sci-sync-domain=2;sci-sync-grants=20;
 sci-sync-pixel-phys=12288;sci-sync-pixel-size=4096;
 sci-sync-entry=0x48000040;sci-sync-code-start=0x48000000;sci-sync-code-end=0x48001000;
 sci-sync-info=2000;sci-sync-cap=1;sci-sync-object=88;
 store64(8192,0);store64(8200,0);store64(8208,508);store64(8216,8);
 return sci-proof-capture-app();
}
fn main()->Int{
 if setup()!=1{return 1;}
 if sci-proof-poll-input()!=0 || current!=0 || sci-sync-domain!=1 || invoked!=1{return 2;}
 if sci-proof-deliver-key(7,97)!=42 || current!=0 || sci-sync-domain!=2 || invoked!=2{return 3;}
 if sci-proof-input[1]!=4096 || sci-proof-app[1]!=8192 || sci-proof-input[2]!=1 || sci-proof-app[2]!=2{return 4;}
 // A seat frame at the last four slots wraps before the three replies.
 if setup()!=1{return 17;}store64(8192,504);store64(8200,504);
 if sci-proof-deliver-key(7,97)!=42 || load64(8192)!=0 || load64(8200)!=12 || invoked!=1{return 18;}
 if setup()!=1 || sci-proof-poll-input()!=0 || sci-proof-deliver-key(7,97)!=42{return 19;}
 // Normal public resume refuses even complete pending frames.
 if sci-resume-sync(2,0)!=-1 || invoked!=2{return 5;}
 if sci-proof-poll-input()!=0 || current!=0 || sci-sync-domain!=1 || invoked!=3{return 6;}
 if setup()!=1{return 7;}current=1;
 if sci-proof-capture(4)!=0 || sci-proof-restore(1)!=0 || sci-proof-fail-app()!=-1 || sci-proof-deliver-key(7,97)!=-1 || sci-proof-poll-input()!=-1{return 8;}
 if sci-proof-app[0]!=4 || sci-proof-input[0]!=1 || invoked!=0 || current!=1{return 9;}
 if setup()!=1 || sci-proof-capture(2)!=0 || sci-proof-restore(2)!=0{return 10;}
 let failure=1;
 while failure<5 {
   if setup()!=1{return 11;}mode=failure;
   if sci-proof-deliver-key(7,97)!=-1 || current!=0 || invoked!=1 || sci-proof-app[0]!=0 || sci-sync-ring-unit!=0{return 12;}
   if sci-proof-deliver-key(7,97)!=-1 || invoked!=1{return 13;}
   if sci-proof-input[0]!=1{return 14;}
   failure+=1;
 }
 // Failed entry switch retires safely in the kernel domain without invoking.
 if setup()!=1{return 20;}fail-switch=1;
 if sci-proof-deliver-key(7,97)!=-1 || invoked!=0 || current!=0 || sci-proof-app[0]!=0{return 21;}
 if sci-proof-deliver-key(7,97)!=-1 || invoked!=0{return 22;}
 // Failed restore stays in guest: no private retirement writes are permitted.
 if setup()!=1{return 23;}fail-switch=2;
 if sci-proof-deliver-key(7,97)!=-1 || invoked!=1 || current!=2 || sci-proof-app[0]!=4 || sci-sync-ring-unit!=4{return 24;}
 if sci-proof-deliver-key(7,97)!=-1 || invoked!=1 || sci-proof-app[0]!=4{return 25;}
 // Explicit mock kernel recovery still cannot replay the pending exchange.
 current=0;fail-switch=0;
 if sci-resume-sync(2,0)!=-1 || invoked!=1{return 26;}
 if sci-proof-deliver-key(7,97)!=-1 || invoked!=1 || sci-proof-app[0]!=0{return 27;}
 // Input restore failure must likewise avoid private writes outside domain zero.
 if setup()!=1{return 28;}fail-switch=2;
 if sci-proof-poll-input()!=-1 || invoked!=1 || current!=1 || sci-proof-input[0]!=1 || sci-sync-ring-unit!=1{return 29;}
 // Dead domain, capability mismatch, malformed/pending preconditions: no entry.
 let bad=0;
 while bad<5 {
   if setup()!=1{return 15;}
   if bad==0{store64(domain-table+56,0);}
   if bad==1{store64(cap-table-base+24,3);}
   if bad==2{store64(8208,509);}
   if bad==3{store64(8200,4);}
   if bad==4{store64(8216,4);}
   if sci-proof-deliver-key(7,97)!=-1 || invoked!=0 || current!=0{return 16;}
   bad+=1;
 }
 return 42;
}
"""
)
with tempfile.TemporaryDirectory(prefix="space-sci-seat-") as directory:
    path = Path(directory) / "seat.in"
    path.write_text(source)
    for profile in ("default", "lean", "harden"):
        checked = subprocess.run(
            [
                args.compiler,
                "compile",
                "--path",
                str(path),
                "--target",
                "jit",
                "--profile",
                profile,
                "--out",
                str(Path(directory) / "out"),
                "--json",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        report = json.loads(checked.stdout)
        assert report.get("success") and report.get("eval_result") == {
            "Int": 42
        }, report
        print(
            f"PASS {profile}: two private snapshots, consume-before-reply, guest/pending/malformed/stale refusals and no replay"
        )
