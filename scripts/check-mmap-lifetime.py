#!/usr/bin/env python3
"""Exercise actual personality mapping/Windows branches with isolated numeric memory.

This proves allocator lifetime, not hardware VM protection or process isolation.
Requires an existing compiler; never builds or executes a hardware memory address.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--in', dest='compiler', required=True)
parser.add_argument('--output-dir', type=Path)
args = parser.parse_args()
repository = Path(__file__).resolve().parent.parent
root = args.output_dir or Path(tempfile.mkdtemp(prefix='space-mmap-'))
root.mkdir(parents=True, exist_ok=True)
binary = Path(args.compiler).resolve()
(root / 'compiler.json').write_text(json.dumps({'binary': str(binary), 'version': subprocess.check_output([binary, '--version'], text=True).strip(), 'sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}, indent=2))
posix = (repository / 'components/posix.in').read_text()
memory = (repository / 'components/memory.in').read_text()
windows = (repository / 'components/windows.in').read_text()
def function(text, name):
    start = text.index('fn ' + name + '(')
    end = text.find('\nfn ', start + 3)
    return text[start:] if end < 0 else text[start:end]

source = '\n'.join(line for line in posix.splitlines() if line.startswith('const LINUX-'))
source += '\n' + posix[posix.index('const POSIX-MMAP-SLOTS'):posix.index('fn posix-sys-mmap(')]
source += '\nvar heap-next:Int=4112;var heap-end:Int=1048576;var free-list:Int=0;var volume-ready:Int=0;var vfs-fd-table:Int=0;\n'
source += 'var memory:[Int]=[' + ','.join(['0'] * 4096) + '];\n'
source += '''fn store8(p:Int,v:Int)->Void{if p<32768{memory[p/8]=v;}return;}
fn store64(p:Int,v:Int)->Void{if p<32768{memory[p/8]=v;}return;}
fn load64(p:Int)->Int{if p<32768{return memory[p/8];}return 0;}
fn panic(message:String)->Void{throw 99;}
// This allocator-only fixture has no valid file descriptors or stream endpoints.
fn vfs-stream-valid(fd:Int)->Int{return 0;}
fn posix-fd-valid(fd:Int)->Int{return 0;}
fn vfs-sparkfs-file-size(p:Int)->Int{return 0;}
fn volume-rpc-pread(p:Int,b:Int,n:Int,o:Int)->Int{return 0;}
fn sparkfs-pread(p:Int,b:Int,n:Int,o:Int)->Int{return 0;}
'''
source += '\n'.join(function(memory, name) for name in ['alloc', 'frame-free', 'frame-alloc'])
source += '\n' + function(posix, 'posix-sys-mmap') + '\n' + function(posix, 'posix-sys-munmap')
cases = {
    'adjacent-frame': '''let mapped=posix-sys-mmap(0,4096,3,0,-1,0);let adjacent=alloc(16);store64(adjacent,12345);if mapped!=8192 || adjacent!=12288{return 1;}if posix-sys-munmap(mapped,4096)!=0{return 2;}if frame-alloc()!=mapped || load64(adjacent)!=12345{return 3;}return 42;''',
    'cross-mapping-zero': '''store64(8192,12345);let first=posix-sys-mmap(123,4096,3,2,-1,0);let second=posix-sys-mmap(0,4096,0,0,-1,0);if first!=8192 || second!=12288 || load64(first)!=0{return 1;}if posix-sys-munmap(first,8192)!=0{return 2;}if frame-alloc()!=second || frame-alloc()!=first{return 3;}return 42;''',
    'partial-and-double': '''let mapped=posix-sys-mmap(0,12288,3,34,-1,0);if posix-sys-munmap(mapped+4096,1)!=0{return 1;}if posix-sys-munmap(mapped,12288)!=-22{return 2;}if posix-sys-munmap(mapped+4096,4096)!=-22{return 3;}if posix-sys-munmap(mapped,4096)!=0 || posix-sys-munmap(mapped+8192,4096)!=0{return 4;}if frame-alloc()!=mapped+8192 || frame-alloc()!=mapped || frame-alloc()!=mapped+4096{return 5;}return 42;''',
    'invalid-atomic': '''let before=heap-next;if posix-sys-mmap(0,0,3,0,-1,0)!=-22{return 1;}if posix-sys-mmap(0,9223372036854775807,3,0,-1,0)!=-12{return 2;}if posix-sys-mmap(0,4096,3,16,-1,0)!=-22{return 3;}if posix-sys-mmap(0,4096,1,0,-1,0)!=-22{return 4;}if posix-sys-mmap(0,4096,3,0,-1,4096)!=-22{return 5;}if posix-sys-mmap(0,4096,3,0,3,0)!=-9{return 6;}if posix-sys-munmap(4096,4096)!=-22 || posix-sys-munmap(8193,4096)!=-22{return 7;}if heap-next!=before || free-list!=0 || posix-map-starts[0]!=0{return 8;}return 42;''',
    'ledger-capacity': '''let first=posix-sys-mmap(0,12288,3,0,-1,0);let i=1;while i<64{if posix-sys-mmap(0,1,3,0,-1,0)<0{return 1;}i+=1;}let before=heap-next;if posix-sys-mmap(0,1,3,0,-1,0)!=-12 || heap-next!=before{return 2;}if posix-sys-munmap(first+4096,4096)!=-12 || free-list!=0 || posix-map-ends[0]!=first+12288{return 3;}if posix-sys-munmap(first,12288)!=0{return 4;}if posix-sys-mmap(0,1,3,0,-1,0)<0{return 5;}return 42;''',
}
# Reuse the exact Windows dispatcher branches, with actual LastError translators.
win = '\n'.join(line for line in windows.splitlines() if line.startswith('const WIN-'))
win += '\nvar win-last-error:Int=0;var win-last-status:Int=0;\n'
win += '\n'.join(function(windows, name) for name in ['win-status-from-error', 'win-set-error', 'win-clear-error'])
a = windows.index('  if num == WIN-CALL-VIRTUALALLOC {')
b = windows.index('  if num == WIN-CALL-CREATEPROCESSA {', a)
win += '\nfn win-memory(num:Int,a0:Int,a1:Int)->Int{\n' + windows[a:b] + '\nreturn -99;}\n'
cases['windows-errors'] = '''heap-end=4096;if win-memory(WIN-CALL-VIRTUALALLOC,0,4096)!=0 || win-last-error!=8{return 1;}heap-end=1048576;let p=win-memory(WIN-CALL-VIRTUALALLOC,0,4096);if p!=8192 || win-last-error!=0{return 2;}if win-memory(WIN-CALL-VIRTUALFREE,p,-1)!=0 || win-last-error!=87{return 6;}if win-memory(WIN-CALL-VIRTUALFREE,p+1,4096)!=0 || win-last-error!=87{return 3;}if win-memory(WIN-CALL-VIRTUALFREE,p,4096)!=1 || win-last-error!=0{return 4;}if win-memory(WIN-CALL-VIRTUALFREE,p,4096)!=0 || win-last-error!=87{return 5;}return 42;'''
rows = []
for name, body in cases.items():
    path = root / (name + '.in')
    path.write_text(source + ('\n' + win if name == 'windows-errors' else '') + '\nfn main()->Int{' + body + '}\n')
    for profile in ['default', 'lean', 'harden']:
        result = subprocess.run([binary, 'compile', '--path', path, '--target', 'jit', '--profile', profile, '--out', root / (name + '-' + profile + '.out'), '--json'], capture_output=True, text=True, timeout=45)
        (root / (name + '-' + profile + '.json')).write_text(result.stdout)
        (root / (name + '-' + profile + '.stderr')).write_text(result.stderr)
        report = json.loads(result.stdout)
        assert result.returncode == 0 and report['success'] and not report.get('degradations') and report['eval_result'] == {'Int': 42}, (name, profile, report)
        rows.append({'case': name, 'profile': profile, 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'result': report['eval_result']})
(root / 'summary.json').write_text(json.dumps(rows, indent=2))
print(f'{len(rows)} mapping lifetime checks passed; evidence {root}')
