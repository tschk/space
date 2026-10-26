#!/usr/bin/env python3
"""Original vi edit/save/reopen oracle on a host PTY; never Space coverage."""
import argparse
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pty
import select
import signal
import struct
import termios
import time

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--app', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
a.app = a.app.resolve(); a.out = a.out.resolve()
if a.out.exists() and any(a.out.iterdir()):
    p.error('--out must be new or empty')
a.out.mkdir(parents=True, exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
app = json.loads((ROOT/'fixtures/applications/busybox-vi-1.36.1.json').read_text())['apps'][0]
assert sha(a.app) == app['sha256'] and a.app.stat().st_size == app['size_bytes']
document = a.out/'tui.txt'; document.write_bytes(b'original\n')
report = dict(classification='host PTY reference only; zero Space compatibility credit',
    application_sha256=sha(a.app), rows=24, columns=80, runs=[], status='failed')


def run(name, chunks):
    pid, master = pty.fork()
    if pid == 0:
        os.execve(str(a.app), ['busybox', 'vi', str(document)],
                  {'LC_ALL': 'C', 'HOME': '/', 'TERM': 'vt100'})
    transcript = bytearray(); reaped = False
    try:
        fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 80, 0, 0))
        deadline = time.monotonic()+15
        ready_at = None; chunk = 0
        while time.monotonic()<deadline:
            if select.select([master], [], [], .05)[0]:
                try:
                    data = os.read(master, 65536)
                    if data: transcript.extend(data)
                except OSError as error:
                    if error.errno != errno.EIO: raise
            if ready_at is None and b'original' in transcript:
                ready_at = time.monotonic()+.2
            if ready_at is not None and time.monotonic()>=ready_at and chunk<len(chunks):
                os.write(master, chunks[chunk]); chunk+=1; ready_at=time.monotonic()+.2
            waited, status = os.waitpid(pid, os.WNOHANG)
            if waited:
                reaped=True
                assert os.waitstatus_to_exitcode(status)==0, (name, status)
                assert chunk==len(chunks), 'vi exited before interaction'
                return dict(name=name, exit=0, transcript_sha256=hashlib.sha256(transcript).hexdigest())
        raise TimeoutError('host vi interaction timed out')
    finally:
        (a.out/(name+'.ansi')).write_bytes(transcript)
        if not reaped:
            os.kill(pid, signal.SIGKILL); os.waitpid(pid, 0)
        os.close(master)


try:
    report['runs'].append(run('edit-save', [b'gg0iSpaceTUI42', b'\x1b', b':wq\r']))
    assert document.read_bytes()==b'SpaceTUI42original\n', document.read_bytes()
    report['runs'].append(run('reopen', [b'\x1b', b':q!\r']))
    assert document.read_bytes()==b'SpaceTUI42original\n'
    report.update(status='passed', saved_sha256=sha(document), saved_text=document.read_text())
except Exception as error:
    report['error']=str(error)
finally:
    (a.out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
print(report['status'].upper()+': host vi PTY reference only; '+str(a.out/'report.json'))
raise SystemExit(0 if report['status']=='passed' else 1)
