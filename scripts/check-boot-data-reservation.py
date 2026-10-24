#!/usr/bin/env python3
"""Execute the actual discover-memory function with simulated Multiboot load services."""
import argparse
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--in', dest='compiler', required=True)
parser.add_argument('--memory', type=Path, default=Path(__file__).resolve().parents[1] / 'components/memory.in')
parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[1] / 'target/verification/boot-data-reservation')
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
text = args.memory.read_text()
start = text.index('fn discover-memory(')
function = text[start:text.index('\n// --- virtual', start)]
cases = [
    ('legacy', 0, 0, 0x100000, 0x1ff00000, 0x300000, 0x20000000),
    ('small-data', 0x200000, 24, 0x100000, 0x1ff00000, 0x300000, 0x20000000),
    ('unaligned-end', 0x200000, 0x100001, 0x100000, 0x1ff00000, 0x301000, 0x20000000),
    ('aligned-end', 0x200000, 0x101000, 0x100000, 0x1ff00000, 0x301000, 0x20000000),
    ('bad-base', 0x200001, 24, 0x100000, 0x1ff00000, None, None),
    ('relocated-data', 0x210000, 24, 0x100000, 0x1ff00000, 0x300000, 0x20000000),
    ('relocated-after-old-reserve', 0x310000, 0x1001, 0x100000, 0x1ff00000, 0x312000, 0x20000000),
    ('relocated-overflow', 0xFFFFF000, 0x1001, 0x100000, 0x200000000, None, None),
    ('out-of-map-base', 0x100000000, 24, 0x100000, 0x200000000, None, None),
    ('below-code-base', 0x1FF000, 24, 0x100000, 0x1ff00000, None, None),
    ('missing-size', 0x200000, 0, 0x100000, 0x1ff00000, None, None),
    ('missing-base', 0, 24, 0x100000, 0x1ff00000, None, None),
    ('negative-size', 0x200000, -1, 0x100000, 0x1ff00000, None, None),
    ('overflow-size', 0x200000, 0xffe00001, 0x100000, 0x1ff00000, None, None),
    ('no-heap-capacity', 0x200000, 0x100001, 0x100000, 0x200000, None, None),
    ('large-ram', 0x200000, 24, 0x100000, 0x200000000, 0x300000, 0x100000000),
    ('end-at-4g', 0x200000, 0xffe00000, 0x100000, 0x200000000, None, None),
]
results = []
for name, database, size, base, length, expected_start, expected_end in cases:
    source = f'''
var total-ram:Int=0;
var region-count:Int=0;
var heap-next:Int=123;
var heap-end:Int=456;
fn load32(p:Int)->Int{{if p==4096{{return 64;}}if p==4140{{return 24;}}if p==4144{{return 8192;}}if p==8192{{return 20;}}if p==8212{{return 1;}}return 0;}}
fn load64(p:Int)->Int{{if p==0x101040{{return {database};}}if p==0x101048{{return {size};}}if p==8196{{return {base};}}if p==8204{{return {length};}}return 0;}}
fn panic(message:String)->void{{throw 9;}}
''' + function
    success = expected_start is not None
    source += f'''
fn main()->Int{{
 try{{discover-memory(4096);
 if {str(not success).lower()}{{return 1;}}
 if heap-next!={expected_start or 0} || heap-end!={expected_end or 0}{{return 2;}}
 if region-count!=1 || total-ram!={length}{{return 3;}}
 return 42;
 }}catch 9{{if {str(success).lower()}{{return 4;}}if heap-next!=123 || heap-end!=456{{return 5;}}return 42;}}
 return 6;
}}
'''
    path = args.out / (name + '.in')
    path.write_text(source)
    for profile in ('default', 'lean', 'harden'):
        run = subprocess.run([args.compiler, 'compile', '--path', str(path),
                              '--out', str(args.out / 'artifact'), '--target',
                              'jit', '--entry', 'main', '--profile', profile,
                              '--json'], capture_output=True, text=True)
        (args.out / f'{name}-{profile}.json').write_text(run.stdout)
        report = json.loads(run.stdout)
        ok = report.get('success') and report.get('eval_result') == {'Int': 42}
        results.append({'case': name, 'profile': profile, 'pass': bool(ok)})
        if not ok:
            raise SystemExit(f'FAIL {name}/{profile}: {run.stdout}\n{run.stderr}')
print(f'PASS {len(results)} actual-function checks ({len(cases)} cases, 3 profiles)')
(args.out / 'summary.json').write_text(json.dumps(results, indent=2))
