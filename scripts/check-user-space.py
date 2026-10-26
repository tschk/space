#!/usr/bin/env python3
"""Exercise native owned address spaces with real CPL3 execution, without a personality."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
CASES = ['shared', 'bounds', 'faults', 'revocation', 'quarantine', 'capacity', 'bridge', 'reinitialize']
MARKERS = {
    'bridge': 'checked active copy bridge held borrow and revoked release',
    'reinitialize': 'reinitialized foreign context refuses stale binding without invalidation',
    'shared': 'shared VM independent CPU contexts and copied backing',
    'bounds': 'authority bounds atomic refusal and revoked code TLS views',
    'faults': 'actual CPL3 RO NX unmapped faults busy refusal and IRQ deadline',
    'revocation': 'revoked grant denies entry mutation but retains owner cleanup',
    'quarantine': 'retained quarantine repaired exact-owner teardown and stale generation',
    'capacity': 'bounded VM binding and copy capacity atomic admission',
}


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--in', dest='compiler', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--root', choices=['standard', 'minimal'], default='standard')
    parser.add_argument('--repeat', type=int, default=10)
    parser.add_argument('--case', dest='selected', action='append', choices=CASES)
    parser.add_argument('--claim-failure-control', action='store_true', help='private snapshot provider refusal; explicitly not unchanged-production coverage')
    parser.add_argument('--wall-timeout', type=int, default=180)
    args = parser.parse_args()
    args.compiler = args.compiler.resolve()
    args.out = args.out.resolve()
    require(1 <= args.repeat <= 100 and 1 <= args.wall_timeout <= 3600, 'invalid repetition/wall limit')
    require(not args.out.exists() or not any(args.out.iterdir()), '--out must be new or empty')
    args.out.mkdir(parents=True, exist_ok=True)
    cases = [] if args.claim_failure_control else [name for name in CASES if args.selected is None or name in args.selected]
    report = dict(status='running', category='native UserAddressSpace; no foreign process ABI',
                  root=args.root, repeat=args.repeat, cases=cases, full_suite=cases == CASES,
                  compiler=dict(path=str(args.compiler), sha256=sha(args.compiler)))
    qemu = None
    try:
        paths = [p for directory in ['boot', 'components', 'kernel', 'protocol', 'services', 'fixtures/user-space']
                 for p in (ROOT / directory).rglob('*') if p.suffix in ['.in', '.asm']]
        paths.append(Path(__file__).resolve())
        contents = {str(p.relative_to(ROOT)): p.read_bytes() for p in paths}
        require(all(p.read_bytes() == contents[str(p.relative_to(ROOT))] for p in paths), 'source changed during capture')
        snapshot = args.out / 'source'
        report['source_sha256'] = {}
        for name, data in contents.items():
            target = snapshot / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            report['source_sha256'][name] = hashlib.sha256(data).hexdigest()
        if args.claim_failure_control:
            path = snapshot / 'components/domain.in'
            original = path.read_text()
            needle = '  store64(row,owner)\n  return 0\n}'
            require(original.count(needle) == 1, 'claim refusal provider pattern changed')
            injected = original.replace(needle, '  if us-provider-refusal != 0 { us-provider-refusal = 0;return -1 }\n' + needle) + '\nvar us-provider-refusal: Int = 1\n'
            path.write_text(injected)
            import difflib
            delta = ''.join(difflib.unified_diff(original.splitlines(True), injected.splitlines(True), fromfile='production/domain.in', tofile='test-snapshot/domain.in'))
            (args.out / 'provider-refusal.diff').write_text(delta)
            report['provider_refusal_control'] = dict(original_sha256=hashlib.sha256(original.encode()).hexdigest(), compiled_sha256=sha(path), exact_delta=delta, scope='one actual provider claim refusal before owner publication; no production hook')
        guest, private = args.out / 'guest.bin', args.out / 'private.sci'
        trampoline, kernel = args.out / 'trampoline.bin', args.out / 'kernel.bin'
        commands = [
            ['nasm', '-f', 'bin', str(snapshot / 'boot/multiboot.asm'), '-o', str(trampoline)],
            ['nasm', '-f', 'bin', str(snapshot / 'fixtures/user-space/guest.asm'), '-o', str(guest)],
            [str(args.compiler), 'compile', '--path', str(snapshot / 'fixtures/user-space/private-import.in'),
             '--entry', 'private-entry', '--emit', 'sci', '--base', '0x7a000000', '--target', 'native',
             '--target-triple', 'x86_64-unknown-none', '--out', str(private)],
        ]
        with (args.out / 'compile.log').open('w') as log:
            for command in commands:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=180, check=True)
        require(guest.stat().st_size == 4096, 'guest image must occupy one page')
        source = (snapshot / ('kernel/kernel-root-minimal.in' if args.root == 'minimal' else 'kernel/kernel-root.in')).read_text()
        source = re.sub(r'import "\.\./([^"]+)"', lambda m: 'import ' + json.dumps(str(snapshot / m.group(1))), source)
        source = 'import ' + json.dumps(str(snapshot / 'fixtures/user-space/checks.in')) + '\n' + source
        require(source.count('  shell(port)') == 1, 'root shell contract changed')
        source = source.replace('  shell(port)', '  us-corpus()\n  shell(port)')
        calls = '\n'.join('us-' + name + '();' for name in cases)
        source += '\nfn us-corpus()->void{\n'
        source += 'if heap-next+0x2000000>=0x10000000{panic("user-space raw payload overlap");}\n'
        source += 'us-initialize();' + ('us-claim-control();' if args.claim_failure_control else 'us-cold();') + 'let oldhook=domain-user-syscall-hook;domain-user-syscall-hook=us-hook;\n'
        source += 'us-private-import(' + str(private.stat().st_size) + ');\n'
        # Warm all selected capacities before recording stable allocator high water.
        source += calls + '\nlet heap=heap-next;let free=us-free-count();let domains=domain-count;let owned=domain-user-owned;let caps=cap-count;\n'
        source += 'let cycle=0;while cycle<' + str(args.repeat) + '{\n' + calls
        source += '\nus-check(heap,heap-next);us-check(free,us-free-count());us-check(domains,domain-count);us-check(owned,domain-user-owned);us-check(caps,cap-count);cycle=cycle+1;}\n'
        source += 'domain-user-syscall-hook=oldhook;serial-write-cstr(com1(),"user-space: executions ");serial-write-dec-wide(com1(),us-executions);serial-nl(com1());\n'
        source += 'serial-write-cstr(com1(),"user-space: native ownership corpus PASS");serial-nl(com1());}\n'
        (args.out / 'kernel.in').write_text(source)
        command = [str(args.compiler), 'compile', '--path', str(args.out / 'kernel.in'), '--entry', 'kernel-entry',
                   '--emit', 'boot', '--trampoline', str(trampoline), '--target', 'native',
                   '--target-triple', 'x86_64-unknown-none', '--linkage', 'static-lib', '--out', str(kernel)]
        commands.append(command)
        report['commands'] = commands
        with (args.out / 'compile.log').open('a') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=180, check=True)
        layout = json.loads(kernel.with_suffix('.component-metadata.json').read_text())['boot_layout']
        require(layout['load_end'] < 0x2F0000 and private.stat().st_size <= 0x10000 and layout['file_size'] == kernel.stat().st_size, 'kernel/payload overlap')
        report['boot_layout'] = layout
        report['artifacts'] = {p.name: dict(sha256=sha(p), size=p.stat().st_size) for p in [kernel, guest, private, trampoline]}
        command = ['qemu-system-x86_64', '-kernel', str(kernel), '-m', '512M', '-cpu', 'max', '-display', 'none',
                   '-no-reboot', '-serial', 'file:' + str(args.out / 'serial.log'),
                   '-device', 'loader,file=' + str(guest) + ',addr=0x10000000,force-raw=on',
                   '-device', 'loader,file=' + str(private) + ',addr=0x2F0000,force-raw=on']
        report['qemu_command'] = command
        with (args.out / 'qemu.log').open('w') as log:
            qemu = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + args.wall_timeout
            text = ''
            while time.monotonic() < deadline:
                serial = args.out / 'serial.log'
                text = serial.read_text(errors='replace') if serial.exists() else ''
                if 'space interactive shell' in text or 'PANIC' in text or 'nanokernel fault handler halting' in text or qemu.poll() is not None:
                    break
                time.sleep(.1)
        require('user-space: native ownership corpus PASS' in text and 'space interactive shell' in text, 'native corpus failed; inspect serial.log')
        require('INVALID private address-space entry' not in text and 'PANIC' not in text, 'private entry or panic')
        for name in cases:
            require(text.count('user-space: ' + MARKERS[name] + ' PASS') == args.repeat + 1, 'missing case completion: ' + name)
        require('user-space: real bounded SCI private imports refused before lifecycle PASS' in text, 'private SCI proof absent')
        require(('user-space: injected provider claim refusal retained discovery repair recovery PASS' if args.claim_failure_control else 'user-space: cold frame metadata generation domain admission bounds PASS') in text, 'cold/control proof absent')
        if 'quarantine' in cases:
            require(text.count('user-space: public release projection retained retry versus committed detach PASS') == args.repeat + 1, 'public release ownership proof absent')
            report['public_release_retained_vs_detached_recovery'] = True
        match = re.search(r'user-space: executions (\d+)', text)
        require(match is not None, 'missing execution accounting')
        report['actual_cpl3_entries'] = int(match[1])
        expected_entries = sum({'shared': 5, 'bounds': 1, 'faults': 5, 'bridge': 1, 'reinitialize': 1}.get(name, 0) for name in cases) * (args.repeat + 1)
        require(report['actual_cpl3_entries'] == expected_entries, 'actual entry accounting differs from selected contracts')
        report['real_page_faults'] = 3 * (args.repeat + 1) if 'faults' in cases else 0
        report['real_irq_deadlines'] = args.repeat + 1 if 'faults' in cases else 0
        report['warmup_cycles'] = 1
        report['allocation_domain_capability_high_water_stable'] = True
        report['private_sci_before_lifecycle_refusal'] = True
        report['private_sci_physical_extent'] = [0x2F0000, 0x2F0000 + private.stat().st_size]
        report['limits'] = 'Native supervisor-owned API only; no Linux migration, vfork, general shared processes, or public SCI pointer API.'
        report['source_unchanged'] = all((ROOT / name).read_bytes() == data for name, data in contents.items())
        require(report['source_unchanged'], 'live source changed during test; snapshot receipt retained but overall fails')
        report['status'] = 'provider-refusal-control-passed' if args.claim_failure_control else 'passed'
        print('PASS: native UserAddressSpace, ' + str(report['actual_cpl3_entries']) + ' actual CPL3 entries; ' + str(args.out))
    except Exception as error:
        report['status'] = 'failed'
        report['error'] = str(error)
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
