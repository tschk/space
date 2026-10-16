#!/usr/bin/env python3
"""Execute actual SPDP teardown/dispatch against isolated compositor records."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--in', dest='compiler', required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
text = (root/'components/display.in').read_text()
functions = []
for name in ('dsp-surface-size', 'dsp-create-surface', 'dsp-surface-valid', 'dsp-surface-destroy', 'dsp-shm-destroy-pool', 'dsp-surface-attach', 'dsp-surface-geometry', 'dsp-surface-commit', 'dsp-handle-msg'):
    start = text.index('fn '+name+'(')
    # The size helper is a single-line declaration.
    end = text.index('\n', start) if name == 'dsp-surface-size' else text.index('\n}', start)+2
    functions.append(text[start:end])
source = (root/'protocol/display.in').read_text() + '\nvar heap:[Int]=[' + ','.join(['0']*2304) + '];\n' + '''
const DSP-MAX-SURFACES=3;
const DSP-MAX-POOLS=8;
var dsp-surfaces:Int=8;
var dsp-surface-count:Int=0;
var dsp-pools:Int=1600;
var dsp-pool-sizes:Int=1700;
fn load64(p:Int)->Int{return heap[p];}
fn store64(p:Int,v:Int)->Void{heap[p]=v;}
fn dsp-shm-create-pool(id:Int,size:Int)->Void{return;}
''' + '\n'.join(functions) + '''
fn main()->Int{
 if dsp-create-surface()!=0 || dsp-create-surface()!=1 || dsp-create-surface()!=2{return 1;}
 store64(dsp-pools,4096);store64(dsp-pool-sizes,4096);
 store64(dsp-pools+8,8192);store64(dsp-pool-sizes+8,2048);
 dsp-surface-attach(0,4);dsp-surface-geometry(0,(64<<16)|16);dsp-surface-commit(0);
 dsp-surface-attach(1,1<<32);dsp-surface-geometry(1,(32<<16)|16);dsp-surface-commit(1);
 dsp-surface-attach(2,8);dsp-surface-geometry(2,(16<<16)|16);dsp-surface-commit(2);
 dsp-handle-msg(SPDP-OBJ-SURFACE,SPDP-SURFACE-DESTROY,0,0,0);
 if dsp-surface-valid(0)!=0 || load64(dsp-surfaces)!=-1 || load64(dsp-surfaces+8)!=-1 || load64(dsp-surfaces+40)!=0{return 2;}
 dsp-surface-attach(0,1<<32);dsp-surface-geometry(0,123);dsp-surface-commit(0);
 dsp-handle-msg(SPDP-OBJ-SURFACE,SPDP-SURFACE-DESTROY,0,0,0);
 if load64(dsp-surfaces+8)!=-1 || load64(dsp-surfaces+24)!=0 || load64(dsp-surfaces+40)!=0{return 3;}
 dsp-handle-msg(SPDP-OBJ-SHM,SPDP-SHM-POOL-DESTROY,0,0,0);
 let second=dsp-surfaces+48;let third=dsp-surfaces+96;
 if load64(dsp-pools)!=0 || load64(dsp-pool-sizes)!=0{return 4;}
 if load64(third+8)!=-1 || load64(third+16)!=0 || load64(third+40)!=0 || dsp-surface-valid(2)!=1{return 5;}
 dsp-handle-msg(SPDP-OBJ-SHM,SPDP-SHM-POOL-DESTROY,0,0,0);
 dsp-surface-destroy(-1);dsp-surface-destroy(3);dsp-shm-destroy-pool(-1);dsp-shm-destroy-pool(8);
 if load64(second+8)!=1 || load64(second+24)!=((32<<16)|16) || load64(second+40)!=1{return 6;}
 if load64(dsp-pools+8)!=8192 || load64(dsp-pool-sizes+8)!=2048{return 7;}
 dsp-surface-attach(2,1<<32);dsp-surface-commit(2);
 if load64(third+8)!=1 || load64(third+40)!=1{return 8;}
 // Tombstones deliberately do not recycle IDs or revive stale requests.
 if dsp-surface-count!=3 || dsp-create-surface()!=-1{return 9;}
 return 42;
}
'''
with tempfile.TemporaryDirectory(prefix='space-spdp-lifetime-') as directory:
    path = Path(directory)/'lifetime.in'
    path.write_text(source)
    for profile in ('default', 'lean', 'harden'):
        result = subprocess.run([args.compiler, 'compile', '--path', str(path), '--target', 'jit', '--profile', profile, '--out', str(Path(directory)/'out'), '--json'], capture_output=True, text=True, check=True, timeout=30)
        report = json.loads(result.stdout)
        assert report.get('success') and report.get('eval_result') == {'Int': 42}, report
        print(f'PASS {profile}: SPDP surface/pool teardown, stale/repeated/invalid requests and other-live-record preservation')
