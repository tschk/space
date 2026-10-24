#!/usr/bin/env python3
"""Execute actual keyboard decoders/editor operations against independent vectors.

Models only: real PS/2 input and rendered carets are checked separately by
check-gui-protected-windows.py. USB controller/enumeration is not proved here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', required=True, type=Path)
p.add_argument('--out', required=True, type=Path)
a = p.parse_args()
out = a.out.resolve()
assert not out.exists() or not any(out.iterdir()), '--out must be new or empty'
out.mkdir(parents=True, exist_ok=True)
compiler = a.compiler.resolve()
paths = [ROOT / x for x in ('protocol/keyboard.in', 'components/input.in',
                            'components/ps2-keyboard.in', 'components/gui-editor-model.in')]
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
snapshot = {str(x.relative_to(ROOT)): sha(x) for x in paths}
def function(source, name):
    start = source.index('fn ' + name + '(')
    return source[start:source.index('\n}', start) + 2] + '\n'
keyboard = paths[0].read_text()
# Golden Set1 make/break byte streams, including real E0/E1 framing.
sequence = [(0xE0,-1),(0x4B,129),(0xE0,-1),(0xCB,-1),
            (0xE0,-1),(0x4D,130),(0xE0,-1),(0x47,132),
            (0xE0,-1),(0x4F,133),(0xE0,-1),(0x53,134),
            (0xE0,-1),(0x48,128),(0xE0,-1),(0x50,131),
            (0xE0,-1),(0x49,135),(0xE0,-1),(0x51,136),
            (0xE0,-1),(0x2A,-1),(0x1E,97), # PrintScreen fake shift
            (0xE0,-1),(0xAA,-1),(0x1E,97),
            (0x1D,-1),(0xE0,-1),(0x1D,-1),(0x9D,-1),(0x1F,19),
            (0xE0,-1),(0x9D,-1),(0x1F,115), # independent Ctrl releases
            (0xE1,-1),(0x1D,-1),(0x45,-1),(0xE1,-1),(0x9D,-1),(0xC5,-1),
            (0x1F,115),(0x2A,-1),(0x09,42),(0xAA,-1),(0x09,56),
            (0xE0,-1),(0x1C,10),(0xE0,-1),(0x35,47)]
common = '''const PS2-DATA=96;
var ps2-kbd-ctrl=0;var ps2-kbd-shift=0;var ps2-kbd-caps=0;
var ps2-kbd-caps-held=0;var ps2-kbd-extended=0;var ps2-kbd-pause=0;
var code=0;
fn ps2-kbd-has-data()->Int{return 1;}
fn inb(port:Int)->Int{return code;}
'''
sources = {}
for name in ('input', 'ps2-keyboard'):
    original = (ROOT / f'components/{name}.in').read_text()
    source = keyboard + common + function(original, 'ps2-scancode-ascii') + function(original, 'ps2-kbd-getchar')
    source += 'fn main()->Int{\n'
    for i, (code, expected) in enumerate(sequence):
        source += f'code={code};if ps2-kbd-getchar()!={expected}{{return {1000+i};}}\n'
    source += 'if ps2-kbd-ctrl!=0 || ps2-kbd-shift!=0 || ps2-kbd-extended!=0 || ps2-kbd-pause!=0{return 2000;}return 42;}\n'
    sources[name] = source
# USB HID Usage Tables keyboard-page US physical keys. Unknown/error usages
# must refuse, rather than publishing NUL or treating Delete as Enter.
hid = {i+4:ord(ch) for i,ch in enumerate('abcdefghijklmnopqrstuvwxyz')}
hid.update({i+0x1e:ord(ch) for i,ch in enumerate('1234567890')})
hid.update({0x28:10,0x29:27,0x2a:8,0x2b:9,0x2c:32,0x2d:45,0x2e:61,
            0x2f:91,0x30:93,0x31:92,0x33:59,0x34:39,0x35:96,0x36:44,
            0x37:46,0x38:47,0x4a:132,0x4b:135,0x4c:134,0x4d:133,
            0x4e:136,0x4f:130,0x50:129,0x51:131,0x52:128})
source = keyboard + function(paths[1].read_text(), 'hid-to-ascii') + 'fn main()->Int{\n'
for usage in range(256):
    source += f'if hid-to-ascii({usage})!={hid.get(usage,-1)}{{return {3000+usage};}}\n'
source += 'if ps2-modified-ascii(115,0,0,1)!=19 || ps2-modified-ascii(56,2,0,0)!=42{return 4000;}return 42;}\n'
sources['hid'] = source
source = keyboard + function(paths[1].read_text(), 'hid-to-ascii') + function(paths[1].read_text(), 'xhci-kbd-report-ascii')
source += """var xhci-kbd-buf=16;var xhci-kbd-prev=0;
var report:[Int]=[0,0,0,0,0,0,0,0];
fn load8(p:Int)->Int{return report[p - 16];}
fn main()->Int{
 report[0]=2;report[2]=0x25;if xhci-kbd-report-ascii()!=42{return 1;}
 if xhci-kbd-report-ascii()!=-1{return 2;}
 report[2]=0;if xhci-kbd-report-ascii()!=-1{return 3;}
 report[0]=1;report[2]=0x16;if xhci-kbd-report-ascii()!=19{return 4;}
 report[0]=0;report[2]=0;if xhci-kbd-report-ascii()!=-1{return 5;}
 report[2]=0xff;if xhci-kbd-report-ascii()!=-1{return 6;}
 report[2]=0x4c;if xhci-kbd-report-ascii()!=134{return 7;}
 return 42;
}
"""
sources['hid-report'] = source
# Independent cursor/string model. Assert every intermediate byte, length,
# cursor, non-text region and save request; rejected full/boundary operations
# preserve content. Cases deliberately repeatedly reach full and empty buffers.
rng = random.Random(241024)
keys = [132,8,134] + list(map(ord,'abcdefgh')) + [132,130,134,ord('x'),129,8,133,130,134,19]
keys += [rng.choice([8,129,130,132,133,134,19] + list(map(ord,'ABCxyz012'))) for _ in range(480)]
source = keyboard + '''var memory:[Int]=[''' + ','.join(['0']*256) + '''];
var escaped=0;var saves=0;var saved-size=0;var saved:[Int]=[0,0,0,0,0,0,0,0];
fn load8(p:Int)->Int{return memory[p];}
fn load64(p:Int)->Int{return memory[p];}
fn store8(p:Int,v:Int)->void{if p<0 || p>=8{escaped=1;return;}memory[p]=v;}
fn store64(p:Int,v:Int)->void{if p!=128 && p!=136{escaped=1;return;}memory[p]=v;}
fn gui-editor-status-at(memory:Int,text:Int)->void{return;}
fn gui-note-write(p:Int,n:Int)->Int{saved-size=n;saves+=1;let i=0;while i<n{saved[i]=memory[p+i];i+=1;}return 0;}
''' + function(paths[3].read_text(), 'gui-editor-key-at') + 'fn main()->Int{\n'
text = bytearray(); cursor = 0; saves = 0
for index,key in enumerate(keys):
    if key == 129: cursor=max(0,cursor-1)
    elif key == 130: cursor=min(len(text),cursor+1)
    elif key == 132: cursor=0
    elif key == 133: cursor=len(text)
    elif key == 8 and cursor: del text[cursor-1]; cursor-=1
    elif key == 134 and cursor<len(text): del text[cursor]
    elif 32<=key<127 and len(text)<8: text[cursor:cursor]=bytes([key]); cursor+=1
    source += f'gui-editor-key-at(0,{key});if load64(128)!={len(text)} || load64(136)!={cursor} || escaped!=0{{return {5000+index};}}\n'
    for i,ch in enumerate(text):
        source += f'if load8({i})!={ch}{{return {6000+index};}}\n'
    if key == 19:
        saves+=1
        source += f'if saves!={saves} || saved-size!={len(text)}{{return {7000+index};}}\n'
        for i,ch in enumerate(text): source += f'if saved[{i}]!={ch}{{return {8000+index};}}\n'
for index,(bad_length,bad_cursor) in enumerate([(-1,0),(9,0),(3,-1),(3,4)]):
    source += f'memory[128]={bad_length};memory[136]={bad_cursor};let before{index}=saves;gui-editor-key-at(0,19);gui-editor-key-at(0,65);gui-editor-key-at(0,8);if memory[128]!={bad_length} || memory[136]!={bad_cursor} || saves!=before{index} || escaped!=0{{return {9000+index};}}\n'
source += 'return 42;}\n'
sources['editor'] = source
report = dict(status='running',classification='Actual decoder/editor source models; not USB hardware evidence',
              compiler_sha256=sha(compiler),source_hashes=snapshot,set1_events=len(sequence),hid_usages=256,editor_operations=len(keys),checks=[])
try:
    for name,source in sources.items():
        fixture=out/(name+'.in');fixture.write_text(source)
        for profile in ('default','lean','harden'):
            result=subprocess.run([str(compiler),'compile','--path',str(fixture),'--target','jit','--profile',profile,'--out',str(out/(name+'-'+profile)),'--json'],capture_output=True,text=True,timeout=120)
            (out/(name+'-'+profile+'.json')).write_text(result.stdout)
            (out/(name+'-'+profile+'.stderr')).write_text(result.stderr)
            emitted=json.loads(result.stdout)
            assert result.returncode==0 and emitted.get('success') and emitted.get('eval_result')=={'Int':42},(name,profile,emitted)
            report['checks'].append(dict(name=name,profile=profile,status='passed'))
            print('PASS',name,profile,flush=True)
    assert snapshot=={str(x.relative_to(ROOT)):sha(x) for x in paths}
    assert sha(compiler)==report['compiler_sha256']
    report['status']='passed'
finally:
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
