#!/usr/bin/env python3
"""Test distributable default protected GUI through serial and desktop command selection."""
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
p.add_argument('--image', type=Path, help='Already built ordinary standard image; otherwise build the default')
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
oracle = module.WindowEvidence(root)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


sources = [p for directory in ('components', 'kernel', 'protocol') for p in (root / directory).rglob('*.in')]
sources += [root / s for s in ('boot/multiboot.asm', 'scripts/build-images.sh', 'scripts/pack-gui-sci.py',
                             'scripts/pack-sci-image.py', 'scripts/gui-window-evidence.py')]
sources.append(Path(__file__).resolve())
snapshot = {str(path.relative_to(root)): sha(path) for path in sources}
(out / 'source-hashes.json').write_text(json.dumps(snapshot, indent=2) + '\n')
report = {'status': 'running', 'compiler': str(compiler), 'compiler_sha256': sha(compiler),
          'inputs': [], 'screenshots': [], 'matrix': []}
if a.image:
    image = a.image.resolve()
else:
    environment = dict(os.environ, IN=str(compiler), BUILD_DIR=str(out / 'images'))
    environment.pop('GUI_PROFILE', None)
    with (out / 'build.log').open('w') as log:
        subprocess.run(['bash', str(root / 'scripts/build-images.sh'), '--variant', 'standard'], cwd=root,
                       env=environment, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=240)
    image = out / 'images/standard.bin'
# Certify the shipped profile rather than inferring it from serial markers.
import struct
blob = image.read_bytes()
table = struct.unpack_from('<Q', blob, 0xf00)[0] - 0x100000
magic, count = struct.unpack_from('<QQ', blob, table)
assert magic == 0x5350414345424f4f
artifacts = {}
for index in range(count):
    kind, physical, size, reserved = struct.unpack_from('<QQQQ', blob, table + 16 + index * 32)
    artifacts[kind] = blob[physical - 0x100000:physical - 0x100000 + size]
assert 20 not in artifacts and 21 not in artifacts and all(k in artifacts for k in (22, 23, 24))
native_magic = int(re.search(r'NATIVE-PROTECTED-MAGIC = (0x[0-9a-fA-F]+)', (root / 'protocol/native-protected.in').read_text())[1], 0)
for kind, grants in ((23, 20), (24, 52)):
    app = artifacts[kind]
    assert struct.unpack_from('<Q', app, 8)[0] == grants
    assert struct.unpack_from('<QQQ', app, len(app) - 64) == (native_magic, 1, 3)
report['default_boot_kinds'] = [22, 23, 24]
report['trusted_gui_fallback_artifacts_absent'] = True
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
    serial.sendall(b'gui apps\n'); wait(READY)
    shot('initial', [('', ''), ('', 'edit')], 0)
    for value in ('6', 'shift-8', '7', 'ret'):
        key(value)
    shot('calculated-42', [('6*7', '42'), ('', 'edit')], 0)
    focus(1)
    for value in 'notes':
        key(value)
    key('ctrl-s')
    texts = [('6*7', '42'), ('notes', 'no disk')]
    shot('edited-save-no-disk', texts, 1)
    previous_generation = 0
    for index, action in enumerate((None, 'ctrl-g', 'ctrl-o', 'ctrl-g', 'ctrl-o', 'ctrl-g')):
        if action:
            key(action)
        layout = shot(f'matrix-{index}-preserved', texts, 1)
        assert layout['generation'] > previous_generation
        previous_generation = layout['generation']
        report['matrix'].append([layout['output_width'], layout['output_height'], layout['scale']])
        focus(0); key('ret')
        shot(f'matrix-{index}-left-pointer', texts, 0)
        focus(1)
        shot(f'matrix-{index}-right-pointer', texts, 1)
    assert set(map(tuple, report['matrix'])) == {(w, h, s) for w, h in ((1024, 768), (1280, 720), (1920, 1080)) for s in (2, 3)}
    key('esc')
    shot('editor-closed-calc-survives', [('6*7', '42'), None], 0)
    for value in ('backspace', '8', 'ret'):
        key(value)
    shot('survivor-48', [('6*8', '48'), None], 0)
    key('esc'); wait(CLOSED)
    shot('both-closed', [None, None], -1)
    start = len(data)
    serial.sendall(b'gui apps\n'); wait(READY, start)
    shot('reopened', [('', ''), ('', 'edit')], 0)
    key('esc'); key('esc'); wait(CLOSED, start)
    shot('reopened-closed', [None, None], -1)
    start = len(data)
    serial.sendall(b'runapp calc\n'); wait(b'calc: integer REPL', start)
    serial.sendall(b'2+3*4\n'); wait(b'calc: 2+3*4 = 14', start)
    serial.sendall(b'q\n'); wait(b'runapp: app-calc returned', start)
    # Launch through the actual desktop command registry in the same shipped
    # image. Returning must restore the desktop, not terminate its input loop.
    start = len(data)
    serial.sendall(b'desktop\n'); wait(b'space: compositor frame ready', start)
    for cycle in range(2):
        start = len(data)
        monitor.sendall(b'sendkey tab 30\n'); wait(b'space: launcher opened', start)
        for character in 'open calculator':
            value = 'spc' if character == ' ' else character
            monitor.sendall(f'sendkey {value} 30\n'.encode()); time.sleep(.06)
        start = len(data)
        monitor.sendall(b'sendkey ret 30\n'); wait(READY, start)
        for value in ('6', 'shift-8', '7', 'ret'): key(value)
        shot(f'desktop-{cycle}-calculated', [('6*7', '42'), ('', 'edit')], 0)
        focus(1)
        for value in ('u', 'i', 'ctrl-s'): key(value)
        shot(f'desktop-{cycle}-edited', [('6*7', '42'), ('ui', 'no disk')], 1)
        key('ctrl-g'); key('ctrl-o')
        shot(f'desktop-{cycle}-resized', [('6*7', '42'), ('ui', 'no disk')], 1)
        key('esc'); key('esc')
        wait(b'gui: desktop output/layout/input restored', start)
        # Actual key routing after return proves the caller desktop survived.
        marker = len(data)
        monitor.sendall(b'sendkey tab 30\n'); wait(b'space: launcher opened', marker)
        monitor.sendall(b'sendkey esc 30\n'); wait(b'space: launcher dismissed', marker)
    marker = len(data)
    monitor.sendall(b'sendkey esc 30\n'); wait(b'space: compositor exited', marker)
    report['actual_desktop_command_launches'] = 2
    report['actual_cpl3_profile'] = 3
    assert snapshot == {str(path.relative_to(root)): sha(path) for path in sources}, 'source changed during run'
    assert sha(compiler) == report['compiler_sha256']
    report['status'] = 'pass'
    print('PASS actual distributable default protected SCI windows: six output/text sizes, real keyboard/pointer, exact two-face labels/content/caret/status/hints, live resize preserves state, close/survivor/reopen and ordinary app afterward')
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
