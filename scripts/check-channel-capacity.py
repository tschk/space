#!/usr/bin/env python3
"""Run actual channel creation/validation with an isolated allocation observer."""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--in", dest="compiler", required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
text = (root / "components/channel.in").read_text()


def function(name):
    start = text.index("fn " + name + "(")
    return text[start:text.index("\n}", start) + 2]


checks = 0
with tempfile.TemporaryDirectory(prefix="space-channel-capacity-") as temporary:
    directory = Path(temporary)
    for capacity in (-1, 0, 4097, 2305843009213693952, 9223372036854775807, 1, 4096):
        valid = 1 <= capacity <= 4096
        source = "var heap:[Int]=[" + ",".join(["0"] * 64) + "];\n" + f"""var calls:Int=0;
var requested:Int=0;
fn load64(p:Int)->Int{{return heap[p];}}
fn store64(p:Int,value:Int)->Void{{heap[p]=value;}}
fn chan-alloc(size:Int)->Int{{calls=calls+1;requested=size;return 8;}}
{function('chan-new')}
{function('chan-valid')}
fn main()->Int{{
 let channel=chan-new({capacity});
 if calls!={int(valid)}{{return 1;}}
 if requested!={48 + capacity * 8 if valid else 0}{{return 2;}}
 if {str(valid).lower()}{{
  if channel==0{{return 3;}}
  if chan-valid(channel)!=1{{return 4;}}
  if load64(channel)!={capacity}{{return 5;}}
  if load64(channel+8)!=0 || load64(channel+16)!=0 || load64(channel+24)!=0{{return 6;}}
  if load64(channel+32)!=-1 || load64(channel+40)!=-1{{return 7;}}
 }}else{{if channel!=0{{return 8;}}}}
 return 42;
}}
"""
        path = directory / f"capacity-{capacity}.in"
        path.write_text(source)
        for profile in ("default", "lean", "harden"):
            run = subprocess.run(
                [args.compiler, "compile", "--path", str(path), "--target", "jit",
                 "--profile", profile, "--out", str(directory / "out"), "--json"],
                capture_output=True, text=True, timeout=30,
            )
            report = json.loads(run.stdout)
            if not report.get("success") or report.get("eval_result") != {"Int": 42}:
                raise SystemExit(f"FAIL capacity={capacity}/{profile}: {run.stdout}\n{run.stderr}")
            checks += 1
print(f"PASS: {checks} actual channel capacity checks")
