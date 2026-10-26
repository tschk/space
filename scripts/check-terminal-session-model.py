#!/usr/bin/env python3
"""Actual native terminal functions with modeled memory/context; no app credit."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
a.out = a.out.resolve()
assert not a.out.exists() or not any(a.out.iterdir()), 'preserve prior evidence'
a.out.mkdir(parents=True, exist_ok=True)
paths = [ROOT / name for name in ['components/terminal-session.in',
    'components/terminal-seat.in', 'components/linux-terminal-keyboard.in',
    'protocol/keyboard.in', 'protocol/input.in', 'components/object.in']]
sources = {str(path.relative_to(ROOT)): path.read_bytes() for path in paths}
def owned(name):
    return '\n'.join(line for line in sources[name].decode().splitlines()
                     if not line.startswith(('package ', 'import ')))
object_source = sources['components/object.in'].decode()
def function(name):
    start = object_source.index('fn ' + name + '(')
    opening = object_source.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (object_source[end] == '{') - (object_source[end] == '}')
        end += 1
    return object_source[start:end]
native = '\n'.join(owned(name) for name in ['protocol/input.in',
    'protocol/keyboard.in','components/terminal-session.in', 'components/terminal-seat.in',
    'components/linux-terminal-keyboard.in'])
native += '\n' + '\n'.join(function(name) for name in [
    'cap-check', 'cap-mint', 'cap-revoke', 'cap-memory', 'cap-input'])
harness = '''
var memory:[Int]=[ZEROS];
var heap-next:Int=65536;var heap-end:Int=120000;
var cap-table-base:Int=256;var cap-table-cap:Int=16;var cap-count:Int=0;
var kernel:Int=1;
fn user-space-kernel()->Int{return kernel;}
fn load64(p:Int)->Int{return memory[p];}
fn store64(p:Int,v:Int)->void{memory[p]=v;}
fn alloc(n:Int)->Int{let p=heap-next;heap-next+=(n+7)&-8;return p;}
fn cpu-mem-fill64(p:Int,v:Int,n:Int)->void{let i=0;while i<n{store64(p+i*8,v);i+=1;}}
'''.replace('ZEROS', ','.join(['0'] * 131072))
pair = '''let a=terminal-session-open(0,2,80,24);let b=terminal-session-open(1,2,100,30);
if a<=0 || b<=0 || a==b{return false;}
'''
cases = {
    'initial-observations': pair + 'return terminal-session-query(a,0,0)==80 && terminal-session-query(b,1,1)==30 && terminal-session-query(a,0,2)==0 && terminal-session-query(a,0,3)==0 && terminal-session-query(a,0,4)==1 && terminal-session-query(a,0,5)==0;',
    'empty-is-would-block': pair + 'return terminal-session-read(a,0)==-7 && terminal-session-output(a,0)==-7 && terminal-session-query(a,0,4)==1;',
    'input-is-private': pair + 'return terminal-session-input(a,0,2,0)==0 && terminal-session-read(b,1)==-7 && terminal-session-read(a,0)==0 && terminal-session-read(a,0)==-7;',
    'output-is-private': pair + 'return terminal-session-write(b,1,255)==0 && terminal-session-output(a,0)==-7 && terminal-session-output(b,1)==255;',
    'wrong-owner': pair + 'return terminal-session-read(a,1)==-2 && terminal-session-close(a,1)==-2 && terminal-session-query(a,0,0)==80;',
    'owner-alias-refused': pair + 'let alias=cap-mint(1001,4);return terminal-session-read(a,alias)==-2;',
    'seat-alias-refused': pair + 'let alias=cap-mint(2001,64);return terminal-session-input(a,0,alias,65)==-2 && terminal-session-query(a,0,2)==0;',
    'focus-switch': pair + 'if terminal-seat-focus(a,0,2)!=0 || terminal-seat-deliver(2,65)!=0 || terminal-seat-focus(b,1,2)!=0 || terminal-seat-deliver(2,66)!=0{return false;}return terminal-session-read(a,0)==65 && terminal-session-read(b,1)==66 && terminal-session-read(a,0)==-7;',
    'invalid-focus-preserves-lease': pair + 'terminal-seat-focus(a,0,2);return terminal-seat-focus(b,0,2)==-2 && terminal-seat-deliver(2,65)==0 && terminal-session-read(a,0)==65;',
    'focus-seat-alias': pair + 'terminal-seat-focus(a,0,2);let alias=cap-mint(2001,64);return terminal-seat-deliver(alias,65)==-2 && terminal-session-query(a,0,2)==0;',
    'focus-clear': pair + 'terminal-seat-focus(a,0,2);return terminal-seat-clear(2)==0 && terminal-seat-deliver(2,65)==-6;',
    'stale-focus-after-reuse': pair + 'terminal-seat-focus(a,0,2);terminal-session-close(a,0);let fresh=terminal-session-open(0,2,80,24);return fresh>0 && fresh!=a && terminal-seat-deliver(2,65)==-6 && terminal-session-query(fresh,0,2)==0;',
    'resize-preserves-data': pair + 'terminal-session-input(a,0,2,65);let epoch=terminal-session-query(a,0,4);return terminal-session-resize(a,0,120,40)==0 && terminal-session-query(a,0,0)==120 && terminal-session-query(a,0,1)==40 && terminal-session-query(a,0,4)==epoch+1 && terminal-session-read(a,0)==65 && terminal-session-query(b,1,0)==100;',
    'resize-noop': pair + 'return terminal-session-resize(a,0,80,24)==0 && terminal-session-query(a,0,4)==1;',
    'invalid-resize-atomic': pair + 'return terminal-session-resize(a,0,0,24)==-1 && terminal-session-resize(a,0,80,129)==-1 && terminal-session-query(a,0,0)==80 && terminal-session-query(a,0,4)==1;',
    'input-byte-bounds': pair + 'return terminal-session-input(a,0,2,-1)==-1 && terminal-session-input(a,0,2,256)==-1 && terminal-session-query(a,0,2)==0;',
    'output-byte-bounds': pair + 'return terminal-session-write(a,0,-1)==-1 && terminal-session-write(a,0,256)==-1 && terminal-session-query(a,0,3)==0;',
    'bounded-construction': pair + 'let mark=heap-next;return terminal-session-open(0,2,80,24)==-3 && heap-next==mark;',
    'owner-revocation-cleanup': pair + 'cap-revoke(0);return terminal-session-read(a,0)==-2 && terminal-session-write(a,0,65)==-2 && terminal-session-close(a,0)==0 && terminal-session-query(b,1,0)==100;',
    'seat-revocation-cleanup': pair + 'terminal-seat-focus(a,0,2);cap-revoke(2);return terminal-seat-deliver(2,65)==-2 && terminal-session-read(a,0)==-2 && terminal-session-close(a,0)==0 && terminal-session-close(b,1)==0;',
    'changed-owner-target': pair + 'store64(cap-table-base,9001);return terminal-session-read(a,0)==-2 && terminal-session-write(a,0,65)==-2;',
    'changed-seat-target': pair + 'store64(cap-table-base+32,9001);return terminal-session-input(a,0,2,65)==-2;',
    'context-refusal': pair + 'kernel=0;return terminal-session-read(a,0)==-4 && terminal-session-close(a,0)==-4 && terminal-seat-focus(a,0,2)==-4;',
    'bad-ring-header': pair + 'let row=terminal-session-row(a,0);let page=terminal-session-page(row,0);store64(page+16,509);return terminal-session-read(a,0)==-5 && terminal-session-input(a,0,2,65)==-5 && load64(page)==0 && terminal-session-query(a,0,4)==1;',
    'bad-ring-byte': pair + 'terminal-session-input(a,0,2,65);let row=terminal-session-row(a,0);let page=terminal-session-page(row,0);store64(page+32,256);return terminal-session-read(a,0)==-5 && load64(page+8)==0 && terminal-session-query(a,0,4)==2;',
    'epoch-overflow-atomic': pair + 'let row=terminal-session-row(a,0);store64(row+56,0x7FFFFFFFFFFFFFFF);return terminal-session-input(a,0,2,65)==-3 && terminal-session-resize(a,0,120,40)==-3 && terminal-session-query(a,0,2)==0 && terminal-session-query(a,0,0)==80;',
    'generation-overflow': 'terminal-session-generation=0x7FFFFFFFFFFFFF;let mark=heap-next;return terminal-session-open(0,2,80,24)==-3 && heap-next==mark;',
    'cold-memory-bound': 'heap-end=heap-next+128;let mark=heap-next;return terminal-session-open(0,2,80,24)==-3 && heap-next==mark && terminal-session-table==0 && terminal-session-queues==0;',
    'cold-authority': 'cap-revoke(0);let mark=heap-next;return terminal-session-open(0,2,80,24)==-2 && heap-next==mark;',
    'cold-geometry': 'let mark=heap-next;return terminal-session-open(0,2,257,24)==-1 && terminal-session-open(0,2,80,0)==-1 && heap-next==mark;',
    'wrap-backpressure-both-queues': pair + '''let cycle=0;while cycle<3{let i=0;while i<507{if terminal-session-input(a,0,2,i&255)!=0 || terminal-session-write(b,1,(i+17)&255)!=0{return false;}i+=1;}
let epoch=terminal-session-query(a,0,4);if terminal-session-input(a,0,2,99)!=-7 || terminal-session-write(b,1,99)!=-7 || terminal-session-query(a,0,4)!=epoch{return false;}
i=0;while i<507{if terminal-session-read(a,0)!=(i&255) || terminal-session-output(b,1)!=((i+17)&255){return false;}i+=1;}cycle+=1;}return terminal-session-read(a,0)==-7 && terminal-session-output(b,1)==-7;''',
    'reuse-zeroes-retired-bytes': pair + '''terminal-session-input(a,0,2,65);terminal-session-write(a,0,66);let row=terminal-session-row(a,0);let page=terminal-session-page(row,0);terminal-session-close(a,0);let i=32;while i<4096{if load64(page+i)!=0{return false;}i+=8;}let fresh=terminal-session-open(0,2,80,24);return fresh>0 && fresh!=a && terminal-session-read(fresh,0)==-7 && terminal-session-output(fresh,0)==-7 && terminal-session-read(a,0)==-6;''',
    'stable-lifetime-cycles': pair + '''terminal-session-close(a,0);terminal-session-close(b,1);let mark=heap-next;let cycle=0;let old=a;while cycle<22{let fresh=terminal-session-open(0,2,80,24);let peer=terminal-session-open(1,2,100,30);if fresh<=0 || peer<=0 || fresh==old || terminal-session-read(old,0)!=-6{return false;}terminal-seat-focus(fresh,0,2);if terminal-seat-deliver(2,65)!=0 || terminal-session-read(fresh,0)!=65{return false;}if terminal-session-close(fresh,0)!=0 || terminal-session-close(peer,1)!=0 || heap-next!=mark{return false;}old=fresh;cycle+=1;}return true;''',
}
checks = []
cases.update({
    'sequence-eight-bytes':pair+'''terminal-seat-focus(a,0,2);let epoch=terminal-session-query(a,0,4);if terminal-seat-deliver-sequence(2,-1,8)!=0 || terminal-session-query(a,0,2)!=8 || terminal-session-query(a,0,4)!=epoch+1{return false;}let i=0;while i<8{if terminal-session-read(a,0)!=255{return false;}i+=1;}return terminal-session-read(a,0)==-7 && terminal-session-read(b,1)==-7;''',
    'sequence-invalid-atomic':pair+'''terminal-seat-focus(a,0,2);return terminal-seat-deliver-sequence(2,256,1)==-1 && terminal-seat-deliver-sequence(2,-1,7)==-1 && terminal-seat-deliver-sequence(2,0,0)==-1 && terminal-seat-deliver-sequence(2,0,9)==-1 && terminal-session-query(a,0,2)==0 && terminal-session-query(a,0,4)==1;''',
    'sequence-authority':pair+'''terminal-seat-focus(a,0,2);let alias=cap-mint(2001,64);if terminal-seat-deliver-sequence(alias,65,1)!=-2 || terminal-session-input-sequence(a,1,2,65,1)!=-2{return false;}cap-revoke(2);return terminal-seat-deliver-sequence(2,65,1)==-2 && load64(terminal-session-page(terminal-session-row(a,0),0))==0;''',
    'sequence-backpressure-wrap':pair+'''terminal-seat-focus(a,0,2);let cycle=0;while cycle<3{let i=0;while i<505{if terminal-seat-deliver(2,65)!=0{return false;}i+=1;}let row=terminal-session-row(a,0);let page=terminal-session-page(row,0);let head=load64(page);let epoch=terminal-session-query(a,0,4);let cell=load64(page+32+head*8);if terminal-seat-deliver-sequence(2,0x435b1b,3)!=-7 || load64(page)!=head || load64(page+32+head*8)!=cell || terminal-session-query(a,0,4)!=epoch{return false;}if terminal-session-read(a,0)!=65 || terminal-seat-deliver-sequence(2,0x435b1b,3)!=0{return false;}i=0;while i<504{if terminal-session-read(a,0)!=65{return false;}i+=1;}if terminal-session-read(a,0)!=27 || terminal-session-read(a,0)!=91 || terminal-session-read(a,0)!=67 || terminal-session-read(a,0)!=-7{return false;}cycle+=1;}return true;''',
    'sequence-stale-focus':pair+'''terminal-seat-focus(a,0,2);terminal-session-close(a,0);let fresh=terminal-session-open(0,2,80,24);return terminal-seat-deliver-sequence(2,65,1)==-6 && terminal-session-query(fresh,0,2)==0;''',
    'sequence-epoch-overflow':pair+'''let row=terminal-session-row(a,0);store64(row+56,0x7fffffffffffffff);return terminal-session-input-sequence(a,0,2,65,1)==-3 && terminal-session-query(a,0,2)==0;''',
    'linux-key-ascii':pair+'''terminal-seat-focus(a,0,2);let i=0;while i<128{if linux-terminal-deliver-key(2,i)!=0 || terminal-session-read(a,0)!=i{return false;}i+=1;}return linux-terminal-deliver-key(2,-1)==-1 && linux-terminal-deliver-key(2,137)==-1 && linux-terminal-deliver-key(2,255)==-1 && terminal-session-query(a,0,2)==0;''',
})
for key,sequence in {128:b'\x1b[A',129:b'\x1b[D',130:b'\x1b[C',131:b'\x1b[B',132:b'\x1b[H',133:b'\x1b[F',134:b'\x1b[3~',135:b'\x1b[5~',136:b'\x1b[6~'}.items():
    body=pair+f'terminal-seat-focus(a,0,2);if linux-terminal-deliver-key(2,{key})!=0{{return false;}}'
    for byte in sequence: body+=f'if terminal-session-read(a,0)!={byte}{{return false;}}'
    cases['linux-key-'+str(key)]=body+'return terminal-session-read(a,0)==-7 && terminal-session-read(b,1)==-7;'
for name, body in cases.items():
    source = harness + native + '\nfn check()->Bool{' + body + '''}
fn main()->Int{cap-mint(1001,4);cap-mint(1002,4);cap-mint(2001,64);cap-mint(1003,4);if check(){return 42;}return 99;}
'''
    path = a.out / (name + '.in')
    path.write_text(source)
    for profile in ('default', 'lean', 'harden'):
        command = [str(a.compiler.resolve()), 'compile', '--path', str(path),
            '--target', 'jit', '--profile', profile, '--out', str(a.out / 'proof'), '--json']
        result = subprocess.run(command, capture_output=True, text=True, timeout=90)
        (a.out / (name + '-' + profile + '.json')).write_text(result.stdout + result.stderr)
        r = json.loads(result.stdout)
        assert result.returncode == 0 and r.get('success') and r.get('eval_result') == {'Int': 42}, (name, profile, r)
        checks.append({'name': name, 'profile': profile, 'status': 'passed'})
assert all((ROOT / name).read_bytes() == data for name, data in sources.items())
(a.out / 'report.json').write_text(json.dumps({'status': 'passed',
    'classification': 'Actual provider and page/cap functions with modeled memory/context; no guest/application credit',
    'compiler_sha256': hashlib.sha256(a.compiler.read_bytes()).hexdigest(),
    'source_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in sources.items()},
    'checks': checks}, indent=2) + '\n')
print(f'PASS {len(checks)} native terminal/session/seat model controls')
