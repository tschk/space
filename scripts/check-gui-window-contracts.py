#!/usr/bin/env python3
"""Execute actual client configure/focus/seat parsers with malformed events."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
source = (root / 'protocol/display.in').read_text() + (root / 'protocol/gui-canvas.in').read_text()
source += re.sub(r'(?m)^import .*?$', '', (root / 'protocol/gui-window.in').read_text())
widget = (root / 'components/gui-window-widget.in').read_text()
for name in ('window-info-valid', 'window-configure', 'window-event', 'window-fill'):
    start = widget.index('fn ' + name + '(')
    source += widget[start:widget.index('\n}', start) + 2] + '\n'
source += '''
var window-width=0;var window-height=0;var window-scale=0;
var window-generation=0;var window-focused=0;var window-ack=0;
var object=0;var opcode=0;var arg0=0;var arg1=0;
var consumed=0;
var descriptor:[Int]=[20,0,0x80000000,0x200000,0x70000000,1,800,600,0,0x70001000,1179648,0];
var writes=0;var minimum=0;var maximum=0;var escaped=0;
fn store32(address:Int,color:Int)->void{
 if address<0x70001000 || address>0x70001000+SCI-CANVAS-BYTES - 4 || (address & 3)!=0{escaped=1;}
 if minimum==0 || address<minimum{minimum=address;}
 if address>maximum{maximum=address;}
 writes+=1;
}
fn chan-page-recv-frame(page:Int,destination:Int)->Int{consumed+=1;return 1;}
fn load64(address:Int)->Int{
 if address>=16 && address<112{return descriptor[(address - 16)/8];}
 if address==0x80000100{return object;}
 if address==0x80000108{return opcode;}
 if address==0x80000110{return arg0;}
 if address==0x80000118{return arg1;}
 return 0;
}
fn main()->Int{
 if window-info-valid(16)!=1{return 21;}
 descriptor[0]=52;if window-info-valid(16)!=1{return 22;}
 descriptor[3]=0x100000;if window-info-valid(16)!=0{return 23;}descriptor[3]=0x200000;
 descriptor[10]=4096;if window-info-valid(16)!=0{return 24;}descriptor[10]=1179648;
 descriptor[9]=0x70002000;if window-info-valid(16)!=0{return 25;}descriptor[9]=0x70001000;
 descriptor[0]=21;if window-info-valid(16)!=0{return 26;}descriptor[0]=52;
 descriptor[1]=1;if window-info-valid(16)!=0{return 27;}descriptor[1]=0;
 if window-configure(1,512,256,2)!=1{return 1;}
 if window-configure(1,512,256,2)!=0 || window-configure(0,512,256,2)!=0 || window-configure(2,769,384,3)!=0 || window-configure(2,474,384,4)!=0{return 2;}
 if window-generation!=1 || window-width!=512 || window-height!=256 || window-scale!=2{return 3;}
 object=SPDP-OBJ-SURFACE;opcode=SPDP-SURFACE-CONFIGURE-V1;arg0=2;
 arg1=gui-window-config-word(474,384,3)+1;
 if window-event()!=-1 || window-generation!=1 || window-ack!=0{return 4;}
 arg1=gui-window-config-word(474,384,3);arg0=1;
 if window-event()!=-1 || window-generation!=1 || window-width!=512{return 5;}
 arg0=2;
 if window-event()!=-2 || window-generation!=2 || window-width!=474 || window-height!=384 || window-scale!=3 || window-ack!=1{return 6;}
 object=SPDP-OBJ-SEAT;opcode=SPDP-SEAT-FOCUS-V1;arg0=1;arg1=1;
 if window-event()!=-1 || window-focused!=0{return 7;}
 arg0=2;arg1=2;if window-event()!=-1 || window-focused!=0{return 8;}
 arg1=1;if window-event()!=-3 || window-focused!=1{return 9;}
 arg1=0;if window-event()!=-3 || window-focused!=0{return 10;}
 opcode=SPDP-SEAT-KEYBOARD-KEY;arg0=0;arg1=spdp-seat-key(27,1);
 if window-event()!=27{return 11;}
 arg1=spdp-seat-key(97,2);if window-event()!=-1{return 12;}
 opcode=SPDP-SEAT-POINTER-BUTTON;arg1=spdp-seat-key(1,1);if window-event()!=0{return 13;}
 arg1=spdp-seat-key(2,1);if window-event()!=-1{return 14;}
 object=SPDP-OBJ-DISPLAY;if window-event()!=-1{return 15;}
 if window-generation!=2 || window-width!=474 || window-height!=384 || window-scale!=3 || window-focused!=0{return 16;}
 if window-configure(3,768,384,3)!=1{return 17;}
 window-fill(0,0,768,384,1);
 if writes!=294912 || escaped!=0 || minimum!=0x70001000 || maximum!=0x70001000+SCI-CANVAS-BYTES - 4{return 18;}
 writes=0;
 window-fill(-1,0,1,1,1);window-fill(0,-1,1,1,1);window-fill(0,0,769,1,1);window-fill(0,0,1,385,1);
 window-fill(0,0,0x7fffffffffffffff,1,1);window-fill(768,384,1,1,1);
 if writes!=0 || escaped!=0{return 19;}
 window-fill(767,383,1,1,1);if writes!=1 || escaped!=0 || maximum!=0x70001000+SCI-CANVAS-BYTES - 4{return 20;}
 return 42;
}
'''
with tempfile.TemporaryDirectory(prefix='space-window-contracts-') as directory:
    path = Path(directory) / 'client.in'
    path.write_text(source)
    for profile in ('default', 'lean', 'harden'):
        result = subprocess.run([a.compiler, 'compile', '--path', str(path), '--target', 'jit',
                                 '--profile', profile, '--out', str(Path(directory) / profile), '--json'],
                                capture_output=True, text=True, check=True, timeout=30)
        report = json.loads(result.stdout)
        assert report.get('success') and report.get('eval_result') == {'Int': 42}, report
        print(f'PASS {profile}: actual stale/malformed window event refusal, state preservation, seat frames and complete canvas raster bounds/overflow')
