#!/usr/bin/env python3
"""Real PS/2 editing in original vi through owned terminal waits; no GUI surface yet."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', type=Path, required=True)
p.add_argument('--app', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--root', choices=['standard','minimal'], default='standard')
a = p.parse_args(); out = a.out.resolve(); compiler = a.compiler.resolve(); app = a.app.resolve()
assert not out.exists() or not any(out.iterdir()), 'preserve prior evidence'
out.mkdir(parents=True, exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = ROOT / 'fixtures/applications/busybox-vi-1.36.1.json'
pin = json.loads(manifest.read_text())['apps'][0]
assert sha(app) == pin['sha256'] and app.stat().st_size == pin['size_bytes']
paths = [x for d in ['components','kernel','protocol','services','fixtures/terminal-session']
         for x in (ROOT / d).rglob('*.in')]
paths += [ROOT / 'boot/multiboot.asm',manifest,Path(__file__).resolve()]
contents = {str(x.relative_to(ROOT)): x.read_bytes() for x in paths}
snapshot = out / 'source'
for name, data in contents.items():
    path = snapshot / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
report = {'status':'running','goal_status':'OPEN','original_application_entries':0,
    'scope':'Original pinned BusyBox vi, actual PS2 keyboard and saved-file oracles over private native terminal; no desktop ANSI renderer/surface, no resize claim',
    'compiler_sha256':sha(compiler),'application_sha256':sha(app),'manifest_sha256':sha(manifest),
    'root':a.root,
    'source_sha256':{name:hashlib.sha256(data).hexdigest() for name,data in contents.items()},'keyboard':[]}
process = None; serial = None; monitor = None; received = bytearray()
def connect(path):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        channel = socket.socket(socket.AF_UNIX); channel.settimeout(.2)
        try: channel.connect(str(path)); return channel
        except (FileNotFoundError,ConnectionRefusedError): channel.close(); time.sleep(.02)
    raise AssertionError('QEMU socket unavailable')
def wait(marker):
    deadline = time.monotonic() + 180
    while marker not in received:
        assert b'PANIC' not in received and b'CPU EXCEPTION' not in received, received[-4000:]
        assert process.poll() is None, 'QEMU exited'
        assert time.monotonic() < deadline, (marker,received[-4000:])
        try:
            block = serial.recv(65536); assert block; received.extend(block)
        except socket.timeout: pass
try:
    fnv = 0xcbf29ce484222325
    for byte in app.read_bytes(): fnv = ((fnv ^ byte) * 1099511628211) & ((1 << 64) - 1)
    if fnv >= 1 << 63: fnv -= 1 << 64
    root = 'kernel-root.in' if a.root == 'standard' else 'kernel-root-minimal.in'
    source = (snapshot / 'kernel' / root).read_text()
    source = re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(snapshot / m[1])),source)
    source = ('const TERMINAL-VI-ELF-SIZE = '+str(app.stat().st_size)+'\nconst TERMINAL-VI-FNV = '+str(fnv)+'\n'
        'import '+json.dumps(str(snapshot / 'fixtures/terminal-session/vi-checks.in'))+'\n'+source)
    if a.root == 'minimal':
        source = 'import '+json.dumps(str(snapshot / 'components/ps2-keyboard.in'))+'\n'+source
    assert source.count('  shell(port)') == 1
    setup = '  counter-init(mb-info)\n' if a.root == 'minimal' else ''
    source = source.replace('  shell(port)',setup+'  terminal-vi-fixture(port)\n  shell(port)')
    (out / 'kernel.in').write_text(source)
    with (out / 'compile.log').open('w') as log:
        subprocess.run(['nasm','-f','bin',str(snapshot / 'boot/multiboot.asm'),'-o',str(out / 'trampoline.bin')],check=True,stdout=log,stderr=subprocess.STDOUT)
        subprocess.run([str(compiler),'compile','--path',str(out / 'kernel.in'),'--entry','kernel-entry','--emit','boot',
            '--trampoline',str(out / 'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none',
            '--linkage','static-lib','--out',str(out / 'kernel.bin')],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    command = ['qemu-system-x86_64','-cpu','max','-kernel',str(out / 'kernel.bin'),'-m','512M','-display','none','-no-reboot',
        '-serial',f'unix:{out}/serial.sock,server=on,wait=on','-monitor',f'unix:{out}/monitor.sock,server=on,wait=off',
        '-device',f'loader,file={app},addr=0x10000000,force-raw=on']
    report.update(qemu_command=command,kernel_sha256=sha(out / 'kernel.bin'))
    with (out / 'qemu.log').open('w') as log:
        process = subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        serial = connect(out / 'serial.sock'); monitor = connect(out / 'monitor.sock')
        for run, text in enumerate(['native42','again42']):
            wait(f'vi: keyboard ready {run}\n'.encode())
            keys = [('i',105)] + [(c,ord(c)) for c in text] + [('esc',27),('shift-semicolon',58),('w',119),('q',113),('ret',10)]
            for index,(key,byte) in enumerate(keys):
                monitor.sendall(f'sendkey {key} 50\n'.encode())
                wait(f'vi: key {run} {index} {byte}\n'.encode())
                # Let the actual key-up finish, especially Shift on the colon.
                time.sleep(.08)
            wait(f'vi: saved exact {run}\n'.encode())
            report['keyboard'].append({'process':run,'real_ps2_text_events':len(keys),'keys':keys,'saved_bytes':(text + ('original\n' if run == 0 else 'native42original\n'))})
        wait(b'vi: two actual original keyboard edit/save/reopen processes PASS\n')
        wait(b'space> ')
        match = re.search(rb'vi: trace (\d+) (\d+)\n',received); assert match
        address,size = map(int,match.groups()); assert 0 < size <= 65536
        capture = out / 'original-vi-output.bin'
        monitor.sendall(f'pmemsave {address:#x} {size} "{capture}"\n'.encode())
        deadline = time.monotonic() + 5
        while (not capture.exists() or capture.stat().st_size != size) and time.monotonic() < deadline: time.sleep(.02)
        output = capture.read_bytes(); assert len(output) == size and b'\x1b[' in output and b'original' in output
    assert all((ROOT / name).read_bytes() == data for name,data in contents.items()), 'source changed during run'
    assert sha(compiler) == report['compiler_sha256'] and sha(app) == report['application_sha256']
    report.update(status='passed',original_application_entries=2,actual_ps2_text_events=27,
        interactive_keyboard=True,interactive_gui=False,original_output_sha256=sha(capture),original_output_bytes=size,
        exact_saved_files=['native42original\n','again42native42original\n'],stable_after_warmup=True)
    print('PASS original vi: two protected keyboard edit/save/reopen processes, 27 real PS2 text events, exact saved files and owned cleanup')
except Exception as error:
    report.update(status='failed',error=str(error)); raise
finally:
    (out / 'serial.log').write_bytes(received)
    if serial: serial.close()
    if monitor: monitor.close()
    if process:
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill(); process.wait()
    (out / 'report.json').write_text(json.dumps(report,indent=2) + '\n')
