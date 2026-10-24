#!/usr/bin/env python3
"""Execute actual protected client descriptor/startup/allocator parsers in a source model."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
out = a.out.resolve()
if out.exists() and any(out.iterdir()): p.error('--out must be new or empty')
out.mkdir(parents=True, exist_ok=True)
paths = ['protocol/display.in', 'protocol/native-protected.in', 'protocol/gui-canvas.in',
         'protocol/gui-window.in', 'components/gui-protected-widget.in', 'components/gui-window-state.in']
report = {'status': 'running', 'scope': 'source-extraction client contract model, not CPL3 execution',
          'compiler': str(a.compiler.resolve()), 'compiler_sha256': hashlib.sha256(a.compiler.read_bytes()).hexdigest(),
          'inputs': {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in paths}, 'profiles': []}
source = ''.join(re.sub(r'(?m)^(?:package|import) .*$', '', (ROOT / n).read_text())
                 for n in paths[:4])
actual = ''.join((ROOT / n).read_text() for n in paths[4:])
for name in ('alloc', 'protected-window-info-valid', 'protected-window-start', 'window-configure', 'window-event-at'):
    start = actual.index('fn ' + name + '(')
    source += actual[start:actual.index('\n}', start) + 2] + '\n'
source += '''
var protected-widget-next=0;
var window-width=0;var window-height=0;var window-scale=0;
var window-generation=0;var window-focused=0;var window-ack=0;
var descriptor:[Int]=[20,0,NATIVE-PROTECTED-HEAP,NATIVE-PROTECTED-HEAP-BYTES,0x70000000,1,80,25,NATIVE-PROTECTED-INFO+256,0x70001000,1179648,0];
var config:[Int]=[GUI-WINDOW-CONFIG-MAGIC,1,512,256,2,1];
var object=0;var opcode=0;var arg0=0;var arg1=0;
var reads=0;var font-count=0;var font-address=0;var sent=0;var received=0;var writes=0;var escaped=0;
fn load64(address:Int)->Int{
 reads+=1;
 if address>=NATIVE-PROTECTED-INFO && address<NATIVE-PROTECTED-INFO+96{return descriptor[(address - NATIVE-PROTECTED-INFO)/8];}
 if address>=NATIVE-PROTECTED-INFO+256 && address<NATIVE-PROTECTED-INFO+304{return config[(address - NATIVE-PROTECTED-INFO - 256)/8];}
 if address==NATIVE-PROTECTED-HEAP+256{return object;}
 if address==NATIVE-PROTECTED-HEAP+264{return opcode;}
 if address==NATIVE-PROTECTED-HEAP+272{return arg0;}
 if address==NATIVE-PROTECTED-HEAP+280{return arg1;}
 if address==0x70000000 || address==0x70000008{return 0;}
 escaped=1;return 0;
}
fn store8(address:Int,value:Int)->void{
 if address<NATIVE-PROTECTED-HEAP || address>=NATIVE-PROTECTED-HEAP+256 || value!=0{escaped=1;}
 writes+=1;
}
fn fb-font-init()->void{font-count+=1;font-address=alloc(32);}
fn chan-page-send-frame(page:Int,object:Int,opcode:Int,arg0:Int,arg1:Int)->Int{
 if page!=0x70000000 || object!=SPDP-OBJ-COMPOSITOR || opcode!=SPDP-COMPOSITOR-CREATE-SURFACE || arg0!=0 || arg1!=0{escaped=1;return 0;}
 sent+=1;return 1;
}
fn chan-page-recv-frame(page:Int,destination:Int)->Int{
 if page!=0x70000000 || destination!=NATIVE-PROTECTED-HEAP+256{escaped=1;return 0;}
 received+=1;return 1;
}
fn main()->Int{
 if protected-window-info-valid(0)!=0 || reads!=0{return 1;}
 if protected-window-info-valid(0x80000000)!=0 || reads!=0{return 2;}
 if protected-window-info-valid(NATIVE-PROTECTED-INFO)!=1{return 3;}
 descriptor[0]=52;if protected-window-info-valid(NATIVE-PROTECTED-INFO)!=1{return 4;}
 descriptor[0]=21;if protected-window-info-valid(NATIVE-PROTECTED-INFO)!=0{return 5;}descriptor[0]=20;
 descriptor[1]=1;if protected-window-info-valid(NATIVE-PROTECTED-INFO)!=0{return 6;}descriptor[1]=0;
 descriptor[2]=0x80000000;if protected-window-info-valid(NATIVE-PROTECTED-INFO)!=0{return 7;}descriptor[2]=NATIVE-PROTECTED-HEAP;
 descriptor[3]=0x100000;if protected-window-info-valid(NATIVE-PROTECTED-INFO)!=0{return 8;}descriptor[3]=NATIVE-PROTECTED-HEAP-BYTES;
 descriptor[8]=0x100000;if protected-window-info-valid(NATIVE-PROTECTED-INFO)!=0{return 9;}descriptor[8]=NATIVE-PROTECTED-INFO+256;
 descriptor[9]=0x70002000;if protected-window-info-valid(NATIVE-PROTECTED-INFO)!=0{return 10;}descriptor[9]=0x70001000;
 descriptor[10]=4096;if protected-window-info-valid(NATIVE-PROTECTED-INFO)!=0{return 11;}descriptor[10]=1179648;
 descriptor[11]=1;if protected-window-info-valid(NATIVE-PROTECTED-INFO)!=0{return 12;}descriptor[11]=0;
 if alloc(16)!=0 || protected-widget-next!=0{return 13;}
 protected-widget-next=NATIVE-PROTECTED-HEAP+4096;
 if alloc(-1)!=0 || alloc(0x7fffffffffffffff)!=0 || protected-widget-next!=NATIVE-PROTECTED-HEAP+4096{return 14;}
 if alloc(17)!=NATIVE-PROTECTED-HEAP+4096 || protected-widget-next!=NATIVE-PROTECTED-HEAP+4128{return 15;}
 protected-widget-next=NATIVE-PROTECTED-HEAP+NATIVE-PROTECTED-HEAP-BYTES;
 if alloc(16)!=0{return 16;}
 protected-widget-next=0;
 config[0]=0;if protected-window-start(NATIVE-PROTECTED-INFO)!=0 || window-generation!=0 || font-count!=0 || sent!=0{return 17;}config[0]=GUI-WINDOW-CONFIG-MAGIC;
 config[5]=2;if protected-window-start(NATIVE-PROTECTED-INFO)!=0 || window-generation!=0 || font-count!=0 || sent!=0{return 18;}config[5]=1;
 config[2]=769;if protected-window-start(NATIVE-PROTECTED-INFO)!=0 || window-generation!=0 || font-count!=0 || sent!=0{return 19;}config[2]=512;
 if protected-window-start(NATIVE-PROTECTED-INFO)!=1 || window-generation!=1 || window-width!=512 || window-height!=256 || window-scale!=2 || window-focused!=1{return 20;}
 if font-count!=1 || font-address!=NATIVE-PROTECTED-HEAP+4096 || protected-widget-next!=NATIVE-PROTECTED-HEAP+4128 || writes!=256 || sent!=1 || escaped!=0{return 21;}
 if protected-window-start(NATIVE-PROTECTED-INFO)!=0 || font-count!=1 || writes!=256 || sent!=1{return 22;}
 descriptor[8]=0;if protected-window-info-valid(NATIVE-PROTECTED-INFO)!=1{return 23;}
 config[0]=0;config[1]=999;config[2]=768;config[3]=384;config[4]=3;config[5]=0;
 object=SPDP-OBJ-SEAT;opcode=SPDP-SEAT-KEYBOARD-KEY;arg0=0;arg1=spdp-seat-key(97,1);
 if window-event-at(NATIVE-PROTECTED-HEAP)!=97 || received!=1 || window-generation!=1 || window-width!=512 || window-focused!=1{return 24;}
 object=SPDP-OBJ-SURFACE;opcode=SPDP-SURFACE-CONFIGURE-V1;arg0=2;arg1=gui-window-config-word(474,384,3);
 if window-event-at(NATIVE-PROTECTED-HEAP)!=-2 || window-generation!=2 || window-width!=474 || window-height!=384 || window-scale!=3 || window-ack!=1{return 25;}
 if escaped!=0 || font-count!=1 || writes!=256 || sent!=1{return 26;}
 return 42;
}
'''
path = out / 'model.in'
path.write_text(source)
for profile in ('default', 'lean', 'harden'):
    result = subprocess.run([str(a.compiler.resolve()), 'compile', '--path', str(path), '--target', 'jit',
                             '--profile', profile, '--out', str(out / profile), '--json'],
                            capture_output=True, text=True, timeout=30)
    (out / (profile + '.json')).write_text(result.stdout)
    (out / (profile + '.stderr')).write_text(result.stderr)
    data = json.loads(result.stdout)
    assert result.returncode == 0 and data.get('success') and data.get('eval_result') == {'Int': 42}, data
    report['profiles'].append(profile)
report['status'] = 'pass'
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS default/lean/harden: actual protected descriptor/startup/allocator/config/event functions, no borrowed supervisor pointer; source model only')
