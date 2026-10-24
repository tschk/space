#!/usr/bin/env python3
"""Owning poll/inline-resize controls with modeled providers; not guest execution."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();a.out=a.out.resolve()
if a.out.exists() and any(a.out.iterdir()):p.error('--out must be new or empty')
a.out.mkdir(parents=True,exist_ok=True)
path=ROOT/'components/linux-process-poll.in'
function=path.read_text().split('fn linux-process-poll(',1)[1]
function='fn linux-process-poll('+function
truncate=(ROOT/'components/linux-process-truncate.in').read_text().split('fn linux-process-file-truncate(',1)[1]
function+='\nfn linux-process-file-truncate('+truncate
resize=(ROOT/'components/filesystem-inline-resize.in').read_text().split('fn fs-resize-inline(',1)[1]
function+='\nfn fs-resize-inline('+resize
harness='''
var heap:[Int]=[ZEROS];
const VFS-MAX-FDS=16;const VFS-READY-READ=1;const VFS-READY-WRITE=2;
var linux-process-authority:Int=0;var linux-process-file-buffer:Int=1024;
var linux-process-file-identities:Int=512;
var linux-process-stdout-open:Int=1;var linux-process-stderr-open:Int=0;
var memory:Int=1;var storage:Int=1;var pointer:Int=1;
var query:Int=0;var revoke:Int=0;var native-result:Int=3;
var vfs-fd-table:Int=700;const VFS-O-RDONLY=0;
var volume-ready:Int=0;var sf-disk-ready:Int=1;var sf-mount-id:Int=7;
const SF-TYPE-FILE=1;const SF-IN-TYPE=0;const SF-IN-SIZE=16;
const SF-IN-INLINE=176;const SF-IN-DIRECT=64;const SF-IN-MTIME=40;
const SF-INLINE-MAX=96;var clock:Int=1700000000;var writes:Int=0;
fn cap-memory()->Int{return 1;}
fn cap-check(a:Int,b:Int)->Int{return memory;}
fn linux-process-files-ready()->Int{if storage==0{return -13;}return 0;}
fn linux-process-range(a:Int,n:Int,w:Int)->Int{return pointer;}
fn linux-process-read32(p:Int)->Int{return heap[p];}
fn linux-process-read8(p:Int)->Int{return heap[p]&255;}
fn linux-process-store8(p:Int,v:Int)->void{heap[p]=v;return;}
fn linux-process-int32(v:Int)->Int{if v>2147483647{return v - 4294967296;}return v;}
fn linux-process-device-is(fd:Int)->Int{if fd==4{return 1;}return 0;}
fn linux-process-pipe-is(fd:Int)->Int{if fd==5{return 1;}return 0;}
fn linux-process-file-host(fd:Int)->Int{if fd==0{return 3;}return -9;}
fn load64(p:Int)->Int{return heap[p];}
fn load32(p:Int)->Int{return heap[p];}
fn store8(p:Int,v:Int)->void{heap[p]=v&255;return;}
fn store64(p:Int,v:Int)->void{heap[p]=v;return;}
fn vfs-fd-valid(fd:Int)->Int{if fd==3{return 1;}return 0;}
fn vfs-discard-tagged(fd:Int)->Int{return 0;}
fn sf-lookup-path(path:Int)->Int{return 1;}
fn sf-inode-addr(ino:Int)->Int{return 256;}
fn fs-metadata-time()->Int{return clock;}
fn sf-write-inode(ino:Int)->Int{writes+=1;return 0;}
fn vfs-regular-readiness(fd:Int,i:Int,m:Int,s:Int)->Int{
query+=1;if revoke==1{memory=0;}if revoke==2{storage=0;}return native-result;}
'''.replace('ZEROS',','.join(['0']*4096))
cases={
    'memory-before-read':'memory=0;return linux-process-poll(64,1,0)==-13 && query==0 && heap[70]==85;',
    'storage-before-query':'storage=0;return linux-process-poll(64,1,0)==-13 && query==0 && heap[70]==85;',
    'pointer-before-query':'pointer=0;return linux-process-poll(64,1,0)==-14 && query==0 && heap[70]==85;',
    'memory-revoked-during-provider':'revoke=1;return linux-process-poll(64,1,0)==-13 && query==1 && heap[70]==85;',
    'storage-revoked-during-provider':'revoke=2;return linux-process-poll(64,1,0)==-13 && query==1 && heap[70]==85;',
    'stale-native-object':'native-result=-5;return linux-process-poll(64,1,0)==-5 && heap[70]==85;',
    'unsupported-native-object':'native-result=-38;return linux-process-poll(64,1,0)==-95 && heap[70]==85;',
    'ready-regular-file':'return linux-process-poll(64,1,-1)==1 && heap[70]==1 && heap[71]==0 && heap[64]==0 && heap[68]==1;',
    'negative-fd':'heap[64]=4294967295;return linux-process-poll(64,1,0)==0 && query==0 && heap[70]==0;',
    'invalid-fd':'heap[64]=99;heap[68]=0;return linux-process-poll(64,1,-1)==1 && heap[70]==32 && query==0;',
    'unsupported-device':'heap[64]=4;return linux-process-poll(64,1,0)==-95 && heap[70]==85;',
    'unsupported-pipe':'heap[64]=5;return linux-process-poll(64,1,0)==-95 && heap[70]==85;',
    'unsupported-serial-after-ready':'heap[72]=1;heap[78]=85;return linux-process-poll(64,2,0)==-95 && heap[70]==85 && heap[78]==85;',
    'unknown-mask-ignored':'heap[68]=2;return linux-process-poll(64,1,0)==0 && heap[70]==0;',
    'actual-wait-refused':'heap[68]=0;return linux-process-poll(64,1,50)==-95 && heap[70]==85;',
    'empty-immediate':'return linux-process-poll(0,0,0)==0 && query==0;',
    'empty-wait-refused':'return linux-process-poll(0,0,-1)==-95 && query==0;',
    'count-bound':'return linux-process-poll(64,17,0)==-22 && query==0 && heap[70]==85;',
    'resize-shrink':'return linux-process-file-truncate(0,4)==0 && writes==1 && heap[272]==4 && heap[323]==7 && heap[324]==0 && heap[415]==0 && heap[296]==clock;',
    'resize-extend-zeroes':'return linux-process-file-truncate(0,19)==0 && writes==1 && heap[272]==19 && heap[328]==7 && heap[329]==0 && heap[338]==0;',
    'resize-zero':'return linux-process-file-truncate(0,0)==0 && writes==1 && heap[272]==0 && heap[320]==0 && heap[415]==0;',
    'resize-negative':'return linux-process-file-truncate(0,-1)==-22 && writes==0 && heap[272]==9;',
    'resize-memory-denied':'memory=0;return linux-process-file-truncate(0,4)==-13 && writes==0 && heap[272]==9;',
    'resize-storage-denied':'storage=0;return linux-process-file-truncate(0,4)==-13 && writes==0 && heap[272]==9;',
    'resize-invalid-fd':'return linux-process-file-truncate(99,4)==-9 && writes==0;',
    'resize-readonly-fd':'heap[812]=0;return linux-process-file-truncate(0,4)==-22 && writes==0 && heap[272]==9;',
    'resize-pipe':'return linux-process-file-truncate(5,4)==-22 && writes==0;',
    'resize-bounded-extent':'return linux-process-file-truncate(0,97)==-95 && writes==0 && heap[272]==9 && heap[324]==7;',
    'resize-block-file-refused':'heap[432]=0;return linux-process-file-truncate(0,4)==-95 && writes==0 && heap[272]==9;',
    'resize-stale-inode':'heap[512]=3;return linux-process-file-truncate(0,4)==-5 && writes==0 && heap[272]==9;',
    'resize-stale-mount':'sf-mount-id=8;return linux-process-file-truncate(0,4)==-5 && writes==0 && heap[272]==9;',
    'resize-missing-clock':'clock=-1;return linux-process-file-truncate(0,4)==-5 && writes==0 && heap[272]==9 && heap[324]==7;',
    'resize-volume-provider-refused':'volume-ready=1;return fs-resize-inline(123,2,7,4)==-2 && writes==0 && heap[272]==9;',
}
results=[]
for name,body in cases.items():
    source=harness+function+'\nfn check()->Bool{'+body+'}\nfn main()->Int{heap[64]=0;heap[68]=1;heap[70]=85;heap[71]=85;heap[812]=1;heap[512]=2;heap[520]=7;heap[256]=1;heap[272]=9;heap[432]=1;let i=320;while i<416{heap[i]=7;i+=1;}if check(){return 42;}return 99;}\n'
    entry=a.out/(name+'.in');entry.write_text(source)
    for profile in ('default','lean','harden'):
        command=[str(a.compiler.resolve()),'compile','--path',str(entry),'--target','jit','--profile',profile,'--out',str(a.out/'proof'),'--json']
        result=subprocess.run(command,capture_output=True,text=True,timeout=60)
        (a.out/(name+'-'+profile+'.json')).write_text(result.stdout+result.stderr)
        report=json.loads(result.stdout)
        assert result.returncode==0 and report.get('success') and report.get('eval_result')=={'Int':42}, (name,profile,report)
        results.append(dict(name=name,profile=profile,status='passed'))
(a.out/'report.json').write_text(json.dumps(dict(status='passed',classification='owning functions with modeled providers; no guest credit',
    source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [path,ROOT/'components/linux-process-truncate.in',ROOT/'components/filesystem-inline-resize.in']},checks=results),indent=2)+'\n')
print(f'PASS: {len(results)} poll model controls; {a.out}/report.json')
