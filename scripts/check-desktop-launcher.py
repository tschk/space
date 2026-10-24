#!/usr/bin/env python3
"""Build without Cargo, then exercise the real compositor through QEMU PS/2 input."""
import argparse
import json
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
# Exercise actual close logic independently of rendering, including focused-close policy.
text = (root/'components/display.in').read_text()
start = text.index('fn comp-win-close(')
close_function = text[start:text.index('\n}', start)+2]
for focus, closed, expected in [(1,0,42), (1,1,7), (2,2,42), (0,2,9)]:
    source = 'var heap:[Int]=[' + ','.join(['0']*256) + '];\n' + f"""
const COMP-WIN-SIZE=64;
const COMP-TASKBAR-H=28;
const COMP-TITLE-BAR-H=28;
var comp-windows:Int=8;
var comp-count:Int=3;
var comp-focused:Int={focus};
var comp-dragging:Int=0;
var comp-drag-mode:Int=1;
var fb-width:Int=1920;
fn comp-win-base(i:Int)->Int{{return comp-windows+i*64;}}
fn load32(p:Int)->Int{{return heap[p];}}
fn load8(p:Int)->Int{{return heap[p];}}
fn store8(p:Int,v:Int)->Void{{heap[p]=v;}}
fn comp-win-clear(i:Int)->Void{{return;}}
fn comp-dmg-add(a:Int,b:Int,c:Int,d:Int)->Void{{return;}}
fn comp-win-damage(i:Int)->Void{{return;}}
{close_function}
fn main()->Int{{heap[8+24]=9;heap[8+64+24]=42;heap[8+128+24]=7;comp-win-close({closed});if heap[comp-win-base(comp-focused)+24]!={expected}{{return 0;}}return 42;}}
"""
    path = out/f'close-{focus}-{closed}.in'
    path.write_text(source)
    for profile in ('default','lean','harden'):
        run = subprocess.run([a.compiler,'compile','--path',str(path),'--target','jit','--profile',profile,'--out',str(out/'close-proof'),'--json'],capture_output=True,text=True,check=True,timeout=30)
        report = json.loads(run.stdout)
        (out/f'close-{focus}-{closed}-{profile}.json').write_text(run.stdout)
        assert report.get('success') and report.get('eval_result') == {'Int':42}, report
# Exercise both actual PS/2 decoders: Ctrl make/break, letters, and nonletters.
for decoder in ('ps2-keyboard', 'input'):
    decoder_text = (root/f'components/{decoder}.in').read_text()
    functions = [(root/'protocol/keyboard.in').read_text()]
    for name in ('ps2-scancode-ascii', 'ps2-kbd-getchar'):
        begin = decoder_text.index('fn '+name+'(')
        functions.append(decoder_text[begin:decoder_text.index('\n}', begin)+2])
    source = """const PS2-DATA=96;
var ps2-kbd-ctrl:Int=0;
var ps2-kbd-extended:Int=0;
var ps2-kbd-pause:Int=0;
var ps2-kbd-shift:Int=0;
var ps2-kbd-caps:Int=0;
var ps2-kbd-caps-held:Int=0;
var code:Int=0;
fn ps2-kbd-has-data()->Int{return 1;}
fn inb(port:Int)->Int{return code;}
""" + '\n'.join(functions) + """
fn main()->Int{
code=0x1D;if ps2-kbd-getchar()!=-1{return 1;}
code=0x31;if ps2-kbd-getchar()!=14{return 2;}
code=0x19;if ps2-kbd-getchar()!=16{return 3;}
code=0x02;if ps2-kbd-getchar()!=49{return 4;}
code=0x9D;if ps2-kbd-getchar()!=-1{return 5;}
code=0x31;if ps2-kbd-getchar()!=110{return 6;}
code=0x19;if ps2-kbd-getchar()!=112{return 7;}
code=0x2A;if ps2-kbd-getchar()!=-1{return 8;}
code=0x09;if ps2-kbd-getchar()!=42{return 9;}
code=0x1E;if ps2-kbd-getchar()!=65{return 10;}
code=0x36;if ps2-kbd-getchar()!=-1{return 11;}
code=0xAA;if ps2-kbd-getchar()!=-1{return 12;}
code=0x09;if ps2-kbd-getchar()!=42{return 13;}
code=0xB6;if ps2-kbd-getchar()!=-1{return 14;}
code=0x09;if ps2-kbd-getchar()!=56{return 15;}
code=0x3A;if ps2-kbd-getchar()!=-1{return 16;}
code=0x3A;if ps2-kbd-getchar()!=-1{return 17;}
code=0x1E;if ps2-kbd-getchar()!=65{return 18;}
code=0x09;if ps2-kbd-getchar()!=56{return 19;}
code=0xBA;if ps2-kbd-getchar()!=-1{return 20;}
code=0x2A;if ps2-kbd-getchar()!=-1{return 21;}
code=0x1E;if ps2-kbd-getchar()!=97{return 22;}
code=0xAA;if ps2-kbd-getchar()!=-1{return 23;}
code=0x1D;if ps2-kbd-getchar()!=-1{return 24;}
code=0x1E;if ps2-kbd-getchar()!=1{return 25;}
code=0x9D;if ps2-kbd-getchar()!=-1{return 26;}
code=0x3A;if ps2-kbd-getchar()!=-1{return 27;}
code=0xBA;if ps2-kbd-getchar()!=-1{return 28;}
code=0x1E;if ps2-kbd-getchar()!=97{return 29;}
return 42;}
"""
    path = out/f'keyboard-{decoder}.in'
    path.write_text(source)
    for profile in ('default', 'lean', 'harden'):
        run = subprocess.run([a.compiler, 'compile', '--path', str(path), '--target', 'jit', '--profile', profile, '--out', str(out/'keyboard-proof'), '--json'], capture_output=True, text=True, check=True, timeout=30)
        report = json.loads(run.stdout)
        (out/f'keyboard-{decoder}-{profile}.json').write_text(run.stdout)
        assert report.get('success') and report.get('eval_result') == {'Int':42}, report
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
        def frame_until(name, predicate):
            deadline = time.monotonic()+15
            while True:
                pixels = capture(name)
                if predicate(pixels): return pixels
                assert time.monotonic()<deadline, 'frame condition timed out: '+name
                time.sleep(.1)
        def panel_visible(pixels):
            return sum(pixels[(y*1920+x)*3:(y*1920+x)*3+3] == bytes((27,24,24)) for y in range(44,268) for x in range(600,1320)) > 30000
        wait('space interactive shell')
        serial.sendall(b'desktop\n'); wait('space: compositor frame ready')
        baseline = capture('desktop')
        # Launcher selection wraps over visible matches and query edits reset it.
        def choose(keys, title, name, row):
            start = len(log)
            command('sendkey tab'); wait('space: launcher opened', start)
            for item in keys:
                if item.startswith('ctrl-'): command('sendkey '+item)
                else: key(item)
            time.sleep(.8)
            def selection_ready(pixels):
                count = 1 if 'terminal 1' in keys else (2 if 'terminal' in keys else 4)
                for candidate in range(count):
                    gold = sum(pixels[(y*1920+x)*3:(y*1920+x)*3+3] == bytes((248,189,56)) for y in range(124+candidate*28,148+candidate*28) for x in range(620,1000))
                    if (gold > 40) != (candidate == row): return False
                return True
            selected_pixels = frame_until(name+'-selected', selection_ready)
            for candidate in range(1 if 'terminal 1' in keys else (2 if 'terminal' in keys else 4)):
                gold = sum(selected_pixels[(y*1920+x)*3:(y*1920+x)*3+3] == bytes((248,189,56)) for y in range(124+candidate*28, 148+candidate*28) for x in range(620,1000))
                assert (gold > 40) == (candidate == row), f'wrong selected result row: {name}/{candidate}'
            start = len(log)
            command('sendkey ret'); wait('space: launcher focused '+title, start)
            time.sleep(.8)
            return frame_until(name+'-focused', lambda pixels:not panel_visible(pixels))
        next_focus = choose(['ctrl-n'], 'UTILITIES', 'selection-next', 1)
        previous_focus = choose(['terminal', 'ctrl-p'], 'TERMINAL 2', 'selection-previous-wrap', 1)
        choose(['terminal', 'ctrl-n'], 'TERMINAL 2', 'selection-filtered-next', 1)
        reset_focus = choose(['ctrl-n', 'terminal 1'], 'TERMINAL 1', 'selection-query-reset', 0)
        def focused_title(pixels):
            return b''.join(pixels[(y*1920+840)*3:(y*1920+1200)*3] for y in range(28))
        assert focused_title(next_focus) != focused_title(previous_focus), 'selection did not change focused window'
        assert focused_title(reset_focus) == focused_title(baseline), 'query edit did not reset selection'
        start = len(log)
        command('sendkey tab'); wait('space: launcher opened', start)
        key('util'); time.sleep(.5)
        opened = frame_until('launcher-util', panel_visible)
        def region(pixels,x0,y0,x1,y1):
            return Counter(tuple(pixels[(y*1920+x)*3:(y*1920+x)*3+3]) for y in range(y0,y1) for x in range(x0,x1))
        colors=region(opened,600,44,1320,268)
        assert colors[(27,24,24)]>30000, 'launcher panel absent'
        assert colors[(248,189,56)]>40, 'matching result accent absent'
        assert baseline != opened, 'launcher did not change framebuffer'
        start = len(log)
        command('sendkey ret'); wait('space: launcher focused UTILITIES', start)
        time.sleep(.8)
        focused = frame_until('focused-utilities',lambda pixels:not panel_visible(pixels))
        assert focused != opened, 'launcher did not disappear after focus'
        # A failed search stays open; Backspace edits it without leaking into terminal.
        start=len(log); command('sendkey tab'); wait('space: launcher opened', start)
        key('zzzz'); command('sendkey ctrl-n'); command('sendkey ctrl-p')
        command('sendkey ret'); unmatched=capture('launcher-no-match')
        assert b'space: launcher focused' not in log[start:], 'no-match keyboard selection focused a window'
        assert unmatched != opened, 'query/result state did not render'
        for _ in range(4): command('sendkey backspace')
        key('terminal 2'); start = len(log)
        command('sendkey ret'); wait('space: launcher focused TERMINAL 2', start)
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
        pointer_focused=frame_until('pointer-taskbar-terminal-1',lambda pixels:focused_title(pixels)==focused_title(baseline))
        assert focused_title(pointer_focused) == focused_title(baseline), 'taskbar did not focus TERMINAL 1'
        assert focused_title(pointer_focused) != focused_title(after_fetch), 'taskbar focus remained TERMINAL 2'
        move(-660,-1050); start=len(log); click()
        wait('space: launcher opened',start)
        capture('pointer-opened-launcher')
        # Filtered first row must select UTILITIES, not window index zero.
        key('util'); move(400,130); start=len(log); click()
        wait('space: launcher focused UTILITIES',start)
        utility_pointer=frame_until('pointer-filtered-utilities',lambda pixels:focused_title(pixels)==focused_title(focused) and not panel_visible(pixels))
        assert focused_title(utility_pointer) == focused_title(focused), 'filtered pointer row selected wrong window'
        # Reopen at topbar, then outside-click must dismiss without focus.
        move(-400,-130); start=len(log); click(); wait('space: launcher opened',start)
        move(200,350); start=len(log); click(); wait('space: launcher dismissed',start)
        assert b'space: launcher focused' not in log[start:], 'outside click focused a window'
        outside=frame_until('pointer-outside-dismissed',lambda pixels:not panel_visible(pixels))
        assert focused_title(outside) == focused_title(utility_pointer), 'outside click changed focus'
        # No-match row cannot accidentally select window zero.
        move(-200,-350); start=len(log); click(); wait('space: launcher opened',start)
        key('zzzz'); move(400,130); start=len(log); click(); wait('space: launcher dismissed',start)
        assert b'space: launcher focused' not in log[start:], 'no-match click focused a window'
        no_match=frame_until('pointer-no-match-dismissed',lambda pixels:not panel_visible(pixels))
        assert focused_title(no_match) == focused_title(utility_pointer), 'no-match click changed focus'
        # Close lower-index TERMINAL 1 while UTILITIES remains focused.
        move(242,-78); click()
        after_close=capture('closed-terminal-1-focus-utilities')
        def window_count(pixels):
            return b''.join(pixels[(y*1920+1830)*3:(y*1920+1900)*3] for y in range(28))
        assert window_count(after_close) != window_count(no_match), 'close click did not remove a window'
        assert focused_title(after_close) == focused_title(utility_pointer), 'closing earlier window changed focus identity'
        key('a'); after_key=capture('utilities-key-routing-after-close')
        def terminal_two(pixels):
            return b''.join(pixels[(y*1920+1000)*3:(y*1920+1900)*3] for y in range(600,900))
        assert terminal_two(after_key) == terminal_two(after_close), 'key leaked to TERMINAL 2 after close'
        def query_key(text):
            def query_pixels(pixels):
                return b''.join(pixels[(y*1920+650)*3:(y*1920+1280)*3] for y in range(88,112))
            for index,char in enumerate(text):
                before=query_pixels(capture('query-before'))
                key(char)
                frame_until('query-step-'+str(index),lambda pixels:query_pixels(pixels)!=before)
        def action(query, title, pointer=False):
            start=len(log); command('sendkey tab'); wait('space: launcher opened',start)
            query_key(query)
            frame_until('command-'+query.replace(' ','-'), panel_visible)
            start=len(log)
            if pointer:
                # Prior pointer is at original TERMINAL 1 close button (942,77).
                move(700-942,138-77); click()
            else: command('sendkey ret')
            wait('space: command '+title,start)
            wait('space: launcher dismissed',start)
            return frame_until('after-'+query.replace(' ','-'), lambda pixels:not panel_visible(pixels))
        def tiled(pixels):
            # Two surviving columns: x16..951 and968..1903, y44..1035.
            desktop=bytes((11,9,9))
            def pixel(x,y): return pixels[(y*1920+x)*3:(y*1920+x)*3+3]
            return all(pixel(x,500)==desktop for x in (0,15,955,960,967,1904,1919)) and all(pixel(x,44)!=desktop for x in (16,951,968,1903)) and pixel(500,1036)==desktop
        tile_enter=action('tile','TILE WINDOWS')
        frame_until('tile-enter-geometry', tiled)
        tile_click=action('tile','TILE WINDOWS',True)
        frame_until('tile-click-geometry', tiled)
        # Bottom-right resizing must be reachable outside the title bar and
        # preserve the pointer's grip offset when geometry changes.
        # Reset at the screen edge: preceding clicks intentionally use generous
        # hit boxes, but an 8x8 grip needs an exact pointer coordinate.
        move(-1920,-1080)
        move(948,1032)
        command('mouse_button 1')
        move(-64,-48)
        def resized_utility(pixels):
            def pixel(x,y): return pixels[(y*1920+x)*3:(y*1920+x)*3+3]
            desktop=bytes((11,9,9))
            return pixel(900,900)==desktop and pixel(800,900)!=desktop and pixel(800,1000)==desktop
        frame_until('pointer-resize-utility', resized_utility)
        move(64,48)
        command('mouse_button 0')
        frame_until('pointer-resize-restored', tiled)
        move(700-948,138-1032)
        # Terminal 2 identity survives the earlier index-zero close.
        restored=action('focus','FOCUS TERMINAL 2')
        minimized=action('minimize','MINIMIZE FOCUSED')
        assert minimized != restored, 'minimize did not remove focused surface'
        restored=action('focus','FOCUS TERMINAL 2')
        frame_until('restored-terminal-2',lambda pixels: pixels != minimized)
        before=capture('restored-before-input'); key('fetch'); command('sendkey ret')
        frame_until('restored-after-input',lambda pixels:pixels != before)
        action('close','CLOSE FOCUSED')
        start=len(log); command('sendkey tab'); wait('space: launcher opened',start)
        query_key('focus'); frame_until('closed-target-query',panel_visible)
        start=len(log); command('sendkey ret')
        # Synchronize input processing with a following dismissal, not a fixed sleep.
        command('sendkey esc'); wait('space: launcher dismissed',start)
        assert b'space: command FOCUS TERMINAL 2' not in log[start:], 'closed terminal action remained available'
        assert b'space: launcher focused' not in log[start:], 'closed target selected another window'
        # First Escape dismisses only the switcher; a second retains desktop exit.
        start=len(log); command('sendkey tab'); wait('space: launcher opened',start)
        start=len(log)
        command('sendkey esc'); wait('space: launcher dismissed',start)
        assert b'space: compositor exited' not in log[start:]
        capture('dismissed')
        command('sendkey esc'); wait('space: compositor exited')
        serial.sendall(b'halt\n')
        print(f'PASS: PS/2 launcher selection/focus, search/edit, terminal input, pointer taskbar/topbar/resize, Escape and rendered pixels ({out})')
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
