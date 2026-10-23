#!/usr/bin/env python3
"""Execute actual native EOF/discard descriptor owners in three compiler profiles."""
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
if a.out.exists() and any(a.out.iterdir()):p.error("--out must be new or empty")
a.out.mkdir(parents=True, exist_ok=True)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

vfs = (ROOT/'components/vfs.in').read_text()
start = vfs.index('fn vfs-sparkfs-file-size(')
end = vfs.index('\n}', start) + 2
vfs = vfs[:start] + 'fn vfs-sparkfs-file-size(path:Int)->Int{return 100;}' + vfs[end:]
vfs = vfs.replace('package space.kernel', '')
stubs = '''
var heap:[Int]=[''' + ','.join(['0'] * 65536) + '''];
var heap-next:Int=8;
var volume-ready:Int=1;
var sf-disk-ready:Int=1;
var storage-calls:Int=0;
const SF-ST-TYPE=0;
const SF-ST-MODE=4;
const SF-ST-NLINK=16;
const SF-ST-INODE=48;
fn alloc(n:Int)->Int{let p=heap-next;heap-next+=n;return p;}
fn load64(p:Int)->Int{return heap[p];}
fn store64(p:Int,v:Int)->Void{heap[p]=v;}
fn load32(p:Int)->Int{return heap[p];}
fn store32(p:Int,v:Int)->Void{heap[p]=v;}
fn load8(p:Int)->Int{return heap[p];}
fn store8(p:Int,v:Int)->Void{heap[p]=v;}
fn strdup(p:Int)->Int{return p;}
fn volume-rpc-open(p:Int,f:Int)->Int{storage-calls+=1;return 0;}
fn sf-lookup-path(p:Int)->Int{storage-calls+=1;return 1;}
fn fs-write-file(p:Int,b:Int,n:Int)->Int{storage-calls+=1;return 0;}
fn volume-rpc-pread(p:Int,b:Int,n:Int,o:Int)->Int{storage-calls+=1;return -99;}
fn volume-rpc-pwrite(p:Int,b:Int,n:Int,o:Int)->Int{storage-calls+=1;return -99;}
fn sparkfs-pread(p:Int,b:Int,n:Int,o:Int)->Int{storage-calls+=1;return -99;}
fn sparkfs-pwrite(p:Int,b:Int,n:Int,o:Int)->Int{storage-calls+=1;return -99;}
fn com1()->Int{return 0;}
fn serial-read(p:Int)->Int{return 10;}
fn serial-put(p:Int,v:Int)->Void{return;}
fn serial-write-cstr(p:Int,v:String)->Void{return;}
fn serial-write-dec-wide(p:Int,v:Int)->Void{return;}
fn halt()->Void{return;}
fn outb(p:Int,v:Int)->Void{return;}
'''
fixture = (ROOT/'fixtures/vfs-discard/check.in').read_text()
source = stubs + vfs + fixture + '''
fn main()->Int{
 if vfs-discard-open(2)!=-9{return 101;}
 vfs-init();
 let result=discard-proof();if result!=42{return result;}
 if storage-calls!=0{return 102;}
 // Verify replacement of a real regular-file target and source.
 let d=vfs-discard-open(2);let regular=vfs-open-borrowed-path(77,2);
 if vfs-dup-file-into(d,regular)!=regular || vfs-discard-valid(regular)!=1{return 103;}
 vfs-close(d);vfs-close(regular);
 let r=vfs-open-borrowed-path(77,2);let target=vfs-discard-open(2);
 vfs-fd-set-offset(r,91);
 if vfs-dup-file-into(r,target)!=target || vfs-fd-offset(target)!=91 || vfs-discard-tagged(target)!=0{return 104;}
 vfs-close(r);vfs-close(target);
 return 42;
}
'''
(a.out/'owner.in').write_text(source)
report = {'status':'running','profiles':[], 'source_sha256': {str(f.relative_to(ROOT)):sha(f) for f in [ROOT/'components/vfs.in',ROOT/'fixtures/vfs-discard/check.in',Path(__file__).resolve()]}}
try:
    for profile in ['default','lean','harden']:
        command = [str(a.compiler.resolve()),'compile','--path',str((a.out/'owner.in').resolve()),'--out',str((a.out/profile).resolve()),'--target','jit','--entry','main','--profile',profile,'--json']
        run = subprocess.run(command, capture_output=True, text=True, timeout=90)
        (a.out/(profile+'.json')).write_text(run.stdout)
        (a.out/(profile+'.stderr')).write_text(run.stderr)
        result = json.loads(run.stdout)
        assert run.returncode==0 and result.get('success') and result.get('eval_result')=={'Int':42}, (profile,run.stdout,run.stderr)
        report['profiles'].append({'profile':profile,'status':'passed','command':command})
        print('PASS',profile,'actual VFS owner: EOF/discard, access, bounds, stat, duplicates, replacement, full pool, malformed tags, no storage calls and 63-cycle no heap/refcount drift',flush=True)
    report['source_changed_during_run']=[name for name,digest in report['source_sha256'].items() if sha(ROOT/name)!=digest]
    assert not report['source_changed_during_run']
    report['status']='passed'
except Exception as error:
    report.update(status='failed',error=str(error))
    print('FAIL:',error,flush=True)
finally:
    (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='passed' else 1)
