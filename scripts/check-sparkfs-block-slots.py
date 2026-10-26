#!/usr/bin/env python3
"""Execute actual SparkFS block-slot owners for empty/bounded/error cases."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',required=True)
p.add_argument('--source',type=Path,default=ROOT/'components/fs2-inode.in')
a=p.parse_args()
text=a.source.read_text()
def extract(name):
    start=text.index('fn '+name+'(')
    return text[start:text.index('\n}',start)+2]
source='\n'.join(line for line in (ROOT/'components/fs2-layout.in').read_text().splitlines() if line.startswith('const '))+'\n'
source+='var memory:[Int]=['+','.join(['0']*8192)+'];\nvar disk:[Int]=['+','.join(['0']*512)+'];\n'
source+='''var sf-inodes:Int=256;var sf-block-buf:Int=2048;
var reads:Int=0;var writes:Int=0;var allocations:Int=0;var io-error:Int=0;
fn load64(p:Int)->Int{return memory[p];}
fn store64(p:Int,v:Int)->Void{memory[p]=v;}
fn load32(p:Int)->Int{return memory[p];}
fn store32(p:Int,v:Int)->Void{memory[p]=v;}
fn sf-read-block(block:Int,buf:Int)->Int{
 reads+=1;if io-error!=0{return -1;}
 let i=0;while i<512{memory[buf+i*8]=disk[i];i+=1;}return 0;
}
fn sf-write-block(block:Int,buf:Int)->Int{
 writes+=1;let i=0;while i<512{disk[i]=memory[buf+i*8];i+=1;}return 0;
}
fn sf-alloc-block()->Int{allocations+=1;return 77;}
'''
source+='\n'.join(extract(name) for name in ('sf-inode-addr','sf-inode-block','sf-set-inode-block'))
source+='''
fn main()->Int{
 let inode=sf-inode-addr(0);
 if sf-inode-block(0,0)!=-1{return 100;}
 store64(inode+SF-IN-DIRECT,42);
 if sf-inode-block(0,0)!=42{return 101;}
 if sf-inode-block(0,-1)!=-1 || sf-inode-block(0,524)!=-1{return 102;}
 store32(inode+SF-IN-INLINE,1);
 if sf-inode-block(0,0)!=-1{return 103;}
 store32(inode+SF-IN-INLINE,0);
 if sf-inode-block(0,12)!=-1{return 104;}
 store64(inode+SF-IN-INDIRECT,77);
 if sf-inode-block(0,12)!=-1{return 105;}
 disk[0]=19;if sf-inode-block(0,12)!=19{return 106;}
 disk[511]=31;if sf-inode-block(0,523)!=31{return 113;}
 io-error=1;if sf-inode-block(0,12)!=-1{return 107;}
 if sf-set-inode-block(0,12,4)!=-1 || writes!=0{return 114;}
 io-error=0;
 let before=reads;
 if sf-set-inode-block(0,-1,4)!=-1 || sf-set-inode-block(0,524,4)!=-1{return 108;}
 if sf-set-inode-block(0,0,0)!=-1 || sf-set-inode-block(0,12,0)!=-1{return 109;}
 if reads!=before || writes!=0 || allocations!=0 || load64(inode+SF-IN-DIRECT)!=42{return 110;}
 if sf-set-inode-block(0,0,22)!=0 || sf-inode-block(0,0)!=22{return 111;}
 if sf-set-inode-block(0,12,23)!=0 || sf-inode-block(0,12)!=23{return 112;}
 return 42;
}
'''
with tempfile.TemporaryDirectory(prefix='space-block-slots-') as directory:
    root=Path(directory);path=root/'slots.in';path.write_text(source)
    for profile in ('default','lean','harden'):
        command=[a.compiler,'compile','--path',str(path),'--target','jit','--entry','main','--profile',profile,'--out',str(root/profile),'--json']
        result=subprocess.run(command,capture_output=True,text=True)
        if not result.stdout:raise SystemExit(result.stderr)
        report=json.loads(result.stdout)
        if result.returncode or not report.get('success') or report.get('eval_result')!={'Int':42}:
            raise SystemExit(f'FAIL {profile}: {result.stdout}\n{result.stderr}')
        print(f'PASS {profile}: direct/indirect empty slots, bounds, failed reads and zero-block install refusal')
