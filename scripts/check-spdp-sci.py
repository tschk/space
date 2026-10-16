#!/usr/bin/env python3
"""Real SCI frames control compositor geometry; pixels remain kernel test content."""
import argparse
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
subprocess.run(['nasm', '-f', 'bin', str(root/'boot/multiboot.asm'), '-o', str(out/'trampoline.bin')], check=True)
for source, entry, extra, output in [
    ('kernel/kernel-root.in', 'kernel-entry', ['--emit', 'boot', '--trampoline', str(out/'trampoline.bin'), '--linkage', 'static-lib'], 'kernel.bin'),
    ('fixtures/spdp-sci/client.in', 'client-entry', ['--emit', 'sci', '--base', '0x48000000'], 'client.sci'),
]:
    with (out/(output+'.log')).open('w') as log:
        subprocess.run([args.compiler, 'compile', '--path', str(root/source), '--entry', entry, '--target', 'native', '--target-triple', 'x86_64-unknown-none', *extra, '--out', str(out/output)], stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
image = bytearray((out/'kernel.bin').read_bytes())
client = (out/'client.sci').read_bytes()
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
            for py in range(80, 112):
                for px in range(x, x+96): assert pixel(px, py) == b'\0\0\0', (word, px, py)
            other = 400 if x == 40 else 40
            assert pixel(other, 80) == bytes((0, 0, 128)), 'old geometry remained visible'
            assert pixel(x-1, 80) == bytes((0, 0, 128)) and pixel(x+96, 80) == bytes((0, 0, 128)), 'surface width mismatch'
            print(f'PASS SCI {word}: five complete frames and exact 96x32 kernel-test-pixel geometry')
    finally:
        (out/'serial.log').write_bytes(data)
        if serial: serial.close()
        if monitor: monitor.close()
        qemu.terminate()
        try: qemu.wait(timeout=3)
        except subprocess.TimeoutExpired: qemu.kill(); qemu.wait()
