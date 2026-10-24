#!/usr/bin/env python3
"""Actual native screen under modeled memory, compared with pinned host pyte.

Host output is an oracle only; this gate claims no GUI or foreign execution.
Run with an interpreter containing fixtures/terminal-session/oracle-requirements.txt.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import random
import re
import subprocess

import pyte

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--original-output', type=Path, default=ROOT/'fixtures/terminal-session/original-vi-output.bin')
a = p.parse_args(); out = a.out.resolve()
assert not out.exists() or not any(out.iterdir()), 'preserve prior evidence'
out.mkdir(parents=True, exist_ok=True)
assert importlib.metadata.version('pyte') == '0.8.2'
paths = [ROOT / ('components/' + name + '.in') for name in ['terminal-vt-table','terminal-screen']]
sha = lambda data: hashlib.sha256(data).hexdigest()
snapshot = {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in paths}
report = dict(status='running', goal_status='OPEN', scope='Native ASCII screen with modeled memory; host pyte oracle, no GUI credit',
              source_sha256=snapshot, compiler_sha256=sha(a.compiler.read_bytes()),
              oracle_version='pyte 0.8.2', original_output_sha256=sha(a.original_output.read_bytes()), checks=[])
native = '\n'.join('\n'.join(line for line in path.read_text().splitlines()
                           if not line.startswith(('package ', 'import '))) for path in paths)
memory = '''var memory:[Int]=[ZEROS];var escaped=0;
fn load64(p:Int)->Int{if p<0 || p>=32784 || (p&7)!=0{escaped=1;return 0;}return memory[p/8];}
fn store64(p:Int,v:Int)->void{if p<8 || p>=32776 || (p&7)!=0{escaped=1;return;}memory[p/8]=v;}
fn screen-digest()->Int{let h=0;let y=0;while y<24{let x=0;while x<80{h=(h*257+(terminal-screen-cell(8,x,y)&255))%1000000007;x+=1;}y+=1;}return h;}
'''.replace('ZEROS', ','.join(['0'] * 4098))
source = memory + native + '\nfn main()->Int{terminal-screen-init(8);\n'
check_count = 0; event_count = 0
def feed(data):
    global source, event_count
    for byte in data:
        source += f'if terminal-screen-feed(8,{byte})!=0{{return 1;}}\n'
        event_count += 1
def check(screen, name):
    global source, check_count
    rows = screen.display
    assert all(len(row) == 80 for row in rows)
    digest = 0
    for byte in ''.join(rows).encode('ascii'): digest = (digest * 257 + byte) % 1000000007
    check_count += 1
    source += f'if escaped!=0 || screen-digest()!={digest}{{return {1000+check_count};}}\n'
    report['checks'].append(dict(name=name, digest=digest))
def scenario(name, data):
    global source
    source += 'terminal-screen-init(8);\n'
    current = pyte.Screen(80,24); stream = pyte.Stream(current)
    normal = current
    # pyte does not implement xterm 1049. The independent wrapper keeps two
    # complete mature Screen instances; normal cells/cursor survive switches.
    tokens = re.split(rb'(\[\?1049[hl])',data)
    for part_index, part in enumerate(tokens):
        if part == b'\x1b[?1049h':
            current = pyte.Screen(80,24); stream = pyte.Stream(current); feed(part)
        elif part == b'\x1b[?1049l':
            current = normal; stream = pyte.Stream(current); feed(part)
        else:
            for offset in range(0,len(part),31):
                chunk = part[offset:offset+31]; feed(chunk); stream.feed(chunk.decode('ascii'))
                check(current,f'{name}/{part_index}/{offset}')
        check(current,f'{name}/{part_index}/end')

try:
    subprocess.run(['python3', str(ROOT / 'scripts/build-terminal-vt-table.py'), '--check'],check=True,capture_output=True,text=True)
    words = list(map(int,re.search(r'var terminal-vt-table:\[Int\]=\[([^]]+)\]',paths[0].read_text())[1].split(',')))
    table = b''.join((word & ((1<<64)-1)).to_bytes(8,'little') for word in words)
    assert sha(table) == 'f6f97d2c6edf44fd49e37123f39bab752bc0f6789893d0ab1a40ae1dc7f6682e'
    for index, byte in enumerate(table):
        source += f'if terminal-vt-transition({index//256},{index%256})!={byte}{{return 2;}}\n'
    source += 'if terminal-vt-transition(-1,0)!=-1 || terminal-vt-transition(16,0)!=-1 || terminal-vt-transition(0,256)!=-1{return 3;}\n'
    scenarios = {
        'cursor-erase': b'hello\rHI\x1b[2;5Hxyz\x1b[1D!\x1b[K\x1b[1;2H\x1b[1J',
        'wrap-scroll': b'A'*80+b'B'*85+b'\r\nrow\n'*29,
        'regions': b'first\x1b[2;4r\x1b[2;1Hone\r\ntwo\r\nthree\r\nfour\x1b[r',
        'motion': b'\x1b[12;40Hx\x1b[2Aup\x1b[3Bdown\x1b[9Cright\x1b[4Dleft\x1b[2Enew\x1b[1Fprev\x1b[9Gcol\x1b[3drow',
        'ignored-osc': b'normal\x1b]52;c;clipboard-refused\x07x',
        'alternate': b'kept\x1b[?1049hother\x1b[?1049l!',
        'original-vi': a.original_output.read_bytes(),
    }
    rng = random.Random(251025)
    scenarios['random-motion-erase'] = b''.join(rng.choice([
        bytes([rng.randrange(32,127)]),b'\r\n',b'\t',b'\b',
        f'\x1b[{rng.randrange(1,25)};{rng.randrange(1,81)}H'.encode(),
        f'\x1b[{rng.randrange(0,3)}K'.encode(),f'\x1b[{rng.randrange(0,3)}J'.encode()]) for _ in range(200))
    for name, data in scenarios.items(): scenario(name,data)
    # Bounds and unsupported profiles: no out-of-range cell writes, recovery
    # after overlong params/intermediates, no memory growth for long OSC/DCS.
    source += 'terminal-screen-init(8);\n'
    feed(b'\x1b['+b'1;'*40+b'2H!\x1b[999999999999999999999H?\x1b[1:2Hignored')
    source += 'if escaped!=0 || terminal-screen-cell(8,-1,0)!=-1 || terminal-screen-cell(8,80,0)!=-1{return 4;}\n'
    source += 'terminal-screen-init(8);\n'
    feed(b'X\x1bPpayload\x1b\\Y')
    source += 'if (terminal-screen-cell(8,0,0)&255)!=88 || (terminal-screen-cell(8,1,0)&255)!=89 || (terminal-screen-cell(8,2,0)&255)!=32{return 8;}\n'
    source += 'if terminal-screen-feed(8,128)!=-95 || terminal-screen-feed(8,-1)!=-1 || terminal-screen-feed(8,256)!=-1{return 5;}\n'
    source += 'terminal-screen-init(8);\n'
    feed(b'\x1b[31;44;1mX\x1b[0mY')
    source += 'if terminal-screen-cell(8,0,0)!=(88|(1<<8)|(4<<16)|(1<<24)) || terminal-screen-cell(8,1,0)!=(89|(7<<8)){return 6;}\n'
    source += 'if escaped!=0 || memory[0]!=0 || memory[4097]!=0{return 7;}return 42;}\n'
    prefix, body = source.split('fn main()->Int{terminal-screen-init(8);\n')
    statements = ['terminal-screen-init(8);'] + body.removesuffix('return 42;}\n').splitlines()
    source = prefix
    parts = []
    for offset in range(0,len(statements),80):
        name = 'screen-part-' + str(offset//80); parts.append(name)
        source += 'fn '+name+'()->Int{\n'+'\n'.join(statements[offset:offset+80])+'\nreturn 0;}\n'
    source += 'fn main()->Int{\n'
    for index, name in enumerate(parts):
        source += f'let result{index}={name}();if result{index}!=0{{return result{index};}}\n'
    source += 'return 42;}\n'
    fixture=out/'screen.in'; fixture.write_text(source)
    for profile in ['default','lean','harden']:
        result=subprocess.run([str(a.compiler),'compile','--path',str(fixture),'--target','jit','--profile',profile,'--out',str(out/profile),'--json'],capture_output=True,text=True,timeout=180)
        (out/(profile+'.json')).write_text(result.stdout);(out/(profile+'.stderr')).write_text(result.stderr)
        actual=json.loads(result.stdout)
        assert result.returncode==0 and actual.get('success') and actual.get('eval_result')=={'Int':42},(profile,actual)
        print('PASS native screen',profile,flush=True)
    assert snapshot=={str(path.relative_to(ROOT)):sha(path.read_bytes()) for path in paths}
    report.update(status='passed',screen_checkpoints=check_count,input_bytes=event_count,table_transitions=4096)
except Exception as error:
    report.update(status='failed',error=str(error));raise
finally:
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
