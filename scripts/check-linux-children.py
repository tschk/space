#!/usr/bin/env python3
"""Test real copied Linux children, self-exec, waiting, inherited descriptors and refusals."""
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
    ('clone-private-pipe-fx', 'clone.asm', None, 42, False),
    ('file-shared-offset', 'file-offset.asm', None, 42, True),
    ('file-exec-descriptors', 'file-exec.asm', None, 42, True),
    ('null-owned-descriptors', 'null.asm', None, 42, False),
    ('null-checked-buffer-profile', 'null.asm', 'CHECKED_BUFFER_PROFILE', 'not-compared', False),
    ('exec-self', 'exec-self.asm', None, 42, False),
    ('exec-refusals', 'exec-refusal.asm', None, 42, False),
    ('signal-mask-inheritance', 'signal-mask.asm', None, 42, False),
    ('two-retained-children', 'two-children.asm', None, 42, False),
    ('pending-sigpipe-clone', 'pending-sigpipe.asm', None, 42, False),
    ('child-ud2', 'termination.asm', None, 42, False),
    ('child-page-fault', 'termination.asm', 'PAGE_FAULT', 42, False),
    ('child-gp', 'termination.asm', 'GENERAL_PROTECTION', 42, False),
    ('child-sigpipe', 'termination.asm', 'SIGPIPE', 42, False),
    ('child-exit134-is-normal', 'termination.asm', 'NORMAL_EXIT_134', 42, False),
    ('child-exit141-is-normal', 'termination.asm', 'NORMAL_EXIT_141', 42, False),
    ('child-deadline', 'termination.asm', 'DEADLINE', 'timeout', False),
    ('bounded-profile-refusals', 'profile-refusals.asm', None, 'not-compared', False),
    ('bounded-record-capacity', 'record-capacity.asm', None, 'not-compared', False),
    ('bounded-depth-limit', 'depth-limit.asm', None, 'not-compared', False),
    ('partial-fd-copy-rollback', 'partial-fd.asm', None, 'not-compared', False),
    ('retry-admission-bound', 'partial-fd.asm', 'ADMISSION_RETRY', 'not-compared', False),
    ('cumulative-irq-budget', 'partial-fd.asm', 'CUMULATIVE_IRQ', 'not-compared', False),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def no_core():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--in', dest='compiler', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--root', choices=['standard', 'minimal'], default='standard')
    parser.add_argument('--repeat', type=int, default=21)
    parser.add_argument('--case', dest='selected', action='append', choices=[case[0] for case in CASES],
                        help='Run an explicitly reported subset; repeat for multiple cases (default: full suite)')
    parser.add_argument('--vfork-fd-profile', action='store_true', help='separate bounded vfork partial-descriptor rollback and32 preparation-admission profile')
    parser.add_argument('--host-only', action='store_true', help='Run only declared host contracts; explicitly does not certify Space')
    parser.add_argument('--budget-carry-negative-control', action='store_true',
                        help='Only with --case cumulative-irq-budget: omit carry in isolated source snapshot; must finish42')
    args = parser.parse_args()
    args.out = args.out.resolve()
    args.compiler = args.compiler.resolve()
    if args.vfork_fd_profile:
        require(args.selected is None and not args.budget_carry_negative_control,'vfork FD profile is separate from existing case selection')
        args.selected=['partial-fd-copy-rollback','retry-admission-bound']
    cases = [case for case in CASES if args.selected is None or case[0] in args.selected]
    require(not args.budget_carry_negative_control or args.selected == ['cumulative-irq-budget'],
            'budget negative control requires exactly --case cumulative-irq-budget')
    require(1 <= args.repeat <= 100, '--repeat must be 1..100')
    require(not args.out.exists() or not any(args.out.iterdir()), '--out must be new or empty')
    args.out.mkdir(parents=True, exist_ok=True)
    report = dict(status='running', goal_status='OPEN', root=args.root, repeat=args.repeat,
                  category='synthetic ordinary Linux ABI probes; not upstream applications',
                  space_status='not-run', vfork_fd_profile=args.vfork_fd_profile, selected_cases=[case[0] for case in cases],
                  full_suite=len(cases) == len(CASES), artifacts=[], executions=[])
    report['budget_carry_negative_control'] = args.budget_carry_negative_control
    qemu = None
    try:
        report['compiler'] = dict(path=str(args.compiler), sha256=sha(args.compiler))
        snapshot = args.out / 'source'
        paths = [path for base in ['boot', 'components', 'kernel', 'protocol', 'services', 'fixtures/linux-children', 'fixtures/linux-pipes']
                 for path in (ROOT / base).rglob('*') if path.suffix in ['.in', '.asm']]
        paths += list((ROOT / 'fixtures/linux-vm').rglob('*.in'))
        paths += [ROOT / 'fixtures/linux-process/checks.in', Path(__file__).resolve()]
        contents = {str(path.relative_to(ROOT)): path.read_bytes() for path in paths}
        require(all(path.read_bytes() == contents[str(path.relative_to(ROOT))] for path in paths), 'source changed while capturing')
        report['source_sha256'] = {}
        for name, data in contents.items():
            target = snapshot / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            report['source_sha256'][name] = hashlib.sha256(data).hexdigest()
        report['compiled_source_sha256'] = dict(report['source_sha256'])
        if any(case[0] == 'cumulative-irq-budget' for case in cases):
            target = snapshot / 'components/user-budget.in'
            original = target.read_text()
            guard = ('  if (load64(frame + 128) & 3) != 3 { return 0 }\n'
                     '  if user-budget-active != 0 && domain-current == user-budget-domain {\n')
            require(original.count(guard) == 1, 'actual CPL3/domain IRQ observer guard changed')
            observed = guard + ('    if child-check-observe-irq != 0 { store64(frame,load64(frame) + 1) }\n')
            target.write_text(original.replace(guard, observed))
            report['irq_observer'] = dict(scope='private test snapshot; enabled only for cumulative IRQ ELF',
                                         real_irq_guard=guard, saved_guest_register='R15 at actual IRQ frame offset0',
                                         original_sha256=hashlib.sha256(original.encode()).hexdigest(),
                                         modified_sha256=sha(target), added_instruction=observed[len(guard):],
                                         production_budget_branch='unchanged; existing decrement and deadline check retained')
            report['compiled_source_sha256']['components/user-budget.in'] = sha(target)
        if args.budget_carry_negative_control:
            instruction = 'else { store64(row + LPS-BUDGET,remaining) }'
            candidates = [snapshot / 'components' / name for name in ['linux-process-children.in', 'linux-process-schedule.in']]
            targets = [path for path in candidates if path.exists() and instruction in path.read_text()]
            require(len(targets) == 1, 'negative-control unique carry owner changed')
            target = targets[0]
            original = target.read_text()
            require(original.count(instruction) == 1, 'negative-control carry instruction contract changed')
            target.write_text(original.replace(instruction, 'else { remaining = remaining }'))
            report['negative_control_source'] = dict(path=str(target), original_sha256=hashlib.sha256(original.encode()).hexdigest(),
                                                     modified_sha256=sha(target), omission=instruction)
            report['compiled_source_sha256'][str(target.relative_to(snapshot))] = sha(target)
        with (args.out / 'build.log').open('w') as log:
            for index, (name, filename, define, expected, file_case) in enumerate(cases):
                obj, binary = args.out / (name + '.o'), args.out / name
                commands = [['nasm', '-f', 'elf64', *(['-DVFORK'] if args.vfork_fd_profile else []), *(['-D' + define] if define else []),
                             *(['-DADMISSION_RETRY'] if define == 'CUMULATIVE_IRQ' else []),
                             str(snapshot / 'fixtures/linux-children' / filename), '-o', str(obj)],
                            ['ld', '-static', '-z', 'noexecstack', '-o', str(binary), str(obj)]]
                for command in commands:
                    subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=60)
                row = dict(index=index, name=name, source=filename, define=define, path=str(binary), sha256=sha(binary),
                           size=binary.stat().st_size, commands=commands, file_case=file_case,
                           host_contract=expected, physical_address=0x10000000 + index * 0x200000)
                row['expected_space_exit'] = 124 if name == 'cumulative-irq-budget' and not args.budget_carry_negative_control else 42
                row['guest_budget_ticks'] = 10 if name == 'cumulative-irq-budget' else 100
                row['rollback_mode'] = {'partial-fd-copy-rollback': 1, 'retry-admission-bound': 2,
                                        'cumulative-irq-budget': 4 if args.budget_carry_negative_control else 3}.get(name, 0)
                if expected == 'not-compared':
                    row['host_status'] = 'not-run: explicit Space profile limits, not Linux conformance'
                else:
                    file_path = args.out / 'host-shared-offset.txt'
                    if file_case:
                        file_path.write_bytes(b'abcdef\n')
                    command = [str(binary), str(file_path)] if file_case else [str(binary)]
                    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                               preexec_fn=no_core, start_new_session=True)
                    try:
                        stdout, stderr = process.communicate(timeout=.4 if expected == 'timeout' else 10)
                        observed = process.returncode
                        require(not stdout and not stderr, name + ': unexpected host output')
                    except subprocess.TimeoutExpired:
                        observed = 'timeout'
                        os.killpg(process.pid, signal.SIGKILL)
                        process.communicate(timeout=3)
                    require(observed == expected, name + ': host contract failed: ' + str(observed))
                    if file_case:
                        require(file_path.read_bytes() == b'abcdXY\n', 'host shared-file write/offset oracle failed')
                    row.update(host_status=observed, host_command=command)
                report['artifacts'].append(row)
        report['host_status'] = 'passed declared host contracts; bounded refusal fixtures explicitly not compared'
        if args.host_only:
            report['status'] = 'host-only'
            print('PASS: declared Linux host contracts; Space not executed; ' + str(args.out))
            return
        source = (snapshot / ('kernel/kernel-root-minimal.in' if args.root == 'minimal' else 'kernel/kernel-root.in')).read_text()
        source = re.sub(r'import "\.\./([^"]+)"', lambda match: 'import ' + json.dumps(str(snapshot / match.group(1))), source)
        source = ''.join('import ' + json.dumps(str(snapshot / name)) + '\n' for name in
                         ['components/linux-process.in', 'fixtures/linux-process/checks.in', 'fixtures/linux-pipes/checks.in', 'fixtures/linux-children/checks.in']) + source
        require(source.count('  shell(port)') == 1, 'unexpected root shell contract')
        source = source.replace('  shell(port)', '  child-corpus(port)\n  shell(port)')
        calls = ['child-check-case(port,' + ','.join(str(word) for word in
                 [row['index'], row['physical_address'], row['size'], int(row['file_case']),
                  row['rollback_mode']]) + ',MEASURED);' for row in report['artifacts']]
        source += '\nfn child-corpus(port:Int)->void{\nchild-check-init();\n'
        source += '\n'.join(call.replace('MEASURED', '0') for call in calls)
        source += '\npipe-check-baseline();let cycle=0;while cycle<' + str(args.repeat) + '{\n'
        source += '\n'.join(call.replace('MEASURED', '1') for call in calls)
        source += '\ncycle=cycle+1;}child-check-finish(port);}\n'
        kernel_source, kernel, trampoline = args.out / 'kernel.in', args.out / 'kernel.bin', args.out / 'trampoline.bin'
        kernel_source.write_text(source)
        commands = [['nasm', '-f', 'bin', str(snapshot / 'boot/multiboot.asm'), '-o', str(trampoline)],
                    [str(args.compiler), 'compile', '--path', str(kernel_source), '--entry', 'kernel-entry', '--emit', 'boot',
                     '--trampoline', str(trampoline), '--target', 'native', '--target-triple', 'x86_64-unknown-none',
                     '--linkage', 'static-lib', '--out', str(kernel)]]
        report['kernel_commands'] = commands
        with (args.out / 'compile.log').open('w') as log:
            for command in commands:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
        layout = json.loads(kernel.with_suffix('.component-metadata.json').read_text())['boot_layout']
        require(layout['load_end'] < 0x10000000 and layout['file_size'] == kernel.stat().st_size, 'kernel/payload overlap')
        report['boot_layout'] = layout
        command = ['qemu-system-x86_64', '-cpu', 'max', '-kernel', str(kernel), '-m', '512M', '-display', 'none',
                   '-no-reboot', '-serial', 'file:' + str(args.out / 'serial.log')]
        for row in report['artifacts']:
            command += ['-device', f'loader,file={row["path"]},addr={row["physical_address"]},force-raw=on']
        report['qemu_command'] = command
        with (args.out / 'qemu.log').open('w') as log:
            qemu = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + max(90, args.repeat * 12)
            while time.monotonic() < deadline:
                serial = args.out / 'serial.log'
                text = serial.read_text(errors='replace') if serial.exists() else ''
                if 'child-corpus: passed activations ' in text or 'PANIC' in text or 'nanokernel fault handler halting' in text or qemu.poll() is not None:
                    break
                time.sleep(.05)
        text = (args.out / 'serial.log').read_text(errors='replace')
        require('PANIC' not in text and 'nanokernel fault handler halting' not in text, 'child execution failed; inspect serial.log')
        require('child-corpus: retained teardown refusal and recovery passed' in text,
                'missing actual retained cleanup refusal/recovery proof')
        matches = re.findall(r'child-corpus: begin (\d+) case (\d+)\n(.*?)child-corpus: end \1 case \2 status (-?\d+)\n', text, re.S)
        expected = len(cases) * (args.repeat + 1)
        require(len(matches) == expected and f'child-corpus: passed activations {expected}\n' in text, 'missing actual executions/cleanup completion')
        for index, (activation, case, body, status) in enumerate(matches):
            row = report['artifacts'][index % len(cases)]
            require(int(activation) == index and int(case) == row['index'] and int(status) == row['expected_space_exit'], 'incorrect actual parent execution')
            if row['name'] != 'exec-refusals':
                require(('linux-process: syscall 58\n' if args.vfork_fd_profile else 'linux-process: syscall 56\n') in body, row['name'] + ': actual clone/vfork path absent')
                if row['expected_space_exit'] != 124:
                    require('linux-process: syscall 61\n' in body, row['name'] + ': actual wait path absent')
            if row['name'] in ['exec-self', 'file-exec-descriptors', 'exec-refusals', 'bounded-profile-refusals']:
                require('linux-process: syscall 59\n' in body, row['name'] + ': actual exec path absent')
            if row['name'] == 'cumulative-irq-budget':
                marker = ('child-corpus: omitted carry control normal exit passed' if args.budget_carry_negative_control
                          else 'child-corpus: cumulative actual IRQ deadline passed')
                require(marker in body, 'missing typed IRQ/control stop-cause proof')
            expected_fault = {'child-ud2': 6, 'child-page-fault': 14, 'child-gp': 13}.get(row['name'])
            faults = [int(word, 16) for word in re.findall(r'space: guest fault vector 0x([0-9A-Fa-f]+)', body)]
            require(faults == ([expected_fault] if expected_fault is not None else []), row['name'] + ': wrong hardware fault cause')
            report['executions'].append(dict(activation=index, case=row['name'], status=int(status),
                                             warmup=index < len(cases), raw_serial_body=body, passed=True))
        require(sha(args.compiler) == report['compiler']['sha256'], 'compiler changed during gate')
        require(all(sha(Path(row['path'])) == row['sha256'] for row in report['artifacts']), 'ELF changed during gate')
        result_label = 'negative-control-passed' if args.budget_carry_negative_control else 'passed'
        report.update(status=result_label, space_status=result_label, actual_parent_activations=expected,
                      kernel_sha256=sha(kernel), cleanup='private memory and FX, inherited descriptors/native offsets, signal/exit wait causes, independent native pair, allocator/domain/FS/GS/authority state')
        label = 'negative control' if args.budget_carry_negative_control else ('full suite' if report['full_suite'] else 'explicit subset')
        print(f'PASS: real protected child execution ({label}), {expected} parent activations; {args.out}')
    except Exception as error:
        report.update(status='failed', space_status='failed' if not args.host_only else 'not-run', error=str(error))
        raise
    finally:
        if qemu:
            qemu.terminate()
            try:
                qemu.wait(timeout=3)
            except subprocess.TimeoutExpired:
                qemu.kill()
                qemu.wait()
        (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
