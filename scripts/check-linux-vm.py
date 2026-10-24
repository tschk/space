#!/usr/bin/env python3
"""Compare an ordinary Linux VM/IO ELF with actual Space execution after native VM migration."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import os
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def require(value, message):
    if not value:
        raise AssertionError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--in', dest='compiler', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--root', choices=['standard', 'minimal'], default='standard')
    parser.add_argument('--repeat', type=int, default=21)
    parser.add_argument('--vfork-deadline', action='store_true', help='declared Space IRQ cancellation profile; host child intentionally does not terminate')
    parser.add_argument('--vfork', action='store_true', help='ordinary shared-VM vfork/exec/fault probe')
    parser.add_argument('--stage-capacity', action='store_true', help='genuine exhausted native binding pool; host77 vs declared SpaceENOMEM/42 profile')
    parser.add_argument('--constructor-control', action='store_true', help='explicit private snapshot native claim refusal; zero Space guest entries')
    parser.add_argument('--host-only', action='store_true')
    parser.add_argument('--wall-timeout', type=int, default=180)
    args = parser.parse_args()
    args.vfork = args.vfork or args.vfork_deadline
    args.out = args.out.resolve()
    args.compiler = args.compiler.resolve()
    require(not args.vfork or (not args.stage_capacity and not args.constructor_control), 'vfork is a separate profile')
    require(not args.constructor_control or not args.stage_capacity, 'constructor control is a separate profile')
    require(not args.constructor_control or not args.host_only, 'constructor control requires its actual Space supervisor proof')
    require(1 <= args.repeat <= 100 and 1 <= args.wall_timeout <= 3600, 'invalid repetition/wall limit')
    require(not args.out.exists() or not any(args.out.iterdir()), '--out must be new or empty')
    args.out.mkdir(parents=True, exist_ok=True)
    report = dict(status='running', category='synthetic ordinary Linux ELF; native VM migration',
                  goal_status='OPEN', profile='shared-vfork-deadline' if args.vfork_deadline else 'shared-vfork' if args.vfork else ('exec-native-capacity' if args.stage_capacity else 'copied-anonymous-vm'), root=args.root, repeat=args.repeat,
                  compiler=dict(path=str(args.compiler), sha256=sha(args.compiler)))
    qemu = None
    try:
        paths = [p for directory in ['boot', 'components', 'kernel', 'protocol', 'services', 'fixtures/linux-vm', 'fixtures/linux-vfork']
                 for p in (ROOT / directory).rglob('*') if p.suffix in ['.in', '.asm']]
        paths.append(Path(__file__).resolve())
        contents = {str(p.relative_to(ROOT)): p.read_bytes() for p in paths}
        require(all(p.read_bytes() == contents[str(p.relative_to(ROOT))] for p in paths), 'source changed during capture')
        snapshot = args.out / 'source'
        report['source_sha256'] = {}
        for name, data in contents.items():
            path = snapshot / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            report['source_sha256'][name] = hashlib.sha256(data).hexdigest()
        if args.constructor_control:
            import difflib
            provider = snapshot / 'components/domain.in'
            original = provider.read_text()
            needle = '  store64(row,owner)\n  return 0\n}'
            require(original.count(needle) == 1, 'native claim provider boundary changed')
            modified = original.replace(needle, '  if lvm-claim-control-armed != 0 { lvm-claim-control-armed = 0;return -1 }\n' + needle)
            provider.write_text(modified)
            delta = ''.join(difflib.unified_diff(original.splitlines(True), modified.splitlines(True), fromfile='production/domain.in', tofile='control/domain.in'))
            (args.out / 'provider-refusal.diff').write_text(delta)
            report['provider_control'] = dict(original_sha256=hashlib.sha256(original.encode()).hexdigest(), compiled_sha256=sha(provider), exact_delta=delta)
        obj, binary = args.out / 'migration.o', args.out / 'migration'
        invariant = args.out / 'invariant.bin'
        startup, startup_obj = args.out / 'startup', args.out / 'startup.o'
        arguments = args.out / 'high-arguments.bin'
        payload = bytearray(768)
        for offset, value in [(0, b'/high-source\0'), (256, b'hello-from-high-source\0'), (512, b'third-high-source\0')]:
            payload[offset:offset + len(value)] = value
        arguments.write_bytes(payload)
        commands = [['nasm', '-f', 'elf64', str(snapshot / ('fixtures/linux-vfork/deadline.asm' if args.vfork_deadline else 'fixtures/linux-vfork/shared.asm' if args.vfork else ('fixtures/linux-vm/exec-capacity.asm' if args.stage_capacity else 'fixtures/linux-vm/migration.asm'))), '-o', str(obj)],
                    ['ld', '-static', '-z', 'noexecstack', '-o', str(binary), str(obj)],
                    ['nasm', '-f', 'bin', str(snapshot / 'fixtures/linux-vm/invariant.asm'), '-o', str(invariant)],
                    ['nasm', '-f', 'elf64', str(snapshot / 'fixtures/linux-vm/startup.asm'), '-o', str(startup_obj)],
                    ['ld', '-static', '-z', 'noexecstack', '-o', str(startup), str(startup_obj)]]
        report['build_commands'] = commands
        with (args.out / 'build.log').open('w') as log:
            for command in commands:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=60)
        if args.vfork_deadline:
            host = subprocess.Popen([str(binary)], cwd='/', env={'LC_ALL':'C','HOME':'/'}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            try:
                host.communicate(timeout=1)
                raise AssertionError('declared host nontermination unexpectedly terminated')
            except subprocess.TimeoutExpired:
                os.killpg(host.pid,signal.SIGKILL)
                stdout,stderr=host.communicate(timeout=5)
                require(not stdout and not stderr,'host cancellation profile emitted bytes')
            report['host'] = dict(status='declared-timeout', binary_sha256=sha(binary), classification='Host vfork child intentionally infinite; Space has actual IRQ cancellation')
        else:
            process = subprocess.run([str(binary)], cwd='/', env={'LC_ALL': 'C', 'HOME': '/'}, capture_output=True, timeout=10)
            report['host'] = dict(status=process.returncode, stdout=process.stdout.decode(errors='replace'), stderr=process.stderr.decode(errors='replace'), binary_sha256=sha(binary))
            require(process.returncode == (77 if args.stage_capacity else 42) and not process.stdout and not process.stderr, 'host contract failed')
        startup_host = subprocess.run(['/high-source', 'hello-from-high-source', 'third-high-source'], executable=str(startup), cwd='/', env={'LC_ALL': 'C', 'HOME': '/'}, capture_output=True, timeout=10)
        require(startup_host.returncode == 42 and not startup_host.stdout and not startup_host.stderr, 'startup host oracle failed')
        report['startup_host'] = dict(status=42, binary_sha256=sha(startup), arguments_sha256=sha(arguments), guest_source_address=0x13000000, guest_image_source_address=0x14000000, capped_heap_end=0x10000000)
        if args.host_only:
            report['status'] = 'host-only'
            print('PASS: host VM migration ELF; Space not executed; ' + str(args.out))
            return
        source = (snapshot / ('kernel/kernel-root-minimal.in' if args.root == 'minimal' else 'kernel/kernel-root.in')).read_text()
        source = re.sub(r'import "\.\./([^"]+)"', lambda m: 'import ' + json.dumps(str(snapshot / m.group(1))), source)
        source = 'import ' + json.dumps(str(snapshot / 'fixtures/linux-vm/checks.in')) + '\n' + source
        if args.vfork: source = 'import ' + json.dumps(str(snapshot / 'fixtures/linux-vfork/checks.in')) + '\n' + source
        require(source.count('  shell(port)') == 1, 'root shell contract changed')
        source = source.replace('  shell(port)', '  lvm-corpus()\n  shell(port)')
        call = 'lvm-case(0x10000000,' + str(binary.stat().st_size)
        if args.constructor_control:
            source += '\nfn lvm-corpus()->void{lvm-init();lvm-constructor-control(0x10000000,' + str(binary.stat().st_size) + ');lvm-finish();}\n'
        else:
            source += '\nfn lvm-corpus()->void{lvm-init();lvm-metadata-check();lvm-high-source-check(0x14000000,' + str(startup.stat().st_size) + ');lvm-invariant-check();' + ('lvm-stage-open();' if args.stage_capacity else '') + ('lvfork-peer-check();lvfork-unpublished-check();' if args.vfork else '') + ('linux-process-budget-ticks=10;' if args.vfork_deadline else '') + call + ',0);' + ('lvfork-deadline-witness();' if args.vfork_deadline else '') + 'lvm-baseline();let cycle=0;while cycle<' + str(args.repeat) + '{' + call + ',1);' + ('lvfork-deadline-witness();' if args.vfork_deadline else '') + 'cycle=cycle+1;}' + ('lvm-stage-close();' if args.stage_capacity else '') + 'lvm-finish();}\n'
        kernel, trampoline = args.out / 'kernel.bin', args.out / 'trampoline.bin'
        (args.out / 'kernel.in').write_text(source)
        commands = [['nasm', '-f', 'bin', str(snapshot / 'boot/multiboot.asm'), '-o', str(trampoline)],
                    [str(args.compiler), 'compile', '--path', str(args.out / 'kernel.in'), '--entry', 'kernel-entry',
                     '--emit', 'boot', '--trampoline', str(trampoline), '--target', 'native', '--target-triple',
                     'x86_64-unknown-none', '--linkage', 'static-lib', '--out', str(kernel)]]
        report['kernel_commands'] = commands
        with (args.out / 'compile.log').open('w') as log:
            for command in commands:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
        layout = json.loads(kernel.with_suffix('.component-metadata.json').read_text())['boot_layout']
        require(layout['load_end'] < 0x10000000 and layout['file_size'] == kernel.stat().st_size, 'kernel/payload overlap')
        report['boot_layout'] = layout
        report['kernel_sha256'] = sha(kernel)
        command = ['qemu-system-x86_64', '-kernel', str(kernel), '-m', '512M', '-cpu', 'max', '-display', 'none',
                   '-no-reboot', '-serial', 'file:' + str(args.out / 'serial.log'),
                   '-device', 'loader,file=' + str(binary) + ',addr=0x10000000,force-raw=on',
                   '-device', 'loader,file=' + str(invariant) + ',addr=0x12000000,force-raw=on',
                   '-device', 'loader,file=' + str(arguments) + ',addr=0x13000000,force-raw=on',
                   '-device', 'loader,file=' + str(startup) + ',addr=0x14000000,force-raw=on']
        report['qemu_command'] = command
        with (args.out / 'qemu.log').open('w') as log:
            qemu = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + args.wall_timeout
            text = ''
            while time.monotonic() < deadline:
                path = args.out / 'serial.log'
                text = path.read_text(errors='replace') if path.exists() else ''
                if 'space interactive shell' in text or 'PANIC' in text or 'nanokernel fault handler halting' in text or qemu.poll() is not None:
                    break
                time.sleep(.1)
        require('linux-vm: owned resource cleanup PASS' in text and 'space interactive shell' in text, 'Space VM contract failed; inspect serial.log')
        if args.constructor_control:
            require('linux-vm: controlled constructor refusal retains companion and native recovery PASS' in text, 'constructor retained-owner proof missing')
            require('linux-vm: migration activation ' not in text, 'control cannot claim guest activations')
            report['source_unchanged'] = all((ROOT / name).read_bytes() == data for name, data in contents.items())
            require(report['source_unchanged'], 'live control inputs changed')
            report.update(status='provider-refusal-control-passed', profile='constructor-retained-ownership', root_activations=0, native_invariant_cpl3_entries=0, vfork_enabled=True,vfork_profile_exercised=args.vfork)
            print('PASS: explicit native provider refusal retains Linux constructor ownership; zero guest entries; ' + str(args.out))
            return
        require(text.count('linux-vm: migration activation ') == args.repeat + 1, 'missing root activation')
        require('PANIC' not in text, 'unexpected panic')
        require('FORBID!!' not in text, 'invariant copy published forbidden bytes')
        require('linux-vm: actual alias copy stops before bytes and postcall marker retained recovery PASS' in text, 'real invariant stop proof absent')
        if args.vfork:
            require('linux-vfork: shared peer survives and final release quarantine recovery PASS' in text, 'vfork peer lifetime proof absent')
            report['vfork_peer_cpl3_entries'] = 12
            require('linux-vfork: failed binding publication retains only counted source owner recovery PASS' in text,'uncounted child publication refusal proof absent')
            require('linux-vfork: shared detach refusal keeps parent blocked and repair reclaims both peers PASS' in text,'shared reference refusal proof absent')
            if args.vfork_deadline:
                require(text.count('linux-vfork: real child Deadline releases blocked parent with SIGKILL wait PASS') == args.repeat + 1,'missing typed child deadline witnesses')
        report['native_invariant_cpl3_entries'] = 2
        require('linux-vm: actual high source argc argv env startup outside heap PASS' in text, 'high trusted source startup proof absent')
        require('linux-vm: refused startup scalar and string copies cannot report success PASS' in text, 'startup copy failure propagation absent')
        report['startup_root_activations'] = 1
        report['main_profile_root_activations'] = args.repeat + 1
        if args.stage_capacity:
            require('linux-vm: actual exec stage capacity refusal old image and descriptors retained PASS' in text, 'actual exec capacity proof absent')
            require(text.count('linux-process: completed ') >= args.repeat + 1 and '-12' in text, 'exec was not genuinely serviced')
        require('linux-vm: sole companion state rejects stale process projections PASS' in text, 'sole companion proof absent')
        require('linux-vm: exact binding association wrong owner revoked query and retired token PASS' in text, 'binding association proof absent')
        require('linux-vm: cross paired process row refuses save load and native entry PASS' in text, 'actual cross-paired row entry refusal absent')
        report['source_unchanged'] = all((ROOT / name).read_bytes() == data for name, data in contents.items())
        require(report['source_unchanged'], 'live source changed during test; retained snapshot is not overall pass')
        report.update(status='passed', root_activations=args.repeat + 2, host_status='declared-timeout' if args.vfork_deadline else 77 if args.stage_capacity else 42, space_status=42,
                      stable_owned_resources=True, vfork_enabled=True,vfork_profile_exercised=args.vfork)
        print('PASS: Linux VM migration ELF, ' + str(args.repeat + 2) + ' actual root activations including high-source startup; ' + str(args.out))
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
