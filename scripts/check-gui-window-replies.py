#!/usr/bin/env python3
"""Execute actual window reply validation before modeled compositor mutation."""
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
for filename, names in (
    ('channel.in', ('chan-page-frame-header-valid', 'chan-page-frame-valid', 'chan-page-send-frame', 'chan-page-recv-frame')),
    ('gui-window-clients.in', ('gui-window-config', 'gui-window-reply')),
):
    module = (root / 'components' / filename).read_text()
    for name in names:
        start = module.index('fn ' + name + '(')
        source += module[start:module.index('\n}', start) + 2] + '\n'
source += 'var memory:[Int]=[' + ','.join(['0'] * 10000) + '];\n'
source += '''
const GUI-RECORD-SIZE=144;const GUI-TOKEN=104;const GUI-ACTIVE=112;
const GUI-SURFACE=120;const GUI-HANDLE=128;const GUI-WINDOW-CONFIG=136;
var gui-records=8;var gui-window-configs=384;var gui-window-layout=640;var gui-replies=1024;
var sci-sync-handle=257;var sci-sync-page=4096;var sci-sync-domain=1;var sci-sync-cap=3;
var sci-sync-pixel-phys=0x100000000;var sci-sync-pixel-size=1179648;
var dsp-pools=512;var dsp-pool-sizes=544;
var mutations=0;var retired=0;var geometry=0;var page-reads=0;var track-page=0;
fn domain-get-current()->Int{return 0;}
fn load64(p:Int)->Int{if track-page==1 && p>=4096 && p<8192{page-reads+=1;}return memory[p];}
fn store64(p:Int,v:Int)->void{memory[p]=v;}
fn sci-sync-provenance-valid(domain:Int,unit:Int)->Int{return 1;}
fn gui-retire(record:Int)->Int{retired+=1;return 1;}
fn dsp-create-surface()->Int{mutations+=1;return 0;}
fn dsp-surface-attach(sid:Int,pool:Int)->void{mutations+=1;}
fn dsp-surface-stride(sid:Int,stride:Int)->Int{mutations+=1;if stride==3072{return 1;}return 0;}
fn dsp-surface-geometry(sid:Int,packed:Int)->void{mutations+=1;geometry=packed;}
fn dsp-surface-commit(sid:Int)->void{mutations+=1;}
fn dsp-composite()->void{mutations+=1;}
fn prepare()->void{
 store64(gui-records+8,sci-sync-page);store64(gui-records+16,1);store64(gui-records+32,sci-sync-pixel-phys);
 store64(gui-records+88,3);store64(gui-records+GUI-HANDLE,257);store64(gui-records+GUI-WINDOW-CONFIG,384);
 store64(384,GUI-WINDOW-CONFIG-MAGIC);store64(392,2);store64(400,512);store64(408,256);store64(416,2);
 store64(gui-window-layout+40,100);store64(gui-window-layout+48,700);store64(gui-window-layout+56,30);
 store64(sci-sync-page,0);store64(sci-sync-page+8,0);store64(sci-sync-page+16,508);store64(sci-sync-page+24,8);
 mutations=0;retired=0;
}
fn reply(kind:Int)->void{
 let generation=2;let extent=(512<<16)|256;let local=0;
 if kind==1{generation=1;}if kind==2{extent=(514<<16)|256;}if kind==3{local=1;}
 chan-page-send-frame(sci-sync-page,SPDP-OBJ-SURFACE,SPDP-SURFACE-CONFIGURE-ACK-V1,generation,gui-window-config-word(512,256,2));
 chan-page-send-frame(sci-sync-page,SPDP-OBJ-SURFACE,SPDP-SURFACE-ATTACH,local,0);
 chan-page-send-frame(sci-sync-page,SPDP-OBJ-SURFACE,SPDP-SURFACE-DAMAGE,0,extent);
 chan-page-send-frame(sci-sync-page,SPDP-OBJ-SURFACE,SPDP-SURFACE-COMMIT,0,0);
}
fn main()->Int{
 let kind=1;
 while kind<=3{
  prepare();reply(kind);
  if gui-window-reply(gui-records,0,0,1)!=0 || mutations!=0 || retired!=0{return kind;}
  if load64(sci-sync-page)!=load64(sci-sync-page+8){return 4;}
  kind+=1;
 }
 prepare();reply(0);store64(sci-sync-page+8,15);
 if gui-window-reply(gui-records,0,0,1)!=0 || load64(sci-sync-page)!=0 || mutations!=0{return 5;}
 prepare();reply(0);store64(gui-records+GUI-HANDLE,0);track-page=1;page-reads=0;
 if gui-window-reply(gui-records,0,0,1)!=0 || page-reads!=0 || mutations!=0{return 6;}
 track-page=0;prepare();reply(0);store64(gui-records+8,8192);track-page=1;page-reads=0;
 if gui-window-reply(gui-records,0,0,1)!=0 || page-reads!=0 || mutations!=0{return 7;}
 track-page=0;prepare();reply(0);
 if gui-window-reply(gui-records,0,0,1)!=1 || mutations!=5 || geometry!=((100<<48)|(30<<32)|(512<<16)|256){return 8;}
 if load64(sci-sync-page)!=load64(sci-sync-page+8){return 9;}
 prepare();chan-page-send-frame(sci-sync-page,SPDP-OBJ-SURFACE,SPDP-SURFACE-DESTROY,0,0);
 chan-page-send-frame(sci-sync-page,SPDP-OBJ-SHM,SPDP-SHM-POOL-DESTROY,1,0);
 if gui-window-reply(gui-records,0,1,0)!=0 || mutations!=0 || retired!=0{return 10;}
 prepare();chan-page-send-frame(sci-sync-page,SPDP-OBJ-SURFACE,SPDP-SURFACE-DESTROY,0,0);
 chan-page-send-frame(sci-sync-page,SPDP-OBJ-SHM,SPDP-SHM-POOL-DESTROY,0,0);
 if gui-window-reply(gui-records,0,1,0)!=1 || retired!=1{return 11;}
 return 42;
}
'''
with tempfile.TemporaryDirectory(prefix='space-window-replies-') as directory:
    path = Path(directory) / 'server.in'
    path.write_text(source)
    for profile in ('default', 'lean', 'harden'):
        result = subprocess.run([a.compiler, 'compile', '--path', str(path), '--target', 'jit',
                                 '--profile', profile, '--out', str(Path(directory) / profile), '--json'],
                                capture_output=True, text=True, check=True, timeout=30)
        report = json.loads(result.stdout)
        assert report.get('success') and report.get('eval_result') == {'Int': 42}, report
        print(f'PASS {profile}: actual full-batch validator refuses stale ACK, bad extent/local identity, partial close/frame and retired/wrong-owner endpoint before compositor/page mutation')
