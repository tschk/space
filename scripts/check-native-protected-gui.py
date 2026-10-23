#!/usr/bin/env python3
"""Actual CPL3 profile3 ring/snapshot/ownership proof, independent of GUI manager."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import time

root = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--mode', choices=['full','oom'], default='full')
a = p.parse_args()
out = a.out.resolve()
if out.exists() and any(out.iterdir()):
    p.error('--out must be new or empty')
out.mkdir(parents=True, exist_ok=True)
source = (root / 'kernel/kernel-root.in').read_text()
source = re.sub(r'import "\.\./([^"]+)"', lambda m: 'import ' + json.dumps(str(root / m[1])), source)
assert source.count('  shell(port)') == 1
entry = 'native-gui-oom-check' if a.mode == 'oom' else 'native-gui-check'
source = source.replace('  shell(port)', '  '+entry+'(port)\n  shell(port)')
source = 'import ' + json.dumps(str(root / 'components/native-protected.in')) + '\nimport ' + json.dumps(str(root / 'fixtures/native-protected-gui/checks.in')) + '\n' + source
(out / 'kernel.in').write_text(source)
tracked = ['protocol/native-protected.in','components/native-protected.in',
           'components/native-protected-image.in','components/native-protected-services.in',
           'components/native-protected-gui.in','components/native-protected-heap.in',
           'components/runtime-pixels.in','components/runtime-instance.in',
           'components/runtime-protected-owned.in','fixtures/native-protected-gui/client.in',
           'fixtures/native-protected-gui/editor.in','fixtures/native-protected-gui/checks.in']
source_hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in tracked}
for name in tracked:
    copied = out / 'source' / name
    copied.parent.mkdir(parents=True, exist_ok=True)
    copied.write_bytes((root / name).read_bytes())
with (out / 'compile.log').open('w') as log:
    commands = [['nasm', '-f', 'bin', str(root / 'boot/multiboot.asm'), '-o', str(out / 'trampoline.bin')]]
    for name, fixture in [('calc', 'client'), ('editor', 'editor')]:
        commands += [[a.compiler, 'compile', '--path', str(root / f'fixtures/native-protected-gui/{fixture}.in'),
                      '--entry', 'client-entry', '--emit', 'sci', '--base', '0x60000000', '--target', 'native',
                      '--target-triple', 'x86_64-unknown-none', '--out', str(out / f'{name}.raw.sci')],
                     ['python3', str(root / 'scripts/pack-gui-sci.py'), str(out / f'{name}.raw.sci'),
                      str(out / f'{name}.raw.component-metadata.json'), str(out / f'{name}.sci'), '--protected']]
    commands += [[a.compiler, 'compile', '--path', str(out / 'kernel.in'), '--entry', 'kernel-entry', '--emit', 'boot',
                  '--trampoline', str(out / 'trampoline.bin'), '--target', 'native', '--target-triple', 'x86_64-unknown-none',
                  '--linkage', 'static-lib', '--out', str(out / 'kernel.bin')],
                 ['python3', str(root / 'scripts/pack-sci-image.py'), str(out / 'kernel.bin'), str(out / 'combined.bin'),
                  f'270:{out}/calc.sci', f'271:{out}/editor.sci']]
    for cmd in commands:
        subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
received = bytearray()
serial = None
with (out / 'qemu.log').open('w') as log:
    sock = out / 'serial.sock'
    qemu = subprocess.Popen(['qemu-system-x86_64', '-kernel', str(out / 'combined.bin'), '-m', '32M' if a.mode == 'oom' else '512M', '-cpu', 'qemu64',
                             '-display', 'none', '-no-reboot', '-serial', f'unix:{sock},server=on,wait=on'], stdout=log, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 10
        while not sock.exists() and qemu.poll() is None and time.monotonic() < deadline:
            time.sleep(.02)
        serial = socket.socket(socket.AF_UNIX)
        serial.settimeout(.2)
        serial.connect(str(sock))
        deadline = time.monotonic() + 240
        while b'space interactive shell' not in received and time.monotonic() < deadline:
            try:
                block = serial.recv(65536)
                if not block:
                    break
                received.extend(block)
                if b'PANIC' in received or b'nanokernel fault handler halting' in received:
                    break
            except socket.timeout:
                if qemu.poll() is not None:
                    break
        text = received.decode(errors='replace')
        marker = 'native: actual protected GUI constrained memory exact refusal IF restoration peer recovery PASS' if a.mode == 'oom' else 'native: actual protected GUI ring snapshots notes faults deadline 140-instance lifetime PASS'
        assert marker in text and 'space interactive shell' in text, text
        serial.sendall(b'halt\n')
        report = {'status': 'passed', 'actual_compiled_cpl3_profile': 3, 'lifecycle_instances': 140,
                  'immutable_accepted_snapshots': True, 'read_only_ring': True, 'all_or_nothing_cross_page_receive': True,
                  'note_owned_bounce_and_live_grants': True, 'hardware_faults_abort_and_deadline': True,
                  'peer_generation_and_view_withdrawal': True, 'exact_lifetime_resource_accounting': True,
                  'compiler_sha256': hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),
                  'image_sha256': hashlib.sha256((out / 'combined.bin').read_bytes()).hexdigest()}
        if a.mode == 'oom':
            match = re.search(r'native: constrained memory budget (\d+) available (\d+)', text)
            assert match, text
            report = {'status':'passed','actual_compiled_cpl3_profile':3,'memory':'32M','required_frame_budget':int(match[1]),'available_frames_at_refusal':int(match[2]),'refused_activations':2,'exact_cap_domain_resource_bytes':True,'caller_if0_if1_restored':True,'peer_and_recovery_survive':True,'compiler_sha256':report['compiler_sha256'],'image_sha256':report['image_sha256']}
        report['source_sha256'] = source_hashes
        report['component_sha256'] = {name: hashlib.sha256((out / (name+'.sci')).read_bytes()).hexdigest() for name in ['calc','editor']}
        if a.mode == 'full':
            report['preallocation_malformed_authority_refusals'] = 21
            report['whole_canvas_front_hash_preserved_on_denial'] = True
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(f'PASS: actual protected GUI core ring/snapshot/lifetime; {out}')
    finally:
        (out / 'serial.log').write_bytes(received)
        if serial:
            serial.close()
        qemu.terminate()
        try:
            qemu.wait(timeout=3)
        except subprocess.TimeoutExpired:
            qemu.kill()
            qemu.wait()
