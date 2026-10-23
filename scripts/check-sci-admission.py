#!/usr/bin/env python3
"""Boot real SCI admission denials before lifecycle allocation or import mutation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parents[1])
a = p.parse_args()
root = a.source_root.resolve()
out = a.out.resolve()
compiler = a.compiler.resolve()
if out.exists() and any(out.iterdir()):
    p.error('--out must be new or empty')
out.mkdir(parents=True, exist_ok=True)

def run(command, log, **options):
    with (out / log).open('w') as stream:
        return subprocess.run([str(x) for x in command], cwd=root, stdout=stream,
                              stderr=subprocess.STDOUT, check=True, timeout=180, **options)

report = {'status': 'running', 'source_root': str(root),
          'compiler_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(),
          'checker_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
# Independent oracle for the installed sysinfo app's eight xorshift rounds.
expected = 0x13579BDF
for _ in range(8):
    expected = (expected ^ (expected << 13)) & ((1 << 64) - 1)
    expected ^= expected >> 7
    expected = (expected ^ (expected << 17)) & ((1 << 64) - 1)
try:
    run(['bash', root / 'scripts/build-images.sh', '--variant', 'standard'], 'build.log',
        env=dict(os.environ, IN=str(compiler), BUILD_DIR=str(out / 'images'), GUI_PROFILE='window'))
    source = (root / 'kernel/kernel-root.in').read_text()
    source = re.sub(r'import "\.\./([^"]+)"', lambda m: 'import ' + json.dumps(str(root / m.group(1))), source)
    assert source.count('  shell(port)') == 1
    source = source.replace('  shell(port)', '  checked-admission(port)\n  shell(port)')
    source += '\nconst CHECKED-EXPECTED=' + str(expected) + '\n' + '''
var checked-heap:Int=0;var checked-free:Int=0;var checked-domains:Int=0;
var checked-caps:Int=0;var checked-objects:Int=0;var checked-exports:Int=0;
fn checked-stable()->void {
 if heap-next!=checked-heap || free-list!=checked-free || domain-count!=checked-domains || cap-count!=checked-caps || obj-arena-next!=checked-objects || dyn-count!=checked-exports || runtime-instance-live!=0 {panic("checked admission allocated resources");}
}
fn checked-deny(port:Int,image:Int,structural:Int)->void {
 if structural==1 && boot-image-find(19)!=0 {panic("checked malformed boot image exposed");}
 if sci-load-runtime-component(port,image,"checked-invalid",1,1,"6*7")!=-1 {panic("checked malformed SCI entered");}
 checked-stable();
}
fn checked-admission(port:Int)->void {
 let image=boot-image-find(19);let bytes=runtime-instance-image-boot-size(image);
 if image==0 || bytes<=64 || runtime-instance-image-valid(image,bytes)!=1 {panic("checked valid artifact refused");}
 if sci-load-runtime-component(port,image,"checked-valid",1,1,0)!=CHECKED-EXPECTED {panic("checked valid app failed");}
 checked-heap=heap-next;checked-free=free-list;checked-domains=domain-count;
 checked-caps=cap-count;checked-objects=obj-arena-next;checked-exports=dyn-count;
'''
    mutations = [(0, '7'), (24, 'bytes+1'), (16, '0x48000041'), (16, '0x100000040'),
                 (32, '-1'), (32, '4097'), (40, '-1'), (40, 'bytes'),
                 (48, '-1'), (48, '513'), (56, '-1'), (56, 'bytes')]
    for index, (offset, value) in enumerate(mutations):
        source += f' let saved{index}=load64(image+{offset});store64(image+{offset},{value});checked-deny(port,image,1);store64(image+{offset},saved{index});\n'
    source += '''
 let table=image+load64(image+56);let count=load64(image+48);
 if count<2 {panic("checked import fixture requires two calls");}
 let first=load64(table+8);let byte=load8(image+64+first);
 store8(image+64+first,0xE9);checked-deny(port,image,1);store8(image+64+first,byte);
 let second=load64(table+24);store64(table+24,first);checked-deny(port,image,1);store64(table+24,second);
 // A final unresolved name must refuse without allocating even a temporary
 // lifecycle, or patching/mapping earlier imports.
 let name=image+load64(table+(count - 1)*16);byte=load8(name);
 store8(name,63);
 if boot-image-find(19)!=image {panic("checked unresolved image lost structural admission");}
 checked-deny(port,image,0);store8(name,byte);
 let index=dyn-resolve-idx(image+load64(table+(count - 1)*16));
 if index<0 {panic("checked real import not restored");}
 let target=load64(dyn-fn-tab+index*8);let site=load64(table+(count - 1)*16+8);
 store64(dyn-fn-tab+index*8,load64(image+16)+site+5+2147483648);
 checked-deny(port,image,0);store64(dyn-fn-tab+index*8,target);
 // A valid importing image is not a self-contained shared provider.
 let library=lib-phys;let entry=lib-entry;let size=lib-size;let registered=lib-registered;
 if sci-register-library(port,image)!=-1 {panic("checked importing provider registered");}
 if lib-phys!=library || lib-entry!=entry || lib-size!=size || lib-registered!=registered {panic("checked provider readiness changed");}
 checked-stable();
 if posix-exec-image(port,image,bytes - 1,"/checked")!=LINUX-ENOEXEC {panic("checked file extent ignored");}
 checked-stable();
 if boot-image-find(19)!=image || runtime-instance-image-ready(image,bytes,1)!=1 {panic("checked image not restored");}
 if sci-load-runtime-component(port,image,"checked-recovery",1,1,0)!=CHECKED-EXPECTED {panic("checked recovery failed");}
 checked-stable();
 serial-write-cstr(port,"sci-admission: structural bounds import preflight provider refusal and recovery PASS");serial-nl(port);
 outb(0xf4,0x10);
}
'''
    (out / 'kernel.in').write_text(source)
    run([compiler, 'compile', '--path', out / 'kernel.in', '--entry', 'kernel-entry', '--emit', 'boot',
         '--trampoline', out / 'images/trampoline.bin', '--target', 'native', '--target-triple',
         'x86_64-unknown-none', '--linkage', 'static-lib', '--out', out / 'kernel.bin'], 'compile.log')
    image = (out / 'images/standard.bin').read_bytes()
    # The packager's immutable file handoff is at0xF00; the boot capsule
    # publishes that pointer to runtime hardware state0x40D0 after entry.
    table = struct.unpack_from('<Q', image, 0xF00)[0] - 0x100000
    magic, count = struct.unpack_from('<2Q', image, table)
    assert magic == 0x5350414345424F4F and count <= 64
    entries = []
    for i in range(count):
        kind, physical, size, _ = struct.unpack_from('<4Q', image, table + 16 + i * 32)
        path = out / f'kind-{kind}.sci'
        path.write_bytes(image[physical - 0x100000:physical - 0x100000 + size])
        entries.append(f'{kind}:{path}')
    run(['python3', root / 'scripts/pack-sci-image.py', out / 'kernel.bin', out / 'combined.bin', *entries], 'pack.log')
    command = ['qemu-system-x86_64', '-kernel', str(out / 'combined.bin'), '-m', '512M', '-display',
               'none', '-no-reboot', '-serial', 'file:' + str(out / 'serial.log'), '-device',
               'isa-debug-exit,iobase=0xf4,iosize=0x04']
    with (out / 'qemu.log').open('w') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=90)
    text = (out / 'serial.log').read_text()
    assert result.returncode == 33 and 'refusal and recovery PASS' in text, text
    report.update(status='passed', actual_structural_denials=14, actual_import_denials=2,
                  importing_provider_refused=True, truncated_file_refused=True, valid_app_runs=2,
                  command=command, kernel_sha256=hashlib.sha256((out / 'kernel.bin').read_bytes()).hexdigest())
    print('PASS actual SCI bounds/import/provider admission before allocation; real sysinfo recovery')
except Exception as error:
    report.update(status='failed', error=str(error))
    raise
finally:
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
