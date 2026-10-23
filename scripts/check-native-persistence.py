#!/usr/bin/env python3
"""Prove actual notes saves survive independent QEMU/NVMe boots.

Creates one owned disposable 64 MiB raw disk beneath a new evidence directory.
It never accepts a host disk path, seeds file content, or counts RAM fallback as
persistence. Boot A formats explicitly; boots B/C reuse exactly that disk.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
import struct
import subprocess
import time
import zlib

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_disk_file(path, name):
    """Read-only oracle for the current bounded SparkFS root/direct/inline ABI."""
    data = path.read_bytes()
    def u32(offset): return struct.unpack_from('<I', data, offset)[0]
    def u64(offset): return struct.unpack_from('<Q', data, offset)[0]
    if (u32(0), u32(4), u32(8)) != (0x53504146, 1, 4096):
        raise AssertionError('owned raw disk lacks the SparkFS superblock')
    total, count, table, root = u64(12), u32(20), u64(40), u32(56)
    assert 2 <= total <= len(data)//4096 and 0 < count <= 4096 and root < count
    assert table < total and table*4096+count*256 <= len(data)
    def inode(number):
        assert 0 <= number < count
        return table*4096+number*256
    directory = inode(root)
    assert u32(directory) == 2
    directory_size = u64(directory+16)
    assert directory_size <= 12*4096
    found = None
    for block_index in range((directory_size+4095)//4096):
        block = u64(directory+64+block_index*8)
        assert 0 < block < total
        for offset in range(block*4096, (block+1)*4096, 32):
            number, length = u32(offset), data[offset+4]
            if number and data[offset+8:offset+8+length] == name.encode():
                assert length <= 24
                found = number
                break
    if found is None:
        raise AssertionError(f'{name} missing from persisted root directory')
    record = inode(found)
    assert u32(record) == 1
    size = u64(record+16)
    assert size <= (12+512)*4096
    if u32(record+176):
        assert size <= 96
        content = data[record+64:record+64+size]
    else:
        content = bytearray()
        for index in range((size+4095)//4096):
            if index < 12:
                block = u64(record+64+index*8)
            else:
                indirect = u64(record+160)
                assert 0 < indirect < total
                block = u64(indirect*4096+(index-12)*8)
            assert 0 < block < total
            content.extend(data[block*4096:(block+1)*4096])
        content = bytes(content[:size])
    return {'inode': found, 'bytes': size, 'sha256': hashlib.sha256(content).hexdigest()}, content


class Boot:
    def __init__(self, image, disk, output, qemu, timeout, receipt):
        self.output, self.timeout, self.receipt = output, timeout, receipt
        output.mkdir()
        self.log = bytearray()
        self.serial = None
        self.process = None
        self.qlog = (output/'qemu.log').open('w')
        path = output/'serial.sock'
        command = [qemu, '-kernel', str(image), '-m', '512M', '-display', 'none', '-no-reboot',
                   '-serial', f'unix:{path},server=on,wait=on',
                   '-drive', f'file={disk},format=raw,if=none,id=owned,cache=writethrough',
                   '-device', 'nvme,drive=owned,serial=space-persistence']
        receipt.update(command=command, inputs=[], checks=[])
        try:
            self.process = subprocess.Popen(command, stdout=self.qlog, stderr=subprocess.STDOUT)
            deadline = time.monotonic()+10
            while not path.exists():
                if self.process.poll() is not None or time.monotonic()>deadline:
                    raise RuntimeError('QEMU serial socket unavailable')
                time.sleep(.02)
            self.serial = socket.socket(socket.AF_UNIX)
            self.serial.settimeout(.1)
            self.serial.connect(str(path))
            self.wait(b'space interactive shell')
            if b'nvme: storage component ready' not in self.log:
                raise RuntimeError('real NVMe backend unavailable; refusing to count RAM fallback')
            receipt['backend'] = 'NVMe driver and direct SparkFS; no Volume SCI in standard image'
        except Exception:
            self.close()
            raise

    def wait(self, marker, start=0):
        self.receipt['last_wait'] = {'marker_hex': marker.hex(), 'serial_offset': start}
        deadline = time.monotonic()+self.timeout
        while marker not in self.log[start:]:
            if time.monotonic()>deadline:
                raise RuntimeError(f'timeout awaiting {marker!r}')
            if any(error in self.log[start:] for error in (b'CPU EXCEPTION', b'nanokernel fault', b'SCI: DENIED')):
                raise RuntimeError('guest fault/admission refusal; inspect boot serial log')
            try:
                data = self.serial.recv(65536)
                if not data: raise RuntimeError('QEMU serial socket closed')
                self.log.extend(data)
            except socket.timeout:
                if self.process.poll() is not None: raise RuntimeError('QEMU exited')
        self.persist_log()

    def persist_log(self):
        (self.output/'serial.log').write_bytes(self.log)

    def send(self, data):
        start = len(self.log)
        self.receipt['inputs'].append({'data_hex': data.hex(), 'serial_offset': start})
        self.serial.sendall(data)
        return start

    def command(self, command, expected):
        start = self.send(command.encode()+b'\n')
        self.wait(expected, start)
        return start

    def frame(self, content, column, dirty, start):
        marker = b'\x1b[?25h'
        self.wait(marker, start)
        end = self.log.index(marker, start)+len(marker)
        first = self.log.find(b'\x1b[?25l', start, end)
        assert first >= 0, 'notes cursor-hide sequence missing'
        expected = b'\x1b[?25l\x1b[2J'
        for row in range(1,23):
            expected += f'\x1b[{row};1H'.encode()
            expected += b'   1 '+content if row == 1 else b'    ~'
            expected += b'\x1b[0K'
        expected += b'\x1b[24;1H\x1b[7m notes.txt'+(b'+' if dirty else b' ')
        expected += f'  1:{column+1}  1 lines'.encode()
        expected += b'\x1b[0K\x1b[0m'+f'\x1b[1;{column+6}H'.encode()+marker
        actual = bytes(self.log[first:end])
        if actual != expected:
            (self.output/'failed-frame-actual.bin').write_bytes(actual)
            (self.output/'failed-frame-expected.bin').write_bytes(expected)
            raise AssertionError('complete notes redraw differs')

    def open_notes(self, content):
        start = self.command('runapp notes', b'notes.txt')
        self.frame(content,0,False,start)

    def type_notes(self, content, suffix):
        if content:
            start = self.send(b'\x1b[F')
            self.frame(content,len(content),False,start)
        for byte in suffix:
            content += bytes([byte])
            start = self.send(bytes([byte]))
            self.frame(content,len(content),True,start)
        start = self.send(b'\x13')
        self.wait(b'SAVED',start)
        self.close_notes()
        return content

    def close_notes(self):
        start = self.send(b'\x11')
        self.wait(b'runapp: app-notes returned 0x0000000000000000',start)

    def checksum(self, content):
        expected = f'sum: notes.txt {len(content)} bytes crc32 0x{zlib.crc32(content):08x}'.encode()
        start = self.command('runapp sum notes.txt', expected)
        self.wait(b'runapp: app-sum returned 0x0000000000000000', start)
        self.receipt['checks'].append({'name': 'separate sum process verifies exact bytes and CRC32', 'expected_hex':expected.hex()})

    def halt(self):
        self.command('halt', b'halting on request')
        self.close()

    def close(self):
        self.persist_log()
        if self.serial:
            self.serial.close()
            self.serial = None
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try: self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.qlog.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--qemu',default='qemu-system-x86_64')
    parser.add_argument('--in',dest='compiler',type=Path,help='Record selected source-built compiler provenance')
    parser.add_argument('--timeout',type=float,default=30)
    args = parser.parse_args()
    image, output = args.image.resolve(), args.out.resolve()
    if not image.is_file(): parser.error('--image requires a built standard image')
    if args.compiler is not None and not args.compiler.is_file(): parser.error('--in requires an existing compiler')
    if output.exists() and any(output.iterdir()): parser.error('--out must be new or empty')
    output.mkdir(parents=True,exist_ok=True)
    disk = output/'owned-nvme.img'
    with disk.open('xb') as file: file.truncate(64*1024*1024)
    note = (ROOT/'fixtures/native-persistence/note.txt').read_bytes().removesuffix(b'\n')
    assert note and len(note)+3 <= 70 and all(32 <= byte < 127 for byte in note)
    report = {'started_utc':datetime.now(timezone.utc).isoformat(), 'image':str(image),
              'image_sha256':sha(image), 'owned_disk':str(disk), 'disk_initial_sha256':sha(disk),
              'evidence':'actual native notes saves on NVMe across independent VM processes', 'boots':[],
              'test_script_sha256':sha(Path(__file__)),
              'fixture_sha256':sha(ROOT/'fixtures/native-persistence/note.txt')}
    if args.compiler is not None:
        report['compiler']={'path':str(args.compiler.resolve()),'sha256':sha(args.compiler),
                            'version':subprocess.run([str(args.compiler.resolve()),'--version'],capture_output=True,text=True,check=True).stdout.strip()}
    boot = None
    try:
        content = b''
        for name, suffix in [('A',note),('B',b' v2'),('C',None)]:
            row = {'name':name,'status':'running','disk_before_sha256':sha(disk)}
            report['boots'].append(row)
            boot = Boot(image,disk,output/name,args.qemu,args.timeout,row)
            if name == 'A':
                # The raw file belongs exclusively to this test; formatting is
                # issued through Space, never by writing a host-side seed.
                boot.command('format', b'disk formatted')
            boot.open_notes(content)
            if suffix is not None:
                content = boot.type_notes(content,suffix)
                boot.open_notes(content)
            boot.close_notes()
            boot.checksum(content)
            boot.halt()
            boot = None
            metadata, actual = read_disk_file(disk,'notes.txt')
            assert actual == content, 'host raw-disk bytes differ from saved content'
            row.update(status='passed',disk_after_sha256=sha(disk),persisted_file=metadata,
                       expected_content_hex=content.hex())
            (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
            print(f'PASS boot {name}: notes, exact checksum and independently read raw-disk content',flush=True)
        report['status']='passed'
    except Exception as error:
        report.update(status='failed',error=str(error))
        if report['boots']: report['boots'][-1].update(status='failed',error=str(error))
        print('FAIL:',error,flush=True)
    finally:
        if boot: boot.close()
        report.update(finished_utc=datetime.now(timezone.utc).isoformat(),disk_final_sha256=sha(disk))
        (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['status']=='passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
