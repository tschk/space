#!/usr/bin/env python3
"""Execute synthetic ordinary Linux ELF blocking graphs under strict Space CPL3.

Upstream application coverage is separately exercised by
check-linux-blocking-pipeline.py. Neither suite replaces the completed23 cases.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ('large-single-write', 'transfer.asm', None, 42, 0),
    ('atomic-two-writers', 'atomic.asm', None, 42, 0),
    ('eof-wakes-reader', 'eof.asm', None, 42, 0),
    ('close-wakes-sigpipe', 'sigpipe.asm', None, 42, 0),
    ('ignored-sigpipe-partial', 'sigpipe.asm', 'IGNORE', 42, 0),
    ('masked-sigpipe-partial', 'sigpipe.asm', 'MASKED', 42, 0),
    ('wait-any-skips-blocked', 'wait-any.asm', None, 42, 0),
    ('cyclic-deadlock', 'cycle.asm', None, 'timeout', 1),
    ('retained-writer-deadlock', 'eof.asm', 'DEADLOCK', 'timeout', 1),
    ('runnable-irq-with-blocked-child', 'eof.asm', 'RUNNABLE_IRQ', 'timeout', 2),
    ('root-fault-with-blocked-writer', 'transfer.asm', 'ROOT_FAULT', -4, 3),
    ('writer-fault-wakes-eof', 'transfer.asm', 'CHILD_FAULT', 42, 0),
    ('nonblocking-regression', '../linux-pipes/probe.asm', None, 42, 0),
    ('activation-policy-bound', 'policy.asm', None, 42, 4),
]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def no_core():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--in', dest='compiler', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--root', choices=['standard', 'minimal'], default='standard')
    parser.add_argument('--repeat', type=int, default=21)
    parser.add_argument('--wall-timeout', type=int, default=600)
    parser.add_argument('--case', dest='selected', action='append', choices=[row[0] for row in CASES])
    parser.add_argument('--host-only', action='store_true')
    args = parser.parse_args()
    args.out = args.out.resolve()
    args.compiler = args.compiler.resolve()
    require(1 <= args.repeat <= 100 and 1 <= args.wall_timeout <= 3600, 'invalid repetition/wall limit')
    require(not args.out.exists() or not any(args.out.iterdir()), '--out must be new or empty')
    args.out.mkdir(parents=True, exist_ok=True)
    cases = [row for row in CASES if args.selected is None or row[0] in args.selected]
    report = dict(status='running', goal_status='OPEN', root=args.root, repeat=args.repeat,
                  category='synthetic ordinary Linux ELF blocking graphs; not upstream apps',
                  selected_cases=[row[0] for row in cases], full_suite=len(cases) == len(CASES),
                  space_status='not-run', artifacts=[], executions=[])
    qemu = None
    try:
        report['compiler'] = dict(path=str(args.compiler), sha256=sha(args.compiler))
        snapshot = args.out / 'source'
        directories = ['boot', 'components', 'kernel', 'protocol', 'services', 'fixtures/linux-blocking',
                       'fixtures/linux-children', 'fixtures/linux-pipes', 'fixtures/linux-process']
        paths = [path for name in directories for path in (ROOT / name).rglob('*') if path.suffix in ['.in', '.asm']]
        paths.append(Path(__file__).resolve())
        contents = {str(path.relative_to(ROOT)): path.read_bytes() for path in paths}
        require(all(path.read_bytes() == contents[str(path.relative_to(ROOT))] for path in paths), 'source changed while capturing')
        report['source_sha256'] = {}
        for name, data in contents.items():
            target = snapshot / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            report['source_sha256'][name] = hashlib.sha256(data).hexdigest()
        with (args.out / 'build.log').open('w') as log:
            for index, (name, filename, define, expected, mode) in enumerate(cases):
                obj, binary = args.out / (name + '.o'), args.out / name
                commands = [['nasm', '-f', 'elf64', *(['-D' + define] if define else []),
                             str(snapshot / 'fixtures/linux-blocking' / filename), '-o', str(obj)],
                            ['ld', '-static', '-z', 'noexecstack', '-o', str(binary), str(obj)]]
                for command in commands:
                    subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=60, check=True)
                row = dict(index=index, name=name, path=str(binary), sha256=sha(binary),
                           size=binary.stat().st_size, source=filename, define=define, commands=commands,
                           host_contract=expected, mode=mode, expected_space_exit={0: 42, 1: 125, 2: 124, 3: 134, 4: 126}[mode],
                           physical_address=0x10000000 + index * 0x200000)
                row['comparison'] = ('ordinary Linux finite byte/status contract' if mode == 0
                                     else 'Space typed fault/budget/owned-graph policy; host behavior recorded separately')
                process = subprocess.Popen([str(binary)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           start_new_session=True, preexec_fn=no_core)
                try:
                    stdout, stderr = process.communicate(timeout=.4 if expected == 'timeout' else 15)
                    observed = process.returncode
                    require(not stdout and not stderr, name + ': unexpected host output')
                except subprocess.TimeoutExpired:
                    observed = 'timeout'
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate(timeout=3)
                require(observed == expected, name + ': Linux host contract failed: ' + str(observed))
                row['host_status'] = observed
                report['artifacts'].append(row)
        report['host_status'] = 'passed: finite host contracts and explicit deadlock/IRQ timeouts'
        if args.host_only:
            report['status'] = 'host-only'
            print('PASS: host contracts; Space not executed; ' + str(args.out))
            return
        source = (snapshot / ('kernel/kernel-root-minimal.in' if args.root == 'minimal' else 'kernel/kernel-root.in')).read_text()
        source = re.sub(r'import "\.\./([^"]+)"', lambda match: 'import ' + json.dumps(str(snapshot / match.group(1))), source)
        source = 'import ' + json.dumps(str(snapshot / 'components/linux-process.in')) + '\n' + source
        source = 'import ' + json.dumps(str(snapshot / 'fixtures/linux-blocking/checks.in')) + '\n' + source
        require(source.count('  shell(port)') == 1, 'root shell contract changed')
        source = source.replace('  shell(port)', '  blocking-corpus(port)\n  shell(port)')
        calls = ['blocking-check-case(port,' + ','.join(str(value) for value in
                 [row['index'], row['physical_address'], row['size'], row['mode']]) + ',MEASURED);' for row in report['artifacts']]
        source += '\nfn blocking-corpus(port:Int)->void{child-check-init();blocking-check-retry-negatives();blocking-check-terminal-root-priority();\n'
        source += '\n'.join(call.replace('MEASURED', '0') for call in calls)
        source += '\npipe-check-baseline();let cycle=0;while cycle<' + str(args.repeat) + '{\n'
        source += '\n'.join(call.replace('MEASURED', '1') for call in calls)
        source += '\ncycle=cycle+1;}child-check-finish(port);}\n'
        kernel_source, kernel, trampoline = args.out / 'kernel.in', args.out / 'kernel.bin', args.out / 'trampoline.bin'
        kernel_source.write_text(source)
        commands = [['nasm', '-f', 'bin', str(snapshot / 'boot/multiboot.asm'), '-o', str(trampoline)],
                    [str(args.compiler), 'compile', '--path', str(kernel_source), '--entry', 'kernel-entry',
                     '--emit', 'boot', '--trampoline', str(trampoline), '--target', 'native',
                     '--target-triple', 'x86_64-unknown-none', '--linkage', 'static-lib', '--out', str(kernel)]]
        report['kernel_commands'] = commands
        with (args.out / 'compile.log').open('w') as log:
            for command in commands:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=180, check=True)
        layout = json.loads(kernel.with_suffix('.component-metadata.json').read_text())['boot_layout']
        require(layout['load_end'] < 0x10000000 and layout['file_size'] == kernel.stat().st_size, 'kernel/payload overlap')
        report['boot_layout'] = layout
        command = ['qemu-system-x86_64', '-cpu', 'max', '-kernel', str(kernel), '-m', '512M',
                   '-display', 'none', '-no-reboot', '-serial', 'file:' + str(args.out / 'serial.log')]
        for row in report['artifacts']:
            command += ['-device', f'loader,file={row["path"]},addr={row["physical_address"]},force-raw=on']
        report['qemu_command'] = command
        with (args.out / 'qemu.log').open('w') as log:
            qemu = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + args.wall_timeout
            while time.monotonic() < deadline:
                serial = args.out / 'serial.log'
                output = serial.read_text(errors='replace') if serial.exists() else ''
                if 'child-corpus: passed activations ' in output or 'PANIC' in output or 'nanokernel fault handler halting' in output or qemu.poll() is not None:
                    break
                time.sleep(.05)
        output = (args.out / 'serial.log').read_text(errors='replace')
        require('PANIC' not in output and 'nanokernel fault handler halting' not in output, 'blocking execution assertion/fault; inspect serial.log')
        require('blocking-corpus: grant and mapping retry checks passed' in output,
                'missing actual pending-operation live grant/range proof')
        require('blocking-corpus: terminal root precedes quota and child retry passed' in output,
                'missing actual root signal/quota boundary priority proof')
        matches = re.findall(r'blocking-corpus: begin (\d+) case (\d+)\n(.*?)blocking-corpus: end \1 case \2 status (-?\d+)\n', output, re.S)
        expected_count = len(cases) * (args.repeat + 1)
        require(len(matches) == expected_count and f'child-corpus: passed activations {expected_count}\n' in output,
                'missing actual executions and ownership cleanup')
        for index, (activation, case, body, status) in enumerate(matches):
            row = report['artifacts'][index % len(cases)]
            require(int(activation) == index and int(case) == row['index'] and int(status) == row['expected_space_exit'], 'wrong actual activation/result')
            if row['name'] != 'nonblocking-regression':
                require('linux-process: syscall 56\n' in body, 'missing real clone path')
            faults = [int(value, 16) for value in re.findall(r'space: guest fault vector 0x([0-9A-Fa-f]+)', body)]
            require(faults == ([6] if row['mode'] == 3 or row['define'] == 'CHILD_FAULT' else []), row['name'] + ': unexpected hardware fault cause')
            report['executions'].append(dict(case=row['name'], status=int(status), warmup=index < len(cases),
                                             raw_serial_body=body, passed=True))
        require(sha(args.compiler) == report['compiler']['sha256'], 'compiler changed during gate')
        require(all(sha(Path(row['path'])) == row['sha256'] for row in report['artifacts']), 'guest ELF changed during gate')
        report.update(status='passed', space_status='passed', actual_parent_activations=expected_count,
                      kernel_sha256=sha(kernel), cleanup='all family records/domains/pages/native descriptors, independent pair, frames/FS/GS/authority restored')
        print(f'PASS: synthetic protected blocking graphs, {expected_count} parent activations; {args.out}')
    except Exception as error:
        report.update(status='failed', error=str(error), space_status='not-run' if args.host_only else 'failed')
        raise
    finally:
        if qemu is not None:
            qemu.terminate()
            try:
                qemu.wait(timeout=3)
            except subprocess.TimeoutExpired:
                qemu.kill()
        (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
