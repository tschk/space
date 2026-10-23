#!/usr/bin/env python3
"""Actual readable protected SCI clients: 129 sessions, exact lifetime and launch authority."""
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
a = p.parse_args()
out = a.out.resolve()
if out.exists() and any(out.iterdir()):
    p.error('--out must be new or empty')
out.mkdir(parents=True, exist_ok=True)
source = (root / 'kernel/kernel-root.in').read_text()
source = re.sub(r'import "\.\./([^"]+)"', lambda m: 'import ' + json.dumps(str(root / m[1])), source)
assert source.count('  shell(port)') == 1
entry = 'gui-protected-lifetime-check'
source = source.replace('  shell(port)', '  '+entry+'(port)\n  shell(port)')
source = 'import ' + json.dumps(str(root / 'components/native-protected.in')) + '\nimport ' + json.dumps(str(root / 'fixtures/gui-protected-readable/lifetime.in')) + '\n' + source
(out / 'kernel.in').write_text(source)
tracked = [str(path.relative_to(root)) for directory in ('components', 'kernel', 'protocol')
           for path in (root / directory).rglob('*.in')]
tracked += ['fixtures/gui-protected-readable/lifetime.in', 'scripts/check-gui-protected-lifetime.py',
            'scripts/pack-gui-sci.py', 'scripts/pack-sci-image.py', 'boot/multiboot.asm']
source_hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in tracked}
for name in tracked:
    copied = out / 'source' / name
    copied.parent.mkdir(parents=True, exist_ok=True)
    copied.write_bytes((root / name).read_bytes())
with (out / 'compile.log').open('w') as log:
    commands = [['nasm', '-f', 'bin', str(root / 'boot/multiboot.asm'), '-o', str(out / 'trampoline.bin')]]
    for name in ('calc', 'editor'):
        commands += [[a.compiler, 'compile', '--path', str(root / f'components/app-protected-window-{name}.in'),
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
    qemu = subprocess.Popen(['qemu-system-x86_64', '-kernel', str(out / 'combined.bin'), '-m', '512M', '-cpu', 'qemu64',
                             '-vga', 'std', '-display', 'none', '-no-reboot', '-serial', f'unix:{sock},server=on,wait=on'], stdout=log, stderr=subprocess.STDOUT)
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
                if (b'PANIC:' in received and b'\n' in received.split(b'PANIC:', 1)[1]) or b'nanokernel fault handler halting' in received:
                    break
            except socket.timeout:
                if qemu.poll() is not None:
                    break
        text = received.decode(errors='replace')
        marker = 'gui-protected: actual readable clients 129 sessions 258 instances resources ABA launch-revocation PASS'
        assert marker in text and 'space interactive shell' in text, text
        serial.sendall(b'halt\n')
        assert source_hashes == {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in tracked}, 'source drift'
        report = {'source_hashes': source_hashes, 'status': 'passed', 'actual_compiled_cpl3_profile': 3, 'sessions': 129,
                  'lifecycle_instances': 258, 'alternating_close_and_peer_input': True,
                  'stale_generation_refusal': True, 'exact_lifetime_resource_accounting': True,
                  'once_owned_launch_scope_revocation': True,
                  'compiler_sha256': hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),
                  'image_sha256': hashlib.sha256((out / 'combined.bin').read_bytes()).hexdigest()}
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(f'PASS: actual protected readable GUI129 sessions; {out}')
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
