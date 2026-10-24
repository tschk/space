#!/usr/bin/env python3
"""Actual default standard-image dispatch and peer recovery with controlled hostile GUI app."""
import argparse
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import socket
import subprocess
import sys
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', required=True, type=Path)
p.add_argument('--out', required=True, type=Path)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
out = a.out.resolve()
if out.exists() and any(out.iterdir()):
    p.error('--out must be new or empty')
out.mkdir(parents=True, exist_ok=True)
compiler = a.compiler.resolve()
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('window_evidence', root / 'scripts/gui-window-evidence.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
oracle = module.WindowEvidence(root,protected=True)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


sources = [p for directory in ('components', 'kernel', 'protocol') for p in (root / directory).rglob('*.in')]
sources += [root / s for s in ('boot/multiboot.asm', 'scripts/build-images.sh', 'scripts/pack-gui-sci.py',
                             'scripts/pack-sci-image.py', 'scripts/gui-window-evidence.py',
                             'fixtures/gui-protected-readable/session.in',
                             'fixtures/gui-protected-readable/input-nonzero.in',
                             'fixtures/gui-protected-readable/input-malformed.in')]
sources.append(Path(__file__).resolve())
snapshot = {str(path.relative_to(root)): sha(path) for path in sources}
(out / 'source-hashes.json').write_text(json.dumps(snapshot, indent=2) + '\n')
report = {'status': 'running', 'compiler': str(compiler), 'compiler_sha256': sha(compiler),
          'inputs': [], 'screenshots': [], 'matrix': []}
images = out / 'images'
environment = dict(os.environ, IN=str(compiler), BUILD_DIR=str(images))
environment.pop('GUI_PROFILE', None)
with (out / 'build.log').open('w') as log:
    subprocess.run(['bash', str(root / 'scripts/build-images.sh'), '--variant', 'standard'],
                   env=environment, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=240)
# Keep the actual default kernel, editor, seat and installed CLI artifacts.
# Only the calculator becomes an explicitly controlled hostile test artifact.
app = (root / 'components/app-protected-window-calc.in').read_text()
app = re.sub(r'import "([^"]+)"', lambda m: 'import ' + json.dumps(str((root / 'components' / m[1]).resolve())), app)
app += '\ninterrupt fn abort() -> void {}\n'
app = app.replace('    if code == -1', """    if code == 1 { store64(NATIVE-PROTECTED-IMAGE, 0) }
    if code == 2 { store64(0x70000000, 0) }
    if code == 3 { store8(0x70001000, 0xc3); return invoke-native1(0x70001000, 0) }
    if code == 4 { abort(); return -4 }
    if code == 5 { while true {} }
    if code == 6 { chan-page-send-frame(0x70000000, SPDP-OBJ-SURFACE, SPDP-SURFACE-COMMIT, 0, 0) }
    if code == -1""")
(out / 'hostile-readable-calc.in').write_text(app)
with (out / 'hostile-build.log').open('w') as log:
    subprocess.run([str(compiler), 'compile', '--path', str(out / 'hostile-readable-calc.in'),
                    '--entry', 'client-entry', '--emit', 'sci', '--base', '0x60000000', '--target', 'native',
                    '--target-triple', 'x86_64-unknown-none', '--out', str(out / 'hostile.raw.sci')],
                   stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
    subprocess.run(['python3', str(root / 'scripts/pack-gui-sci.py'), str(out / 'hostile.raw.sci'),
                    str(out / 'hostile.raw.component-metadata.json'), str(out / 'hostile.sci'), '--protected'],
                   stdout=log, stderr=subprocess.STDOUT, check=True, timeout=30)
import struct
blob = (images / 'standard.bin').read_bytes()
table = struct.unpack_from('<Q', blob, 0xf00)[0] - 0x100000
magic, count = struct.unpack_from('<QQ', blob, table)
assert magic == 0x5350414345424f4f
specs = []
for index in range(count):
    kind, physical, size, reserved = struct.unpack_from('<QQQQ', blob, table + 16 + index * 32)
    assert reserved == 0
    artifact = out / f'kind-{kind}.sci'
    artifact.write_bytes(blob[physical - 0x100000:physical - 0x100000 + size])
    if kind == 23: artifact = out / 'hostile.sci'
    specs.append(f'{kind}:{artifact}')
image = out / 'controlled-hostile-standard.bin'
with (out / 'pack.log').open('w') as log:
    subprocess.run(['python3', str(root / 'scripts/pack-sci-image.py'), str(images / 'kernel-standard.bin'), str(image), *specs],
                   stdout=log, stderr=subprocess.STDOUT, check=True, timeout=30)
report['original_default_image_sha256'] = sha(images / 'standard.bin')
report['scope'] = 'unchanged default kernel/dispatcher/seat/editor/CLI; only calculator is controlled hostile fixture'
report['image_sha256'] = sha(image)
data = bytearray()
serial = monitor = process = None
qlog = (out / 'qemu.log').open('w')
READY = b'gui: calculator left, text editor right; click or Tab to focus, Escape closes focused app'
CLOSED = b'gui: both applications closed; stable session counters; returning to shell'


def connect(path):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        channel = socket.socket(socket.AF_UNIX)
        try:
            channel.connect(str(path)); channel.settimeout(.1); return channel
        except OSError:
            channel.close(); time.sleep(.02)
    raise AssertionError(f'QEMU socket unavailable: {path}')


def wait(marker, start=0):
    deadline = time.monotonic() + 30
    while marker not in data[start:]:
        assert time.monotonic() < deadline, (marker, data[-3500:])
        try:
            chunk = serial.recv(65536)
            assert chunk, 'QEMU serial closed'
            data.extend(chunk)
        except socket.timeout:
            pass
        assert b'gui: native session unavailable or failed' not in data[start:], data[-3000:]
    (out / 'serial.log').write_bytes(data)


def key(value):
    start = len(data)
    report['inputs'].append({'key': value, 'serial_offset': start})
    monitor.sendall(f'sendkey {value} 30\n'.encode())
    if value in ('ctrl-g', 'ctrl-o'):
        prefix = b'gui-window: mode '
        wait(prefix, start)
        wait(b'\n', data.index(prefix, start))
    elif value == 'esc':
        wait(b'gui: focused app closed, retired token refused', start)
    elif value == 'tab':
        wait(b'gui: focus ', start)
    else:
        code = {'ret': 10, 'backspace': 8, 'shift-8': 42, 'ctrl-s': 19}.get(value)
        if code is None:
            code = ord(value)
        wait(f'gui: app rendered key {code}\n'.encode(), start)
    time.sleep(.08)


def move(x, y):
    layout = oracle.layout(data)
    count = max(layout['output_width'], layout['output_height']) // 100 + 3
    for _ in range(count):
        monitor.sendall(b'mouse_move -100 -100\n'); time.sleep(.02)
    while x or y:
        dx, dy = min(x, 100), min(y, 100)
        monitor.sendall(f'mouse_move {dx} {dy}\n'.encode())
        x -= dx; y -= dy; time.sleep(.03)
    time.sleep(.1)


def focus(slot):
    layout = oracle.layout(data)
    left = layout['left' if slot == 0 else 'right']
    x, y = left + layout['width'] // 2, layout['top'] + 8 * layout['scale']
    move(x, y)
    start = len(data)
    monitor.sendall(b'mouse_button 1\n')
    wait(b'gui: pointer focused app ', start)
    monitor.sendall(b'mouse_button 0\n')
    report['inputs'].append({'pointer_focus': slot, 'x': x, 'y': y, 'layout': layout})
    # Park in unused background so the exact text oracle also detects any holes
    # left by incorrectly clearing the old cursor after client compositing.
    move(10, layout['output_height'] - 20)


def shot(name, texts, focused):
    layout = oracle.layout(data)
    path = out / (name + '.ppm')
    rgb = oracle.capture_checked(monitor, path, layout, texts, focused)
    report['screenshots'].append({'name': path.name, 'sha256': sha(path), 'layout': layout,
                                  'texts': texts, 'focused': focused})
    return layout


try:
    command = ['qemu-system-x86_64', '-kernel', str(image), '-m', '512M', '-vga', 'std',
               '-display', 'none', '-no-reboot', '-serial', f'unix:{out}/serial.sock,server=on,wait=on',
               '-monitor', f'unix:{out}/monitor.sock,server=on,wait=off']
    report['qemu'] = command
    process = subprocess.Popen(command, stdout=qlog, stderr=subprocess.STDOUT)
    serial, monitor = connect(out / 'serial.sock'), connect(out / 'monitor.sock')
    wait(b'space interactive shell')
    for index in range(6):
        cursor = len(data)
        serial.sendall(b'gui apps\n'); wait(READY, cursor)
        shot(f'fault-{index}-initial', [('', ''), ('', 'edit')], 0)
        start = len(data)
        trigger = ('ctrl-a', 'ctrl-b', 'ctrl-c', 'ctrl-d', 'ctrl-e', 'ctrl-f')[index]
        report['inputs'].append({'fault_key': trigger, 'serial_offset': start})
        monitor.sendall(f'sendkey {trigger} 30\n'.encode())
        wait(b'gui-protected: failed app retired; survivor interactive', start)
        for value in ('o', 'k', 'ctrl-s'): key(value)
        shot(f'fault-{index}-peer-interactive', [None, ('ok', 'no disk')], 1)
        key('esc'); wait(CLOSED, start)
    marker = len(data)
    serial.sendall(b'runapp calc\n'); wait(b'calc: integer REPL', marker)
    serial.sendall(b'2+3*4\n'); wait(b'calc: 2+3*4 = 14', marker)
    serial.sendall(b'q\n'); wait(b'runapp: app-calc returned', marker)
    assert snapshot == {str(path.relative_to(root)): sha(path) for path in sources}, 'source changed during run'
    assert sha(compiler) == report['compiler_sha256']
    report['status'] = 'pass'
    report['actual_cpl3_profile'] = 3
    report['trusted_input_driver'] = True
    report['session_failures'] = ['text-write', 'ring-write', 'canvas-execute', 'abort', 'deadline', 'malformed-reply']
    report['actual_default_dispatcher'] = True
    print('PASS actual default-image protected GUI session: fault/abort/deadline/malformed peer recovery, real keyboard and exact peer pixels, ordinary CLI survives')
except Exception as error:
    report['status'] = 'fail'; report['error'] = repr(error); raise
finally:
    (out / 'serial.log').write_bytes(data)
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    for channel in (serial, monitor):
        if channel: channel.close()
    if process:
        process.terminate()
        try: process.wait(timeout=3)
        except subprocess.TimeoutExpired: process.kill(); process.wait()
    qlog.close()
