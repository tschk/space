#!/usr/bin/env python3
"""Check real native directory snapshots against an independent byte oracle."""
import argparse
import hashlib
import io
import json
import re
import shutil
import struct
import subprocess
import tarfile
from pathlib import Path

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
snap = a.out / 'source'
snap.mkdir()
with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git', 'archive', 'HEAD'], cwd=ROOT))) as tar:
    tar.extractall(snap, filter='data')
shutil.copyfile(ROOT / 'components/fs-directory-snapshot.in', snap / 'components/fs-directory-snapshot.in')
provider = snap / 'components/fs-directory-snapshot.in'
provider.write_text(provider.read_text().replace('sf-read-block(', 'directory-test-read('))
loader = snap / 'components/sci-loader.in'
s = loader.read_text()
anchor = '  if dyn-name-prefix(name,"fs-path-") != 0 { return 0 }\n'
assert s.count(anchor) == 1
if 'dyn-name-prefix(name,"fs-directory-")' not in s:
    s = s.replace(anchor, anchor + '  if dyn-name-prefix(name,"fs-directory-") != 0 { return 0 }\n')
loader.write_text(s)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

hashes = {str(f.relative_to(snap)): sha(f) for f in snap.rglob('*') if f.is_file()}
report = {'status': 'running', 'compiler_sha256': sha(a.compiler), 'runner_sha256': sha(Path(__file__)),
          'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
          'source_sha256': hashes, 'commands': [], 'cpl3_entries': 0,
          'source_test_variance': 'native read wrapper forwards unchanged except one explicit I/O refusal and one stopped trusted live-grant revocation',
          'scope': 'synchronous native storage provider on real guest RAM-backed SparkFS; no foreign app execution'}

def run(command, name, timeout=180):
    report['commands'].append(command)
    with (a.out / name).open('w') as log:
        return subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)

try:
    entries = [(f'f{i:04}', 1, i % 7 + 1) for i in range(1700) if i not in [0, 64, 128, 1699]]
    entries += [('sub', 2, 0), ('é😀', 1, 7)]
    expected = bytearray(32 + len(entries) * 64)
    struct.pack_into('<QQQQ', expected, 0, 0x5346444952530001, 0, len(entries), 64)
    for i, (name, kind, size) in enumerate(entries):
        name = name.encode()
        identity = int(name[1:]) + 4 if name.startswith(b'f') else (1704 if name == b'sub' else 1705)
        struct.pack_into('<QQQQ', expected, 32 + i * 64, kind, identity, size, len(name))
        expected[64 + i * 64:64 + i * 64 + len(name)] = name
    (a.out / 'expected.bin').write_bytes(expected)
    report['expected_entries'] = len(entries)
    report['oracle_sha256'] = sha(a.out / 'expected.bin')
    private = '''package space.fixture
interrupt fn fs-directory-snapshot-into(path:Int,authority:Int,output:Int,capacity:Int,scratch:Int,scratchbytes:Int)->Int{}
fn private-entry(info:Int)->Int{return fs-directory-snapshot-into(info,0,0,0,0,0);}
'''
    (a.out / 'private.in').write_text(private)
    assert run([str(a.compiler), 'compile', '--path', str(a.out / 'private.in'), '--entry', 'private-entry',
                '--emit', 'sci', '--base', '0x7a000000', '--target', 'native', '--target-triple',
                'x86_64-unknown-none', '--out', str(a.out / 'private.sci')], 'private.log').returncode == 0
    source = (snap / 'kernel/kernel-root.in').read_text()
    source = re.sub(r'import "\.\./([^"]+)"', lambda m: 'import ' + json.dumps(str(snap / m[1])), source)
    source = 'import ' + json.dumps(str(provider)) + '\n' + source
    assert source.count('  shell(port)') == 1
    source = source.replace('  shell(port)', '  directory-check(port)')
    source += r'''
var directory-test-fail:Int=0
var directory-test-revoke:Int=0
fn directory-test-read(block:Int,buffer:Int)->Int{if directory-test-fail!=0{directory-test-fail=0;return -1;}let result=sf-read-block(block,buffer);if result==0&&directory-test-revoke!=0{cap-revoke(directory-test-revoke);directory-test-revoke=0;}return result;}
fn directory-name(i:Int,buffer:Int)->void{
 let j=0;while j<7{store8(buffer+j,load8("/enum/f"+j));j+=1;}
 store8(buffer+7,48+(i/1000)%10);store8(buffer+8,48+(i/100)%10);store8(buffer+9,48+(i/10)%10);store8(buffer+10,48+i%10);store8(buffer+11,0);
}
fn directory-equal(a:Int,b:Int,bytes:Int)->void{let i=0;while i<bytes{if load8(a+i)!=load8(b+i){serial-write-dec-wide(com1(),i);panic("directory bytes changed");}i+=1;}}
fn directory-fill(buffer:Int,bytes:Int)->void{let i=0;while i<bytes{store8(buffer+i,165);i+=1;}}
fn directory-refuse(path:Int,auth:Int,output:Int,cap:Int,scratch:Int,want:Int)->void{
 directory-fill(output,131104);let result=fs-directory-snapshot-into(path,auth,output,cap,scratch,cap+4096);
 if result!=want{serial-write-dec-wide(com1(),result);serial-write-dec-wide(com1(),want);panic("directory refusal status");}
 let i=0;while i<131104{if load8(output+i)!=165{panic("directory partial refusal write");}i+=1;}
}
fn directory-check(port:Int)->void{
 if dyn-resolve-idx("fs-directory-snapshot-into")!=-1||dyn-resolve-idx("serial-write-cstr")<0{panic("directory private registry");}
 let table=alloc(48);store64(table,BOOT-IMAGE-TABLE-MAGIC);store64(table+8,1);store64(table+16,254);store64(table+24,0x2f0000);store64(table+32,PRIVATE_SIZE);store64(table+40,0);
 let previous=load64(0x40d0);store64(0x40d0,table);let priorheap=heap-next;let priorcaps=cap-count;let priordomains=domain-count;let live=runtime-instance-live;
 if sci-load-runtime-component(port,0x2f0000,"private-native-directory",1,1,0)!=-1||heap-next!=priorheap||cap-count!=priorcaps||domain-count!=priordomains||runtime-instance-live!=live{panic("directory private SCI ingress");}store64(0x40d0,previous);
 if sf-mem-disk==0||volume-ready!=0{panic("directory RAM setup");}
 if sf-do-format(SF-MEM-DISK-BLOCKS,2048)!=0{panic("directory test format");}
 let path=alloc(64);let out=alloc(131104);let scratch=alloc(135200);let saved=alloc(131104);let blockcopy=alloc(4096);let metadata=alloc(524320);
 let auth=cap-mint(root-realm,cap-storage());let wrong=cap-mint(root-realm,cap-memory());let revoked=cap-mint(root-realm,cap-storage());cap-revoke(revoked);let revocable=cap-mint(root-realm,cap-storage());
 if fs-mkdir("/enum")<0||fs-mkdir("/empty")<0{panic("directory mkdir");}
 let i=0;while i<1700{directory-name(i,path);if fs-write-file(path,"payload",i%7+1)!=0{serial-write-dec-wide(port,i);panic("directory seed");}i+=1;}
 if fs-mkdir("/enum/sub")<0||fs-write-file("/enum/é😀","payload",7)!=0{panic("directory Unicode seed");}
 directory-name(0,path);if fs-delete(path)!=0{panic("directory hole0");}directory-name(64,path);if fs-delete(path)!=0{panic("directory hole64");}directory-name(128,path);if fs-delete(path)!=0{panic("directory hole128");}directory-name(1699,path);if fs-delete(path)!=0{panic("directory hole1699");}
 let inode=sf-lookup-path("/enum");let addr=sf-inode-addr(inode);if load64(addr+SF-IN-SIZE)<=12*4096||load64(addr+SF-IN-INDIRECT)==0{panic("directory indirect setup");}
 if fs-write-file("/sentinel","sentinel",8)!=0{panic("directory sentinel seed");}let host=vfs-open("/sentinel",0);if host<3{panic("directory ambient open");}let first=vfs-fd-alloc();let hostpath=load64(vfs-fd-table+host*32);
 i=0;while i<524288{store8(metadata+i,load8(sf-inodes+i));i+=1;}i=0;while i<32{store8(metadata+524288+i,load8(sf-bitmap+i));i+=1;}
 // Warm only the filesystem's own lookup/mutation scratch, not this provider.
 let heap=heap-next;let domains=domain-count;let caps=cap-count;let free=free-list;
 let cycle=0;while cycle<21{
  directory-fill(out,131104);let bytes=fs-directory-snapshot-into("/enum",auth,out,131104,scratch,135200);
  if bytes!=ORACLE_SIZE||load64(out+8)!=sf-mount-id{serial-write-dec-wide(port,bytes);panic("directory snapshot size/mount");}
  i=0;while i<bytes{let skip=0;if i>=8&&i<16{skip=1;}
   if skip==0&&load8(out+i)!=load8(0x11000000+i){serial-write-dec-wide(port,i);serial-write-dec-wide(port,load8(out+i));serial-write-dec-wide(port,load8(0x11000000+i));panic("directory independent oracle");}i+=1;}
  i=bytes;while i<131104{if load8(out+i)!=165{panic("directory output tail");}i+=1;}
  i=0;while i<1698{let id=load64(out+32+i*64+8);if id<2||id>2048{panic("directory observed inode identity");}i+=1;}
  if heap-next!=heap||domain-count!=domains||cap-count!=caps||free-list!=free{panic("directory allocation state");}cycle+=1;
  directory-equal(sf-inodes,metadata,524288);directory-equal(sf-bitmap,metadata+524288,32);
  if vfs-fd-alloc()!=first||vfs-fd-valid(host)==0||vfs-fd-offset(host)!=0||load64(vfs-fd-table+host*32)!=hostpath{panic("directory ambient descriptor");}
 }
 let bytes=fs-directory-snapshot-into("/empty",auth,out,131104,scratch,135200);if bytes!=32||load64(out+16)!=0{panic("directory empty");}
 directory-refuse("/enum",-1,out,131104,scratch,-2);directory-refuse("/enum",wrong,out,131104,scratch,-2);directory-refuse("/enum",revoked,out,131104,scratch,-2);
 directory-refuse("/missing",auth,out,131104,scratch,-4);directory-refuse("/enum/é😀",auth,out,131104,scratch,-5);directory-refuse("/enum",auth,out,96,scratch,-6);
 directory-refuse("/enum/../empty",auth,out,131104,scratch,-1);directory-refuse("/enum/",auth,out,131104,scratch,-1);
 if fs-directory-snapshot-into("/enum",auth,out,131104,out,135200)!=-1{panic("directory scratch alias");}
 directory-test-fail=1;directory-refuse("/enum",auth,out,131104,scratch,-7);
 directory-test-revoke=revocable;directory-refuse("/enum",revocable,out,131104,scratch,-2);
 let total=load64(sf-super+SF-SB-TOTAL-BLOCKS);store64(sf-super+SF-SB-TOTAL-BLOCKS,0);directory-refuse("/enum",auth,out,131104,scratch,-7);store64(sf-super+SF-SB-TOTAL-BLOCKS,total);
 let root=load32(sf-super+SF-SB-ROOT-INODE);let rootblock=load64(sf-inode-addr(root)+SF-IN-DIRECT);if sf-read-block(rootblock,blockcopy)!=0{panic("directory path corrupt setup");}let target=load32(blockcopy);store32(blockcopy,2048);if sf-write-block(rootblock,blockcopy)!=0{panic("directory path corrupt write");}directory-refuse("/enum",auth,out,131104,scratch,-7);store32(blockcopy,target);if sf-write-block(rootblock,blockcopy)!=0{panic("directory path corrupt restore");}
 let direct=load64(addr+SF-IN-DIRECT);store64(addr+SF-IN-DIRECT,SF-MAX-TOTAL-BLOCKS);directory-refuse("/enum",auth,out,131104,scratch,-7);store64(addr+SF-IN-DIRECT,direct);
 let indirect=load64(addr+SF-IN-INDIRECT);store64(addr+SF-IN-INDIRECT,SF-MAX-TOTAL-BLOCKS);directory-refuse("/enum",auth,out,131104,scratch,-7);store64(addr+SF-IN-INDIRECT,indirect);
 if sf-read-block(direct,blockcopy)!=0{panic("directory corrupt setup");}let length=load8(blockcopy+32+4);store8(blockcopy+32+4,255);if sf-write-block(direct,blockcopy)!=0{panic("directory corrupt write");}
 directory-refuse("/enum",auth,out,131104,scratch,-7);store8(blockcopy+32+4,length);if sf-write-block(direct,blockcopy)!=0{panic("directory corrupt restore");}
 directory-equal(sf-inodes,metadata,524288);directory-equal(sf-bitmap,metadata+524288,32);
 bytes=fs-directory-snapshot-into("/enum",auth,out,131104,scratch,135200);i=0;while i<bytes{store8(saved+i,load8(out+i));i+=1;}
 directory-name(1,path);if fs-delete(path)!=0||fs-write-file("/enum/reused","new",3)!=0{panic("directory reuse setup");}directory-equal(out,saved,bytes);
 if fs-directory-snapshot-into("/enum",auth,out,131104,scratch,135200)!=bytes{panic("directory fresh size");}let found=0;i=0;while i<1698{if strcmp(out+32+i*64+32,"reused")==0{found+=1;if load64(out+32+i*64+16)!=3{panic("directory fresh size value");}}i+=1;}if found!=1{panic("directory fresh observation");}
 // Output may alias the path because publication happens after traversal.
 i=0;while i<6{store8(out+i,load8("/enum"+i));i+=1;}if fs-directory-snapshot-into(out,auth,out,131104,scratch,135200)!=bytes{panic("directory path/output alias");}
 if heap-next!=heap||domain-count!=domains||cap-count!=caps||free-list!=free{panic("directory final allocation state");}
 if vfs-fd-alloc()!=first||vfs-fd-offset(host)!=0||vfs-close(host)!=0{panic("directory final descriptor");}
 serial-write-cstr(port,"native-directory: 1698 entries indirect/tombstones 21 stable snapshots PASS");serial-nl(port);outb(0xf4,16);
}
'''.replace('ORACLE_SIZE', str(len(expected))).replace('PRIVATE_SIZE', str((a.out / 'private.sci').stat().st_size))
    (a.out / 'kernel.in').write_text(source)
    assert run(['nasm', '-f', 'bin', str(snap / 'boot/multiboot.asm'), '-o', str(a.out / 'trampoline.bin')], 'nasm.log').returncode == 0
    assert run([str(a.compiler), 'compile', '--path', str(a.out / 'kernel.in'), '--entry', 'kernel-entry',
                '--emit', 'boot', '--trampoline', str(a.out / 'trampoline.bin'), '--target', 'native',
                '--target-triple', 'x86_64-unknown-none', '--linkage', 'static-lib', '--out', str(a.out / 'kernel.bin')],
               'compile.log').returncode == 0, (a.out / 'compile.log').read_text()[-4000:]
    layout = json.loads((a.out / 'kernel.component-metadata.json').read_text())['boot_layout']
    assert layout['load_end'] < 0x2f0000 and layout['file_size'] == (a.out / 'kernel.bin').stat().st_size
    assert (a.out / 'private.sci').stat().st_size <= 0x10000
    report['boot_layout'] = layout
    report['artifacts'] = {name: sha(a.out / name) for name in ['kernel.bin', 'private.sci', 'trampoline.bin', 'expected.bin']}
    assert run(['qemu-system-x86_64', '-kernel', str(a.out / 'kernel.bin'), '-m', '512M', '-display', 'none',
                '-no-reboot', '-serial', 'file:' + str(a.out / 'serial.log'), '-device',
                'isa-debug-exit,iobase=0xf4,iosize=0x04', '-device',
                f'loader,file={a.out / "expected.bin"},addr=0x11000000,force-raw=on', '-device',
                f'loader,file={a.out / "private.sci"},addr=0x2f0000,force-raw=on'], 'qemu.log', 180).returncode == 33, (a.out / 'serial.log').read_text()[-4000:]
    assert '1698 entries indirect/tombstones 21 stable snapshots PASS' in (a.out / 'serial.log').read_text()
    assert 'DENIED unresolved import fs-directory-snapshot-into' in (a.out / 'serial.log').read_text()
    report['source_changed'] = [name for name, digest in hashes.items() if sha(snap / name) != digest]
    assert not report['source_changed']
    report.update(status='passed', snapshots=21)
    print('PASS native directory snapshots: 1698 real entries, 21 measured cycles', flush=True)
except Exception as error:
    report.update(status='failed', error=str(error))
    print('FAIL', error, flush=True)
finally:
    (a.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
raise SystemExit(0 if report['status'] == 'passed' else 1)
