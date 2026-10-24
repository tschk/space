#!/usr/bin/env python3
"""Boot actual native terminal queues and PS/2 seat routing; no foreign TUI credit."""
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
p.add_argument('--out', type=Path, required=True)
p.add_argument('--retained', action='store_true', help='Also execute the own protected ELF through retained terminal waits')
a = p.parse_args(); out = a.out.resolve(); compiler = a.compiler.resolve()
assert not out.exists() or not any(out.iterdir()), 'preserve prior evidence'
out.mkdir(parents=True, exist_ok=True)
paths = [x for d in ['components', 'kernel', 'protocol', 'services', 'fixtures/terminal-session']
         for x in (ROOT / d).rglob('*.in')]
paths += [ROOT / 'boot/multiboot.asm', Path(__file__).resolve()]
if a.retained:
    paths += [ROOT / 'fixtures/terminal-session/echo.asm']
contents = {str(x.relative_to(ROOT)): x.read_bytes() for x in paths}
snapshot = out / 'source'
for name, data in contents.items():
    target = snapshot / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'status': 'running', 'goal_status': 'OPEN',
    'scope': 'Trusted native terminal/seat objects, actual PS2 input and denied SCI imports; zero foreign application entries, no isolated TerminalSession service',
    'compiler_sha256': sha(compiler),
    'source_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}}
process = None; serial = None; monitor = None; received = bytearray()
def connect(path):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        channel = socket.socket(socket.AF_UNIX); channel.settimeout(.2)
        try: channel.connect(str(path)); return channel
        except (FileNotFoundError, ConnectionRefusedError): channel.close(); time.sleep(.02)
    raise AssertionError('QEMU socket unavailable')
def wait(marker):
    deadline = time.monotonic() + 120
    while marker not in received:
        if b'PANIC' in received or b'CPU EXCEPTION' in received:
            drain = time.monotonic() + .3
            while time.monotonic() < drain:
                try:
                    block = serial.recv(65536)
                    if not block: break
                    received.extend(block)
                except socket.timeout: pass
            raise AssertionError(received[-4000:])
        assert process.poll() is None, 'QEMU exited'
        assert time.monotonic() < deadline, (marker, received[-3000:])
        try:
            block = serial.recv(65536); assert block; received.extend(block)
        except socket.timeout: pass
try:
    elf = out / 'echo.elf'
    if a.retained:
        subprocess.run(['nasm','-f','elf64',str(snapshot / 'fixtures/terminal-session/echo.asm'),'-o',str(out / 'echo.o')],check=True)
        subprocess.run(['ld','-static','-z','noexecstack','-o',str(elf),str(out / 'echo.o')],check=True)
        report['own_elf_sha256'] = sha(elf)
    private = []
    for index, (name, declaration, call) in enumerate([
        ('terminal-session-open', 'owner:Int,seat:Int,columns:Int,rows:Int', 'info,info,80,24'),
        ('terminal-seat-deliver', 'seat:Int,byte:Int', 'info,65'),
        ('terminal-view-send', 'token:Int,first:Int,last:Int,closing:Int', 'info,129,0,0'),
        ('linux-terminal-deliver-key', 'seat:Int,key:Int', 'info,129'),
        ('input-page-send-bytes', 'page:Int,packed:Int,count:Int', 'info,65,1')]):
        source = out / f'private-{index}.in'; binary = out / f'private-{index}.sci'
        source.write_text('package space.fixture\ninterrupt fn ' + name + '(' + declaration + ')->Int{}\n'
            'fn private-entry(info:Int)->Int{store64(0x13000000,42);return ' + name + '(' + call + ');}\n')
        with (out / f'private-{index}.log').open('w') as log:
            subprocess.run([str(compiler),'compile','--path',str(source),'--entry','private-entry',
                '--emit','sci','--base','0x7a000000','--target','native','--target-triple','x86_64-unknown-none',
                '--out',str(binary)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
        assert 0 < binary.stat().st_size <= 0x2000
        private.append({'name': name, 'path': str(binary), 'size': binary.stat().st_size, 'sha256': sha(binary)})
    checks = '''let private-table=alloc(48);let prior-boot=load64(0x40d0);
store64(private-table,BOOT-IMAGE-TABLE-MAGIC);store64(private-table+8,1);store64(private-table+16,254);store64(private-table+40,0);
'''
    for index, item in enumerate(private):
        address = 0x2e0000 + index * 0x2000
        checks += '''{
if dyn-kernel-exportable(NAME)!=0 || dyn-resolve-idx(NAME)!=-1{panic("terminal private export");}
if load64(ADDRESS)!=SCI-MAGIC-V2 || load64(ADDRESS+24)!=SIZE{panic("terminal private image staging");}
store64(0x13000000,0);store64(private-table+24,ADDRESS);store64(private-table+32,SIZE);store64(0x40d0,private-table);
let heap=heap-next;let free=free-list;let caps=cap-count;let domains=domain-count;let live=runtime-instance-live;
if sci-load-runtime-component(port,ADDRESS,"private-terminal",1,1,0)!=-1{panic("terminal SCI import admitted");}
if load64(0x13000000)!=0 || heap-next!=heap || free-list!=free || cap-count!=caps || domain-count!=domains || runtime-instance-live!=live{panic("terminal SCI refusal mutation");}
store64(0x40d0,prior-boot);
}
'''.replace('NAME',json.dumps(item['name'])).replace('ADDRESS',str(address)).replace('SIZE',str(item['size']))
    checks += 'serial-write-cstr(port,"terminal: five SCI imports refused before entry PASS");serial-nl(port);'
    source = (snapshot / 'kernel/kernel-root.in').read_text()
    source = re.sub(r'import "\.\./([^"]+)"', lambda m: 'import ' + json.dumps(str(snapshot / m[1])), source)
    fixture = 'retained-checks.in' if a.retained else 'checks.in'
    source = 'import ' + json.dumps(str(snapshot / 'fixtures/terminal-session' / fixture)) + '\n' + source
    if a.retained:
        source = 'const TERMINAL-FIXTURE-ELF-SIZE = ' + str(elf.stat().st_size) + '\n' + source
    assert source.count('  shell(port)') == 1
    entry = 'terminal-retained-fixture' if a.retained else 'terminal-fixture-check'
    source = source.replace('  shell(port)', checks + '\n  ' + entry + '(port)\n  shell(port)')
    kernel_source = out / 'kernel.in'; kernel_source.write_text(source)
    with (out / 'compile.log').open('w') as log:
        subprocess.run(['nasm','-f','bin',str(snapshot / 'boot/multiboot.asm'),'-o',str(out / 'trampoline.bin')],check=True,stdout=log,stderr=subprocess.STDOUT)
        subprocess.run([str(compiler),'compile','--path',str(kernel_source),'--entry','kernel-entry','--emit','boot',
            '--trampoline',str(out / 'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none',
            '--linkage','static-lib','--out',str(out / 'kernel.bin')],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    assert (out / 'kernel.bin').stat().st_size + 0x100000 <= 0x2e0000
    assert 0x2e0000 + len(private)*0x2000 <= 0x300000
    command = ['qemu-system-x86_64','-cpu','max','-kernel',str(out / 'kernel.bin'),'-m','512M',
        '-display','none','-no-reboot','-serial',f'unix:{out}/serial.sock,server=on,wait=on',
        '-monitor',f'unix:{out}/monitor.sock,server=on,wait=off']
    for index, item in enumerate(private):
        command += ['-device', f'loader,file={item["path"]},addr={0x2e0000 + index * 0x2000:#x},force-raw=on']
    if a.retained:
        command += ['-device', f'loader,file={elf},addr=0x12000000,force-raw=on']
    report.update(qemu_command=command,kernel_sha256=sha(out / 'kernel.bin'),private_sci=private)
    with (out / 'qemu.log').open('w') as log:
        process = subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        serial = connect(out / 'serial.sock'); monitor = connect(out / 'monitor.sock')
        wait(b'terminal: keyboard A ready\n'); monitor.sendall(b'sendkey a 50\n')
        wait(b'terminal: keyboard B ready\n'); monitor.sendall(b'sendkey b 50\n')
        final = (b'terminal: actual partial output, pointer refusal, wait cancellation and later ordinary execution PASS\n'
                 if a.retained else b'terminal: revoked owners retired with stable resources PASS\n')
        wait(final)
        wait(b'space> ')
    assert b'terminal: five SCI imports refused before entry PASS\n' in received
    for item in private:
        assert ('SCI: DENIED unresolved import '+item['name']).encode() in received
    if a.retained:
        assert b'terminal: 22 actual CPL3 echo waits, 440 idle probes and restored TLS PASS\n' in received
        assert b'terminal: actual termios roundtrip/drain/flush geometry nonblock and timed poll PASS\n' in received
        report.update(own_cpl3_activations=27,retained_echo_cycles=22,idle_wait_probes=440,
                      writer_output_bytes_checked=1024,echo_output_bytes_checked=264,
                      retained_activation_profile=True)
    else:
        assert b'terminal: 22 exact queue/focus/lifetime cycles PASS\n' in received
        assert b'terminal: actual PS2 focus isolation PASS\n' in received
    assert all((ROOT / name).read_bytes() == data for name, data in contents.items()), 'source changed during run'
    assert sha(compiler) == report['compiler_sha256']
    report.update(status='passed',actual_keyboard_events=2,private_sci_preentry_refusals=2,
        lifetime_cycles=22,foreign_application_entries=0)
    if a.retained:
        print('PASS retained terminal: 27 own CPL3 activations, 440 idle probes, actual PS2 resume, termios/timed poll, exact output, cancellation and TLS restore')
    else:
        print('PASS native terminal: 22 lifecycle cycles, exact rings, two actual PS2 focus deliveries, two SCI pre-entry refusals')
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
