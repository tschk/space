#!/usr/bin/env python3
"""Actual protected readable session recovery after faults, abort, deadline and malformed replies."""
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
oracle = module.WindowEvidence(root)


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
image = out / 'combined.bin'
source = (root / 'kernel/kernel-root.in').read_text()
source = re.sub(r'import "\.\./([^"]+)"', lambda m: 'import ' + json.dumps(str(root / m[1])), source)
assert source.count('  shell(port)') == 1
source = source.replace('  shell(port)', '  gui-protected-demo(port)\n  shell(port)')
fixture = (root / 'fixtures/gui-protected-readable/session.in').read_text()
fixture = fixture.replace('import "../../components/gui-protected-session.in"', 'import ' + json.dumps(str(root / 'components/gui-protected-session-run.in')))
fixture = fixture.replace('while iteration < 2', 'while iteration < 6')
probe = """  let input-image = boot-image-find(22)
  if sci-load-retained-component(port, input-image, "unrelated-seat", SCI-INPUT-GRANTS, 0) != 0 { panic("protected GUI refusal peer setup") }
  let peer = runtime-instance-last-handle
  let page = sci-sync-page
  let peer-domain = sci-sync-domain
  runtime-instance-launch-guard = 1
  let refused = gui-protected-session-run(port)
  runtime-instance-launch-guard = 0
  if refused != 0 || gui-session-input-handle != 0 || gui-session-input-page != 0 || runtime-instance-record(peer, 1) == 0 || sci-sync-handle != peer || sci-sync-page != page || sci-sync-domain != peer-domain { panic("protected GUI stale capture retired peer") }
  if sci-admit-input-sync(peer-domain) != 1 || sci-sync-provenance-valid(peer-domain, 1) != 1 || sci-sync-enter(peer-domain, 0) != 0 { panic("protected GUI refused load peer execution") }
  if sci-proof-capture-input() != 1 { panic("protected GUI startup peer snapshot") }
  let watermark = runtime-instance-retained-watermark()
  if runtime-instance-new-trusted-retained(-1) != 0 || runtime-instance-new-trusted-retained(watermark + 1) != 0 || runtime-instance-new-trusted-retained(watermark) != 0 || runtime-instance-discard-new-trusted(peer, watermark) != -1 || runtime-instance-discard-new-trusted(peer + 0x100, watermark) != -1 { panic("protected GUI startup ownership refusal") }
  let active-watermark = runtime-instance-retained-watermark()
  if sci-load-retained-component(port, boot-image-find(272), "startup-active-control", SCI-INPUT-GRANTS, 0) != 7 { panic("protected GUI active setup result") }
  let active-owner = runtime-instance-new-trusted-retained(active-watermark)
  let active-record = runtime-instance-record(active-owner, 1)
  if active-owner == 0 || active-record == 0 { panic("protected GUI active setup owner") }
  let active-state = load64(active-record)
  let active-page = load64(active-state + 32)
  let old-head = load64(active-page)
  let old-tail = load64(active-page + 8)
  let active-frames = gui-protected-startup-free-count()
  store64(active-state + 296, 1)
  if runtime-instance-new-trusted-retained(active-watermark) != 0 || gui-protected-discard-input(active-owner, active-watermark) != 0 || gui-session-input-handle != active-owner || gui-session-input-page != 0 || runtime-instance-record(active-owner, 1) == 0 || load64(active-page) != old-head || load64(active-page + 8) != old-tail || gui-protected-startup-free-count() != active-frames { panic("protected GUI active state discarded") }
  store64(active-state + 296, 0)
  runtime-instance-active = active-state
  if runtime-instance-new-trusted-retained(active-watermark) != 0 || runtime-instance-discard-new-trusted(active-owner, active-watermark) != -1 || load64(active-page) != old-head || load64(active-page + 8) != old-tail || gui-protected-startup-free-count() != active-frames { panic("protected GUI active context discarded") }
  runtime-instance-active = 0
  if gui-protected-discard-input(active-owner, active-watermark) != 1 || gui-session-input-handle != 0 || runtime-instance-record(active-owner, 1) != 0 || sci-sync-handle != 0 { panic("protected GUI quarantine retry") }
  let protected-watermark = runtime-instance-retained-watermark()
  let protected-image = boot-image-find(270)
  store64(gui-protected-args, gui-protected-records + 48)
  store64(gui-protected-args + 8, 48)
  let protected-owner = gui-protected-launch(port, protected-image, runtime-instance-image-boot-size(protected-image), 20, gui-protected-args)
  if protected-owner <= 0 || runtime-instance-new-trusted-retained(protected-watermark) != 0 || runtime-instance-discard-new-trusted(protected-owner, protected-watermark) != -1 || native-protected-profile(protected-owner) != 3 { panic("protected GUI wrong execution kind discarded") }
  if runtime-instance-retire(protected-owner) != 0 || runtime-instance-release(protected-owner) != 0 { panic("protected GUI kind control cleanup") }
  let warm = 0
  while warm < 4 {
    let bad = boot-image-find(272 + (warm & 1))
    if gui-protected-session-run-images(port, bad, boot-image-find(270), boot-image-find(271)) != 0 || gui-session-input-handle != 0 || gui-session-input-page != 0 || sci-proof-restore(1) != 1 || sci-sync-enter(peer-domain, 0) != 0 { panic("protected GUI startup failed owner warmup") }
    warm += 1
  }
  let heap = heap-next
  let frames = gui-protected-startup-free-count()
  let caps = cap-count
  let domains = domain-count
  let objects = obj-arena-next
  let live = runtime-instance-live
  let caller = current-cap
  let callback = native-protected-note-backend
  let attempt = 0
  while attempt < 140 {
    let bad = boot-image-find(272 + (attempt & 1))
    if gui-protected-session-run-images(port, bad, boot-image-find(270), boot-image-find(271)) != 0 || gui-session-input-handle != 0 || gui-session-input-page != 0 || sci-sync-handle != 0 || runtime-instance-record(peer, 1) == 0 { panic("protected GUI startup failed owner cleanup") }
    if heap-next != heap || gui-protected-startup-free-count() != frames || cap-count != caps || domain-count != domains || obj-arena-next != objects || runtime-instance-live != live || current-cap != caller || native-protected-note-backend != callback { panic("protected GUI startup failed owner resources") }
    if sci-proof-restore(1) != 1 || sci-sync-enter(peer-domain, 0) != 0 { panic("protected GUI startup failed owner peer resume") }
    attempt += 1
  }
  serial-write-cstr(port, "gui-protected: nonzero malformed startup 140 exact cleanups unrelated peer survives PASS"); serial-nl(port)
  if runtime-instance-retire(peer) != 0 || runtime-instance-release(peer) != 0 { panic("protected GUI refusal peer release") }
  serial-write-cstr(port, "gui-protected: wrapper refusal preserves unrelated retained peer PASS"); serial-nl(port)
"""
fixture = fixture.replace('  let iteration = 0', probe + '  let iteration = 0')
fixture += """
fn gui-protected-startup-free-count() -> Int {
  let count = 0
  let cursor = free-list
  while cursor != 0 {
    if cursor < 0x100000 || cursor >= heap-end || (cursor & 4095) != 0 || count > 1048576 { panic("protected GUI startup free list") }
    count += 1
    cursor = load64(cursor)
  }
  return count
}
"""
(out / 'fixture.in').write_text(fixture)
source = 'import ' + json.dumps(str(out / 'fixture.in')) + '\n' + source

(out / 'kernel.in').write_text(source)
commands = [['nasm', '-f', 'bin', str(root / 'boot/multiboot.asm'), '-o', str(out / 'trampoline.bin')]]
for name in ('calc', 'editor'):
    client = root / f'components/app-protected-window-{name}.in'
    if name == 'calc':
        app = client.read_text()
        app = re.sub(r'import "([^"]+)"', lambda m: 'import ' + json.dumps(str((root / 'components' / m[1]).resolve())), app)
        app += '\ninterrupt fn abort() -> void {}\n'
        app = app.replace('    if code == -1', """    if code == 1 { store64(NATIVE-PROTECTED-IMAGE, 0) }
    if code == 2 { store64(0x70000000, 0) }
    if code == 3 { store8(0x70001000, 0xc3); return invoke-native1(0x70001000, 0) }
    if code == 4 { abort(); return -4 }
    if code == 5 { while true {} }
    if code == 6 { chan-page-send-frame(0x70000000, SPDP-OBJ-SURFACE, SPDP-SURFACE-COMMIT, 0, 0) }
    if code == -1""")
        client = out / 'hostile-readable-calc.in'
        client.write_text(app)
    commands += [[str(compiler), 'compile', '--path', str(client),
                  '--entry', 'client-entry', '--emit', 'sci', '--base', '0x60000000', '--target', 'native',
                  '--target-triple', 'x86_64-unknown-none', '--out', str(out / f'{name}.raw.sci')],
                 ['python3', str(root / 'scripts/pack-gui-sci.py'), str(out / f'{name}.raw.sci'),
                  str(out / f'{name}.raw.component-metadata.json'), str(out / f'{name}.sci'), '--protected']]
for kind, fixture_name in ((272, 'nonzero'), (273, 'malformed')):
    commands += [[str(compiler), 'compile', '--path', str(root / f'fixtures/gui-protected-readable/input-{fixture_name}.in'),
                  '--entry', 'input-poll-entry', '--emit', 'sci', '--base', '0x50000000', '--target', 'native',
                  '--target-triple', 'x86_64-unknown-none', '--out', str(out / f'input-{kind}.sci')]]
commands += [[str(compiler), 'compile', '--path', str(root / 'components/input.in'), '--entry', 'input-poll-entry',
              '--emit', 'sci', '--base', '0x50000000', '--target', 'native', '--target-triple', 'x86_64-unknown-none',
              '--out', str(out / 'input.sci')],
             [str(compiler), 'compile', '--path', str(out / 'kernel.in'), '--entry', 'kernel-entry', '--emit', 'boot',
              '--trampoline', str(out / 'trampoline.bin'), '--target', 'native', '--target-triple', 'x86_64-unknown-none',
              '--linkage', 'static-lib', '--out', str(out / 'kernel.bin')],
             ['python3', str(root / 'scripts/pack-sci-image.py'), str(out / 'kernel.bin'), str(image),
              f'22:{out}/input.sci', f'270:{out}/calc.sci', f'271:{out}/editor.sci',
              f'272:{out}/input-272.sci', f'273:{out}/input-273.sci']]
with (out / 'build.log').open('w') as log:
    for command in commands:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=240)
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
    rgb = oracle.capture(monitor, path, layout)
    oracle.check(rgb, layout, texts, focused)
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
    wait(b'gui-protected: nonzero malformed startup 140 exact cleanups unrelated peer survives PASS')
    wait(b'gui-protected: wrapper refusal preserves unrelated retained peer PASS')
    cursor = 0
    for index in range(6):
        wait(READY, cursor)
        shot(f'fault-{index}-initial', [('', ''), ('', 'edit')], 0)
        start = len(data)
        trigger = ('ctrl-a', 'ctrl-b', 'ctrl-c', 'ctrl-d', 'ctrl-e', 'ctrl-f')[index]
        report['inputs'].append({'fault_key': trigger, 'serial_offset': start})
        monitor.sendall(f'sendkey {trigger} 30\n'.encode())
        wait(b'gui-protected: failed app retired; survivor interactive', start)
        for value in ('o', 'k', 'ctrl-s'):
            key(value)
        shot(f'fault-{index}-peer-interactive', [None, ('ok', 'no disk')], 1)
        key('esc')
        wait(CLOSED, start)
        cursor = data.index(CLOSED, start) + len(CLOSED)
    wait(b'gui-protected: actual CPL3 readable session PASS')
    wait(b'space interactive shell')
    assert snapshot == {str(path.relative_to(root)): sha(path) for path in sources}, 'source changed during run'
    assert sha(compiler) == report['compiler_sha256']
    report['status'] = 'pass'
    report['actual_cpl3_profile'] = 3
    report['trusted_input_driver'] = True
    report['session_failures'] = ['text-write', 'ring-write', 'canvas-execute', 'abort', 'deadline', 'malformed-reply']
    report['forced_wrapper_refusal_peer_survives'] = True
    report['failed_startup_exact_cleanups'] = 140
    report['normal_nonzero_and_malformed_zero_startup'] = True
    print('PASS actual protected readable GUI session: fault/abort/deadline/malformed peer recovery, real keyboard and exact peer pixels, stale input-loader ownership refusal')
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
