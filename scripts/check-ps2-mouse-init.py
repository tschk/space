#!/usr/bin/env python3
"""Execute both actual PS/2 init functions against scripted device replies."""
import argparse
import json
from pathlib import Path
import subprocess
p = argparse.ArgumentParser()
p.add_argument('--in', dest='compiler', required=True)
p.add_argument('--out', type=Path, default=Path('/tmp/space-ps2-mouse-init'))
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
root = Path(__file__).resolve().parents[1]
cases = [('ready', [0,250,170,0,250,250], 6, True),
         ('reset-nack', [0,254], 2, False),
         ('bat-failed', [0,250,252,0], 4, False),
         ('wrong-id', [0,250,170,3], 4, False),
         ('defaults-nack', [0,250,170,0,254], 5, False),
         ('enable-nack', [0,250,170,0,250,254], 6, False)]
results=[]
for filename in ('mouse.in', 'input.in'):
    text=(root/'components'/filename).read_text()
    start=text.index('fn mouse-init() -> Int {')
    end=text.index('\n}',start)+2
    actual=text[start:end]
    for name,replies,read_count,success in cases:
        source=f'''var replies:[Int]=[{','.join(map(str,replies))}];
var read-count:Int=0;
var keyboard-enabled:Int=1;
var mouse-ready:Int=1;
var mouse-x:Int=0;var mouse-y:Int=0;var mouse-buttons:Int=0;var mouse-cycle:Int=0;
var fb-width:Int=1920;var fb-height:Int=1080;
var mouse-screen-w:Int=1920;var mouse-screen-h:Int=1080;
const PS2-STATUS=100;const PS2-DATA=96;
fn ps2-cmd(cmd:Int)->Void{{if cmd==0xAD{{keyboard-enabled=0;}}if cmd==0xAE{{keyboard-enabled=1;}}return;}}
fn mouse-cmd(cmd:Int)->Void{{return;}}
fn mouse-wait-input()->Void{{return;}}
fn inb(port:Int)->Int{{return 0;}}
fn outb(port:Int,value:Int)->Void{{return;}}
fn ps2-read()->Int{{let value=replies[read-count];read-count=read-count+1;return value;}}
{actual}
fn main()->Int{{let result=mouse-init();
if read-count!={read_count} || keyboard-enabled!=1{{return 1;}}
if result!={0 if success else -1} || mouse-ready!={1 if success else 0}{{return 2;}}
if {str(success).lower()} && (mouse-x!=960 || mouse-y!=540){{return 3;}}
return 42;}}
'''
        # The module lexer expects separate top-level declarations per line.
        source=source.replace(';var ',';\nvar ').replace(';const ',';\nconst ')
        path=a.out/(filename+'-'+name+'.in');path.write_text(source)
        for profile in ('default','lean','harden'):
            run=subprocess.run([a.compiler,'compile','--path',str(path),'--target','jit','--entry','main','--out',str(a.out/'artifact'),'--profile',profile,'--json'],capture_output=True,text=True)
            (a.out/(filename+'-'+name+'-'+profile+'.json')).write_text(run.stdout)
            report=json.loads(run.stdout)
            if not report.get('success') or report.get('eval_result')!={'Int':42}:
                raise SystemExit(f'FAIL {filename}/{name}/{profile}: {run.stdout}\n{run.stderr}')
            results.append({'source':filename,'case':name,'profile':profile,'pass':True})
(a.out/'summary.json').write_text(json.dumps(results,indent=2))
print(f'PASS {len(results)} actual PS/2 initialization checks')
