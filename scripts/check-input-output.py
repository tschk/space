#!/usr/bin/env python3
"""Execute actual retained input poll output-size validation and pointer clamp."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
text = (root / 'components/input.in').read_text()
start = text.index('fn input-poll-entry(')
poll = text[start:text.index('\n}', start) + 2]
source = (root / 'protocol/input.in').read_text().replace('package space.protocol.input', '', 1)
source += '''
var memory:[Int]=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0];
var input-initialized=0;var initialized=0;var polls=0;
var mouse-screen-w=800;var mouse-screen-h=600;
var mouse-x=799;var mouse-y=599;var mouse-buttons=0;var input-previous-buttons=0;
fn load64(p:Int)->Int{return memory[p];}
fn store64(p:Int,v:Int)->void{memory[p]=v;}
fn input-initialize(info:Int)->Int{initialized+=1;input-initialized=1;return 0;}
fn usb-kbd-ready()->Int{return 0;}
fn usb-kbd-getchar()->Int{return -1;}
fn ps2-kbd-getchar()->Int{return -1;}
fn mouse-poll()->Int{polls+=1;return 0;}
fn input-chan-send(page:Int,event:Int)->Int{return 0;}
''' + poll + '''
fn main()->Int{
 let info=8;
 if input-output-argument(0,1080)!=0 || input-output-argument(65536,1080)!=0 || input-output-argument(1920,-1)!=0{return 1;}
 let output=input-output-argument(1920,1080);
 store64(info+64,output+1);
 if input-poll-entry(info)!=-1 || initialized!=0 || polls!=0 || mouse-screen-w!=800{return 2;}
 store64(info+64,INPUT-OUTPUT-MAGIC | (1080<<16) | 1);
 if input-poll-entry(info)!=-1 || initialized!=0 || polls!=0{return 3;}
 store64(info+64,output);
 if input-poll-entry(info)!=0 || initialized!=1 || polls!=1 || mouse-screen-w!=1920 || mouse-screen-h!=1080 || mouse-x!=799{return 4;}
 mouse-x=1900;mouse-y=1000;
 store64(info+64,input-output-argument(1024,768));
 if input-poll-entry(info)!=0 || initialized!=1 || polls!=2 || mouse-screen-w!=1024 || mouse-screen-h!=768 || mouse-x!=1023 || mouse-y!=767{return 5;}
 store64(info+64,0);
 if input-poll-entry(info)!=0 || mouse-screen-w!=1024 || mouse-screen-h!=768 || polls!=3{return 6;}
 store64(info+64,output | (1<<63));
 if input-poll-entry(info)!=-1 || polls!=3 || mouse-screen-w!=1024 || mouse-x!=1023{return 7;}
 input-initialized=0;mouse-screen-w=800;mouse-screen-h=600;store64(info+64,0);
 if input-poll-entry(info)!=0 || initialized!=2 || mouse-screen-w!=800 || mouse-screen-h!=600{return 8;}
 return 42;
}
'''
with tempfile.TemporaryDirectory(prefix='space-input-output-') as directory:
    path = Path(directory) / 'input.in'
    path.write_text(source)
    for profile in ('default', 'lean', 'harden'):
        result = subprocess.run([a.compiler, 'compile', '--path', str(path), '--target', 'jit',
                                 '--profile', profile, '--out', str(Path(directory) / profile), '--json'],
                                capture_output=True, text=True, check=True, timeout=30)
        report = json.loads(result.stdout)
        assert report.get('success') and report.get('eval_result') == {'Int': 42}, report
        print(f'PASS {profile}: actual poll validates output scalar before hardware/state mutation,1920 reachability,1024 shrink clamp and legacy zero argument')
