#!/usr/bin/env python3
"""Try pinned original GUI ELF admission; blocked applications never count as passes.

--index is a local acquisition JSON with apps[{id,binary}]. Full host SHA256
checks bind every executable to the committed manifest. The native oracle checks
64-byte samples at the start, end and each MiB; it is not a full-byte oracle.
No foreign code is entered, and no host runtime is forwarded into Space.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inspect_elf(path, out):
    result = {}
    for name, flags in [('headers', ['-hW', '-lW']), ('dynamic', ['-dW']),
                        ('symbols', ['--dyn-syms', '-W']), ('versions', ['-VW'])]:
        text = subprocess.check_output(['readelf', *flags, str(path)], text=True, timeout=30)
        (out / (name + '.txt')).write_text(text)
        result[name] = text
    with path.open('rb') as stream:
        header = stream.read(64)
    return {
        'elf_type': struct.unpack_from('<H', header, 16)[0],
        'machine': struct.unpack_from('<H', header, 18)[0],
        'interpreter': (re.findall(r'Requesting program interpreter: ([^\]]+)', result['headers']) or [None])[0],
        'needed': re.findall(r'\(NEEDED\).*?\[([^\]]+)\]', result['dynamic']),
        'undefined_symbols': sorted(set(re.findall(r'\bUND\s+(\S+)', result['symbols']))),
        'load_segments': sum(bool(re.match(r'\s*LOAD\s', line)) for line in result['headers'].splitlines()),
        'current_profile_blockers': (
            (['exceeds current 16 MiB image bound'] if path.stat().st_size > 0x1000000 else [])
            + (['ELF PIE relocation and dynamic-loader startup'] if struct.unpack_from('<H', header, 16)[0] == 3 else [])
            + (['PT_INTERP/shared-library initialization'] if 'INTERP' in result['headers'] else [])),
    }


def sample_table(path):
    size = path.stat().st_size
    offsets = sorted({0, size - 64, *range(0, size - 63, 1024 * 1024)})
    assert len(offsets) <= 1024 and 64 <= size <= 0x20000000
    data = bytearray(struct.pack('<QQ', size, len(offsets)))
    with path.open('rb') as stream:
        for offset in offsets:
            stream.seek(offset)
            sample = stream.read(64)
            assert len(sample) == 64
            digest = 0xcbf29ce484222325
            for byte in sample:
                digest = ((digest ^ byte) * 0x100000001b3) & ((1 << 64) - 1)
            data += struct.pack('<QQ', offset, digest)
    return data, offsets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--in', dest='compiler', type=Path, required=True)
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--app', action='append', help='Selected manifest id; default all')
    args = parser.parse_args()
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    compiler = args.compiler.resolve()
    manifest = ROOT / 'fixtures/applications/desktop-corpus.json'
    pins = json.loads(manifest.read_text())['apps']
    if args.app:
        assert set(args.app) <= {pin['id'] for pin in pins}, 'unknown app id'
        pins = [pin for pin in pins if pin['id'] in args.app]
    paths = {row['id']: Path(row['binary']).resolve() for row in json.loads(args.index.read_text())['apps']}
    tracked = [path for directory in ('components', 'kernel', 'protocol', 'services')
               for path in (ROOT / directory).rglob('*.in')]
    tracked += [ROOT / 'boot/multiboot.asm', ROOT / 'fixtures/applications/desktop-admission.in',
                Path(__file__).resolve(), manifest]
    sources = {str(path.relative_to(ROOT)): sha(path) for path in tracked}
    report = dict(goal_status='OPEN', status='running', scope=__doc__,
                  source_sha256=sources, compiler_sha256=sha(compiler), applications=[])

    def save():
        (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')

    save()
    try:
        source = args.out / 'probe.in'
        source.write_text('package space.kernel\n' + '\n'.join(
            'import ' + json.dumps(str(ROOT / path)) for path in
            ['kernel/kernel-root.in', 'components/linux-process.in', 'fixtures/applications/desktop-admission.in']) + '\n')
        trampoline = args.out / 'trampoline.bin'
        subprocess.run(['nasm', '-f', 'bin', str(ROOT / 'boot/multiboot.asm'), '-o', str(trampoline)], check=True, timeout=30)
        kernel = args.out / 'probe.bin'
        command = [str(compiler), 'compile', '--path', str(source), '--entry', 'desktop-admission-entry',
                   '--emit', 'boot', '--trampoline', str(trampoline), '--target', 'native',
                   '--target-triple', 'x86_64-unknown-none', '--linkage', 'static-lib', '--out', str(kernel)]
        report['compile_command'] = command
        with (args.out / 'compile.log').open('w') as log:
            subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=180)
        report['kernel_sha256'] = sha(kernel)
        for pin in pins:
            folder = args.out / pin['id']; folder.mkdir()
            app = paths[pin['id']]
            row = dict(id=pin['id'], name=pin['name'], application_status='not-tested',
                       execution_started=False, artifact_sha256=sha(app), binary=str(app))
            report['applications'].append(row); save()
            assert app.stat().st_size == pin['size_bytes'] and row['artifact_sha256'] == pin['sha256'], 'pinned artifact mismatch'
            row['elf'] = inspect_elf(app, folder)
            table, offsets = sample_table(app)
            (folder / 'samples.bin').write_bytes(table)
            row['sampled_byte_oracle'] = dict(bytes_per_sample=64, offsets=offsets, full_byte_oracle=False)
            command = ['qemu-system-x86_64', '-kernel', str(kernel), '-m', '1G', '-display', 'none', '-no-reboot',
                       '-serial', 'file:' + str(folder / 'serial.log'), '-device', 'isa-debug-exit,iobase=0xf4,iosize=0x04',
                       '-device', 'loader,file=' + str(app) + ',addr=0x10000000,force-raw=on',
                       '-device', 'loader,file=' + str(folder / 'samples.bin') + ',addr=0x0f000000,force-raw=on']
            row['qemu_command'] = command; save()
            with (folder / 'qemu.log').open('w') as log:
                result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=90)
            serial = (folder / 'serial.log').read_text()
            assert result.returncode == 33, serial
            assert 'desktop: sampled original payload PASS\n' in serial, serial
            assert 'desktop: unchanged resources; application not entered PASS\n' in serial, serial
            admission = int(re.search(r'desktop: admission (-?\d+)\n', serial)[1])
            row.update(probe_status='passed', admission_return=admission,
                       application_status='blocked' if admission < 0 else 'admitted-not-executed')
            assert sha(app) == pin['sha256'], 'artifact changed during run'
            print(pin['name'] + ': ' + row['application_status'], flush=True)
            save()
        changed = [name for name, digest in sources.items() if sha(ROOT / name) != digest]
        assert not changed and sha(compiler) == report['compiler_sha256'], 'inputs changed during run'
        report.update(status='blocked', source_changed_during_run=changed, compiler_changed_during_run=False,
                      original_application_entries=0, successful_applications=0,
                      blocked=sum(row['application_status'] == 'blocked' for row in report['applications']))
    except Exception as error:
        report.update(status='test-error', error=str(error))
    finally:
        save()
    print(report['status'].upper() + ': ' + str(args.out / 'report.json'))
    return 1  # Admission diagnostics are never successful application executions.


if __name__ == '__main__':
    raise SystemExit(main())
