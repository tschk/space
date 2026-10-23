#!/usr/bin/env python3
"""Record actual protected-loader admission for pinned FLTK; refusal stays blocked."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', type=Path, required=True)
p.add_argument('--app', type=Path, required=True)
p.add_argument('--source-root', type=Path, default=ROOT)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
a.out = a.out.resolve()
a.source_root = a.source_root.resolve()
if a.out.exists() and any(a.out.iterdir()):
    p.error('--out must be new or empty')
a.out.mkdir(parents=True, exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = ROOT / 'fixtures/applications/fltk-1.3.9.json'
app = json.loads(manifest.read_text())['apps'][0]
assert sha(a.app) == app['sha256'] and a.app.stat().st_size == app['size_bytes'], 'pinned artifact mismatch'
sources = [path for directory in ('components', 'kernel', 'protocol', 'services')
           for path in (a.source_root / directory).rglob('*.in')]
sources.append(a.source_root / 'boot/multiboot.asm')
inventory = {str(path.relative_to(a.source_root)): sha(path) for path in sources}
report = {'application_status': 'not-tested', 'execution_started': False,
          'scope': 'actual protected ELF validator; never invokes the foreign payload at CPL0',
          'app_sha256': sha(a.app), 'manifest_sha256': sha(manifest),
          'compiler_sha256': sha(a.compiler), 'source_sha256': inventory}
try:
    source = a.out / 'probe.in'
    source.write_text('package space.kernel\nimport ' + json.dumps(str(a.source_root / 'kernel/kernel-root.in')) + '\nimport ' + json.dumps(str(a.source_root / 'components/linux-process.in')) + '''
fn gui-admission-entry(mb:Int)->Int{
 let port=com1();serial-init(port);
 let heap=heap-next;let free=free-list;let domains=domain-count;let caps=cap-count;
 let i=0;
 while i<2{
  let result=linux-process-elf-entry(0x10000000,''' + str(app['size_bytes']) + ''');
  serial-write-cstr(port,"fluid: protected admission ");serial-write-dec-wide(port,result);serial-nl(port);
  if result!=-8{panic("fluid admission expectation changed; add protected execution scenario");}
  i+=1;
 }
 if heap-next!=heap || free-list!=free || domain-count!=domains || cap-count!=caps{panic("fluid refusal mutated resources");}
 serial-write-cstr(port,"fluid: allocation-free refusal; payload not entered PASS");serial-nl(port);
 outb(0xf4,0x10);while true{hlt();}return 0;
}
''')
    trampoline = a.out / 'trampoline.bin'
    subprocess.run(['nasm', '-f', 'bin', str(a.source_root / 'boot/multiboot.asm'), '-o', str(trampoline)], check=True, timeout=30)
    kernel = a.out / 'kernel.bin'
    command = [str(a.compiler.resolve()), 'compile', '--path', str(source), '--entry', 'gui-admission-entry',
               '--emit', 'boot', '--trampoline', str(trampoline), '--target', 'native',
               '--target-triple', 'x86_64-unknown-none', '--linkage', 'static-lib', '--out', str(kernel)]
    with (a.out / 'compile.log').open('w') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
    command = ['qemu-system-x86_64', '-kernel', str(kernel), '-m', '256M', '-display', 'none', '-no-reboot',
               '-serial', 'file:' + str(a.out / 'serial.log'), '-device', 'isa-debug-exit,iobase=0xf4,iosize=0x04',
               '-device', 'loader,file=' + str(a.app.resolve()) + ',addr=0x10000000,force-raw=on']
    with (a.out / 'qemu.log').open('w') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=30)
    serial = (a.out / 'serial.log').read_text()
    assert result.returncode == 33 and serial.count('fluid: protected admission -8\n') == 2, serial
    assert 'fluid: allocation-free refusal; payload not entered PASS\n' in serial, serial
    changed = [name for name, digest in inventory.items() if sha(a.source_root / name) != digest]
    assert not changed and sha(a.compiler) == report['compiler_sha256'] and sha(a.app) == report['app_sha256']
    report.update(application_status='blocked', admission_return=-8, probe_status='passed',
                  source_changed_during_run=changed, kernel_sha256=sha(kernel), qemu_command=command,
                  blockers=['ELF PIE/dynamic linker and shared dependencies', 'X11 client/server compatibility and owned GUI adapter'])
except Exception as error:
    report.update(application_status='test-error', error=str(error))
finally:
    (a.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['application_status'].upper() + ': original FLTK fluid; no Space execution; ' + str(a.out / 'report.json'))
raise SystemExit(1)
