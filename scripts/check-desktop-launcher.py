#!/usr/bin/env python3
"""Build without Cargo, then exercise the real compositor through QEMU PS/2 input."""
import argparse
from collections import Counter
import pathlib
import socket
import subprocess
import time

p = argparse.ArgumentParser()
p.add_argument('--in', dest='compiler', required=True, help='Explicit source-built Inauguration binary')
p.add_argument('--build-dir', default='/tmp/space-desktop-launcher')
a = p.parse_args()
root = pathlib.Path(__file__).resolve().parents[1]
out = pathlib.Path(a.build_dir).resolve()
out.mkdir(parents=True, exist_ok=True)
serial_path, monitor_path = out/'serial.sock', out/'monitor.sock'
for path in [serial_path, monitor_path]:
    if path.exists(): path.unlink()
subprocess.run(['nasm', '-f', 'bin', str(root/'boot/multiboot.asm'), '-o', str(out/'trampoline.bin')], check=True)
assert (out/'trampoline.bin').stat().st_size == 4096
with (out/'compile.log').open('w') as log:
    subprocess.run([str(pathlib.Path(a.compiler).resolve()), 'compile', '--path', str(root/'kernel/kernel-root.in'), '--entry', 'kernel-entry', '--emit', 'boot', '--trampoline', str(out/'trampoline.bin'), '--target', 'native', '--target-triple', 'x86_64-unknown-none', '--linkage', 'static-lib', '--out', str(out/'kernel.bin')], stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)

def connect(path):
    deadline = time.monotonic()+30
    while time.monotonic()<deadline:
        sock = socket.socket(socket.AF_UNIX)
        try:
            sock.connect(str(path)); sock.settimeout(.2); return sock
        except OSError:
            sock.close(); time.sleep(.05)
    raise AssertionError(f'QEMU socket unavailable: {path}')

log = bytearray()
with (out/'qemu.log').open('w') as qlog:
    qemu = subprocess.Popen(['qemu-system-x86_64', '-kernel', str(out/'kernel.bin'), '-m', '256M', '-no-reboot', '-vga', 'std', '-display', 'none', '-serial', f'unix:{serial_path},server=on,wait=on', '-monitor', f'unix:{monitor_path},server=on,wait=off'], stdout=qlog, stderr=subprocess.STDOUT)
    serial = monitor = None
    try:
        serial = connect(serial_path); monitor = connect(monitor_path)
        def wait(marker, start=0):
            deadline = time.monotonic()+35
            while marker.encode() not in log[start:] and time.monotonic()<deadline:
                try:
                    chunk = serial.recv(65536)
                    if not chunk: raise AssertionError('QEMU serial closed')
                    log.extend(chunk)
                except socket.timeout: pass
            (out/'serial.log').write_bytes(log)
            assert marker.encode() in log[start:], f'missing {marker}: {log[-2000:]!r}'
        def command(text):
            if text.startswith('sendkey '): text += ' 30'
            monitor.sendall((text+'\n').encode()); time.sleep(.15)
            try: monitor.recv(65536)
            except socket.timeout: pass
        def key(text):
            for char in text:
                command('sendkey '+('spc' if char==' ' else char))
                time.sleep(.08)
        def capture(name):
            path = out/(name+'.ppm')
            if path.exists(): path.unlink()
            command('screendump '+str(path))
            deadline=time.monotonic()+5
            while (not path.exists() or path.stat().st_size < 1920*1080*3+17) and time.monotonic()<deadline: time.sleep(.05)
            data=path.read_bytes(); header=data.split(b'\n',3)
            assert header[0]==b'P6' and header[1]==b'1920 1080' and header[2]==b'255', header[:3]
            assert len(header[3])==1920*1080*3
            return header[3]
        wait('space interactive shell')
        serial.sendall(b'desktop\n'); wait('space: compositor frame ready')
        baseline = capture('desktop')
        command('sendkey tab'); wait('space: launcher opened')
        key('util'); time.sleep(.5)
        opened = capture('launcher-util')
        def region(pixels,x0,y0,x1,y1):
            return Counter(tuple(pixels[(y*1920+x)*3:(y*1920+x)*3+3]) for y in range(y0,y1) for x in range(x0,x1))
        colors=region(opened,600,44,1320,268)
        assert colors[(27,24,24)]>30000, 'launcher panel absent'
        assert colors[(248,189,56)]>40, 'matching result accent absent'
        assert baseline != opened, 'launcher did not change framebuffer'
        command('sendkey ret'); wait('space: launcher focused UTILITIES')
        time.sleep(.8)
        focused = capture('focused-utilities')
        assert focused != opened, 'launcher did not disappear after focus'
        # A failed search stays open; Backspace edits it without leaking into terminal.
        start=len(log); command('sendkey tab'); wait('space: launcher opened', start)
        key('zzzz'); command('sendkey ret'); unmatched=capture('launcher-no-match')
        assert unmatched != opened, 'query/result state did not render'
        for _ in range(4): command('sendkey backspace')
        key('terminal 2'); command('sendkey ret'); wait('space: launcher focused TERMINAL 2')
        before_fetch=capture('focused-terminal-2'); key('fetch'); command('sendkey ret'); time.sleep(.8)
        after_fetch=capture('terminal-2-fetch')
        assert before_fetch != after_fetch, 'focused terminal did not accept input'
        # Relative PS/2 pointer starts at screen center; move in bounded packets.
        def move(dx,dy):
            while dx or dy:
                sx=max(-100,min(100,dx)); sy=max(-100,min(100,dy))
                command(f'mouse_move {sx} {sy}'); dx-=sx; dy-=sy
        def click():
            command('mouse_button 1'); time.sleep(.2); command('mouse_button 0'); time.sleep(.8)
        move(0,525); click()  # First taskbar button: TERMINAL 1.
        pointer_focused=capture('pointer-taskbar-terminal-1')
        def focused_title(pixels):
            return b''.join(pixels[(y*1920+840)*3:(y*1920+1200)*3] for y in range(28))
        assert focused_title(pointer_focused) == focused_title(baseline), 'taskbar did not focus TERMINAL 1'
        assert focused_title(pointer_focused) != focused_title(after_fetch), 'taskbar focus remained TERMINAL 2'
        move(-660,-1050); start=len(log); click()
        wait('space: launcher opened',start)
        capture('pointer-opened-launcher')
        command('sendkey esc'); wait('space: launcher dismissed',start)
        # First Escape dismisses only the switcher; a second retains desktop exit.
        start=len(log); command('sendkey tab'); wait('space: launcher opened',start)
        start=len(log)
        command('sendkey esc'); wait('space: launcher dismissed',start)
        assert b'space: compositor exited' not in log[start:]
        capture('dismissed')
        command('sendkey esc'); wait('space: compositor exited')
        serial.sendall(b'halt\n')
        print(f'PASS: PS/2 launcher focus, search/edit, terminal input, pointer taskbar/topbar, Escape and rendered pixels ({out})')
    finally:
        (out/'serial.log').write_bytes(log)
        if monitor:
            try: monitor.sendall(b'quit\n')
            except OSError: pass
            monitor.close()
        if serial: serial.close()
        try: qemu.wait(timeout=5)
        except subprocess.TimeoutExpired: qemu.kill(); qemu.wait()
        for path in [serial_path,monitor_path]:
            if path.exists(): path.unlink()
