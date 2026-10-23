#!/usr/bin/env python3
"""Execute the actual bounded GUI layout and inverse hit-testing contracts."""
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
source = (root / 'protocol/gui-canvas.in').read_text()
source += re.sub(r'(?m)^import .*?$', '', (root / 'protocol/gui-window.in').read_text())
source += re.sub(r'(?m)^(package .*|import .*?)$', '', (root / 'components/gui-window-layout.in').read_text())
source += '''
var memory:[Int]=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0];
fn load64(p:Int)->Int{return memory[p/8];}
fn store64(p:Int,v:Int)->void{memory[p/8]=v;}
fn main()->Int{
 let mode=0;
 while mode<3{
  let ow=1024;let oh=768;
  if mode==1{ow=1280;oh=720;}if mode==2{ow=1920;oh=1080;}
  let scale=2;
  while scale<=3{
   if gui-window-layout-fill(8,ow,oh,scale,mode*2+scale)!=1{return 1;}
   let w=load64(24);let h=load64(32);let left=load64(48);let right=load64(56);let top=load64(64);
   if w<128*scale || w>768 || h<64*scale || h>384 || w%scale!=0 || h%scale!=0{return 2;}
   if left<0 || left+w>=right || right+w>ow || top<0 || top+h>oh{return 3;}
   if gui-window-layout-hit(8,left,top)!=0 || gui-window-layout-hit(8,right+w - 1,top+h - 1)!=1{return 4;}
   if gui-window-layout-hit(8,left+w,top)!=-1 || gui-window-layout-hit(8,left,top+h)!=-1 || gui-window-layout-hit(8,right - 1,top)!=-1{return 5;}
   if gui-window-local-x(8,0,left+7*scale,top)!=7 || gui-window-local-x(8,1,right+w - 1,top)!=w/scale - 1{return 6;}
   if gui-window-local-x(8,1,left,top)!=-1 || gui-window-local-x(8,-1,left,top)!=-1{return 7;}
   scale+=1;
  }
  mode+=1;
 }
 let generation=load64(16);let width=load64(24);let x=load64(48);
 if gui-window-layout-fill(8,1024,768,1,10)!=0 || gui-window-layout-fill(8,1024,768,4,10)!=0 || gui-window-layout-fill(8,1024,768,3,0)!=0{return 8;}
 if gui-window-layout-fill(8,1024,599,3,10)!=0 || gui-window-layout-fill(8,959,768,3,10)!=0 || gui-window-layout-fill(8,0x7fffffffffffffff,768,3,10)!=0{return 9;}
 if load64(16)!=generation || load64(24)!=width || load64(48)!=x{return 10;}
 if gui-window-layout-fill(0,1024,768,2,10)!=0 || gui-window-layout-hit(0,0,0)!=-1{return 11;}
 return 42;
}
'''
with tempfile.TemporaryDirectory(prefix='space-gui-window-layout-') as directory:
    path = Path(directory) / 'layout.in'
    path.write_text(source)
    for profile in ('default', 'lean', 'harden'):
        result = subprocess.run([a.compiler, 'compile', '--path', str(path), '--target', 'jit',
                                 '--profile', profile, '--out', str(Path(directory) / profile), '--json'],
                                capture_output=True, text=True, check=True, timeout=30)
        report = json.loads(result.stdout)
        assert report.get('success') and report.get('eval_result') == {'Int': 42}, report
        print(f'PASS {profile}: actual bounded window layout1024/1280/1920 at2x/3x, inverse pointer coordinates, invalid transaction preserves layout')
