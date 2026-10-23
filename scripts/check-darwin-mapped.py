#!/usr/bin/env python3
"""Execute the finite high-VA Darwin mapper on genuine CPL3 hardware paths."""
import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--jq', type=Path, required=True)
p.add_argument('--profile', choices=['default', 'lean', 'harden'], default='default')
p.add_argument('--root', choices=['standard', 'minimal'], default='standard')
a = p.parse_args()
a.out = a.out.resolve()
a.compiler = a.compiler.resolve()
a.jq = a.jq.resolve()
if a.out.exists() and any(a.out.iterdir()):
    p.error('--out must be new or empty')
a.out.mkdir(parents=True, exist_ok=True)
snap = a.out / 'source'
snap.mkdir()
# Freeze committed dependencies, excluding unrelated work in the shared tree.
archive = subprocess.check_output(['git', 'archive', 'HEAD'], cwd=ROOT)
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
    tar.extractall(snap, filter='data')
for name in ['components/darwin-mapped-process.in', 'fixtures/darwin-mapped/process.asm',
             'fixtures/darwin-mapped/private-import.in']:
    target = snap / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / name, target)
loader = snap / 'components/sci-loader.in'
s = loader.read_text()
anchor = '  if dyn-name-prefix(name,"user-space-")'
assert s.count(anchor) == 1
if 'dyn-name-prefix(name,"darwin-mapped-")' not in s:
    s = s.replace(anchor, '  if dyn-name-prefix(name,"darwin-mapped-") != 0 { return 0 }\n' + anchor)
loader.write_text(s)
provider = snap / 'components/darwin-mapped-process.in'
s = provider.read_text()
for stage, name in enumerate(['map', 'populate', 'fixups', 'startup', 'seal'], 1):
    pattern = r'(fn darwin-mapped-' + name + r'\([^\n]+\{)'
    s, count = re.subn(pattern, r'\1\n  if mapped-test-stage == ' + str(stage) + r' { return -12 }', s)
    assert count == 1
anchor = '  let plan = state + 256\n  let image = load64(state + 24)'
assert s.count(anchor) == 1
s = s.replace(anchor, '  if mapped-test-stage == 7 { store8(load64(state + 24) + 0x1b00,121) }\n' + anchor)
assert s.count('let binding = user-space-attach(vm,memory,state + 4096)') == 1
s = s.replace('let binding = user-space-attach(vm,memory,state + 4096)', 'let binding = mapped-test-attach(vm,memory,state + 4096)')
s = s.replace('domain-user-syscall-hook = darwin-mapped-trap', 'domain-user-syscall-hook = mapped-test-trap')
s = s.replace('let status = user-space-release-binding(binding,authority)', 'let status = mapped-test-release(binding,authority)')
provider.write_text(s)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

hashes = {str(f.relative_to(snap)): sha(f) for f in snap.rglob('*') if f.is_file()}
report = {'status': 'running', 'compiler': str(a.compiler), 'compiler_sha256': sha(a.compiler),
          'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
          'profile': a.profile, 'root': a.root,
          'runner_sha256': sha(Path(__file__)), 'source_sha256': hashes, 'commands': [],
          'scope': 'ABI fixture execution; no original application coverage',
          'source_test_variance': 'snapshot-only stage refusals, setup-source mutation, trap-time grant revocation and real native ownership/PDE corruption at teardown; production source remains unchanged'}

def run(cmd, name, timeout=180):
    report['commands'].append(cmd)
    with (a.out / name).open('w') as log:
        return subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)

try:
    manifest = json.loads((snap / 'fixtures/applications/jq-1.8.1.json').read_text())
    pinned = next(x for x in manifest['apps'] if x['personality'] == 'darwin')
    assert sha(a.jq) == pinned['sha256'] and a.jq.stat().st_size == pinned['size_bytes']
    report['original_jq'] = {'sha256': sha(a.jq), 'executions': 0, 'admission': -38,
                             'first_unavailable_import': '__DefaultRuneLocale'}
    assert run(['nasm', '-f', 'bin', str(snap / 'fixtures/darwin-mapped/process.asm'),
                '-o', str(a.out / 'process.macho')], 'nasm.log').returncode == 0
    image_size = (a.out / 'process.macho').stat().st_size
    binary = (a.out / 'process.macho').read_bytes()
    report['fixture_sha256'] = sha(a.out / 'process.macho')
    assert run([str(a.compiler), 'compile', '--path', str(snap / 'fixtures/darwin-mapped/private-import.in'),
                '--entry', 'private-entry', '--emit', 'sci', '--base', '0x7a000000', '--target', 'native',
                '--target-triple', 'x86_64-unknown-none', '--out', str(a.out / 'private.sci')], 'private-compile.log').returncode == 0
    source = (snap / ('kernel/kernel-root-minimal.in' if a.root == 'minimal' else 'kernel/kernel-root.in')).read_text()
    source = re.sub(r'import "\.\./([^"]+)"', lambda m: 'import ' + json.dumps(str(snap / m[1])), source)
    source = 'import ' + json.dumps(str(snap / 'components/darwin-mapped-process.in')) + '\n' + source
    assert source.count('  shell(port)') == 1
    source = source.replace('  shell(port)', '  mapped-check(port)')
    source += r'''
var mapped-test-stage:Int=0
var mapped-test-revoke:Int=0
var mapped-test-slot:Int=0
var mapped-test-old:Int=0
fn mapped-test-attach(vm:Int,auth:Int,context:Int)->Int{if mapped-test-stage==6{return -3;}return user-space-attach(vm,auth,context);}
fn mapped-test-trap(frame:Int)->Int{
 let result=darwin-mapped-trap(frame);
 if result==2&&mapped-test-revoke!=0{cap-revoke(mapped-test-revoke);mapped-test-revoke=0;}
 return result;
}
fn mapped-test-release(binding:Int,auth:Int)->Int{
 if mapped-test-stage==8||mapped-test-stage==9{
  let state=load64(mapped-test-state-holder);let domain=load64(state+120);
  if mapped-test-stage==8{mapped-test-slot=domain-user-object-table+domain*24+8;mapped-test-old=load64(mapped-test-slot);store64(mapped-test-slot,0);}
  else{let root=load64(domain-table+domain*24);let pdpt=load64(root)&PAGE-ADDRESS-MASK;let pd=load64(pdpt+4*8)&PAGE-ADDRESS-MASK;mapped-test-slot=pd;mapped-test-old=load64(pd);store64(pd,mapped-test-old|128);}
  mapped-test-stage=0;
 }
 return user-space-release-binding(binding,auth);
}
var mapped-test-state-holder:Int=0
fn mapped-free-count()->Int{let f=free-list;let n=0;while f!=0&&n<8192{n+=1;f=load64(f);}return n;}
fn mapped-invoke(state:Int,input:Int,serial:Int,memory:Int,budget:Int)->Int{
 let prepared=darwin-mapped-prepare(0x11000000,IMAGE_SIZE,state,20480,DARWIN-MAPPED-IDENTITY);
 if prepared!=0{return prepared;}
 let plan-hash=darwin-mapped-digest(state+256,3840);
 let result=darwin-mapped-run(state,input,1024,DARWIN-MAPPED-IDENTITY,serial,memory,budget);
 if darwin-mapped-digest(state+256,3840)!=plan-hash{panic("mapped immutable launch plan");}
 return result;
}
fn mapped-check(port:Int)->void{
 if dyn-kernel-exportable("darwin-mapped-run")!=0||dyn-resolve-idx("darwin-mapped-run")!=-1{panic("mapped registry");}
 let table=alloc(48);store64(table,BOOT-IMAGE-TABLE-MAGIC);store64(table+8,1);store64(table+16,254);store64(table+24,0x2f0000);store64(table+32,PRIVATE_SIZE);store64(table+40,0);
 let previous=load64(0x40d0);store64(0x40d0,table);let before=heap-next;let oldcaps=cap-count;let olddomains=domain-count;let live=runtime-instance-live;
 if sci-load-runtime-component(port,0x2f0000,"private-darwin-mapper",1,1,0)!=-1||heap-next!=before||cap-count!=oldcaps||domain-count!=olddomains||runtime-instance-live!=live{panic("mapped private SCI ingress");}store64(0x40d0,previous);
 let state=alloc(20480);cpu-mem-fill64(state,0,2560);
 mapped-test-state-holder=alloc(8);store64(mapped-test-state-holder,state);
 let input=alloc(1024);cpu-mem-fill64(input,0,128);
 store64(input,2);store64(input+8,input+64);store64(input+16,1);store64(input+24,input+96);store64(input+32,1);store64(input+40,input+112);
 store64(input+64,input+256);store64(input+72,input+272);store64(input+96,input+288);store64(input+112,input+304);
 store8(input+256,104);store8(input+272,120);store8(input+288,101);store8(input+304,97);
 let serial=cap-mint(root-realm,cap-serial());let memory=cap-mint(root-realm,cap-memory());let caps=cap-count;
 let source-copy=alloc(IMAGE_SIZE);let byte=0;while byte<IMAGE_SIZE{store8(source-copy+byte,load8(0x11000000+byte));byte+=1;}
 if fs-write-file("mapped-host.txt","sentinel",8)!=0{panic("mapped host seed");}
 let host=vfs-open("mapped-host.txt",0);if host<3{panic("mapped host open");}let first=vfs-fd-alloc();let host-path=load64(vfs-fd-table+host*32);
 let result=mapped-invoke(state,input,serial,memory,1000);
 if result!=42{serial-write-cstr(port,"mapped first result ");serial-write-dec-wide(port,result);serial-write-cstr(port," native ");serial-write-dec-wide(port,load64(state+152));serial-nl(port);panic("mapped first execution");}
 let heap=heap-next;let free=mapped-free-count();let domains=domain-count;let executions=1;let cycle=0;
 while cycle<21{
  let mode=0;
  while mode<13{
   store64(0x11003000,mode);let budget=1000;if mode==8{budget=3;}
   result=mapped-invoke(state,input,serial,memory,budget);let expected=42;
   if mode>=1&&mode<=7{expected=142;}if mode==8{expected=124;}if mode==9{expected=134;}
   if result!=expected{serial-write-cstr(port,"mapped mode ");serial-write-dec-wide(port,mode);serial-write-cstr(port," result ");serial-write-dec-wide(port,result);serial-write-cstr(port," native ");serial-write-dec-wide(port,load64(state+152));serial-nl(port);panic("mapped guest result");}
   if mode>=1&&mode<=7{let error=7;if mode<=2{error=4;}if mode==4||mode==6{error=21;}if load64(state+4096+696)!=14||load64(state+4096+704)!=error||load64(state+160)!=USER-CONTEXT-FAULT{panic("mapped hardware page permissions");}}
   if mode==8&&load64(state+160)!=USER-CONTEXT-DEADLINE{panic("mapped actual IRQ deadline");}
   if heap-next!=heap||mapped-free-count()!=free||domain-count!=domains||cap-count!=caps||domain-current!=0||user-context-active!=0||domain-user-syscall-hook!=0||darwin-mapped-active!=0||load64(state+56)!=0||load64(state+64)!=0||load64(state+168)!=0||load64(state+48)!=3{panic("mapped cleanup");}
   if vfs-fd-alloc()!=first||vfs-fd-valid(host)==0||vfs-fd-offset(host)!=0||load64(vfs-fd-table+host*32)!=host-path{panic("mapped ambient descriptor");}
   byte=0;while byte<IMAGE_SIZE{if byte<12288||byte>=12296{if load8(0x11000000+byte)!=load8(source-copy+byte){panic("mapped caller source changed");}}byte+=1;}
   executions+=1;mode+=1;
  }
  cycle+=1;
 }
 store64(0x11003000,0);cycle=0;
 while cycle<21{
  let stage=1;while stage<=9{
   mapped-test-stage=stage;result=mapped-invoke(state,input,serial,memory,1000);mapped-test-stage=0;
   if stage==7{store8(0x11001b00,120);}
   let expected=-12;if stage==7{expected=-8;}if stage>=8{expected=-5;}
   if result!=expected{serial-write-dec-wide(port,stage);serial-write-dec-wide(port,result);panic("mapped failure stage");}
   if stage>=8{
    if load64(state+48)!=4||load64(state+56)==0||load64(state+168)!=0{panic("mapped retained owner");}
    if stage==8&&load64(state+64)==0{panic("mapped lost retained binding");}
    if stage==9&&load64(state+64)!=0{panic("mapped committed detach token");}
    store64(mapped-test-slot,mapped-test-old);
    if darwin-mapped-recover(state)!=0||load64(state+56)!=0||load64(state+64)!=0||load64(state+48)!=3{panic("mapped retained recovery");}
   }
   if heap-next!=heap||mapped-free-count()!=free||domain-count!=domains||cap-count!=caps{panic("mapped failure resources");}
   stage+=1;
  }cycle+=1;
 }
 let old-generation=user-space-generation;
 if mapped-invoke(state,input,serial,-1,1000)!=-13||mapped-invoke(state,input,serial,serial,1000)!=-13||mapped-invoke(state,input,memory,memory,1000)!=-13||user-space-generation!=old-generation||heap-next!=heap||mapped-free-count()!=free{panic("mapped capability admission");}
 if darwin-mapped-prepare(0x11000000,IMAGE_SIZE,state,20480,DARWIN-MAPPED-IDENTITY)!=0{panic("mapped malformed prepare");}
 store64(state+256+40,0);
 if darwin-mapped-run(state,input,1024,DARWIN-MAPPED-IDENTITY,serial,memory,1000)!=-8{panic("mapped altered plan");}
 if darwin-mapped-prepare(0x11000000,IMAGE_SIZE,state,20480,DARWIN-MAPPED-IDENTITY)!=0{panic("mapped source prepare");}
 store8(0x11001b00,121);
 if darwin-mapped-run(state,input,1024,DARWIN-MAPPED-IDENTITY,serial,memory,1000)!=-8{panic("mapped altered source");}store8(0x11001b00,120);
 if darwin-mapped-prepare(0x11000000,IMAGE_SIZE,state,20480,DARWIN-MAPPED-IDENTITY)!=0{panic("mapped input prepare");}
 store64(input,17);
 if darwin-mapped-run(state,input,1024,DARWIN-MAPPED-IDENTITY,serial,memory,1000)!=-22{panic("mapped invalid argc");}store64(input,2);
 if darwin-mapped-run(state,input,1024,DARWIN-MAPPED-IDENTITY,serial,memory,0)!=-22||darwin-mapped-run(state,input,1024,0,serial,memory,1000)!=-8||darwin-mapped-prepare(0x11000000,IMAGE_SIZE,state,20479,DARWIN-MAPPED-IDENTITY)!=-14{panic("mapped contract admission");}
 if darwin-mapped-prepare(0x12000000,JQ_SIZE,state,20480,DARWIN-MAPPED-IDENTITY)!=0||darwin-mapped-run(state,input,1024,DARWIN-MAPPED-IDENTITY,serial,memory,1000)!=-38{panic("mapped original jq refusal");}
 // PROFILE_IMPORT_CONTROLS
 if user-space-generation!=old-generation||heap-next!=heap||mapped-free-count()!=free||domain-count!=domains||cap-count!=caps{panic("mapped preflight allocated");}
 let saved-end=heap-end;let saved-free=free-list;heap-end=heap-next;free-list=0;
 result=mapped-invoke(state,input,serial,memory,1000);heap-end=saved-end;free-list=saved-free;
 if result!=-12||heap-next!=heap||mapped-free-count()!=free||load64(state+56)!=0||domain-count!=domains{panic("mapped insufficient frames");}
 // Revocation occurs in the real first stopped CPL3 write, before service.
 let revserial=cap-mint(root-realm,cap-serial());mapped-test-revoke=revserial;
 if mapped-invoke(state,input,revserial,memory,1000)!=99||cap-check(revserial,cap-serial())!=0{panic("mapped serial revoke");}
 let revmemory=cap-mint(root-realm,cap-memory());mapped-test-revoke=revmemory;
 if mapped-invoke(state,input,serial,revmemory,1000)!=-13||cap-check(revmemory,cap-memory())!=0{panic("mapped memory revoke");}
 if heap-next!=heap||mapped-free-count()!=free||domain-count!=domains||load64(state+56)!=0||load64(state+64)!=0{panic("mapped revoked cleanup");}
 if vfs-close(host)!=0{panic("mapped host close");}
 serial-write-cstr(port,"darwin-mapped: 318 CPL3 executions 21 stable cycles PASS");serial-nl(port);outb(0xF4,16);
}
'''.replace('IMAGE_SIZE', str(image_size)).replace('JQ_SIZE', str(a.jq.stat().st_size)).replace('PRIVATE_SIZE', str((a.out / 'private.sci').stat().st_size))
    positions = [m.start() for m in re.finditer(b'_write\x00', binary)]
    assert len(positions) == 2
    changes = '\n'.join(f'store8(0x11000000+{offset+i},{value});' for offset in positions for i, value in enumerate(b'_close'))
    restores = '\n'.join(f'store8(0x11000000+{offset+i},{value});' for offset in positions for i, value in enumerate(b'_write'))
    source = source.replace('// PROFILE_IMPORT_CONTROLS', changes + '\nif darwin-mapped-prepare(0x11000000,' + str(image_size) + ',state,20480,DARWIN-MAPPED-IDENTITY)!=0||darwin-image-import-preflight(state+256)!=0||darwin-mapped-run(state,input,1024,DARWIN-MAPPED-IDENTITY,serial,memory,1000)!=-38{panic("mapped finite import refusal");}\n' + restores)
    (a.out / 'kernel.in').write_text(source)
    assert run(['nasm', '-f', 'bin', str(snap / 'boot/multiboot.asm'), '-o', str(a.out / 'trampoline.bin')], 'trampoline.log').returncode == 0
    assert run([str(a.compiler), 'compile', '--path', str(a.out / 'kernel.in'), '--entry', 'kernel-entry',
                '--emit', 'boot', '--trampoline', str(a.out / 'trampoline.bin'), '--target', 'native',
                '--target-triple', 'x86_64-unknown-none', '--linkage', 'static-lib', '--profile', a.profile, '--out', str(a.out / 'kernel.bin')],
               'compile.log').returncode == 0, (a.out / 'compile.log').read_text()[-4000:]
    layout = json.loads((a.out / 'kernel.component-metadata.json').read_text())['boot_layout']
    assert layout['load_end'] < 0x2f0000 and layout['file_size'] == (a.out / 'kernel.bin').stat().st_size
    assert (a.out / 'private.sci').stat().st_size <= 0x10000
    report['boot_layout'] = layout
    report['artifacts'] = {name: sha(a.out / name) for name in ['kernel.bin', 'process.macho', 'private.sci', 'trampoline.bin']}
    command = ['qemu-system-x86_64', '-kernel', str(a.out / 'kernel.bin'), '-m', '512M', '-display', 'none',
               '-no-reboot', '-serial', 'file:' + str(a.out / 'serial.log'), '-device',
               'isa-debug-exit,iobase=0xf4,iosize=0x04', '-device',
               f'loader,file={a.out / "process.macho"},addr=0x11000000,force-raw=on', '-device',
               f'loader,file={a.jq},addr=0x12000000,force-raw=on', '-device',
               f'loader,file={a.out / "private.sci"},addr=0x2f0000,force-raw=on']
    result = run(command, 'qemu.log', 120)
    serial_log = (a.out / 'serial.log').read_text()
    assert result.returncode == 33 and '318 CPL3 executions 21 stable cycles PASS' in serial_log, serial_log[-5000:]
    assert 'INVALID private Darwin mapper entry' not in serial_log
    report['source_changed'] = [name for name, digest in hashes.items() if sha(snap / name) != digest]
    assert not report['source_changed']
    assert sha(a.jq) == pinned['sha256']
    report.update(status='passed', executions=318, cycles=21, setup_refusals=147)
    print('PASS Darwin high-VA mapper: 318 actual CPL3 executions', flush=True)
except Exception as error:
    report.update(status='failed', error=str(error))
    print('FAIL', error, flush=True)
finally:
    (a.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
raise SystemExit(0 if report['status'] == 'passed' else 1)
