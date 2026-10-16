#!/usr/bin/env python3
"""Execute actual loader-page SPDP frame helpers; no compiler build or hardware."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--in', dest='compiler', required=True)
args = parser.parse_args()
text = (Path(__file__).resolve().parent.parent / 'components/channel.in').read_text()
functions = []
for name in ('chan-page-frame-header-valid', 'chan-page-frame-valid', 'chan-page-send-frame', 'chan-page-recv-frame'):
    start = text.index('fn ' + name + '(')
    functions.append(text[start:text.index('\n}', start) + 2])
display = (Path(__file__).resolve().parent.parent / 'components/display.in').read_text()
start = display.index('fn dsp-drain-page(')
functions.append(display[start:display.index('\n}', start) + 2])
source = 'var memory:[Int]=[' + ','.join(['0'] * 2048) + '];\n' + '''
var dsp-msg:Int=1200;
var dispatches:Int=0;
fn dsp-handle-msg(object:Int,opcode:Int,arg0:Int,arg1:Int,port:Int)->Void{dispatches+=1;}
fn load64(p:Int)->Int{return memory[p];}
fn store64(p:Int,v:Int)->Void{memory[p]=v;}
''' + '\n'.join(functions) + '''
fn main()->Int{
 let page=8;let message=1200;
 store64(page+16,12);store64(page+24,8);
 if chan-page-send-frame(page,1,2,3,4)!=1{return 1;}
 if load64(page+8)!=4 || load64(page)!=0{return 2;}
 if chan-page-send-frame(page,5,6,7,8)!=1{return 3;}
 if chan-page-send-frame(page,9,10,11,12)!=0 || load64(page+8)!=8{return 4;}
 if chan-page-recv-frame(page,message)!=1{return 5;}
 if load64(message)!=1 || load64(message+24)!=4 || load64(page)!=4{return 6;}
 if chan-page-send-frame(page,9,10,11,12)!=1 || load64(page+8)!=0{return 7;}
 if chan-page-recv-frame(page,message)!=1 || load64(message)!=5{return 8;}
 if chan-page-recv-frame(page,message)!=1 || load64(message)!=9 || load64(message+24)!=12{return 9;}
 if chan-page-recv-frame(page,message)!=0{return 10;}
 store64(message,42);
 // A partial frame must neither advance head nor overwrite destination.
 store64(page+8,2);
 if chan-page-recv-frame(page,message)!=-1 || load64(page)!=0 || load64(message)!=42{return 11;}
 if chan-page-send-frame(page,1,2,3,4)!=-1 || load64(page+8)!=2{return 12;}
 store64(page+8,0);
 store64(page+16,512);if chan-page-frame-valid(page)!=0{return 13;}
 store64(page+16,9);if chan-page-frame-valid(page)!=0{return 14;}
 store64(page+16,4);if chan-page-frame-valid(page)!=0{return 15;}
 store64(page+16,508);store64(page+24,4);if chan-page-frame-valid(page)!=0{return 16;}
 store64(page+24,8);store64(page,-4);if chan-page-frame-valid(page)!=0{return 17;}
 store64(page,508);if chan-page-frame-valid(page)!=0{return 18;}
 store64(page,0);store64(page+8,508);if chan-page-frame-valid(page)!=0{return 19;}
 if chan-page-recv-frame(0,message)!=-1 || chan-page-recv-frame(page,0)!=-1{return 20;}
 store64(page,0);store64(page+8,2);store64(message,42);
 if dsp-drain-page(page,0)!=-1 || dispatches!=0 || load64(message)!=42 || load64(page)!=0{return 21;}
 store64(page+8,4);
 if dsp-drain-page(page,0)!=1 || dispatches!=1 || load64(page)!=4{return 22;}
 return 42;
}
'''
with tempfile.TemporaryDirectory(prefix='space-spdp-frames-') as directory:
    path = Path(directory) / 'frames.in'
    path.write_text(source)
    for profile in ('default', 'lean', 'harden'):
        result = subprocess.run([args.compiler, 'compile', '--path', str(path), '--target', 'jit', '--profile', profile, '--out', str(Path(directory) / 'out'), '--json'], capture_output=True, text=True, check=True, timeout=30)
        report = json.loads(result.stdout)
        assert report.get('success') and report.get('eval_result') == {'Int': 42}, report
        print(f'PASS {profile}: complete SPDP frames, wrap/full/empty and malformed/partial refusal')
