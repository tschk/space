#!/usr/bin/env python3
"""Drive actual shipped Space applications in a built standard boot image.

This exercises native Space apps, not upstream ELF/Mach-O/PE compatibility.
Use scripts/build-images.sh to construct an image; retain build failures too.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import time
import zlib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--allow-boot-denial', action='store_true', help='Allow an explicit boot-time negative fixture before the shell; app admission remains strict')
    parser.add_argument('--qemu', default='qemu-system-x86_64')
    parser.add_argument('--timeout', type=float, default=15)
    parser.add_argument('--repeat-cycles', type=int, default=0, help='Additional calc/checksum pairs in this same VM')
    args = parser.parse_args()
    if args.repeat_cycles<0: parser.error('--repeat-cycles must be nonnegative')
    image = args.image.resolve()
    output = args.out.resolve()
    if not image.is_file():
        parser.error('--image must name a built standard image')
    if output.exists() and any(output.iterdir()):
        parser.error('--out must be new or empty')
    output.mkdir(parents=True, exist_ok=True)
    report = {
        'started_utc': datetime.now(timezone.utc).isoformat(),
        'evidence': 'native Space shipped application scenarios in QEMU',
        'foreign_applications': False,
        'repeat_cycles_requested': args.repeat_cycles,
        'image': str(image),
        'image_sha256': hashlib.sha256(image.read_bytes()).hexdigest(),
        'scenarios': [],
        'inputs': [],
    }
    input_started = time.monotonic()
    log = bytearray()
    serial = None
    process = None
    def save():
        (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
        (output/'serial.log').write_bytes(log)
    def wait(marker, start=0, allow_denial=False):
        report['last_wait'] = {'marker_hex': marker.hex(), 'serial_offset': start}
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            if marker in log[start:]:
                return
            if not allow_denial and b'SCI: DENIED' in log[start:] and b'\n' in bytes(log[start:]).split(b'SCI: DENIED',1)[1]:
                raise RuntimeError('application admission denied: '+bytes(log[start:]).decode(errors='replace').split('SCI: DENIED',1)[1].splitlines()[0])
            if b'CPU EXCEPTION' in log[start:] or b'nanokernel fault' in log[start:]:
                raise RuntimeError('guest fault; inspect serial.log')
            try:
                data = serial.recv(65536)
                if not data:
                    raise RuntimeError('serial connection closed')
                log.extend(data)
            except socket.timeout:
                if process.poll() is not None:
                    raise RuntimeError('QEMU exited before expected application output')
        raise RuntimeError(f'timed out awaiting fresh output {marker!r}')
    def send(data):
        start = len(log)
        serial.sendall(data)
        report['inputs'].append({'serial_offset': start, 'data_hex': data.hex(),
                                 'elapsed_seconds': time.monotonic()-input_started})
        return start
    def command(text, marker):
        start = send(text.encode()+b'\n')
        wait(marker, start)
        return start
    def run_app(name, markers, returned=b'0000000000000000'):
        start = send(f'runapp {name}\n'.encode())
        for marker in markers:
            wait(marker, start)
        prefix = b'runapp: app-'+name.split()[0].encode()+b' returned 0x'
        wait(prefix, start)
        line_start = log.index(prefix, start)
        wait(b'\n', line_start)
        actual = bytes(log[line_start:]).splitlines()[0]
        expected = prefix+returned
        if actual != expected:
            raise RuntimeError(f'application returned {actual!r}; expected {expected!r}')
    def scenario(name, action):
        entry = {'name': name, 'status': 'running', 'serial_offset': len(log)}
        report['scenarios'].append(entry)
        save()
        try:
            action()
            entry['status'] = 'passed'
            print('PASS:', name, flush=True)
        except Exception as error:
            entry.update(status='failed', error=str(error))
            print('FAIL:', name, error, flush=True)
            # Admission refusal leaves the supervisor alive; retain this failure
            # and continue independent app scenarios. Other failures abort safely.
            scenario_log = bytes(log[entry['serial_offset']:])
            last_activation=scenario_log.rfind(b'SCI: starting app-')
            returns=list(re.finditer(rb'runapp: app-[a-z]+ returned 0x[0-9a-f]+',scenario_log))
            last_return=returns[-1].start() if returns else -1
            if b'SCI: DENIED' not in scenario_log and last_return<last_activation:
                raise
            if b'SCI: DENIED' not in scenario_log and last_return<0:
                raise
            wait(b'space> ', entry['serial_offset'], allow_denial=True)
        finally:
            entry['serial_end'] = len(log)
            save()
    try:
        with (output/'qemu.log').open('w') as qlog:
            serial_path = output/'serial.sock'
            qcommand = [args.qemu, '-kernel', str(image), '-m', '512M', '-display', 'none',
                        '-no-reboot', '-serial', f'unix:{serial_path},server=on,wait=on']
            report['command'] = qcommand
            process = subprocess.Popen(qcommand, stdout=qlog, stderr=subprocess.STDOUT)
            deadline = time.monotonic()+10
            while not serial_path.exists():
                if process.poll() is not None or time.monotonic()>deadline:
                    raise RuntimeError('QEMU serial socket unavailable; inspect qemu.log')
                time.sleep(.02)
            serial = socket.socket(socket.AF_UNIX)
            serial.settimeout(.1)
            serial.connect(str(serial_path))
            wait(b'space interactive shell',allow_denial=args.allow_boot_denial)
            def calc():
                command('runapp calc', b'calc: integer REPL')
                command('2+3*4', b'calc: 2+3*4 = 14')
                command('(18-6)/4', b'calc: (18-6)/4 = 3')
                command('7/0', b'calc: divide by zero')
                command('q', b'runapp: app-calc returned 0x0000000000000000')
            scenario('calc arithmetic and divide-by-zero recovery', calc)
            note = b'real native app save and reopen'
            def notes_frame(content, dirty, start, column=None):
                if column is None: column=len(content)
                end_marker=b'\x1b[?25h'
                wait(end_marker,start)
                end=log.index(end_marker,start)+len(end_marker)
                frame_start=log.find(b'\x1b[?25l',start,end)
                if frame_start<0:
                    raise RuntimeError('notes redraw lost cursor-hide sequence')
                expected=b'\x1b[?25l\x1b[2J'
                for row in range(1,23):
                    expected+=f'\x1b[{row};1H'.encode()
                    expected+=(b'   1 '+content) if row==1 else b'    ~'
                    expected+=b'\x1b[0K'
                expected+=b'\x1b[24;1H\x1b[7m notes.txt'+(b'+' if dirty else b' ')
                expected+=f'  1:{column+1}  1 lines'.encode()
                expected+=b'\x1b[0K\x1b[0m'+f'\x1b[1;{column+6}H'.encode()+end_marker
                actual=bytes(log[frame_start:end])
                report['last_render']={'content_hex':content.hex(),'serial_offset':frame_start,
                                       'actual_bytes':len(actual),'expected_bytes':len(expected)}
                if actual!=expected:
                    (output/'failed-render-actual.bin').write_bytes(actual)
                    (output/'failed-render-expected.bin').write_bytes(expected)
                    raise RuntimeError('notes redraw bytes differ; inspect failed-render artifacts')
            def notes():
                start=command('runapp notes', b'notes.txt')
                notes_frame(b'',False,start)
                # Complete each redraw before the next key, checking every
                # ANSI/content byte as well as the visible text prefix.
                for count in range(1, len(note)+1):
                    start = send(note[count-1:count])
                    wait(note[:count], start)
                    notes_frame(note[:count],True,start)
                start = send(b'\x13')
                wait(b'SAVED', start)
                start = send(b'\x11')
                wait(b'runapp: app-notes returned 0x0000000000000000', start)
                start = command('runapp notes', b'notes.txt')
                wait(note, start)
                notes_frame(note,False,start,column=0)
                start = send(b'\x11')
                wait(b'runapp: app-notes returned 0x0000000000000000', start)
            scenario('notes edit save close and reopen within one boot', notes)
            crc = zlib.crc32(note)
            scenario('sum verifies notes bytes and host-computed CRC32', lambda: run_app(
                'sum notes.txt', [f'sum: notes.txt {len(note)} bytes crc32 0x{crc:08x}'.encode(), b'sum: ok']))
            def hd():
                command('runapp hd', b'hd> ')
                start = command('notes.txt', b'hd: dumped')
                wait(b'runapp: app-hd returned 0x0000000000000000', start)
                if b'0000  72 65 61 6c ' not in log[start:]:
                    raise RuntimeError('hex dump does not match saved file bytes 72 65 61 6c')
            scenario('hd opens saved notes file', hd)
            scenario('files write read-back delete', lambda: run_app('files',
                [b'files: read-back verified 46 bytes', b'files: cleaned up', b'files: ok']))
            scenario('man renders application platform manual', lambda: run_app('man',
                [b'man: Space application platform manual, APP-API v1']))
            scenario('clock reports calendar and uptime', lambda: run_app('clock', [b'clock: 20', b'(uptime ']))
            scenario('sysinfo reports granted capabilities', lambda: run_app('sysinfo',
                [b'app-sysinfo: granted caps 0x0000000000000001'], b'308662a96818da74'))
            def sysmon():
                command('runapp sysmon', b'sysmon: kernel state')
                command('q', b'runapp: app-sysmon returned 0x0000000000000000')
            scenario('sysmon starts and exits interactively', sysmon)
            scenario('bench computes known prime count', lambda: run_app('bench', [b'bench: found 9592 primes'], b'0000000000002578'))
            scenario('unknown application is refused', lambda: command('runapp no-such-app', b'runapp: unknown app'))
            for cycle in range(args.repeat_cycles):
                def repeat_pair():
                    calc()
                    run_app('sum notes.txt',[f'sum: notes.txt {len(note)} bytes crc32 0x{crc:08x}'.encode()])
                scenario(f'same-boot lifecycle {cycle+1}: actual calc and checksum',repeat_pair)
                if report['scenarios'][-1]['status']!='passed':
                    raise RuntimeError(f'same-boot lifecycle cycle {cycle+1} failed')
            command('halt', b'halting on request')
            report['status'] = 'failed' if any(x['status']=='failed' for x in report['scenarios']) else 'passed'
    except Exception as error:
        report.update(status='failed', error=str(error))
        print('FAIL:', error, flush=True)
    finally:
        if serial:
            serial.close()
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        report['passed'] = sum(x['status']=='passed' for x in report['scenarios'])
        report['failed'] = sum(x['status']=='failed' for x in report['scenarios'])
        report['not_run'] = 11+args.repeat_cycles-len(report['scenarios'])
        save()
    print(f"{report['passed']} passed, {report['failed']} failed, {report['not_run']} not run; {output/'report.json'}")
    return 0 if report['status']=='passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
