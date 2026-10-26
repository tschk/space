#!/usr/bin/env python3
"""Verify staging keeps all bytes and rejects overlap at the real boundaries."""
import argparse
import hashlib
import json
from pathlib import Path

from boot_fixture_layout import IMAGE_BASE, HEAP_BASE, stage_fixture

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
if a.out.exists() and any(a.out.iterdir()):p.error('--out must be new or empty')
a.out.mkdir(parents=True,exist_ok=True)
checks=[]
for physical in (0x2b0000,0x2c0000,0x2d0000,0x2e0000,0x2f0000):
    kernel=b'kernel'+bytes(physical-IMAGE_BASE-7)
    payload=b'fixture'+bytes(HEAP_BASE-physical-7)
    packed=stage_fixture(kernel,payload,physical)
    assert packed[:len(kernel)]==kernel
    assert packed[len(kernel):physical-IMAGE_BASE]==b'\0'
    assert packed[physical-IMAGE_BASE:]==payload and IMAGE_BASE+len(packed)==HEAP_BASE
    checks.append({'physical':hex(physical),'status':'passed','packed_sha256':hashlib.sha256(packed).hexdigest()})
for kernel,payload,physical in [
    (b'x'*(0x1f0000+1),b'x',0x2f0000),
    (b'x',b'x'*65537,0x2f0000),
    (b'x',b'',0x2f0000),
    (b'x',b'x',IMAGE_BASE-4096),
    (b'x',b'x',HEAP_BASE),
    (b'x',b'x',0x2f0001)]:
    try:stage_fixture(kernel,payload,physical)
    except ValueError:checks.append({'physical':hex(physical),'status':'refused-as-required'})
    else:raise AssertionError('unsafe fixture placement accepted')
# Realistic growth: the old slot must still fail; relocating the payload is
# different from dropping the kernel-size guard or moving the native heap.
kernel=bytes(0x180001);payload=b'fixture'
try:stage_fixture(kernel,payload,0x280000)
except ValueError:pass
else:raise AssertionError('old overlapping slot accepted')
packed=stage_fixture(kernel,payload,0x2f0000)
assert packed[0x1f0000:]==payload
checks.append({'old_slot':'refused','new_slot':'passed','heap_unchanged':HEAP_BASE==0x300000})
(a.out/'report.json').write_text(json.dumps({'status':'passed','checks':checks},indent=2)+'\n')
print(f'PASS: {len(checks)} boot fixture layout checks; heap remains at {HEAP_BASE:#x}')
