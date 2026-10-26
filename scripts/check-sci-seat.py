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
loader = (root / "components/sci-loader.in").read_text()
schema_start = loader.index("struct SciProofSnapshot {")
schema_end = loader.index("\n}", schema_start) + 2
snapshot_declarations = (
    loader[schema_start:schema_end]
    + "\n"
    + "\n".join(
        line
        for line in loader.splitlines()
        if line.startswith(("var sci-proof-input:", "var sci-proof-app:"))
    )
)
functions = [snapshot_declarations]
for filename, names in [
    (
        "components/channel.in",
        [
            "chan-page-frame-header-valid",
            "chan-page-send-frame",
            "chan-page-recv-frame",
        ],
    ),
    ("components/runtime-pixels.in", ["runtime-instance-canvas-slot", "runtime-instance-pixel-bytes"]),
    ("components/runtime-retained.in", ["runtime-instance-kernel-context", "runtime-instance-record", "runtime-instance-resume"]),
    ("components/domain.in", ["domain-restore-service-context"]),
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
const RUNTIME-INSTANCE-PIXEL-PAGES=288;const SCI-CANVAS-BYTES=1179648;
var domain-clone-owned:Int=6;var domain-user-owned:Int=0;const NATIVE-PROTECTED-KIND=2;const NATIVE-PROTECTED-GUI-PAGED=3;const NATIVE-PROTECTED-EXTRA-MAGIC=0x5350434e4c454447;const RUNTIME-INSTANCE-CATALOG-SLOTS=64;const RUNTIME-INSTANCE-LIVE=0x52554e54494d4531;
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
var domain-current:Int=0;var current-cap:Int=0;var model-root:Int=4096;
var runtime-instance-catalog:Int=16000;var runtime-instance-active:Int=0;var runtime-aborted:Int=0;
var sci-sync-handle:Int=0;var invoked:Int=0;var mode:Int=0;var fail-switch:Int=0;var expected-key:Int=97;
fn load64(p:Int)->Int{return memory[p];}
fn store64(p:Int,v:Int)->Void{memory[p]=v;return;}
fn cap-memory()->Int{return 4;}
fn cap-display()->Int{return 16;}
fn cr3-read()->Int{return model-root;}
fn cr3-write(root:Int)->Void{if fail-switch==2 && root==4096{return;}model-root=root;return;}
fn runtime-invoke-entry(entry:Int,info:Int)->Int{return invoke1(entry,info);}
fn domain-get-current()->Int{return domain-current;}
fn domain-switch(id:Int)->Void{if (fail-switch==1 && id!=0) || (fail-switch==2 && id==0){return;}domain-current=id;model-root=load64(domain-table+id*24);current-cap=load64(domain-table+id*24+16);return;}
fn invoke1(entry:Int,info:Int)->Int{
 invoked+=1;
 if domain-current==1 {if entry!=0x50000040 || info!=13528{return -1;}return 0;}
 if domain-current!=2 || entry!=0x48000040 || info!=14128{return -1;}
 if load64(info)!=20 || load64(info+8)!=0 || load64(info+16)!=COMP-HEAP-VIRT || load64(info+32)!=COMP-SHARED-VIRT || load64(info+40)!=2 || load64(info+64)!=0 || load64(info+72)!=COMP-PIXEL-VIRT || load64(info+80)!=4096{return -1;}
 if mode==1{return 42;}
 if chan-page-recv-frame(8192,3000)!=1{return -1;}
 if load64(3000)!=4 || load64(3008)!=4 || load64(3016)!=7 || load64(3024)!=spdp-seat-key(expected-key,1){return -1;}
 if mode==2{store64(8192,(load64(8192)+4)%508);return 42;}
 if mode==3{store64(8208,0);return 42;}
 if mode==4{return 7;}
 if expected-key==27 {
   if chan-page-send-frame(8192,2,4,0,0)!=1{return -1;}
   if mode!=6 && chan-page-send-frame(8192,3,1,0,0)!=1{return -1;}
   if mode==7 && chan-page-send-frame(8192,2,3,0,0)!=1{return -1;}
   if mode==8{store64(8208,0);}
   return 42;
 }
 let i=0;while i<96{store64(info+i,-1);i+=8;}
 if chan-page-send-frame(8192,2,1,0,0)!=1 || chan-page-send-frame(8192,2,2,0,0)!=1 || chan-page-send-frame(8192,2,3,0,0)!=1{return -1;}
 return 42;
}
"""
    + "\n".join(functions)
    + """
fn retained-model(state:Int,component:Int,domain:Int,cap:Int,entry:Int,shared:Int,pixel:Int,generation:Int,slot:Int)->Void{
 let handle=(generation<<8)|(slot+1);let record=runtime-instance-catalog+slot*64;
 store64(state,domain);store64(state+8,component);store64(state+16,cap);store64(state+32,shared);store64(state+40,pixel);
 store64(state+112,0);store64(state+304,if pixel==0{0}else{1});store64(state+256,RUNTIME-INSTANCE-LIVE);store64(state+280,handle);store64(state+288,entry);store64(state+296,0);
 store64(component,generation+100);store64(component+8,5);store64(component+16,entry);store64(component+40,domain);
 store64(record,state);store64(record+8,generation);store64(record+16,generation+100);store64(record+24,component);store64(record+32,cap);store64(record+40,domain);store64(record+48,1);
 return;
}
fn setup()->Int{
 domain-current=0;current-cap=0;model-root=4096;runtime-instance-active=0;runtime-aborted=0;invoked=0;mode=0;fail-switch=0;expected-key=97;sci-proof-input.unit=0;sci-proof-app.unit=0;
 store64(domain-table,4096);store64(domain-table+8,1);
 store64(domain-table+24,8192);store64(domain-table+32,1);store64(domain-table+40,0);
 store64(domain-table+48,12288);store64(domain-table+56,1);store64(domain-table+64,1);
 store64(cap-table-base,14500);store64(cap-table-base+8,3);
 store64(cap-table-base+16,14600);store64(cap-table-base+24,20);
 retained-model(13400,14500,1,0,0x50000040,4096,0,1,0);
 retained-model(14000,14600,2,1,0x48000040,8192,12288,2,1);
 sci-sync-handle=257;
 sci-sync-ring-unit=1;sci-sync-page=4096;sci-sync-domain=1;sci-sync-grants=3;
 sci-sync-pixel-phys=0;sci-sync-pixel-size=0;sci-sync-pixel-pool=0;
 sci-sync-entry=0x50000040;sci-sync-code-start=0x50000000;sci-sync-code-end=0x50001000;
 sci-sync-info=13528;sci-sync-cap=0;sci-sync-object=14500;
 store64(4096,1);store64(4104,1);store64(4112,508);store64(4120,8);
 if sci-proof-capture-input()!=1{return 0;}
 sci-sync-handle=514;
 sci-sync-ring-unit=4;sci-sync-page=8192;sci-sync-domain=2;sci-sync-grants=20;
 sci-sync-pixel-phys=12288;sci-sync-pixel-size=4096;
 sci-sync-entry=0x48000040;sci-sync-code-start=0x48000000;sci-sync-code-end=0x48001000;
 sci-sync-info=14128;sci-sync-cap=1;sci-sync-object=14600;
 store64(8192,0);store64(8200,0);store64(8208,508);store64(8216,8);
 return sci-proof-capture-app();
}
fn main()->Int{
 if setup()!=1{return 1;}
 if sci-proof-poll-input()!=0 || domain-current!=0 || sci-sync-domain!=1 || invoked!=1{return 2;}
 if sci-proof-deliver-key(7,97)!=42 || domain-current!=0 || sci-sync-domain!=2 || invoked!=2{return 3;}
 if sci-proof-input.page!=4096 || sci-proof-app.page!=8192 || sci-proof-input.domain!=1 || sci-proof-app.domain!=2{return 4;}
 // A seat frame at the last four slots wraps before the three replies.
 if setup()!=1{return 17;}store64(8192,504);store64(8200,504);
 if sci-proof-deliver-key(7,97)!=42 || load64(8192)!=0 || load64(8200)!=12 || invoked!=1{return 18;}
 if setup()!=1 || sci-proof-poll-input()!=0 || sci-proof-deliver-key(7,97)!=42{return 19;}
 // Normal public resume refuses even complete pending frames.
 if sci-resume-sync(2,0)!=-1 || invoked!=2{return 5;}
 if sci-proof-poll-input()!=0 || domain-current!=0 || sci-sync-domain!=1 || invoked!=3{return 6;}
 if setup()!=1{return 7;}domain-current=1;
 if sci-proof-capture(4)!=0 || sci-proof-restore(1)!=0 || sci-proof-fail-app()!=-1 || sci-proof-deliver-key(7,97)!=-1 || sci-proof-poll-input()!=-1{return 8;}
 if sci-proof-app.unit!=4 || sci-proof-input.unit!=1 || invoked!=0 || domain-current!=1{return 9;}
 if setup()!=1 || sci-proof-capture(2)!=0 || sci-proof-restore(2)!=0{return 10;}
 let failure=1;
 while failure<5 {
   if setup()!=1{return 11;}mode=failure;
   if sci-proof-deliver-key(7,97)!=-1 || domain-current!=0 || invoked!=1 || sci-proof-app.unit!=0 || sci-sync-ring-unit!=0{return 12;}
   if sci-proof-deliver-key(7,97)!=-1 || invoked!=1{return 13;}
   if sci-proof-input.unit!=1{return 14;}
   failure+=1;
 }
 // Successful close consumes one seat frame and publishes exactly two replies.
 if setup()!=1{return 30;}expected-key=27;
 if sci-proof-deliver-key(7,27)!=42 || invoked!=1 || domain-current!=0 || load64(8192)!=4 || load64(8200)!=12{return 31;}
 if chan-page-recv-frame(8192,3000)!=1 || chan-page-recv-frame(8192,3000)!=1 || chan-page-recv-frame(8192,3000)!=0{return 32;}
 sci-proof-app.unit=0;sci-sync-ring-unit=0;
 if sci-proof-deliver-key(7,27)!=-1 || sci-proof-deliver-key(7,97)!=-1 || invoked!=1 || sci-proof-app.unit!=0 || load64(8192)!=12 || load64(8200)!=12{return 33;}
 let close-failure=6;
 while close-failure<9 {
   if setup()!=1{return 34;}expected-key=27;mode=close-failure;
   if sci-proof-deliver-key(7,27)!=-1 || invoked!=1 || domain-current!=0 || sci-proof-app.unit!=0{return 35;}
   if sci-proof-deliver-key(7,27)!=-1 || invoked!=1{return 36;}
   close-failure+=1;
 }
 // Close restore failure preserves private state until explicit kernel recovery.
 if setup()!=1{return 37;}expected-key=27;fail-switch=2;
 if sci-proof-deliver-key(7,27)!=-1 || domain-current!=2 || invoked!=1 || sci-proof-app.unit!=4{return 38;}
 if sci-proof-deliver-key(7,27)!=-1 || invoked!=1 || sci-proof-app.unit!=4{return 39;}
 domain-current=0;model-root=4096;fail-switch=0;
 if sci-resume-sync(2,0)!=-1 || sci-proof-deliver-key(7,27)!=-1 || invoked!=1 || sci-proof-app.unit!=0{return 40;}
 // Failed entry switch retires safely in the kernel domain without invoking.
 if setup()!=1{return 20;}fail-switch=1;
 if sci-proof-deliver-key(7,97)!=-1 || invoked!=0 || domain-current!=0 || sci-proof-app.unit!=0{return 21;}
 if sci-proof-deliver-key(7,97)!=-1 || invoked!=0{return 22;}
 // Failed restore stays in guest: no private retirement writes are permitted.
 if setup()!=1{return 23;}fail-switch=2;
 if sci-proof-deliver-key(7,97)!=-1 || invoked!=1 || domain-current!=2 || sci-proof-app.unit!=4 || sci-sync-ring-unit!=4{return 24;}
 if sci-proof-deliver-key(7,97)!=-1 || invoked!=1 || sci-proof-app.unit!=4{return 25;}
 // Explicit mock kernel recovery still cannot replay the pending exchange.
 domain-current=0;model-root=4096;fail-switch=0;
 if sci-resume-sync(2,0)!=-1 || invoked!=1{return 26;}
 if sci-proof-deliver-key(7,97)!=-1 || invoked!=1 || sci-proof-app.unit!=0{return 27;}
 // Input restore failure must likewise avoid private writes outside domain zero.
 if setup()!=1{return 28;}fail-switch=2;
 if sci-proof-poll-input()!=-1 || invoked!=1 || domain-current!=1 || sci-proof-input.unit!=1 || sci-sync-ring-unit!=1{return 29;}
 // Dead domain, capability mismatch, malformed/pending preconditions: no entry.
 let bad=0;
 while bad<12 {
   if setup()!=1{return 15;}
   if bad==0{store64(domain-table+56,0);}
   if bad==1{store64(cap-table-base+24,3);}
   if bad==2{store64(8208,509);}
   if bad==3{store64(8200,4);}
   if bad==4{store64(8216,4);}
   if bad==5{sci-proof-app.handle=770;}
   if bad==6{store64(runtime-instance-catalog+64+8,3);}
   if bad==7{store64(14600,999);}
   if bad==8{store64(14000+32,4096);}
   if bad==9{store64(14000+296,1);}
   if bad==10{store64(runtime-instance-catalog+64+48,2);}
   // Reuse the same metadata, domain, cap and component addresses with a fresh
   // generation/ID; the old snapshot must still fail before any guest entry.
   if bad==11{store64(runtime-instance-catalog+64+8,3);store64(runtime-instance-catalog+64+16,103);store64(14600,103);store64(14000+280,770);}

   if sci-proof-deliver-key(7,97)!=-1 || invoked!=0 || domain-current!=0{return 16;}
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
            f"PASS {profile}: two private snapshots, consume-before-reply, guest/pending/malformed/stale-generation refusals, CR3 restore failures and no replay"
        )
