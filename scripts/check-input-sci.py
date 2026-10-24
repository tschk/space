#!/usr/bin/env python3
"""Run one retained input SCI: real PS/2 keys consumed once, no app-seat claim."""
from boot_fixture_layout import stage_fixture
import argparse
import hashlib
import json
from pathlib import Path
import socket
import struct
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--in', dest='compiler', required=True)
parser.add_argument('--build-dir', type=Path, default=Path('/tmp/space-input-sci'))
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
out = args.build_dir.resolve()
out.mkdir(parents=True, exist_ok=True)
compiler = Path(args.compiler).resolve()
compiler_hash = hashlib.sha256(compiler.read_bytes()).hexdigest()
(out/'compiler.json').write_text(json.dumps({'path': str(compiler), 'sha256': compiler_hash,
    'version': subprocess.check_output([str(compiler), '--version'], text=True).strip()}, indent=2)+'\n')
sources = [root/'protocol/keyboard.in', root/'components/input.in', root/'components/channel.in', root/'protocol/input.in',
           root/'components/sci-loader.in', root/'components/shell.in', root/'components/shell-common.in']
snapshot = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
# Execute the actual bounded mouse parser with a continuous synthetic device:
# 32-byte boundaries intentionally split three-byte packets across calls.
input_source = (root/'components/input.in').read_text()
mouse_functions = []
for name in ('mouse-process-byte', 'mouse-poll'):
    start = input_source.index('fn '+name+'(')
    mouse_functions.append(input_source[start:input_source.index('\n}', start)+2])
mouse_source = """
const PS2-DATA=96;
var mouse-ready:Int=1;var mouse-cycle:Int=0;
var mouse-buf0:Int=0;var mouse-buf1:Int=0;var mouse-buf2:Int=0;
var mouse-buttons:Int=0;var mouse-x:Int=0;var mouse-y:Int=0;
var mouse-screen-w:Int=800;var mouse-screen-h:Int=600;
var reads:Int=0;
fn mouse-has-data()->Int{if reads<72{return 1;}return 0;}
fn inb(port:Int)->Int{let part=reads%3;reads+=1;if part==0{return 8;}if part==1{return 1;}return 0;}
"""+'\n'.join(mouse_functions)+"""
fn main()->Int{
 if mouse-poll()!=10 || reads!=32 || mouse-cycle!=2 || mouse-x!=10{return 1;}
 if mouse-poll()!=11 || reads!=64 || mouse-cycle!=1 || mouse-x!=21{return 2;}
 if mouse-poll()!=3 || reads!=72 || mouse-cycle!=0 || mouse-x!=24{return 3;}
 if mouse-poll()!=0 || reads!=72{return 4;}
 mouse-ready=0;reads=0;if mouse-poll()!=0 || reads!=0{return 5;}
 return 42;
}
"""
(out/'mouse-budget.in').write_text(mouse_source)
for profile in ('default', 'lean', 'harden'):
    checked = subprocess.run([str(compiler), 'compile', '--path', str(out/'mouse-budget.in'),
        '--target', 'jit', '--profile', profile, '--out', str(out/'mouse-budget'), '--json'],
        capture_output=True, text=True, check=True, timeout=30)
    (out/f'mouse-budget-{profile}.json').write_text(checked.stdout)
    report = json.loads(checked.stdout)
    assert report.get('success') and report.get('eval_result') == {'Int': 42}, report
subprocess.run(['nasm', '-f', 'bin', str(root/'boot/multiboot.asm'), '-o', str(out/'trampoline.bin')], check=True)
for source, entry, extra, output in [
    ('kernel/kernel-root.in', 'kernel-entry', ['--emit', 'boot', '--trampoline', str(out/'trampoline.bin'), '--linkage', 'static-lib'], 'kernel.bin'),
    ('components/input.in', 'input-poll-entry', ['--emit', 'sci', '--base', '0x50000000'], 'input.sci'),
]:
    with (out/(output+'.log')).open('w') as log:
        subprocess.run([str(compiler), 'compile', '--path', str(root/source), '--entry', entry,
            '--target', 'native', '--target-triple', 'x86_64-unknown-none', *extra,
            '--out', str(out/output)], stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
    assert (out/output).is_file(), (out/(output+'.log')).read_text()
# This existing Input manifest's ordinal serial/input bits match Space's fixed bits.
metadata = json.loads((out/'input.component-metadata.json').read_text())
assert metadata['component'] == 'space.input/Input' and metadata['target'] == 'x86_64-unknown-none'
assert [(c['name'], c['capability_type'], c['args']) for c in metadata['capabilities_required']] == [
    ('serial', 'DebugConsole', ['write']), ('input', 'InputDevice', ['publish'])]
client = (out/'input.sci').read_bytes()
assert struct.unpack_from('<Q', client, 8)[0] == 3
image = bytearray((out/'kernel.bin').read_bytes())
offset = 0x2f0000-0x100000
assert len(image) <= offset and len(client) <= 0x10000
assert 0x2f0000+len(client) < 0x300000
image = bytearray(stage_fixture(image,client,0x2f0000))
(out/'combined.bin').write_bytes(image)
serial_path, monitor_path = out/'serial.sock', out/'monitor.sock'
for path in (serial_path, monitor_path):
    if path.exists(): path.unlink()

def connect(path):
    deadline = time.monotonic()+20
    while time.monotonic() < deadline:
        channel = socket.socket(socket.AF_UNIX)
        try:
            channel.connect(str(path))
            channel.settimeout(.2)
            return channel
        except OSError:
            channel.close()
            time.sleep(.05)
    raise AssertionError(f'no QEMU socket: {path}')

with (out/'qemu.log').open('w') as log:
    qemu = subprocess.Popen(['qemu-system-x86_64', '-kernel', str(out/'combined.bin'), '-m', '256M',
        '-no-reboot', '-vga', 'std', '-display', 'none', '-serial', f'unix:{serial_path},server=on,wait=on',
        '-monitor', f'unix:{monitor_path},server=on,wait=off'], stdout=log, stderr=subprocess.STDOUT)
    serial = monitor = None
    data = bytearray()
    try:
        serial, monitor = connect(serial_path), connect(monitor_path)
        def wait(marker, start=0):
            deadline = time.monotonic()+30
            while marker.encode() not in data[start:] and time.monotonic() < deadline:
                try:
                    chunk = serial.recv(65536)
                    if not chunk: raise AssertionError('serial closed')
                    data.extend(chunk)
                except socket.timeout:
                    pass
            (out/'serial.log').write_bytes(data)
            assert marker.encode() in data[start:], data[-3000:]
        wait('space interactive shell')
        serial.sendall(b'input sci\n')
        wait('input: retained SCI ready')
        monitor.sendall(b'mouse_move 5 3\n')
        wait('input: mouse move 405,303\n')
        # Physical PS/2 modifier release must restore ordinary letter decoding.
        for key, code in [('a', 97), ('ctrl-n', 14), ('n', 110), ('b', 98), ('esc', 27)]:
            start = len(data)
            monitor.sendall(f'sendkey {key}\n'.encode())
            wait(f'input: key {code}\n', start)
            time.sleep(.25)
        wait('input: exactly-once, same domain/page, allocation counters unchanged PASS')
        # Drain pending serial output to catch duplicate publications after release.
        deadline = time.monotonic()+.5
        while time.monotonic() < deadline:
            try: data.extend(serial.recv(65536))
            except socket.timeout: pass
        assert data.count(b'input: mouse move 405,303\n') == 1, data[-2000:]
        assert data.count(b'input: mouse move ') == 1, data[-2000:]
        for code in (97, 14, 110, 98, 27):
            assert data.count(f'input: key {code}\n'.encode()) == 1, (code, data[-2000:])
        assert data.count(b'SCI: loading input-poll-proof') == 1
        assert data.count(b'SCI: domain created') == 1
    finally:
        (out/'serial.log').write_bytes(data)
        if serial: serial.close()
        if monitor: monitor.close()
        qemu.terminate()
        try: qemu.wait(timeout=3)
        except subprocess.TimeoutExpired:
            qemu.kill()
            qemu.wait()
assert snapshot == {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
assert hashlib.sha256(compiler.read_bytes()).hexdigest() == compiler_hash
(out/'source-hashes.json').write_text(json.dumps(snapshot, indent=2)+'\n')
print('PASS retained input SCI: one mouse move to405,303 and five PS/2 keys exactly once, modifier release, stable domain/page/allocation counters')
