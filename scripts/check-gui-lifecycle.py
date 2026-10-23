#!/usr/bin/env python3
"""Exercise >128 real standard-image GUI sessions; behavioral lifetime gate.

This checks input, pixels, alternating close order and surviving-client work.
Resource ownership and stale runtime handles require the separate core observer;
successful rendering alone does not establish physical reclamation.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import struct
import subprocess
import sys
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--in', dest='compiler', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--sessions', type=int, default=129)
    parser.add_argument('--observe', action='store_true',
                        help='instrument unchanged product entry/close calls with private ownership/ABA assertions')
    args = parser.parse_args()
    if args.sessions < 129:
        parser.error('--sessions must exceed128')
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        parser.error('--out must be new or empty')
    out.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    compiler = args.compiler.resolve()
    sources = [p for directory in ('components', 'kernel', 'protocol')
               for p in (root / directory).rglob('*.in')]
    sources += [root / name for name in ('boot/multiboot.asm', 'scripts/build-images.sh',
                'scripts/pack-gui-sci.py', 'scripts/pack-spdp-sci.py', 'scripts/pack-sci-image.py', 'scripts/gui-window-evidence.py')]
    sources.append(Path(__file__).resolve())
    sources.append(root / 'fixtures/gui-lifecycle/observer.in')
    snapshot = {str(p.relative_to(root)): sha(p) for p in sources}
    report = {'status': 'running', 'scope': 'standard GUI behavior; not physical ownership proof',
              'target_sessions': args.sessions, 'completed_sessions': 0,
              'compiler': str(compiler), 'compiler_sha256': sha(compiler),
              'sessions': []}
    (out / 'source-hashes.json').write_text(json.dumps(snapshot, indent=2) + '\n')
    glyphs = {}
    for match in re.finditer(r'fb-font-set\(([^)]+)\)', (root / 'components/font.in').read_text()):
        try:
            values = [int(value.strip(), 0) for value in match.group(1).split(',')]
        except ValueError:
            continue
        if len(values) == 9:
            glyphs[values[0]] = values[1:]
    environment = dict(os.environ, IN=str(compiler), BUILD_DIR=str(out / 'images'))
    with (out / 'build.log').open('w') as log:
        subprocess.run(['bash', str(root / 'scripts/build-images.sh'), '--variant', 'standard'],
                       cwd=root, env=environment, stdout=log, stderr=subprocess.STDOUT,
                       check=True, timeout=180)
    image = out / 'images/standard.bin'
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location('window_evidence', root / 'scripts/gui-window-evidence.py')
    window_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(window_module)
    window_oracle = window_module.WindowEvidence(root)
    readable = window_module.image_has_canvas(image)
    report['gui_profile'] = 'window' if readable else 'legacy'
    if args.observe:
        def absolute_imports(source, directory):
            return re.sub(r'(?m)^import "([^"]+)"',
                          lambda match: 'import ' + json.dumps(str((directory / match.group(1)).resolve())), source)

        manager = (root / 'components/gui-clients.in').read_text()
        manager = manager.replace('fn gui-admit(', 'fn gui-admit-implementation(', 1)
        manager = manager.replace('fn gui-retire(', 'fn gui-retire-implementation(', 1)
        manager += '\n' + (root / 'fixtures/gui-lifecycle/observer.in').read_text().replace('package space.kernel', '', 1)
        (out / 'manager.in').write_text(manager)
        window_manager = (root / 'components/gui-window-clients.in').read_text()
        window_manager = absolute_imports(window_manager, root / 'components')
        window_manager = window_manager.replace('fn gui-window-admit(', 'fn gui-window-admit-implementation(', 1)
        (out / 'window-manager.in').write_text(window_manager)
        session = (root / 'components/gui-session.in').read_text().replace('fn gui-session-run(', 'fn gui-session-run-implementation(', 1)
        (out / 'session.in').write_text(session)
        desktop = absolute_imports((root / 'components/desktop-hub.in').read_text(), root / 'components')
        desktop = desktop.replace(json.dumps(str(root / 'components/gui-clients.in')), json.dumps(str(out / 'manager.in')))
        desktop = desktop.replace(json.dumps(str(root / 'components/gui-window-clients.in')), json.dumps(str(out / 'window-manager.in')))
        desktop = desktop.replace(json.dumps(str(root / 'components/gui-session.in')), json.dumps(str(out / 'session.in')))
        (out / 'desktop.in').write_text(desktop)
        kernel = absolute_imports((root / 'kernel/kernel-root.in').read_text(), root / 'kernel')
        kernel = kernel.replace(json.dumps(str(root / 'components/desktop-hub.in')), json.dumps(str(out / 'desktop.in')))
        (out / 'kernel.in').write_text(kernel)
        with (out / 'observer-build.log').open('w') as log:
            subprocess.run([str(compiler), 'compile', '--path', str(out / 'kernel.in'),
                            '--entry', 'kernel-entry', '--emit', 'boot', '--trampoline',
                            str(out / 'images/trampoline.bin'), '--target', 'native',
                            '--target-triple', 'x86_64-unknown-none', '--linkage', 'static-lib',
                            '--out', str(out / 'observer-kernel.bin')], cwd=root,
                           stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
        blob = image.read_bytes()
        table = struct.unpack_from('<Q', blob, 0xf00)[0] - 0x100000
        magic, count = struct.unpack_from('<QQ', blob, table)
        assert magic == 0x5350414345424f4f
        specs = []
        for index in range(count):
            kind, physical, size, reserved = struct.unpack_from('<QQQQ', blob, table + 16 + index * 32)
            assert reserved == 0
            path = out / f'kind-{kind}.sci'
            path.write_bytes(blob[physical - 0x100000:physical - 0x100000 + size])
            specs.append(f'{kind}:{path}')
        image = out / 'observed.bin'
        with (out / 'observer-pack.log').open('w') as log:
            subprocess.run(['python3', str(root / 'scripts/pack-sci-image.py'),
                            str(out / 'observer-kernel.bin'), str(image), *specs], cwd=root,
                           stdout=log, stderr=subprocess.STDOUT, check=True, timeout=30)
        report['scope'] = 'standard GUI behavior plus private resource/ownership/ABA observer'
        report['observer_sha256'] = sha(root / 'fixtures/gui-lifecycle/observer.in')
    report['image_sha256'] = sha(image)
    ready = b'gui: calculator left, text editor right; click or Tab to focus, Escape closes focused app'
    closed = b'gui: both applications closed; stable session counters; returning to shell'
    data = bytearray()
    current_focus = 0
    live = [True, True]
    serial = monitor = process = None
    qlog = (out / 'qemu.log').open('w')

    def connect(path):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            channel = socket.socket(socket.AF_UNIX)
            try:
                channel.connect(str(path))
                channel.settimeout(.1)
                return channel
            except OSError:
                channel.close()
                time.sleep(.02)
        raise AssertionError(f'QEMU socket unavailable: {path}')

    def wait(marker, start=0):
        deadline = time.monotonic() + 30
        while marker not in data[start:]:
            if time.monotonic() > deadline:
                raise AssertionError((marker, data[-3000:]))
            try:
                chunk = serial.recv(65536)
                assert chunk, 'QEMU serial closed'
                data.extend(chunk)
            except socket.timeout:
                pass
            assert b'capacity exhausted' not in data[start:], 'retained capacity exhausted'
            assert b'gui: native session unavailable or failed' not in data[start:]
        (out / 'serial.log').write_bytes(data)

    def key(value):
        nonlocal current_focus
        code = {'ret': 10, 'tab': 9, 'esc': 27}.get(value)
        if code is None:
            code = 43 if value == 'shift-equal' else ord(value)
        marker = f'gui: app rendered key {code}\n'.encode()
        if value == 'tab':
            marker = b'gui: focus '
        if value == 'esc':
            marker = b'gui: focused app closed, retired token refused'
        start = len(data)
        monitor.sendall(f'sendkey {value} 20\n'.encode())
        wait(marker, start)
        time.sleep(.04)
        record['keys'].append(value)
        if value == 'tab' and live[1 - current_focus]:
            current_focus = 1 - current_focus
        if value == 'esc':
            live[current_focus] = False
            current_focus = next((slot for slot in range(2) if live[slot]), -1)

    def pixels(label, texts):
        path = out / 'frame.ppm'
        if readable:
            layout = window_oracle.layout(data)
            rgb = window_oracle.capture(monitor, path, layout)
            window_oracle.check(rgb, layout, texts, current_focus)
            receipt = {'state': label, 'sha256': sha(path), 'texts': texts, 'layout': layout, 'focused': current_focus}
            if cycle in (0, 1, 63, 127, args.sessions - 1):
                target = out / f'session-{cycle + 1:03}-{label}.ppm'
                path.rename(target)
                receipt['path'] = target.name
            record['pixels'].append(receipt)
            return
        path.unlink(missing_ok=True)
        monitor.sendall(f'screendump {path}\n'.encode())
        deadline = time.monotonic() + 5
        while (not path.exists() or path.stat().st_size < 1920 * 1080 * 3 + 17):
            assert time.monotonic() < deadline, 'screenshot timeout'
            time.sleep(.02)
        header = path.read_bytes().split(b'\n', 3)
        assert header[:3] == [b'P6', b'1920 1080', b'255']
        rgb = header[3]
        for slot, text in enumerate(texts):
            left = 40 + slot * 120
            for y in range(79, 97):
                for x in range(left - 1, left + 65):
                    expected = bytes((0, 0, 128))
                    if text is not None and 80 <= y < 96 and left <= x < left + 64:
                        row, column = y - 80, x - left
                        line = text[row // 8].ljust(8)
                        bits = glyphs.get(ord(line[column // 8]), [0] * 8)[row % 8]
                        expected = bytes((255, 255, 255) if bits & (128 >> (column % 8)) else (32, 32, 32))
                    actual = rgb[(y * 1920 + x) * 3:(y * 1920 + x) * 3 + 3]
                    assert actual == expected, (cycle, label, slot, x, y, actual, expected)
        receipt = {'state': label, 'sha256': sha(path), 'texts': texts}
        if cycle in (0, 1, 63, 127, args.sessions - 1):
            target = out / f'session-{cycle + 1:03}-{label}.ppm'
            path.rename(target)
            receipt['path'] = target.name
        record['pixels'].append(receipt)

    def editor_pointer_focus():
        nonlocal current_focus
        current_focus = 1
        if readable:
            record['pointer'] = window_oracle.focus_pointer(monitor, wait, data, 1)
            return
        for _ in range(25):
            monitor.sendall(b'mouse_move -100 -100\n')
            time.sleep(.02)
        for x, y in ((100, 80), (70, 8)):
            monitor.sendall(f'mouse_move {x} {y}\n'.encode())
            time.sleep(.1)
        start = len(data)
        monitor.sendall(b'mouse_button 1\n')
        wait(b'gui: pointer focused app ', start)
        monitor.sendall(b'mouse_button 0\n')
        time.sleep(.04)
        record['pointer'] = 'clamp to0,0 then170,88; leftpress/release editor'

    try:
        report['qemu'] = ['qemu-system-x86_64', '-kernel', str(image), '-m', '512M',
                          '-vga', 'std', '-display', 'none', '-no-reboot', '-serial',
                          f'unix:{out}/serial.sock,server=on,wait=on', '-monitor',
                          f'unix:{out}/monitor.sock,server=on,wait=off']
        process = subprocess.Popen(report['qemu'], stdout=qlog, stderr=subprocess.STDOUT)
        serial = connect(out / 'serial.sock')
        monitor = connect(out / 'monitor.sock')
        wait(b'space interactive shell')
        for cycle in range(args.sessions):
            current_focus = 0
            live[:] = [True, True]
            record = {'session': cycle + 1, 'close_first': 'calculator' if cycle % 2 else 'editor',
                      'keys': [], 'pixels': []}
            report['sessions'].append(record)
            start = len(data)
            serial.sendall(b'gui apps\n')
            wait(ready, start)
            for value in ('2', 'shift-equal', '3', 'ret'):
                key(value)
            if cycle % 16 == 0:
                editor_pointer_focus()
            else:
                key('tab')
            key('n')
            pixels('both-active', [('2+3', '5'), ('n', 'edit')])
            if cycle % 2:
                key('tab')
                key('esc')
                key('s')
                pixels('editor-survives', [None, ('ns', 'edit')])
            else:
                key('esc')
                key('ret')
                pixels('calculator-survives', [('2+3', '5'), None])
            key('esc')
            wait(closed, start)
            if args.observe:
                wait(f'gui-lifetime: resource and ABA observation {cycle + 1}\n'.encode(), start)
            pixels('both-closed', [None, None])
            report['completed_sessions'] += 1
            (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        assert snapshot == {str(p.relative_to(root)): sha(p) for p in sources}, 'source changed during run'
        assert sha(compiler) == report['compiler_sha256'], 'compiler changed during run'
        assert data.count(closed) == args.sessions
        if args.observe:
            assert data.count(b'gui-lifetime: resource and ABA observation ') == args.sessions
        report['status'] = 'pass'
        suffix = '; stable ownership/resources and stale-generation/alias ABA refusal' if args.observe else ''
        print(f'PASS {args.sessions} actual standard GUI sessions: keyboard, exact pixels, alternating close order, surviving app{suffix}')
    except Exception as error:
        report['status'] = 'fail'
        report['error'] = repr(error)
        raise
    finally:
        (out / 'serial.log').write_bytes(data)
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        for channel in (serial, monitor):
            if channel:
                channel.close()
        if process:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        qlog.close()


if __name__ == '__main__':
    main()
