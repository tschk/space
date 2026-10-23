#!/usr/bin/env python3
"""Check real protected Linux pipe syscalls; optional upstream pipeline failures fail this gate."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import resource
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


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
    parser.add_argument('--busybox', type=Path, help='Also require the actual pinned upstream ash pipeline to succeed')
    args = parser.parse_args()
    args.out = args.out.resolve()
    args.compiler = args.compiler.resolve()
    require(1 <= args.repeat <= 100, '--repeat must be 1..100')
    require(not args.out.exists() or not any(args.out.iterdir()), '--out must be new or empty')
    args.out.mkdir(parents=True, exist_ok=True)
    report = {'status': 'running', 'goal_status': 'OPEN', 'root': args.root, 'repeat': args.repeat,
              'scope': 'Synthetic Linux ABI pipe contracts; optional unmodified BusyBox follow-on pipeline is separate',
              'synthetic_guest_budget_ticks': 10,
              'artifacts': [], 'executions': []}
    qemu = None
    try:
        report['compiler'] = {'path': str(args.compiler), 'sha256': sha(args.compiler)}
        snapshot = args.out / 'source'
        paths = [path for base in ['boot', 'components', 'kernel', 'protocol', 'services', 'fixtures/linux-pipes']
                 for path in (ROOT / base).rglob('*') if path.suffix in ['.in', '.asm']]
        paths += [ROOT / 'fixtures/linux-process/checks.in', Path(__file__).resolve()]
        captured = {str(path.relative_to(ROOT)): path.read_bytes() for path in paths}
        require(all(path.read_bytes() == captured[str(path.relative_to(ROOT))] for path in paths),
                'source changed while capturing inputs')
        report['source_sha256'] = {}
        for name, data in captured.items():
            target = snapshot / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            report['source_sha256'][name] = hashlib.sha256(data).hexdigest()
        modes = [('normal', None, 42, 42, 0, None),
                 ('default-sigpipe', 'DEFAULT_SIGPIPE', -13, 141, 13, None),
                 ('leaked-fault', 'LEAK_FAULT', -4, 134, 0, 6),
                 ('leaked-timeout', 'LEAK_TIMEOUT', 'timeout', 124, 0, None),
                 ('blocking-no-runnable-deadlock', 'BLOCKING_LIMIT', 'timeout', 125, 0, None)]
        with (args.out / 'build.log').open('w') as log:
            for index, (name, define, host_status, space_status, signal, fault) in enumerate(modes):
                obj = args.out / (name + '.o')
                binary = args.out / name
                commands = [['nasm', '-f', 'elf64', *(['-D' + define] if define else []),
                             str(snapshot / 'fixtures/linux-pipes/probe.asm'), '-o', str(obj)],
                            ['ld', '-static', '-z', 'noexecstack', '-o', str(binary), str(obj)]]
                for command in commands:
                    subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=60)
                try:
                    host = subprocess.run([str(binary)], capture_output=True, preexec_fn=no_core, timeout=.3)
                    observed = host.returncode
                    require(not host.stdout and not host.stderr, name + ': unexpected host output')
                except subprocess.TimeoutExpired:
                    observed = 'timeout'
                require(observed == host_status, name + ': host Linux oracle failed: ' + str(observed))
                row = dict(index=index, name=name, path=str(binary), sha256=sha(binary), size=binary.stat().st_size,
                           commands=commands, host_status=observed, space_status=space_status, signal=signal,
                           fault=fault, physical_address=0x10000000 + index * 0x200000)
                report['artifacts'].append(row)
        busybox = None
        if args.busybox:
            busybox = args.busybox.resolve()
            manifest = json.loads((ROOT / 'fixtures/applications/busybox-1.36.1.json').read_text())
            app = manifest['apps'][0]
            require(sha(busybox) == app['sha256'] and busybox.stat().st_size == app['size_bytes'], 'BusyBox artifact mismatch')
            command = ['/ash', '-c', 'printf "hello\\n" | wc -c']
            host = subprocess.run(command, executable=str(busybox), env={'LC_ALL': 'C', 'HOME': '/'},
                                  capture_output=True, text=True, timeout=10)
            require((host.returncode, host.stdout, host.stderr) == (0, '6\n', ''), 'BusyBox host pipeline oracle failed')
            report['busybox'] = dict(path=str(busybox), sha256=sha(busybox), host_exit=host.returncode,
                                     host_stdout=host.stdout, host_stderr=host.stderr, guest_budget_ticks=100)
        source = (snapshot / ('kernel/kernel-root-minimal.in' if args.root == 'minimal' else 'kernel/kernel-root.in')).read_text()
        source = re.sub(r'import "\.\./([^"]+)"', lambda match: 'import ' + json.dumps(str(snapshot / match.group(1))), source)
        source = ''.join('import ' + json.dumps(str(snapshot / name)) + '\n' for name in
                         ['components/linux-process.in', 'fixtures/linux-process/checks.in', 'fixtures/linux-pipes/checks.in']) + source
        require(source.count('  shell(port)') == 1, 'unexpected boot shell contract')
        source = source.replace('  shell(port)', '  pipe-corpus(port)\n  shell(port)')
        calls = ['pipe-check-case(port,' + ','.join(str(word) for word in
                  [row['index'], row['physical_address'], row['size'], row['space_status'], row['signal']]) + ',MEASURED);'
                 for row in report['artifacts']]
        busycall = 'pipe-check-busybox(port,0x12000000,' + str(busybox.stat().st_size) + ',MEASURED);' if busybox else ''
        source += '\nfn pipe-corpus(port:Int)->void{\npipe-check-init();\n'
        source += '\n'.join(call.replace('MEASURED', '0') for call in calls) + '\n' + busycall.replace('MEASURED', '0')
        source += '\npipe-check-negatives();pipe-check-baseline();\nlet cycle=0;while cycle<' + str(args.repeat) + '{\n'
        source += '\n'.join(call.replace('MEASURED', '1') for call in calls)
        source += '\npipe-check-negatives();pipe-check-released(1);cycle=cycle+1;}\n'
        source += busycall.replace('MEASURED', '1') + '\npipe-check-finish(port);}\n'
        kernel_source = args.out / 'kernel.in'
        kernel_source.write_text(source)
        trampoline = args.out / 'trampoline.bin'
        kernel = args.out / 'kernel.bin'
        commands = [['nasm', '-f', 'bin', str(snapshot / 'boot/multiboot.asm'), '-o', str(trampoline)],
                    [str(args.compiler), 'compile', '--path', str(kernel_source), '--entry', 'kernel-entry', '--emit', 'boot',
                     '--trampoline', str(trampoline), '--target', 'native', '--target-triple', 'x86_64-unknown-none',
                     '--linkage', 'static-lib', '--out', str(kernel)]]
        report['kernel_commands'] = commands
        with (args.out / 'compile.log').open('w') as log:
            for command in commands:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
        layout = json.loads(kernel.with_suffix('.component-metadata.json').read_text())['boot_layout']
        report['boot_layout'] = layout
        require(layout['load_end'] < 0x10000000 and layout['file_size'] == kernel.stat().st_size, 'kernel/payload overlap')
        command = ['qemu-system-x86_64', '-cpu', 'max', '-kernel', str(kernel), '-m', '512M', '-display', 'none',
                   '-no-reboot', '-serial', 'file:' + str(args.out / 'serial.log')]
        for row in report['artifacts']:
            command += ['-device', f'loader,file={row["path"]},addr={row["physical_address"]},force-raw=on']
        if busybox:
            command += ['-device', 'loader,file=' + str(busybox) + ',addr=0x12000000,force-raw=on']
        report['qemu_command'] = command
        with (args.out / 'qemu.log').open('w') as log:
            qemu = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + max(90, args.repeat * 5)
            while time.monotonic() < deadline:
                serial = args.out / 'serial.log'
                text = serial.read_text(errors='replace') if serial.exists() else ''
                if 'pipe-corpus: passed activations ' in text or 'PANIC' in text or 'nanokernel fault handler halting' in text or qemu.poll() is not None:
                    break
                time.sleep(.05)
        text = (args.out / 'serial.log').read_text(errors='replace')
        require('PANIC' not in text and 'nanokernel fault handler halting' not in text, 'kernel assertions failed; inspect serial.log')
        matches = re.findall(r'pipe-corpus: begin (\d+) case (\d+)\n(.*?)pipe-corpus: end \1 case \2 status (-?\d+) signal (\d+)\n', text, re.S)
        expected = len(modes) * (args.repeat + 1)
        require(len(matches) == expected and f'pipe-corpus: passed activations {expected}\n' in text,
                'missing activations/cleanup completion; inspect serial.log')
        for index, (activation, case, body, status, signal) in enumerate(matches):
            row = report['artifacts'][index % len(modes)]
            require(int(activation) == index and int(case) == row['index'], 'activation order changed')
            require(int(status) == row['space_status'] and int(signal) == row['signal'], row['name'] + ': incorrect termination cause')
            faults = [int(word, 16) for word in re.findall(r'space: guest fault vector 0x([0-9A-Fa-f]+)', body)]
            require(faults == ([row['fault']] if row['fault'] is not None else []), row['name'] + ': unexpected CPU fault')
            require('linux-process: syscall 293\nlinux-process: result 0\n' in body, row['name'] + ': no successful actual pipe2')
            report['executions'].append(dict(activation=index, case=row['name'], status=int(status), signal=int(signal),
                                             fault_vectors=faults, warmup=index < len(modes), passed=True))
        report.update(status='passed', pipe_status='passed', actual_activations=expected, kernel_sha256=sha(kernel),
                      cleanup='native endpoint references, independent buffered native pair, heap, frames, domain ownership, FS/GS and syscall/budget state verified')
        if busybox:
            bodies = re.findall(r'pipe-corpus: BusyBox pipeline begins\n(.*?)pipe-corpus: BusyBox pipeline status (-?\d+)\n', text, re.S)
            require(len(bodies) == 2, 'missing actual BusyBox pipeline probes')
            executions = []
            for body, status in bodies:
                pattern = r'linux-process: (syscall|result|suspended|completed) (-?\d+(?: -?\d+)*)\n'
                output = re.sub(pattern, '', body)
                stops = [dict(pid=int(pid), kind=int(kind), detail=int(detail), wait_status=int(wait), remaining_ticks=int(remaining))
                         for pid, kind, detail, wait, remaining in re.findall(
                             r'pipe-corpus: BusyBox stop (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+)\n', body)]
                output = re.sub(r'pipe-corpus: BusyBox stop -?\d+(?: -?\d+){4}\n', '', output)
                events = [dict(kind=kind, values=[int(value) for value in values.split()])
                          for kind, values in re.findall(pattern, body)]
                # Suspended processes interleave: a completion belongs to its
                # explicit PID/operation, never a positional syscall/result zip.
                executions.append(dict(exit=int(status), output=output, raw_serial_body=body, trace_events=events, stop_causes=stops,
                                       passed=int(status) == 0 and output == '6\n'))
            report['busybox']['executions'] = executions
            report['busybox']['status'] = 'passed' if all(row['passed'] for row in executions) else 'failed'
            require(report['busybox']['status'] == 'passed', 'unmodified BusyBox pipeline still fails; inspect reported actual next blocker')
        require(sha(args.compiler) == report['compiler']['sha256'], 'compiler changed during gate')
        require(all(sha(Path(row['path'])) == row['sha256'] for row in report['artifacts']), 'probe ELF changed during gate')
        print(f'PASS: real Linux pipes, {expected} protected activations and {args.repeat} ownership/capability/capacity cycles; {args.out}')
    except Exception as error:
        report.update(status='failed', error=str(error))
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
