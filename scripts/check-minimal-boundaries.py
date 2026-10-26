#!/usr/bin/env python3
"""Check the real minimal import graph and its unavailable device transport."""
import argparse
import json
from pathlib import Path
import re
import socket
import time
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', required=True)
p.add_argument('--image', type=Path, help='Also exercise a built minimal image in QEMU')
p.add_argument('--out', type=Path, help='New evidence directory, required with --image')
a = p.parse_args()
visited = set()
def imports(path):
    path = path.resolve()
    if path in visited:
        return
    visited.add(path)
    for relative in re.findall(r'^import "([^"]+)"', path.read_text(), re.M):
        imports(path.parent / relative)
imports(root/'kernel/kernel-root-minimal.in')
paths = {str(path.relative_to(root)) for path in visited}
for required in ('components/cpu.in', 'components/shell-common.in', 'components/shell-minimal.in',
                 'components/nvme-unavailable.in', 'components/sci-loader.in'):
    assert required in paths, required
for absent in ('components/display.in', 'components/storage.in', 'components/nvme.in',
               'components/network.in', 'components/netstack.in', 'components/posix.in',
               'components/linux.in', 'components/darwin.in', 'components/windows.in',
               'components/shell.in'):
    assert absent not in paths, absent
print(f'PASS: minimal import graph ({len(paths)} source modules) excludes desktop, drivers and personalities')
source = (root/'components/nvme-unavailable.in').read_text()
assert not re.search(r'\b(?:inb|outb|inw|outw|load8|store8|load64|store64)\(', source)
source += '''
fn main()->Int{
 if nvme-ready!=0 || storage-data-page!=0{return 1;}
 if nvme-read(0,1,0)!=-19 || nvme-write(0,1,0)!=-19{return 2;}
 if nvme-read(-1,-1,-1)!=-19 || nvme-write(-1,-1,-1)!=-19{return 3;}
 if nvme-ready!=0 || storage-data-page!=0{return 4;}
 return 42;
}
'''
with tempfile.TemporaryDirectory(prefix='space-minimal-transport-') as directory:
    fixture = Path(directory)/'transport.in'; fixture.write_text(source)
    for profile in ('default','lean','harden'):
        result = subprocess.run([a.compiler,'compile','--path',str(fixture),'--entry','main',
                                 '--target','jit','--profile',profile,'--out',str(Path(directory)/profile),
                                 '--json'],capture_output=True,text=True,timeout=30)
        report = json.loads(result.stdout)
        assert result.returncode==0 and report.get('success') and report.get('eval_result')=={'Int':42}, (result.stdout,result.stderr)
        print(f'PASS {profile}: unavailable block transport refuses reads/writes without publishing state')

if a.image:
    if not a.out:
        p.error('--image requires --out')
    out=a.out.resolve()
    if out.exists() and any(out.iterdir()):
        p.error('--out must be new or empty')
    out.mkdir(parents=True,exist_ok=True)
    path=out/'serial.sock'; data=bytearray(); channel=None
    with (out/'qemu.log').open('w') as log:
        process=subprocess.Popen(['qemu-system-x86_64','-kernel',str(a.image.resolve()),
            '-m','256M','-no-reboot','-display','none','-serial',f'unix:{path},server=on,wait=on'],
            stdout=log,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+10
            while not path.exists():
                assert time.monotonic()<deadline and process.poll() is None,'QEMU did not start'
                time.sleep(.02)
            channel=socket.socket(socket.AF_UNIX);channel.connect(str(path));channel.settimeout(.1)
            def wait(marker,start=0):
                deadline=time.monotonic()+15
                while marker not in data[start:]:
                    assert time.monotonic()<deadline,(marker,bytes(data[start:]))
                    try:
                        chunk=channel.recv(65536)
                        assert chunk,'serial connection closed'
                        data.extend(chunk)
                    except socket.timeout:
                        assert process.poll() is None,'QEMU exited'
                assert b'CPU EXCEPTION' not in data and b'nanokernel fault' not in data
            def command(text,expected):
                start=len(data);channel.sendall(text.encode()+b'\n');wait(expected,start)
            wait(b'space interactive shell')
            for text in ['desktop','net','linux','nvme']:
                command(text,b"  unavailable in minimal image (try 'help')")
            command('mkdir lab',b'  created')
            command('write lab/a payload',b'  written')
            command('cat lab/a',b'\npayload\n')
            command('echo redirect > lab/b',b'  redirected to lab/b')
            command('cat lab/b',b'\nredirect\n')
            command('echo pipe | cat',b'\npipe\n')
            command('halt',b'halting on request')
            print('PASS QEMU: unsupported optional services refuse; real RAM files, redirection and pipeline work')
        finally:
            (out/'serial.log').write_bytes(data)
            if channel:channel.close()
            if process.poll() is None:process.terminate()
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            if path.exists():path.unlink()
