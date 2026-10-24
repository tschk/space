#!/usr/bin/env python3
"""Prove all-import resolution and signed rel32 limits before loader mutation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
a.out = a.out.resolve()
a.compiler = a.compiler.resolve()
if a.out.exists() and any(a.out.iterdir()):
    p.error('--out must be new or empty')
a.out.mkdir(parents=True, exist_ok=True)
path = ROOT / 'components/runtime-link-validation.in'
owner = path.read_text().replace('package space.kernel', '')
# Model only supervisor registry storage/resolution and allocator function
# addresses. The admission/target functions above execute unchanged.
source = '''
const SCI-MAGIC-V2=0x5343490000000002;
const SCI-V2-IMPORT-COUNT=48;const SCI-V2-IMPORT-TABLE=56;
const DYN-MAX-EXPORTS=4096;
const runtime-instance-malloc=111;const runtime-instance-calloc=222;
const runtime-instance-realloc=333;const runtime-instance-free=444;
var dyn-count:Int=2;var dyn-fn-tab:Int=512;
var words:[Int]=[''' + ','.join(['0'] * 1024) + '''];
var missing:Int=0;var lookups:Int=0;var writes:Int=0;
fn load64(p:Int)->Int{return words[p];}
fn put(p:Int,v:Int)->void{words[p]=v;writes=writes+1;}
fn dyn-resolve-idx(name:Int)->Int{
 lookups=lookups+1;
 if missing==name{return -1;}
 if name==144{return 0;}if name==160{return 1;}return -1;
}
fn dyn-str-eq(a:Int,b:Int)->Int{if a==b{return 1;}return 0;}
''' + owner + '''
fn main()->Int{
 put(16,SCI-MAGIC-V2);put(16+48,2);put(16+56,80);
 put(96,128);put(104,0);put(112,144);put(120,8);
 put(512,4096);put(520,8192);
 let before=writes;
 if runtime-instance-image-bindings(16,64,0)!=1 || writes!=before || lookups!=2{return 100;}
 missing=160;lookups=0;
 if runtime-instance-image-bindings(16,64,0)!=0 || writes!=before || lookups!=2{return 101;}
 missing=0;put(16+48,1);
 // Exact positive/negative limits and one byte beyond each limit.
 put(512,64+5+2147483647);
 if runtime-instance-image-bindings(16,64,0)!=1{return 102;}
 put(512,64+5+2147483648);
 if runtime-instance-image-bindings(16,64,0)!=0{return 103;}
 put(512,4294963264+5-2147483648);
 if runtime-instance-image-bindings(16,4294963264,0)!=1{return 104;}
 put(512,4294963264+5-2147483649);
 if runtime-instance-image-bindings(16,4294963264,0)!=0{return 105;}
 put(512,0);if runtime-instance-image-bindings(16,64,0)!=0{return 106;}
 put(512,-1);if runtime-instance-image-bindings(16,64,0)!=0{return 107;}
 put(512,9223372036854775807);
 if runtime-instance-image-bindings(16,64,0)!=0{return 108;}
 dyn-count=-1;if runtime-instance-image-bindings(16,64,0)!=0{return 109;}
 dyn-count=4097;if runtime-instance-image-bindings(16,64,0)!=0{return 110;}
 dyn-count=2;put(16+48,0);lookups=0;
 if runtime-instance-image-bindings(16,64,0)!=1 || lookups!=0{return 111;}
 put(16,0x5343490000000001);
 if runtime-instance-image-bindings(16,32,0)!=1 || lookups!=0{return 112;}
 // Private allocator targets must replace borrowed provider addresses only
 // for owned instances. This model supplies stable function-address values.
 put(512,9876);
 if runtime-instance-image-target("malloc",0,1)!=111{return 113;}
 if runtime-instance-image-target("calloc",0,1)!=222{return 114;}
 if runtime-instance-image-target("realloc",0,1)!=333{return 115;}
 if runtime-instance-image-target("free",0,1)!=444{return 116;}
 if runtime-instance-image-target("malloc",0,0)!=9876{return 117;}
 if runtime-instance-image-target("other",0,1)!=9876{return 118;}
 if runtime-instance-image-target("malloc",-1,1)!=-1{return 119;}
 if runtime-instance-image-target("malloc",2,1)!=-1{return 120;}
 return 42;
}
'''
fixture = a.out / 'bindings.in'
fixture.write_text(source)
report = {'status': 'running', 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
          'compiler_sha256': hashlib.sha256(a.compiler.read_bytes()).hexdigest(), 'profiles': []}
try:
    for profile in ['default', 'lean', 'harden']:
        command = [str(a.compiler), 'compile', '--path', str(fixture), '--target', 'jit',
                   '--profile', profile, '--out', str(a.out / profile), '--json']
        result = subprocess.run(command, capture_output=True, text=True, timeout=90)
        (a.out / (profile + '.json')).write_text(result.stdout)
        (a.out / (profile + '.stderr')).write_text(result.stderr)
        data = json.loads(result.stdout)
        assert result.returncode == 0 and data.get('eval_result') == {'Int': 42}, data
        report['profiles'].append({'profile': profile, 'status': 'passed', 'command': command})
        print('PASS ' + profile + ': all-import preflight and signed rel32 bounds', flush=True)
    report['status'] = 'passed'
except Exception as error:
    report.update(status='failed', error=str(error))
    raise
finally:
    (a.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
