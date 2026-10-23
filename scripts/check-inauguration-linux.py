#!/usr/bin/env python3
"""Compare synthetic ordinary Inauguration Linux ELFs on host and strict Space CPL3.

This compiler corpus is separate from unmodified upstream jq/Lua applications.
Identical ELF bytes execute on Linux and Space. The privileged instruction case
is an explicit negative control: host SIGSEGV maps to Space's controlled #GP.
"""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import re
import resource
import shutil
import struct
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def no_core():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def inspect_elf(path):
    data = path.read_bytes()
    require(data[:7] == b'\x7fELF\x02\x01\x01', 'not owned ELF64 little endian')
    require(struct.unpack_from('<HH', data, 16) == (2, 62), 'expected static x86_64 ET_EXEC')
    offset = struct.unpack_from('<Q', data, 32)[0]
    width, count = struct.unpack_from('<HH', data, 54)
    require(width == 56 and 0 < count <= 32, 'invalid program header table')
    segments = []
    nx_stack = False
    for index in range(count):
        kind, flags, file_offset, address, _, files, memory, align = struct.unpack_from('<IIQQQQQQ', data, offset + index * width)
        require(kind not in (2, 3), 'dynamic loader/runtime substitution is not allowed')
        if kind == 0x6474E551:
            require(flags == 6, 'owned ELF stack must be RW and non-executable')
            nx_stack = True
        if kind == 1:
            require(flags in (4, 5, 6) and 0 < files <= memory, 'empty or W+X load segment')
            require(file_offset + files <= len(data), 'load segment exceeds file')
            segments.append(dict(flags=flags, offset=file_offset, address=address, file_size=files, memory_size=memory, alignment=align))
    require(nx_stack, 'owned ELF must explicitly declare a non-executable stack')
    require({row['flags'] for row in segments} >= {5, 6}, 'corpus must exercise separate RX text and RW data')
    return segments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--in', dest='compiler', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--root', choices=('standard', 'minimal'), default='standard')
    parser.add_argument('--repeat', type=int, default=21, help='complete measured cycles after warming every ELF')
    args = parser.parse_args()
    require(platform.system() == 'Linux' and platform.machine() == 'x86_64', 'the native host oracle requires Linux x86_64')
    args.compiler = args.compiler.resolve()
    args.out = args.out.resolve()
    require(1 <= args.repeat <= 100, '--repeat must be 1..100')
    require(not args.out.exists() or not any(args.out.iterdir()), '--out must be new or empty')
    args.out.mkdir(parents=True, exist_ok=True)
    report = dict(category='synthetic compiler corpus; not upstream applications', status='running', host_status='not-run', space_status='not-run', root=args.root, repeat=args.repeat, artifacts=[], executions=[])
    qemu = None
    try:
        compiler_hash = digest(args.compiler)
        version = subprocess.check_output([str(args.compiler), '--version'], text=True).strip()
        report['compiler'] = dict(path=str(args.compiler), sha256=compiler_hash, version=version)
        # Freeze imported sources before compiling; other work can continue in
        # the shared checkout without changing this gate's build inputs.
        snapshot = args.out / 'source-snapshot'
        files = []
        for directory in ('components', 'kernel', 'boot', 'protocol', 'services'):
            files.extend(path for path in (ROOT / directory).rglob('*') if path.suffix in ('.in', '.asm'))
        files.extend((ROOT / 'fixtures/inauguration-linux').iterdir())
        files.append(ROOT / 'fixtures/linux-process/checks.in')
        hashes = {}
        for source in files:
            if not source.is_file():
                continue
            target = snapshot / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            hashes[str(source.relative_to(ROOT))] = digest(target)
        report['source_sha256'] = hashes
        fixture_root = snapshot / 'fixtures/inauguration-linux'
        manifest = json.loads((fixture_root / 'manifest.json').read_text())
        rows = report['artifacts']
        for case in manifest['cases']:
            for profile in manifest['profiles']:
                name = case['name'] + '-' + profile
                executable = args.out / name
                command = [str(args.compiler), 'compile', '--path', str(fixture_root / case['source']), '--target', 'native', '--target-triple', manifest['target'], '--linkage', 'executable', '--entry', 'main', '--profile', profile, '--out', str(executable), '--json']
                result = subprocess.run(command, capture_output=True, timeout=60)
                (args.out / (name + '.compile.json')).write_bytes(result.stdout)
                (args.out / (name + '.compile.stderr')).write_bytes(result.stderr)
                compiled = json.loads(result.stdout)
                require(result.returncode == 0 and compiled.get('success'), name + ': compiler refused: ' + str(compiled.get('reason')))
                require(compiled.get('external_invocations') == [], name + ': external compiler invocation')
                segments = inspect_elf(executable)
                data = executable.read_bytes()
                if case.get('owned_memcpy'):
                    require(bytes.fromhex('4889f84889d1fcf3a4c3') in data, name + ': owned memcpy absent')
                oracle = subprocess.run([str(executable)], capture_output=True, timeout=10, preexec_fn=no_core)
                require(oracle.returncode == case['host_exit'], name + ': host oracle status mismatch')
                require(not oracle.stdout and not oracle.stderr, name + ': unexpected host output')
                row = dict(case, profile=profile, name=name, index=len(rows), path=str(executable), sha256=digest(executable), size=executable.stat().st_size, segments=segments, host=dict(exit=oracle.returncode, stdout='', stderr=''), command=command)
                row['physical_address'] = 0x10000000 + row['index'] * 0x200000
                rows.append(row)
        report['host_status'] = 'passed'
        report['root_note'] = 'production standard bootstrap with a test-only adapter' if args.root == 'standard' else 'minimal bootstrap with explicitly imported Linux process component and a test-only adapter'
        # This adds a test adapter to a snapshot, never a product shell command
        # or a second Linux translator. Calls go through the existing runtime.
        root_file = 'kernel-root.in' if args.root == 'standard' else 'kernel-root-minimal.in'
        source = (snapshot / 'kernel' / root_file).read_text()
        source = re.sub(r'import "\.\./([^"]+)"', lambda match: 'import ' + json.dumps(str(snapshot / match.group(1))), source)
        imports = [snapshot / 'components/linux-process.in', snapshot / 'fixtures/linux-process/checks.in', fixture_root / 'runtime.in']
        source = ''.join('import ' + json.dumps(str(path)) + '\n' for path in imports) + source
        require(source.count('  shell(port)') == 1, 'kernel entry shell hook changed')
        source = source.replace('  shell(port)', '  compiler-corpus-test(port)\n  shell(port)')
        def calls(measured):
            return '\n'.join(f'compiler-corpus-case(port,{row["index"]},{row["physical_address"]},{row["size"]},{row["space_exit"]},{measured});' for row in rows)
        source += '\nfn compiler-corpus-test(port:Int)->Void{\ncompiler-corpus-init();\n' + calls(0) + '\ncompiler-corpus-baseline();\nlet cycle=0;while cycle<' + str(args.repeat) + '{\n' + calls(1) + '\ncycle=cycle+1;}\ncompiler-corpus-finish(port);\n}\n'
        kernel_source = args.out / 'kernel.in'
        kernel_source.write_text(source)
        kernel = args.out / 'kernel.bin'
        commands = [
            ['nasm', '-f', 'bin', str(snapshot / 'boot/multiboot.asm'), '-o', str(args.out / 'trampoline.bin')],
            [str(args.compiler), 'compile', '--path', str(kernel_source), '--entry', 'kernel-entry', '--emit', 'boot', '--trampoline', str(args.out / 'trampoline.bin'), '--target', 'native', '--target-triple', 'x86_64-unknown-none', '--linkage', 'static-lib', '--out', str(kernel)],
        ]
        report['kernel_commands'] = commands
        with (args.out / 'compile.log').open('w') as log:
            for command in commands:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180, cwd=snapshot)
        metadata = json.loads(kernel.with_suffix('.component-metadata.json').read_text())
        layout = metadata['boot_layout']
        report['boot_layout'] = layout
        require(layout['file_size'] == kernel.stat().st_size, 'boot layout size mismatch')
        require(layout['load_end'] == layout['load_base'] + kernel.stat().st_size, 'boot loaded range mismatch')
        require(layout['load_end'] <= min(row['physical_address'] for row in rows), 'kernel/payload physical overlap')
        qcommand = ['qemu-system-x86_64', '-cpu', 'max', '-kernel', str(kernel), '-m', '512M', '-display', 'none', '-no-reboot', '-serial', 'file:' + str(args.out / 'serial.log')]
        for row in rows:
            qcommand += ['-device', f'loader,file={row["path"]},addr={row["physical_address"]},force-raw=on']
        report['qemu_command'] = qcommand
        with (args.out / 'qemu.log').open('w') as log:
            qemu = subprocess.Popen(qcommand, stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + max(120, args.repeat * 12)
            while time.monotonic() < deadline:
                path = args.out / 'serial.log'
                data = path.read_bytes() if path.exists() else b''
                if b'compiler-corpus: passed activations ' in data or b'PANIC' in data or b'nanokernel fault handler halting' in data or qemu.poll() is not None:
                    break
                time.sleep(.05)
        text = (args.out / 'serial.log').read_text(errors='replace')
        require('PANIC' not in text and 'nanokernel fault handler halting' not in text, 'kernel failed; inspect serial.log')
        matches = list(re.finditer(r'compiler-corpus: begin (\d+) case (\d+)\n(.*?)compiler-corpus: end \1 case \2 status (-?\d+)\n', text, re.S))
        expected = len(rows) * (args.repeat + 1)
        require(len(matches) == expected, f'expected {expected} actual executions, found {len(matches)}; inspect serial.log')
        for activation, match in enumerate(matches):
            row = rows[activation % len(rows)]
            serial, case, body, status = match.groups()
            require(int(serial) == activation and int(case) == row['index'], 'execution order mismatch')
            syscalls = [int(number) for number in re.findall(r'^linux-process: syscall (\d+)$', body, re.M)]
            syscall_results = [dict(number=int(number), result=int(result)) for number, result in re.findall(r'linux-process: syscall (-?\d+)\nlinux-process: result (-?\d+)\n', body)]
            require(len(syscall_results) == len(syscalls), row['name'] + ': incomplete syscall trace')
            for call in syscall_results:
                if call['number'] == 9:
                    require(call['result'] > 0 and call['result'] % 4096 == 0, row['name'] + ': mmap did not return a real page-aligned guest address')
            require(set(row['syscalls']) <= set(syscalls), row['name'] + ': required real syscall absent')
            require(not set(row.get('forbidden_syscalls', [])) & set(syscalls), row['name'] + ': forbidden syscall occurred')
            faults = [int(vector, 16) for vector in re.findall(r'space: guest fault vector 0x([0-9A-Fa-f]+)', body)]
            require(faults == ([row['fault_vector']] if 'fault_vector' in row else []), row['name'] + ': unexpected CPU fault')
            remainder = re.sub(r'^linux-process: (?:syscall|result) -?\d+\n', '', body, flags=re.M)
            remainder = re.sub(r'^space: guest fault vector 0x[0-9A-Fa-f]+ rip 0x[0-9A-Fa-f]+\n', '', remainder, flags=re.M)
            require(not remainder, row['name'] + ': unexpected guest output: ' + repr(remainder))
            require(int(status) == row['space_exit'], row['name'] + ': Space/host contract mismatch')
            report['executions'].append(dict(activation=activation, case=row['name'], warmup=activation < len(rows), host_exit=row['host_exit'], space_exit=int(status), syscalls=syscalls, syscall_results=syscall_results, fault_vectors=faults, passed=True))
        require(f'compiler-corpus: passed activations {expected}\n' in text, 'cleanup/other-domain witness assertions did not finish')
        require(digest(args.compiler) == compiler_hash, 'compiler changed during gate')
        for row in rows:
            require(digest(Path(row['path'])) == row['sha256'], 'ELF changed after host/Space execution')
        report.update(status='passed', space_status='passed', kernel_sha256=digest(kernel), actual_activations=expected, normal_exit_activations=sum(rows[index % len(rows)]['outcome_kind'] == 'normal-exit' for index in range(expected)), owned_abort_activations=sum(rows[index % len(rows)]['outcome_kind'] == 'owned-abort' for index in range(expected)), hardware_negative_activations=sum(rows[index % len(rows)].get('negative_control', False) for index in range(expected)), cleanup='heap/free-list/domain table/owned bits/current cap/FS/syscall hook/budget/ledger and same-VA witness checked after every measured activation')
        print(f'PASS: synthetic compiler corpus, {len(rows)} host artifacts, {expected} actual Space activations; {args.out}')
    except Exception as error:
        report.update(status='failed', error=str(error))
        raise
    finally:
        if qemu is not None:
            qemu.terminate()
            try:
                qemu.wait(timeout=3)
            except subprocess.TimeoutExpired:
                qemu.kill()
                qemu.wait()
        (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
