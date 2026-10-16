#!/usr/bin/env python3
"""Real SCI frames control geometry and pixels in a loader-granted shared page."""
import argparse
import copy
import hashlib
import importlib.util
import json
import struct
import sys
from pathlib import Path
import socket
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--in', dest='compiler', required=True)
parser.add_argument('--build-dir', type=Path, default=Path('/tmp/space-spdp-sci'))
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
out = args.build_dir.resolve()
out.mkdir(parents=True, exist_ok=True)
inputs = [root/'fixtures/spdp-sci/client.in', root/'protocol/display.in']
def source_hashes():
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
source_snapshot = source_hashes()
subprocess.run(['nasm', '-f', 'bin', str(root/'boot/multiboot.asm'), '-o', str(out/'trampoline.bin')], check=True)
for source, entry, extra, output in [
    ('kernel/kernel-root.in', 'kernel-entry', ['--emit', 'boot', '--trampoline', str(out/'trampoline.bin'), '--linkage', 'static-lib'], 'kernel.bin'),
    ('fixtures/spdp-sci/client.in', 'client-entry', ['--emit', 'sci', '--base', '0x48000000'], 'client.sci'),
]:
    with (out/(output+'.log')).open('w') as log:
        subprocess.run([args.compiler, 'compile', '--path', str(root/source), '--entry', entry, '--target', 'native', '--target-triple', 'x86_64-unknown-none', *extra, '--out', str(out/output)], stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
assert source_hashes() == source_snapshot, 'source/protocol changed during SCI compilation'
(out/'source-hashes.json').write_text(json.dumps(source_snapshot, indent=2)+'\n')
metadata_path = out/'client.component-metadata.json'
raw = (out/'client.sci').read_bytes()
metadata = json.loads(metadata_path.read_text())
packager = root/'scripts/pack-spdp-sci.py'
spec = importlib.util.spec_from_file_location('space_spdp_pack', packager)
module = importlib.util.module_from_spec(spec)
sys.dont_write_bytecode = True
spec.loader.exec_module(module)
assert struct.unpack_from('<Q', raw, 8)[0] == 3
packed = module.translate(raw, metadata)
assert struct.unpack_from('<Q', packed, 8)[0] == 20
# Invalid names/rights/count/identity cannot mutate a previously valid artifact.
sentinel = out/'refusal-output.sci'
sentinel.write_bytes(b'preserve-existing-artifact')
invalid = []
for mutation in ('unknown', 'duplicate', 'missing', 'rights', 'target', 'component'):
    bad = copy.deepcopy(metadata)
    if mutation == 'unknown': bad['capabilities_required'][0]['name'] = 'unknown'
    elif mutation == 'duplicate': bad['capabilities_required'].append(copy.deepcopy(bad['capabilities_required'][0]))
    elif mutation == 'missing': bad['capabilities_required'].pop()
    elif mutation == 'rights': bad['capabilities_required'][0]['args'] = ['arbitrary']
    elif mutation == 'target': bad['target'] = 'wrong-target'
    else: bad['component'] = 'wrong-component'
    invalid.append((mutation, raw, bad))
bad_mask = bytearray(raw)
struct.pack_into('<Q', bad_mask, 8, 20)
invalid.append(('ordinal-mask', bytes(bad_mask), metadata))
for name, bad_image, bad_metadata in invalid:
    (out/'invalid.sci').write_bytes(bad_image)
    (out/'invalid.json').write_text(json.dumps(bad_metadata))
    rejected = subprocess.run(['python3', str(packager), str(out/'invalid.sci'), str(out/'invalid.json'), str(sentinel)], capture_output=True, text=True)
    assert rejected.returncode != 0 and 'packaging refused' in rejected.stderr
    assert sentinel.read_bytes() == b'preserve-existing-artifact', name
subprocess.run(['python3', str(packager), str(out/'client.sci'), str(metadata_path), str(out/'client-space.sci')], check=True)
image = bytearray((out/'kernel.bin').read_bytes())
client = (out/'client-space.sci').read_bytes()
offset = 0x280000 - 0x100000
# This fixture exclusively uses the existing Linux-proof slot, below the 3MiB heap.
assert len(image) <= offset and len(client) <= 0x10000, 'fixture overlaps kernel/reserved heap'
assert 0x280000 + len(client) <= 0x300000
image += bytes(offset-len(image)) + client
(out/'combined.bin').write_bytes(image)
serial_path, monitor_path = out/'serial.sock', out/'monitor.sock'
for path in (serial_path, monitor_path):
    if path.exists(): path.unlink()

def connect(path):
    deadline = time.monotonic()+20
    while time.monotonic() < deadline:
        channel = socket.socket(socket.AF_UNIX)
        try:
            channel.connect(str(path)); channel.settimeout(.2); return channel
        except OSError:
            channel.close(); time.sleep(.05)
    raise AssertionError(f'no QEMU socket: {path}')

with (out/'qemu.log').open('w') as log:
    qemu = subprocess.Popen(['qemu-system-x86_64', '-kernel', str(out/'combined.bin'), '-m', '256M', '-no-reboot', '-vga', 'std', '-display', 'none', '-serial', f'unix:{serial_path},server=on,wait=on', '-monitor', f'unix:{monitor_path},server=on,wait=off'], stdout=log, stderr=subprocess.STDOUT)
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
                except socket.timeout: pass
            (out/'serial.log').write_bytes(data)
            assert marker.encode() in data[start:], data[-3000:]
        wait('space interactive shell')
        for phase, word, x in [(0, 'left', 40), (1, 'right', 400)]:
            start = len(data)
            serial.sendall(f'dsp sci {word}\n'.encode())
            wait(f'dsp: SCI frame proof {phase} PASS', start)
            time.sleep(.5)
            path = out/f'{word}.ppm'
            monitor.sendall(f'screendump {path}\n'.encode())
            deadline = time.monotonic()+5
            while (not path.exists() or path.stat().st_size < 1920*1080*3+17) and time.monotonic() < deadline: time.sleep(.05)
            header = path.read_bytes().split(b'\n', 3)
            assert header[:3] == [b'P6', b'1920 1080', b'255'], header[:3]
            pixels = header[3]
            def pixel(px, py): return pixels[(py*1920+px)*3:(py*1920+px)*3+3]
            for py in range(80, 96):
                for px in range(x, x+64):
                    expected = bytes((255, 0, 0)) if px < x+20 else bytes((0, 255, 0))
                    assert pixel(px, py) == expected, (word, px, py)
            assert pixel(x, 79) == bytes((0, 0, 128)) and pixel(x, 96) == bytes((0, 0, 128)), 'surface height mismatch'
            other = 400 if x == 40 else 40
            assert pixel(other, 80) == bytes((0, 0, 128)), 'old geometry remained visible'
            assert pixel(x-1, 80) == bytes((0, 0, 128)) and pixel(x+64, 80) == bytes((0, 0, 128)), 'surface width mismatch'
            print(f'PASS SCI {word}: {4 if phase == 0 else 3} complete frames and exact 64x16 SCI-client pixels (forged cap-info restored)')
        for attempt in range(2):
            start = len(data)
            serial.sendall(b'dsp sci destroy\n')
            wait('dsp: SCI teardown PASS', start)
            time.sleep(.5)
            path = out/f'destroy-{attempt}.ppm'
            monitor.sendall(f'screendump {path}\n'.encode())
            deadline = time.monotonic()+5
            while (not path.exists() or path.stat().st_size < 1920*1080*3+17) and time.monotonic() < deadline: time.sleep(.05)
            header = path.read_bytes().split(b'\n', 3)
            assert header[:3] == [b'P6', b'1920 1080', b'255']
            pixels = header[3]
            for x in (40, 400):
                for py in range(80, 96):
                    for px in range(x, x+64):
                        offset = (py*1920+px)*3
                        assert pixels[offset:offset+3] == bytes((0, 0, 128)), 'destroyed client pixels remained visible'
            print(f'PASS SCI teardown {attempt}: blue after destroy, harmless repeated request')
        assert data.count(b'SCI: loading spdp-proof') == 1, 'proof reloaded the SCI instance'
        assert data.count(b'SCI: domain created') == 1, 'proof allocated another domain'
        assert data.count(b'dsp: same SCI instance, allocation counters unchanged') == 3, 'resume identity/allocation proof missing'
        print('PASS one SCI instance: stable domain, ring/pixel pages and allocation counters across three reentries')
    finally:
        (out/'serial.log').write_bytes(data)
        if serial: serial.close()
        if monitor: monitor.close()
        qemu.terminate()
        try: qemu.wait(timeout=3)
        except subprocess.TimeoutExpired: qemu.kill(); qemu.wait()
