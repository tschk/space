#!/usr/bin/env python3
"""Execute actual Space allocators and SPDP pool handler with isolated memory."""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--in", dest="compiler", required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]


def function(filename, name):
    text = (root / "components" / filename).read_text()
    start = text.index("fn " + name + "(")
    return text[start : text.index("\n}", start) + 2]


cases = [
    ("negative", 4096, 8192, -32, False, 4096),
    ("negative-one", 4096, 8192, -1, False, 4096),
    ("rounding-overflow", 4096, 8192, 9223372036854775807, False, 4096),
    ("rounding-overflow-edge", 4096, 8192, 9223372036854775793, False, 4096),
    ("exhausted", 4096, 4112, 17, False, 4096),
    (
        "pointer-overflow",
        9223372036854775800,
        9223372036854775807,
        16,
        False,
        9223372036854775800,
    ),
    ("rounded", 4096, 8192, 17, True, 4128),
    ("exact-fit", 4096, 4112, 16, True, 4112),
    ("zero", 4096, 8192, 0, True, 4096),
]
results = []
with tempfile.TemporaryDirectory(prefix="space-display-allocation-") as temporary:
    directory = Path(temporary)

    def check(name, source):
        path = directory / (name + ".in")
        path.write_text(source)
        for profile in ("default", "lean", "harden"):
            run = subprocess.run(
                [
                    args.compiler,
                    "compile",
                    "--path",
                    str(path),
                    "--target",
                    "jit",
                    "--entry",
                    "main",
                    "--profile",
                    profile,
                    "--out",
                    str(directory / "out"),
                    "--json",
                ],
                capture_output=True,
                text=True,
            )
            report = json.loads(run.stdout)
            if not report.get("success") or report.get("eval_result") != {"Int": 42}:
                raise SystemExit(f"FAIL {name}/{profile}: {run.stdout}\n{run.stderr}")
            results.append((name, profile))

    for filename in ("memory.in", "display-standalone.in"):
        for name, start, end, size, valid, next_pointer in cases:
            kernel = filename == "memory.in"
            source = f"""var heap-next:Int={start};
var heap-end:Int={end};
fn panic(message:String)->Void{{throw 9;}}
{function(filename, 'alloc')}
fn main()->Int{{
 try{{let pointer=alloc({size});
 if heap-next!={next_pointer}{{return 1;}}
 if pointer!={start if valid else 0}{{return 2;}}
 if {str(kernel and not valid).lower()}{{return 3;}}
 return 42;
 }}catch 9{{if {str(valid or not kernel).lower()} || heap-next!={start}{{return 4;}}return 42;}}
 return 5;
}}
"""
            check(filename + "-" + name, source)
    for name, pool_id, size, allocated, calls, expected_pool, expected_size in [
        ("negative", 0, -32, 888, 0, 777, 32),
        ("zero", 0, 0, 888, 0, 777, 32),
        ("overflow", 0, 9223372036854775807, 888, 0, 777, 32),
        ("bad-id", -1, 16, 888, 0, 777, 32),
        ("past-id", 16, 16, 888, 0, 777, 32),
        ("failed-allocation", 0, 16, 0, 1, 777, 32),
        ("valid", 0, 16, 888, 1, 888, 16),
    ]:
        source = (
            """const DSP-MAX-POOLS=16;
var dsp-pools:Int=8;
var dsp-pool-sizes:Int=136;
var calls:Int=0;
var memory:[Int]=["""
            + ",".join(["0"] * 512)
            + f"""];
fn store64(p:Int,v:Int)->Void{{memory[p]=v;}}
fn alloc(n:Int)->Int{{calls+=1;return {allocated};}}
{function('display.in', 'dsp-shm-create-pool')}
fn main()->Int{{memory[8]=777;memory[136]=32;
 dsp-shm-create-pool({pool_id},{size});
 if calls!={calls} || memory[8]!={expected_pool} || memory[136]!={expected_size}{{return 1;}}
 return 42;
}}
"""
        )
        check("pool-" + name, source)
print(
    f"PASS {len(results)} actual allocator/pool checks (kernel panic, standalone zero, no mutation on rejection)"
)
