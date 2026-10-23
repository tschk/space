#!/usr/bin/env python3
"""Probe pinned real ELF/Mach-O/PE binaries with Space's actual QEMU loaders.

This measures admission, not application execution. Refused applications are
reported blocked and the command returns 1. Foreign payloads are never invoked
by the trusted CPL0 fixture runner. A native host reference is labeled separately.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import socket
import struct
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = 0x280000
DESCRIPTOR = BASE - 32


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def describe(data, abi):
    if abi == 'linux':
        assert data[:6] == b'\x7fELF\x02\x01', 'expected little-endian ELF64'
        elf_type, machine = struct.unpack_from('<HH', data, 16)
        offset = struct.unpack_from('<Q', data, 32)[0]
        stride, count = struct.unpack_from('<HH', data, 54)
        assert machine == 62 and stride == 56 and offset + stride * count <= len(data)
        segments = [struct.unpack_from('<II6Q', data, offset + i * stride) for i in range(count)]
        return {'format': 'ELF64', 'machine': machine, 'type': elf_type,
                'program_headers': count, 'load_segments': sum(s[0] == 1 for s in segments),
                'interpreter': any(s[0] == 3 for s in segments),
                'blockers': ['Current loader requires one fixed-address RX program header, no BSS or process startup.']}
    if abi == 'darwin':
        header = struct.unpack_from('<8I', data)
        assert header[0] == 0xfeedfacf and header[1] == 0x1000007, 'expected x86_64 Mach-O'
        commands, offset = [], 32
        for _ in range(header[4]):
            cmd, size = struct.unpack_from('<II', data, offset)
            assert size >= 8 and offset + size <= len(data)
            commands.append(hex(cmd)); offset += size
        return {'format': 'Mach-O64', 'load_commands': commands, 'flags': hex(header[6]),
                'blockers': ['Current loader requires exactly one fixed-address RX segment and LC_MAIN; ordinary dyld/PIE/framework startup is unsupported.']}
    assert data[:2] == b'MZ', 'expected DOS/PE header'
    pe = struct.unpack_from('<I', data, 60)[0]
    signature, machine, sections = struct.unpack_from('<IHH', data, pe)
    assert signature == 0x4550 and machine == 0x8664, 'expected x86_64 PE'
    return {'format': 'PE32+', 'pe_header_offset': pe, 'sections': sections,
            'blockers': ['Current loader requires one fixed-address section and a bounded KERNEL32 import list; general relocation/import/process startup is unsupported.']}


def connect(path, process):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('QEMU exited before serial connection; inspect qemu.log')
        channel = socket.socket(socket.AF_UNIX)
        try:
            channel.connect(str(path)); channel.settimeout(.2); return channel
        except OSError:
            channel.close(); time.sleep(.05)
    raise TimeoutError('QEMU serial socket did not become ready')


def probe(kernel, binary, abi, directory):
    data = binary.read_bytes()
    image = kernel.read_bytes()
    descriptor_offset = DESCRIPTOR - 0x100000
    assert len(image) <= descriptor_offset, 'probe kernel overlaps descriptor/payload'
    # Preserve every input byte and its actual size. No fixture-sized truncation.
    combined = image + bytes(descriptor_offset - len(image))
    combined += struct.pack('<4Q', {'linux': 1, 'darwin': 2, 'windows': 3}[abi], len(data), 0, 0) + data
    (directory / 'combined.bin').write_bytes(combined)
    path = directory / 'serial.sock'
    command = ['qemu-system-x86_64', '-kernel', str(directory / 'combined.bin'),
               '-m', '256M', '-display', 'none', '-no-reboot',
               '-serial', f'unix:{path},server=on,wait=on']
    received = bytearray()
    with (directory / 'qemu.log').open('w') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        channel = None
        try:
            channel = connect(path, process)
            deadline = time.monotonic() + 30
            while b'space interactive shell' not in received and time.monotonic() < deadline:
                try:
                    part = channel.recv(65536)
                    if not part:
                        break
                    received.extend(part)
                except socket.timeout:
                    if process.poll() is not None:
                        break
            text = received.decode(errors='replace')
            match = re.search(r'real-app: validator result (-?\d+)\r?\n', text)
            assert match is not None, text
            result = int(match.group(1))
            assert result == -8 or result >= 0, text
            assert 'real-app: payload was not executed\n' in text, text
            assert 'space interactive shell' in text, text
            assert 'CPU EXCEPTION' not in text and 'nanokernel fault' not in text, text
            channel.sendall(b'halt\n')
            return {'probe_status': 'passed', 'admission_return': result,
                    'application_status': 'blocked' if result < 0 else 'admitted-not-executed', 'application_executed': False,
                    'serial_log': str(directory / 'serial.log'), 'qemu_command': command}
        finally:
            (directory / 'serial.log').write_bytes(received)
            if channel:
                channel.close()
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
            if path.exists():
                path.unlink()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--in', dest='compiler', type=Path, required=True)
    p.add_argument('--manifest', type=Path, default=ROOT / 'fixtures/applications/jq-1.8.1.json')
    p.add_argument('--apps-dir', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--download', action='store_true', help='Fetch pinned release binaries into apps-dir')
    a = p.parse_args()
    a.out = a.out.resolve(); a.apps_dir = a.apps_dir.resolve(); a.compiler = a.compiler.resolve()
    if a.out.exists() and any(a.out.iterdir()):
        p.error('--out must be new or empty; earlier evidence is preserved')
    a.out.mkdir(parents=True, exist_ok=True); a.apps_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(a.manifest.read_text())
    report = {'schema_version': 1, 'evidence': 'real-binary-admission-only',
              'manifest_sha256': sha(a.manifest), 'compiler_sha256': sha(a.compiler),
              'space_commit': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
              'loader_sha256': {name: sha(ROOT / name) for name in ['components/posix.in', 'components/darwin-macho.in', 'components/windows-pe.in']},
              'apps': []}
    report_path = a.out / 'report.json'
    def save():
        report_path.write_text(json.dumps(report, indent=2) + '\n')
    source = a.out / 'probe.in'
    source.write_text('package space.kernel\nimport ' + json.dumps(str(ROOT / 'kernel/kernel-root.in')) + '''
fn real-app-probe-entry(mb-info: Int) -> Int {
  let port = com1()
  serial-init(port)
  let kind = load64(0x27FFE0)
  let size = load64(0x27FFE8)
  let rc = -99
  if kind == 1 { rc = posix-elf-entry(0x280000, size) }
  if kind == 2 { rc = darwin-macho-entry(0x280000, size) }
  if kind == 3 { rc = win-pe-entry(0x280000, size) }
  serial-write-cstr(port, "real-app: validator result ")
  serial-write-dec-wide(port, rc)
  serial-nl(port)
  serial-write-cstr(port, "real-app: payload was not executed")
  serial-nl(port)
  return kernel-entry(mb-info)
}
''')
    subprocess.run(['nasm', '-f', 'bin', str(ROOT / 'boot/multiboot.asm'), '-o', str(a.out / 'trampoline.bin')], check=True)
    kernel = a.out / 'kernel.bin'
    with (a.out / 'compile.log').open('w') as log:
        subprocess.run([str(a.compiler), 'compile', '--path', str(source), '--entry', 'real-app-probe-entry',
                        '--emit', 'boot', '--trampoline', str(a.out / 'trampoline.bin'), '--target', 'native',
                        '--target-triple', 'x86_64-unknown-none', '--linkage', 'static-lib', '--out', str(kernel)],
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
    report['probe_source_sha256'] = sha(source); report['kernel_sha256'] = sha(kernel)
    save()
    for app in manifest['apps']:
        row = dict(app, application_status='not-tested', application_executed=False)
        report['apps'].append(row); save()
        directory = a.out / app['id']; directory.mkdir()
        try:
            binary = a.apps_dir / app['filename']
            if not binary.exists() and a.download:
                with urllib.request.urlopen(app['url'], timeout=60) as response:
                    data = response.read(32 * 1024 * 1024 + 1)
                assert len(data) <= 32 * 1024 * 1024, 'download exceeds app lab limit'
                assert hashlib.sha256(data).hexdigest() == app['sha256'], 'download checksum mismatch'
                binary.write_bytes(data)
            assert binary.is_file(), 'missing binary; provide apps-dir or --download'
            assert sha(binary) == app['sha256'], 'binary checksum mismatch'
            assert binary.stat().st_size == app['size_bytes'], 'binary size mismatch'
            row['binary_description'] = describe(binary.read_bytes(), app['personality'])
            if app['size_bytes'] > 0x200000:
                row['binary_description']['blockers'].insert(0, 'Binary exceeds current 2 MiB fixture admission limit.')
            row['host_reference'] = {'status': 'not-run', 'reason': 'Host platform does not match this binary.'}
            if app['personality'] == 'linux' and platform.system() == 'Linux' and platform.machine() == 'x86_64':
                binary.chmod(binary.stat().st_mode | 0o100)
                command = [str(binary), *app['scenario']['args']]
                result = subprocess.run(command, capture_output=True, text=True, timeout=15)
                version = subprocess.run([str(binary), '--version'], capture_output=True, text=True, timeout=15)
                (directory / 'host-stdout.log').write_text(result.stdout)
                (directory / 'host-stderr.log').write_text(result.stderr)
                assert result.returncode == app['scenario']['exit_code'] and result.stdout == app['scenario']['stdout']
                assert version.returncode == 0 and version.stdout.strip() == 'jq-' + app['version']
                row['host_reference'] = {'status': 'passed', 'command': command, 'exit_code': result.returncode,
                                         'stdout': result.stdout, 'version_stdout': version.stdout,
                                         'scope': 'Host Linux execution; not Space application coverage.'}
            row['probes'] = []
            for cycle in range(2):
                case = directory / f'cycle-{cycle + 1}'; case.mkdir()
                row['probes'].append(probe(kernel, binary, app['personality'], case))
            outcomes = {case['application_status'] for case in row['probes']}
            assert len(outcomes) == 1, 'loader admission changed between repeated boots'
            row['application_status'] = outcomes.pop()
            print(f"{row['application_status'].upper()} {app['id']}: admission measured in two QEMU boots; no foreign execution", flush=True)
        except (OSError, AssertionError, ValueError, subprocess.SubprocessError) as error:
            row.update(application_status='test-error', error=str(error))
            print(f"ERROR {app['id']}: {error}", flush=True)
        save()
    report['summary'] = {status: sum(row['application_status'] == status for row in report['apps'])
                         for status in ['passed', 'blocked', 'admitted-not-executed', 'test-error']}
    save()
    print(f"Application results: {report['summary']}; {report_path}")
    return 1 if any(row['application_status'] != 'passed' for row in report['apps']) else 0


if __name__ == '__main__':
    raise SystemExit(main())
