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
display = (Path(__file__).resolve().parent.parent / 'components/display.in').read_text() + '\n' + (Path(__file__).resolve().parent.parent / 'components/display-spdp.in').read_text()
start = display.index('fn dsp-drain-page(')
functions.append(display[start:display.index('\n}', start) + 2])
for filename, names in [('runtime-retained.in', ('runtime-instance-kernel-context','runtime-instance-record')), ('runtime-pixels.in', ('runtime-instance-canvas-slot','runtime-instance-pixel-bytes')), ('sci-loader.in', ('sci-display-cap-info', 'sci-sync-pixels')), ('shell.in', ('dsp-adopt-sync-pixels',))]:
    module = (Path(__file__).resolve().parent.parent / 'components' / filename).read_text()
    for name in names:
        start = module.index('fn '+name+'(')
        functions.append(module[start:module.index('\n}', start)+2])
source = 'var memory:[Int]=[' + ','.join(['0'] * 20000) + '];\n' + '''
const COMP-PIXEL-VIRT=0x70001000;
var domain-clone-owned:Int=6;var domain-user-owned:Int=0;const NATIVE-PROTECTED-KIND=2;const NATIVE-PROTECTED-GUI-PAGED=3;const NATIVE-PROTECTED-EXTRA-MAGIC=0x5350434e4c454447;const RUNTIME-INSTANCE-CATALOG-SLOTS=64;const RUNTIME-INSTANCE-LIVE=0x52554e54494d4531;
const RUNTIME-INSTANCE-PIXEL-PAGES=288;const SCI-CANVAS-BYTES=1179648;
var domain-current:Int=0;var runtime-instance-catalog:Int=16000;var sci-sync-handle:Int=257;
var cap-count:Int=1;var cap-table-base:Int=1904;
fn cr3-read()->Int{return 4096;}
const DOMAIN-ACTIVE=1;
var domain-count:Int=2;
var domain-table:Int=1500;
var sci-sync-domain:Int=1;
var sci-sync-grants:Int=20;
var sci-sync-pixel-phys:Int=4096;
var sci-sync-pixel-size:Int=4096;
var sci-sync-pixel-pool:Int=0;
var dsp-pools:Int=1600;
var dsp-pool-sizes:Int=1680;
fn cap-memory()->Int{return 4;}
fn cap-display()->Int{return 16;}
var dsp-msg:Int=1200;
var dispatches:Int=0;
fn dsp-handle-msg(object:Int,opcode:Int,arg0:Int,arg1:Int,port:Int)->Void{dispatches+=1;}
fn load64(p:Int)->Int{return memory[p];}
fn store64(p:Int,v:Int)->Void{memory[p]=v;}
''' + '\n'.join(functions) + '''
fn main()->Int{
 store64(domain-table,4096);store64(domain-table+24,8192);store64(domain-table+40,0);
 store64(cap-table-base,14600);store64(cap-table-base+8,20);
 store64(14600,101);store64(14608,5);store64(14640,1);
 store64(14000,1);store64(14008,14600);store64(14016,0);store64(14040,4096);
 store64(14256,RUNTIME-INSTANCE-LIVE);store64(14280,257);store64(14304,1);
 store64(16000,14000);store64(16008,1);store64(16016,101);store64(16024,14600);store64(16032,0);store64(16040,1);store64(16048,1);
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
 // Optional display fields are absent unless a real page was granted.
 let info=1800;
 store64(info+72,77);store64(info+80,88);store64(info+88,99);
 sci-display-cap-info(info,0);
 if load64(info+72)!=0 || load64(info+80)!=0 || load64(info+88)!=0{return 23;}
 sci-display-cap-info(info,4096);
 if load64(info+72)!=COMP-PIXEL-VIRT || load64(info+80)!=4096 || load64(info+88)!=0{return 24;}
 store64(domain-table+32,DOMAIN-ACTIVE);
 // Forged client descriptor values cannot supply a physical pool address.
 store64(info+72,0xDEAD0000);store64(info+80,9223372036854775807);store64(info+88,7);
 if dsp-adopt-sync-pixels(1,0)!=1 || load64(dsp-pools)!=4096 || load64(dsp-pool-sizes)!=4096{return 25;}
 store64(dsp-pools,77);store64(dsp-pool-sizes,88);
 sci-sync-grants=4;if dsp-adopt-sync-pixels(1,0)!=0{return 26;}
 sci-sync-grants=16;if dsp-adopt-sync-pixels(1,0)!=0{return 27;}
 sci-sync-grants=20;
 if dsp-adopt-sync-pixels(0,0)!=0 || dsp-adopt-sync-pixels(2,0)!=0 || dsp-adopt-sync-pixels(1,1)!=0{return 28;}
 sci-sync-domain=0;if dsp-adopt-sync-pixels(1,0)!=0{return 29;}sci-sync-domain=1;
 sci-sync-pixel-size=4095;if dsp-adopt-sync-pixels(1,0)!=0{return 30;}sci-sync-pixel-size=4096;
 sci-sync-pixel-pool=1;if dsp-adopt-sync-pixels(1,0)!=0{return 31;}sci-sync-pixel-pool=0;
 sci-sync-pixel-phys=4097;if dsp-adopt-sync-pixels(1,0)!=0{return 32;}
 sci-sync-pixel-phys=0;if dsp-adopt-sync-pixels(1,0)!=0{return 33;}
 sci-sync-pixel-phys=0x100000000;if dsp-adopt-sync-pixels(1,0)!=0{return 34;}
 sci-sync-pixel-phys=4096;store64(domain-table+32,0);
 if dsp-adopt-sync-pixels(1,0)!=0{return 35;}
 if load64(dsp-pools)!=77 || load64(dsp-pool-sizes)!=88{return 36;}
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
        print(f'PASS {profile}: SPDP frame guards plus loader pixel-grant provenance, forged descriptor and refusal controls')
