#!/usr/bin/env python3
"""Generate native lookup data from pinned MIT VTE definitions and table rules."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, default=ROOT / 'assets/terminal/vte')
p.add_argument('--out', type=Path, default=ROOT / 'components/terminal-vt-table.in')
p.add_argument('--check', action='store_true')
p.add_argument('--upstream-reference', type=Path, help='Optional exact 4096-byte dump from the original Rust macro')
a = p.parse_args()
manifest = json.loads((a.source / 'provenance.json').read_text())
assert manifest['revision'] == '89c12df969145ffb5084d1122627d7292c2c638f'
for item in manifest['files']:
    assert hashlib.sha256((a.source / item['file']).read_bytes()).hexdigest() == item['sha256']
definitions = (a.source / 'definitions.rs').read_text()
enums = {}
for name in ['State', 'Action']:
    body = re.search(r'pub enum ' + name + r'\s*\{([^}]+)\}', definitions).group(1)
    enums[name] = {key: int(value) for key,value in re.findall(r'(\w+)\s*=\s*(\d+)',body)}
    assert sorted(enums[name].values()) == list(range(16))
source = re.sub(r'//[^\n]*', '', (a.source / 'table.rs').read_text())
table = bytearray(4096)
states = re.findall(r'(\w+)\s*\{([^{}]*)\}',source)
assert len(states) == 15
for state, body in states:
    assert state in enums['State']
    rule = r'(0x[0-9a-f]+)(?:\s*\.\.=\s*(0x[0-9a-f]+))?\s*=>\s*\((\w+),\s*(\w+)\)\s*,?'
    residue = re.sub(rule,'',body)
    assert not residue.strip(), (state,residue)
    for first,last,target,action in re.findall(rule,body):
        first = int(first,16); last = int(last,16) if last else first
        assert 0 <= first <= last <= 255
        encoded = enums['State'][target] | (enums['Action'][action] << 4)
        for byte in range(first,last+1): table[enums['State'][state] * 256 + byte] = encoded
if a.upstream_reference:
    assert a.upstream_reference.read_bytes() == table, 'native data differs from the original Rust macro'
words = []
for offset in range(0,len(table),8):
    word = int.from_bytes(table[offset:offset+8],'little')
    words.append(word if word < 1 << 63 else word - (1 << 64))
result = '''// SPDX-License-Identifier: MIT
// Copyright (c) 2016 Joe Wilm
// Generated from alacritty/vte 0.13.1 at 89c12df969145ffb5084d1122627d7292c2c638f.
// Full permission notice: assets/terminal/vte/LICENSE-MIT.
// This is transition data, not a screen model or a complete terminal emulator.
// Regenerate with scripts/build-terminal-vt-table.py.
package space.terminal

var terminal-vt-table:[Int]=[WORDS]

fn terminal-vt-transition(state:Int,byte:Int)->Int{
  if state<0 || state>=16 || byte<0 || byte>255{return -1;}
  let index=state*256+byte;
  return (terminal-vt-table[index/8] >> ((index%8)*8)) & 255;
}
'''.replace('WORDS',','.join(map(str,words)))
if a.check:
    assert a.out.read_text() == result, 'generated table is stale'
else:
    a.out.write_text(result)
print('PASS 4096 VTE transitions; sha256='+hashlib.sha256(table).hexdigest())
