#!/usr/bin/env python3
"""Run the bounded application lab; the broader compatibility/desktop goal stays OPEN."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_inventory(root, excluded):
    """Include tracked and new source inputs, detecting additions and removals too."""
    names = subprocess.check_output(
        ['git', '-C', str(root), 'ls-files', '--cached', '--others', '--exclude-standard', '-z']
    ).decode().split('\0')
    inventory = {}
    for name in sorted(set(names)):
        if not name or '__pycache__' in Path(name).parts:
            continue
        path = root / name
        if any(path == base or base in path.parents for base in excluded):
            continue
        if path.is_file():
            inventory[name] = sha(path)
    return inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--in', dest='compiler', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True, help='New or empty evidence directory')
    parser.add_argument('--apps-dir', type=Path, required=True, help='Pinned upstream application cache')
    for name in ['lua', 'busybox', 'sqlite', 'fbv', 'quickjs', 'sed']:
        parser.add_argument('--' + name, type=Path,
                            help='Pinned source-built ' + name + '; otherwise --download builds an absent artifact')
    parser.add_argument('--busybox-vfork', type=Path, help='Separate pinned upstream xargs ELF; otherwise cache busybox-vfork or --download builds it')
    parser.add_argument('--busybox-vi', type=Path, help='Separate pinned upstream vi ELF; otherwise cache busybox-vi or --download builds it')
    parser.add_argument('--terminal-oracle-python',type=Path,default=Path(sys.executable),
                        help='Interpreter with fixtures/terminal-session/oracle-requirements.txt for screen/pixel comparisons')
    parser.add_argument('--cohort',choices=['all','cross-os','cli'],default='all',
                        help='all gates, original cross-OS assembler cohort, or broader original CLI cohort')
    parser.add_argument('--fasmg-archive',type=Path,help='Existing pinned fasmg archive; otherwise cache or --download')
    parser.add_argument('--download', action='store_true', help='Acquire/build absent pinned applications; every hash remains required')
    parser.add_argument('--pipeline-wall-timeout', type=int, default=1200,
                        help='external wall limit for repeated BusyBox transfers; guest IRQ budget/assertions stay unchanged')
    args = parser.parse_args()
    if not 1 <= args.pipeline_wall_timeout <= 3600:
        parser.error('--pipeline-wall-timeout must be in 1..3600 seconds')
    args.compiler = args.compiler.resolve()
    args.out = args.out.resolve()
    args.apps_dir = args.apps_dir.resolve()
    if not args.compiler.is_file():
        parser.error('--in must name an existing source-built compiler')
    if args.out.exists() and (not args.out.is_dir() or any(args.out.iterdir())):
        parser.error('--out must be new or empty')
    if args.apps_dir == ROOT or args.apps_dir in ROOT.parents:
        parser.error('--apps-dir must be a separate application cache, not the repository or its ancestor')
    args.out.mkdir(parents=True, exist_ok=True)
    args.apps_dir.mkdir(parents=True, exist_ok=True)
    report = {
        'schema_version': 2, 'started_utc': datetime.now(timezone.utc).isoformat(),
        'compiler': str(args.compiler), 'compiler_sha256': sha(args.compiler),
        'goal_status': 'OPEN', 'cohort':args.cohort,
        'scope': 'Bounded native workflows, upstream Linux jq/Lua/BusyBox/SQLite execution including SQLite NVMe durability, original fbv CLI entry with counted-argument startup fixtures plus an explicit single-canvas BMP viewer profile, protected Linux pipes, generic compiler ELF execution, protected Darwin/Windows fixtures, native clocks and readable GUI workflows. Bounded BusyBox copied children, shared-vfork xargs and blocking pipelines are included, along with native owned address spaces, protected native SCI ownership, explicit trusted GUI baselines and the default protected GUI. Windows Unicode and composed APIs have separate runtime/model gates. Finite root Find imports have real CPL3 RAM and readonly NVMe reboot gates. Native immutable file observations supply original fbv pixels and original fbv/BusyBox/Lua CLI across v1/UTC NVMe reboots, with separate argv/executable identity. Original BusyBox vi EX edit/save and separate-process reopen run on both native roots and both NVMe schemas, with distinct own poll/resize fixtures. Exact mature-font desktop coverage and visual interactions are included. Original QuickJS/GNU sed add language/file/regex work, owned launch vectors and true stopped-CPU clock deadlines. Original Linux/macOS/Windows fasmg executes unchanged with exact compiler outputs, errors and cleanup; native32/low-VM controls remain separately counted. Broader dependencies, general foreign GUI/FLTK/X11 and desktop app launch remain open.',
        'gates': [], 'applications': [],
        'source_sha256': source_inventory(ROOT, [args.out, args.apps_dir]),
    }
    if args.cohort=='cross-os':report['scope']='Pinned original Linux/macOS/Windows assembler builds across six CPU profiles, acquisition and four separate native ownership/CPU gates; no new graphical application claim.'
    if args.cohort=='cli':report['scope']='Original unchanged-source QuickJS and GNU sed on standard/minimal roots, explicit no-HPET wall-clock profile and separate compiled-private SCI refusals; no graphical application claim.'
    # Retain explicit trusted baseline gates; dedicated default GUI gates clear
    # this choice and build the shipped protected image independently.
    environment = dict(os.environ, IN=str(args.compiler), BUILD_DIR=str(args.out / 'images'),
                       GUI_PROFILE='window')
    if args.compiler.parts[-4:] in [('in-cli', 'target', 'release', 'in'), ('in-cli', 'target', 'debug', 'in')]:
        environment['INAUGURATION_DIR'] = str(args.compiler.parents[3])

    def save():
        temporary = args.out / 'report.json.tmp'
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(args.out / 'report.json')

    def integrity():
        current = source_inventory(ROOT, [args.out, args.apps_dir])
        changed = sorted(name for name in set(current) | set(report['source_sha256'])
                         if current.get(name) != report['source_sha256'].get(name))
        previous = report.get('source_changed_during_run', [])
        report['source_changed_during_run'] = sorted(set(previous) | set(changed))
        compiler_changed = not args.compiler.is_file() or sha(args.compiler) != report['compiler_sha256']
        report['compiler_changed_during_run'] = report.get('compiler_changed_during_run', False) or compiler_changed
        changed_apps = [app['id'] for app in report['applications']
                        if not Path(app['path']).is_file() or sha(Path(app['path'])) != app['sha256']]
        report['applications_changed_during_run'] = sorted(set(report.get('applications_changed_during_run', [])) | set(changed_apps))
        return not (report['source_changed_during_run'] or report['compiler_changed_during_run']
                    or report['applications_changed_during_run'])

    def run(name, command, timeout=600, dependency=True):
        entry = {'name': name, 'command': [str(word) for word in command],
                 'log': str(args.out / (name + '.log'))}
        report['gates'].append(entry)
        if not integrity():
            entry.update(status='blocked', reason='source/compiler/application changed during this run')
            save()
            return False
        if not dependency:
            entry.update(status='blocked', reason='required prior gate failed')
            save()
            return False
        entry['status'] = 'running'
        save()
        print('RUN ' + name, flush=True)
        start = time.monotonic()
        try:
            with Path(entry['log']).open('w') as log:
                result = subprocess.run(entry['command'], cwd=ROOT, env=environment, stdout=log,
                                        stderr=subprocess.STDOUT, timeout=timeout)
            entry.update(status='passed' if result.returncode == 0 else 'failed', exit_code=result.returncode)
        except (OSError, subprocess.TimeoutExpired) as error:
            entry.update(status='failed', error=str(error))
        if not integrity():
            entry.update(status='failed', integrity_failure='source/compiler/application changed during this run')
        entry['elapsed_seconds'] = round(time.monotonic() - start, 3)
        save()
        print(entry['status'].upper() + ' ' + name, flush=True)
        return entry['status'] == 'passed'

    def finish():
        coherent = integrity()
        report['integrity_status'] = 'passed' if coherent else 'failed'
        report.update(finished_utc=datetime.now(timezone.utc).isoformat(),
                      passed=sum(gate['status'] == 'passed' for gate in report['gates']),
                      failed=sum(gate['status'] != 'passed' for gate in report['gates']))
        report['lab_status'] = 'passed' if coherent and not report['failed'] and not report.get('artifact_failure') else 'failed'
        save()
        print(f"{report['passed']} passed, {report['failed']} failed or blocked; lab {report['lab_status']}; broader goal OPEN; {args.out / 'report.json'}")
        return 0 if report['lab_status'] == 'passed' else 1

    def require_artifact(app, path):
        if not path.is_file() or sha(path) != app['sha256'] or path.stat().st_size != app['size_bytes']:
            report['artifact_failure'] = {'id': app['id'], 'path': str(path), 'reason': 'absent or invalid pinned artifact'}
            raise RuntimeError('absent or invalid pinned application ' + str(path))
        report['applications'].append({'id': app['id'], 'path': str(path), 'sha256': sha(path),
                                       'size_bytes': path.stat().st_size})
        save()
        return path

    save()
    if args.cohort in ['all','cross-os']:
        # This mandatory cohort preserves original bytes and licenses, and is also
        # runnable independently while the complete all-gates receipt stays scoped.
        fasmg_cache=args.apps_dir/'fasmg'
        command=[sys.executable,ROOT/'scripts/acquire-fasmg.py','--out',fasmg_cache]
        if args.fasmg_archive:command+=['--archive',args.fasmg_archive.resolve()]
        if args.download:command+=['--download']
        acquired=run('fasmg-acquire',command)
        fasmg_apps={}
        if acquired:
            try:
                for app in json.loads((ROOT/'fixtures/applications/fasmg.json').read_text())['apps']:
                    app=dict(app,id='fasmg-'+app['personality'])
                    fasmg_apps[app['personality']]=require_artifact(app,fasmg_cache/app['id'])
            except (OSError,RuntimeError,ValueError) as error:
                report.setdefault('artifact_failure',{'reason':str(error)});return finish()
        for personality,cpus in [('linux',['max','qemu64-rdrand']),('darwin',['max','qemu64']),('windows',['max','qemu64'])]:
            for cpu in cpus:
                name='original-fasmg-'+personality+'-'+cpu
                run(name,[sys.executable,ROOT/('scripts/check-fasmg-'+personality+'.py'),
                          '--in',args.compiler,'--app',fasmg_apps.get(personality,fasmg_cache/('fasmg-'+personality)),
                          '--cpu',cpu,'--out',args.out/name],dependency=acquired)
        for cpu in ['max','qemu64']:
            for profile,script in [('compat32','check-user-context-compat32.py'),('low-view','check-user-space-low.py')]:
                name='native-'+profile+'-'+cpu
                run(name,[sys.executable,ROOT/'scripts'/script,'--in',args.compiler,
                          '--cpu',cpu,'--out',args.out/name])
    if args.cohort=='cross-os':return finish()
    if args.cohort in ['all','cli']:
        cli_apps={}
        try:
            for name,version,filename in [('quickjs','2024-01-13','qjs'),('sed','4.9','sed')]:
                explicit=getattr(args,name)
                path=explicit.resolve() if explicit else args.apps_dir/filename
                if not path.exists() and args.download and not explicit:
                    if not run(name+'-source-build',[sys.executable,ROOT/'scripts/build-cli-corpus.py',
                               '--application',name,'--out',args.out/(name+'-build')],timeout=900):
                        raise RuntimeError(name+' unchanged source build failed; receipt retained')
                    path=args.out/(name+'-build')/filename
                app=json.loads((ROOT/'fixtures/applications'/(name+'-'+version+'.json')).read_text())['apps'][0]
                cli_apps[name]=require_artifact(app,path)
        except (OSError,RuntimeError,ValueError) as error:
            report.setdefault('artifact_failure',{'reason':str(error)});return finish()
        for name in ['quickjs','sed']:
            for variant in ['standard','minimal']:
                gate='original-'+name+'-'+variant
                extra=['--timer-grant','--expect-deadline-wait'] if name=='quickjs' else []
                version='2024-01-13' if name=='quickjs' else '4.9'
                run(gate,[sys.executable,ROOT/'scripts/check-linux-corpus.py','--in',args.compiler,
                          '--application',name,'--app',cli_apps[name],'--suite','--input-suite',
                          '--case-config',ROOT/'fixtures/applications'/(name+'-'+version+'-cases.json'),
                          '--root',variant,*extra,'--out',args.out/gate],timeout=900)
        gate='original-quickjs-no-hpet'
        run(gate,[sys.executable,ROOT/'scripts/check-linux-corpus.py','--in',args.compiler,
                  '--application','quickjs','--app',cli_apps['quickjs'],'--suite','--input-suite',
                  '--case-config',ROOT/'fixtures/applications/quickjs-2024-01-13-nohpet-cases.json',
                  '--timer-grant','--no-hpet','--out',args.out/gate],timeout=900)
        run('private-execution-imports',[sys.executable,ROOT/'scripts/check-private-execution-imports.py',
                                       '--in',args.compiler,'--out',args.out/'private-execution-imports'])
    if args.cohort=='cli':return finish()
    applications = {}
    try:
        for app in json.loads((ROOT / 'fixtures/applications/jq-1.8.1.json').read_text())['apps']:
            path = args.apps_dir / app['filename']
            if not path.exists() and args.download:
                print('ACQUIRE ' + app['id'], flush=True)
                temporary = path.with_suffix(path.suffix + '.part')
                try:
                    with urllib.request.urlopen(app['url'], timeout=60) as response, temporary.open('xb') as target:
                        while block := response.read(65536):
                            target.write(block)
                    if sha(temporary) != app['sha256'] or temporary.stat().st_size != app['size_bytes']:
                        raise RuntimeError('upstream artifact checksum/size mismatch: ' + app['id'])
                    temporary.chmod(0o755)
                    temporary.replace(path)
                finally:
                    temporary.unlink(missing_ok=True)
            applications[app['personality']] = require_artifact(app, path)
        for name, version, filename in [('lua', 'lua-5.4.7', 'lua'), ('busybox', 'busybox-1.36.1', 'busybox'),
                                        ('sqlite', 'sqlite-3.46.1', 'sqlite3'), ('fbv', 'fbv-1.1', 'fbv')]:
            explicit = getattr(args, name)
            path = explicit.resolve() if explicit else args.apps_dir / filename
            if not path.exists() and args.download and not explicit:
                if not run(name + '-source-build', [sys.executable, ROOT / ('scripts/build-' + name + '-corpus.py'),
                                                    '--out', args.out / (name + '-build')]):
                    raise RuntimeError(name + ' source build failed; evidence retained')
                path = args.out / (name + '-build') / filename
            app = json.loads((ROOT / ('fixtures/applications/' + version + '.json')).read_text())['apps'][0]
            applications[name] = require_artifact(app, path)
        # This upstream Kconfig profile has distinct bytes and provenance. Never
        # replace the completed default BusyBox artifact/case corpus with it.
        manifest = ROOT / 'fixtures/applications/busybox-1.36.1-vfork.json'
        cases = ROOT / 'fixtures/applications/busybox-1.36.1-vfork-cases.json'
        explicit = args.busybox_vfork
        path = explicit.resolve() if explicit else args.apps_dir / 'busybox-vfork'
        if not path.exists() and args.download and not explicit:
            if not run('busybox-vfork-source-build', [sys.executable, ROOT / 'scripts/build-busybox-corpus.py',
                                                       '--manifest', manifest, '--case-config', cases,
                                                       '--out', args.out / 'busybox-vfork-build']):
                raise RuntimeError('BusyBox vfork profile source build failed; evidence retained')
            path = args.out / 'busybox-vfork-build/busybox'
        app = json.loads(manifest.read_text())['apps'][0]
        applications['busybox-vfork'] = require_artifact(app, path)
        manifest = ROOT / 'fixtures/applications/busybox-vi-1.36.1.json'
        explicit = args.busybox_vi
        path = explicit.resolve() if explicit else args.apps_dir / 'busybox-vi'
        if not path.exists() and args.download and not explicit:
            if not run('busybox-vi-source-build', [sys.executable, ROOT / 'scripts/build-busybox-corpus.py',
                       '--manifest', manifest, '--out', args.out / 'busybox-vi-build']):
                raise RuntimeError('BusyBox vi profile source build failed; evidence retained')
            path = args.out / 'busybox-vi-build/busybox'
        applications['busybox-vi'] = require_artifact(json.loads(manifest.read_text())['apps'][0],path)
    except (OSError, RuntimeError, ValueError) as error:
        report.setdefault('artifact_failure', {'reason': str(error)})
        save()
        print('FAIL: ' + str(error), file=sys.stderr)
        return finish()

    def check(name, script, *arguments, interpreter=None, **options):
        return run(name, [interpreter or sys.executable, ROOT / 'scripts' / script, *arguments], **options)

    check('fixture-boot-layout','check-boot-fixture-layout.py','--out',args.out / 'fixture-boot-layout')
    check('terminal-session-model','check-terminal-session-model.py','--in',args.compiler,
          '--out',args.out / 'terminal-session-model')
    check('terminal-session-native','check-terminal-session.py','--in',args.compiler,
          '--out',args.out / 'terminal-session-native')
    check('linux-terminal-retained','check-terminal-session.py','--in',args.compiler,'--retained',
          '--out',args.out / 'linux-terminal-retained')
    for variant in ['standard', 'minimal']:
        check('linux-terminal-vi-keyboard-' + variant, 'check-linux-terminal-vi.py',
              '--in', args.compiler, '--app', applications['busybox-vi'],
              '--root', variant, '--out', args.out / ('linux-terminal-vi-keyboard-' + variant))
    run('terminal-screen-model',[args.terminal_oracle_python,ROOT/'scripts/check-terminal-screen.py',
                               '--in',args.compiler,'--out',args.out/'terminal-screen-model'])
    check('linux-terminal-vi-view','check-linux-terminal-vi.py','--in',args.compiler,
          '--app',applications['busybox-vi'],'--view','--oracle-python',args.terminal_oracle_python,
          '--out',args.out/'linux-terminal-vi-view')
    check('linux-terminal-vi-navigation-view','check-linux-terminal-vi.py','--in',args.compiler,
          '--app',applications['busybox-vi'],'--view','--navigation','--oracle-python',args.terminal_oracle_python,
          '--out',args.out/'linux-terminal-vi-navigation-view')
    check('linux-terminal-vi-navigation-minimal','check-linux-terminal-vi.py','--in',args.compiler,
          '--app',applications['busybox-vi'],'--root','minimal','--navigation',
          '--out',args.out/'linux-terminal-vi-navigation-minimal')
    for schema,options in [('v1',[]),('utc',['--utc'])]:
        check('linux-terminal-vi-durable-'+schema,'check-linux-terminal-vi-persistence.py',
              '--in',args.compiler,'--app',applications['busybox-vi'],
              '--oracle-python',args.terminal_oracle_python,*options,
              '--out',args.out/('linux-terminal-vi-durable-'+schema))
    built = run('images', ['bash', 'scripts/build-images.sh'], timeout=900)
    for variant in ['standard', 'minimal']:
        check('native-' + variant, 'check-native-applications.py', '--image', args.out / 'images' / (variant + '.bin'),
              '--out', args.out / ('native-' + variant), dependency=built)
    check('linux-file-control-model', 'check-linux-poll-model.py', '--in', args.compiler,
          '--out', args.out / 'linux-file-control-model')
    for variant in ['standard', 'minimal']:
        gate='linux-vi-batch-'+variant
        check(gate,'check-linux-tui.py','--in',args.compiler,'--app',applications['busybox-vi'],
              '--batch-ex','--root',variant,'--out',args.out / gate)
    for schema, options in [('v1',[]),('utc',['--utc'])]:
        gate='linux-vi-batch-nvme-'+schema
        check(gate,'check-linux-tui.py','--in',args.compiler,'--app',applications['busybox-vi'],
              '--batch-ex','--nvme',*options,'--out',args.out / gate)
    check('native-persistence', 'check-native-persistence.py', '--in', args.compiler,
          '--image', args.out / 'images/standard.bin', '--out', args.out / 'native-persistence', dependency=built)
    for name, script in [('linux-jq', 'check-linux-real-app.py'), ('linux-lua', 'check-linux-corpus.py'),
                         ('linux-busybox', 'check-linux-corpus.py'), ('linux-sqlite-memory', 'check-linux-corpus.py')]:
        application = name.split('-')[1]
        command = ['--in', args.compiler, '--app', applications['linux' if application == 'jq' else application],
                   '--suite', '--out', args.out / name]
        if application != 'jq':
            command += ['--application', application]
        if application != 'sqlite':
            command += ['--input-suite']
        check(name, script, *command)
    check('linux-sqlite-files', 'check-linux-corpus.py', '--in', args.compiler,
          '--application', 'sqlite', '--app', applications['sqlite'], '--suite', '--input-suite',
          '--wall-timeout', '600', '--out', args.out / 'linux-sqlite-files', timeout=660)
    check('linux-sqlite-nvme', 'check-linux-persistence.py', '--in', args.compiler,
          '--app', applications['sqlite'], '--out', args.out / 'linux-sqlite-nvme')
    for application in ['jq', 'lua', 'busybox', 'sqlite']:
        name = 'linux-' + application + '-minimal'
        check(name, 'check-linux-corpus.py', '--in', args.compiler, '--root', 'minimal',
              '--application', application,
              '--app', applications['linux' if application == 'jq' else application],
              '--suite', '--input-suite', '--wall-timeout', '600',
              '--out', args.out / name, timeout=660)
    for variant in ['standard', 'minimal']:
        # Keep native pipe contracts and copied-process application scenarios distinct.
        check('linux-pipes-' + variant, 'check-linux-pipes.py', '--in', args.compiler,
              '--root', variant, '--out', args.out / ('linux-pipes-' + variant))
    for variant in ['standard', 'minimal']:
        check('linux-children-' + variant, 'check-linux-children.py', '--in', args.compiler,
              '--root', variant, '--out', args.out / ('linux-children-' + variant))
        check('linux-blocking-' + variant, 'check-linux-blocking.py', '--in', args.compiler,
              '--root', variant, '--out', args.out / ('linux-blocking-' + variant), timeout=660)
        check('linux-busybox-blocking-' + variant, 'check-linux-blocking-pipeline.py',
              '--in', args.compiler, '--busybox', applications['busybox'], '--root', variant,
              '--wall-timeout', str(args.pipeline_wall_timeout),
              '--out', args.out / ('linux-busybox-blocking-' + variant), timeout=args.pipeline_wall_timeout+60)
        check('linux-busybox-children-' + variant, 'check-linux-corpus.py', '--in', args.compiler,
              '--application', 'busybox', '--app', applications['busybox'], '--suite', '--input-suite',
              '--case-config', ROOT / 'fixtures/applications/busybox-1.36.1-children-cases.json',
              '--root', variant, '--wall-timeout', '600',
              '--out', args.out / ('linux-busybox-children-' + variant), timeout=660)
    for variant in ['standard', 'minimal']:
        check('compiler-linux-' + variant, 'check-inauguration-linux.py', '--in', args.compiler,
              '--root', variant, '--out', args.out / ('compiler-linux-' + variant))
    for variant in ['standard', 'minimal']:
        for name, options in [('owned', []), ('exec-capacity', ['--stage-capacity']),
                              ('constructor', ['--constructor-control'])]:
            gate = 'linux-vm-' + name + '-' + variant
            check(gate, 'check-linux-vm.py', '--in', args.compiler, '--root', variant,
                  *options, '--out', args.out / gate)
    for variant in ['standard', 'minimal']:
        for profile, option in [('shared', '--vfork'), ('deadline', '--vfork-deadline')]:
            gate = 'linux-vfork-' + profile + '-' + variant
            check(gate, 'check-linux-vm.py', '--in', args.compiler, '--root', variant,
                  option, '--out', args.out / gate)
        gate = 'linux-vfork-fd-' + variant
        check(gate, 'check-linux-children.py', '--in', args.compiler, '--root', variant,
              '--vfork-fd-profile', '--out', args.out / gate)
        gate = 'linux-busybox-vfork-' + variant
        check(gate, 'check-linux-corpus.py', '--in', args.compiler, '--root', variant,
              '--application', 'busybox', '--app', applications['busybox-vfork'],
              '--manifest', ROOT / 'fixtures/applications/busybox-1.36.1-vfork.json',
              '--case-config', ROOT / 'fixtures/applications/busybox-1.36.1-vfork-cases.json',
              '--suite', '--input-suite', '--out', args.out / gate)
    for variant in ['standard', 'minimal']:
        gate = 'linux-fbv-cli-' + variant
        # Original viewer startup is distinct from the separately counted ELF
        # stack probes and does not certify framebuffer/GUI presentation.
        check(gate, 'check-linux-fbv.py', '--in', args.compiler, '--root', variant,
              '--app', applications['fbv'], '--out', args.out / gate)
    check('linux-framebuffer', 'check-linux-framebuffer.py', '--in', args.compiler,
          '--app', applications['fbv'], '--out', args.out / 'linux-framebuffer')
    check('stored-fbv-ram', 'check-linux-framebuffer.py', '--in', args.compiler,
          '--app', applications['fbv'], '--file-source', '--out', args.out / 'stored-fbv-ram')
    for schema, options in [('v1', []), ('utc', ['--utc'])]:
        check('stored-fbv-nvme-' + schema, 'check-file-observation-persistence.py',
              '--in', args.compiler, '--app', applications['fbv'], *options,
              '--out', args.out / ('stored-fbv-nvme-' + schema))
        check('stored-cli-nvme-' + schema, 'check-file-observation-apps.py',
              '--in', args.compiler, '--fbv', applications['fbv'],
              '--busybox', applications['busybox'], '--lua', applications['lua'],
              *options, '--out', args.out / ('stored-cli-nvme-' + schema))
    check('native-canvas', 'check-native-canvas.py', '--in', args.compiler,
          '--out', args.out / 'native-canvas')
    check('darwin-process', 'check-darwin-protected.py', '--in', args.compiler, '--imports',
          '--app', applications['darwin'], '--out', args.out / 'darwin-process')
    check('darwin-startup-owner', 'check-darwin-startup-owner.py', '--in', args.compiler,
          '--out', args.out / 'darwin-startup-owner')
    check('darwin-startup', 'check-darwin-startup.py', '--in', args.compiler,
          '--app', applications['darwin'], '--out', args.out / 'darwin-startup')
    check('darwin-eager-owner', 'check-darwin-eager-owner.py', '--in', args.compiler,
          '--out', args.out / 'darwin-eager-owner')
    check('darwin-eager', 'check-darwin-eager.py', '--in', args.compiler,
          '--app', applications['darwin'], '--out', args.out / 'darwin-eager')
    check('darwin-heap-owner', 'check-darwin-heap-owner.py', '--in', args.compiler,
          '--out', args.out / 'darwin-heap-owner')
    check('darwin-heap-import-baseline', 'check-darwin-heap-import-baseline.py', '--in', args.compiler,
          '--app', applications['darwin'], '--out', args.out / 'darwin-heap-import-baseline')
    check('darwin-heap', 'check-darwin-heap.py', '--in', args.compiler,
          '--app', applications['darwin'], '--out', args.out / 'darwin-heap')
    for variant in ['standard', 'minimal']:
        check('darwin-mapped-' + variant, 'check-darwin-mapped.py', '--in', args.compiler,
              '--jq', applications['darwin'], '--root', variant,
              '--out', args.out / ('darwin-mapped-' + variant))
        check('darwin-rune-' + variant,'check-darwin-rune.py','--in',args.compiler,
              '--root',variant,'--out',args.out / ('darwin-rune-' + variant))
    check('darwin-files', 'check-darwin-files.py', '--in', args.compiler, '--out', args.out / 'darwin-files')
    check('windows-process', 'check-windows-protected.py', '--in', args.compiler,
          '--app', applications['windows'], '--out', args.out / 'windows-process')
    check('windows-general', 'check-windows-application.py', '--in', args.compiler,
          '--app', applications['windows'], '--out', args.out / 'windows-general')
    check('windows-startup', 'check-windows-startup.py', '--in', args.compiler,
          '--out', args.out / 'windows-startup')
    for name, script in [('windows-parameters', 'check-windows-parameters.py'),
                         ('windows-identity', 'check-windows-identity.py'),
                         ('windows-pe-view', 'check-windows-pe-view.py'),
                         ('windows-filetime', 'check-windows-filetime.py'),
                         ('windows-environment', 'check-windows-environment.py'),
                         ('windows-counter', 'check-windows-counter.py'),
                         ('windows-heap', 'check-windows-heap.py'),
                         ('windows-local', 'check-windows-local.py'),
                         ('windows-critical', 'check-windows-critical.py'),
                         ('windows-composed', 'check-windows-composed.py')]:
        check(name, script, '--in', args.compiler, '--out', args.out / name)
    unicode_ok = check('windows-unicode', 'check-windows-unicode.py', '--in', args.compiler,
                       '--out', args.out / 'windows-unicode', timeout=900)
    check('unicode-scalars', 'check-unicode-scalars.py', '--in', args.compiler,
          '--oracles', args.out / 'windows-unicode/oracles.bin',
          '--out', args.out / 'unicode-scalars', dependency=unicode_ok)
    check('windows-unicode-mixed', 'check-windows-composed.py', '--in', args.compiler,
          '--profile', '11', '--out', args.out / 'windows-unicode-mixed')
    check('native-path-normalization', 'check-fs-path-normalize.py', '--in', args.compiler,
          '--out', args.out / 'native-path-normalization')
    check('windows-paths', 'check-windows-paths.py', '--in', args.compiler,
          '--out', args.out / 'windows-paths')
    check('windows-paths-nvme', 'check-windows-path-persistence.py', '--in', args.compiler,
          '--out', args.out / 'windows-paths-nvme')
    check('windows-find', 'check-windows-find.py', '--in', args.compiler,
          '--out', args.out / 'windows-find')
    check('windows-find-nvme', 'check-windows-find-persistence.py', '--in', args.compiler,
          '--out', args.out / 'windows-find-nvme')
    check('native-utc-metadata', 'check-native-utc-metadata.py', '--in', args.compiler,
          '--out', args.out / 'native-utc-metadata')
    check('native-utc-persistence', 'check-native-utc-persistence.py', '--in', args.compiler,
          '--out', args.out / 'native-utc-persistence')
    check('native-directory', 'check-native-directory.py', '--in', args.compiler,
          '--out', args.out / 'native-directory')
    check('native-directory-nvme', 'check-native-directory.py', '--in', args.compiler,
          '--nvme', '--out', args.out / 'native-directory-nvme')
    check('windows-files', 'check-windows-files.py', '--in', args.compiler, '--out', args.out / 'windows-files')
    check('windows-write', 'check-windows-write.py', '--in', args.compiler, '--out', args.out / 'windows-write')
    check('windows-nvme', 'check-windows-persistence.py', '--in', args.compiler, '--out', args.out / 'windows-nvme')
    check('native-large-files', 'check-native-large-files.py', '--in', args.compiler, '--out', args.out / 'native-large-files')
    for name, script in [('native-file-services', 'check-native-file-services.py'),
                         ('native-range-leases', 'check-file-range-leases.py'),
                         ('native-stat-identity', 'check-fs-stat-identity.py'),
                         ('native-nvme-flush', 'check-nvme-flush.py'),
                         ('native-time-model', 'check-time-service.py'),
                         ('native-time-rtc', 'check-time-rtc.py'),
                         ('native-counter-owner', 'check-counter-owner.py'),
                         ('native-counter-hardware', 'check-hardware-counter.py'),
                         ('native-discard-owner', 'check-vfs-discard.py'),
                         ('native-discard-runtime', 'check-vfs-discard-runtime.py')]:
        check(name, script, '--in', args.compiler, '--out', args.out / name)
    check('native-lifecycle', 'check-native-lifecycle.py', '--in', args.compiler, '--out', args.out / 'native-lifecycle')
    check('native-retained', 'check-native-retained.py', '--in', args.compiler,
          '--out', args.out / 'native-retained')
    for profile in ['immutable', 'paged']:
        check('native-protected-' + profile, 'check-native-protected.py', '--in', args.compiler,
              '--profile', profile, '--out', args.out / ('native-protected-' + profile))
    check('native-protected-oom', 'check-native-protected.py', '--in', args.compiler,
          '--profile', 'paged', '--mode', 'oom', '--out', args.out / 'native-protected-oom')
    for mode in ['full', 'oom']:
        check('native-protected-gui-' + mode, 'check-native-protected-gui.py', '--in', args.compiler,
              '--mode', mode, '--out', args.out / ('native-protected-gui-' + mode))
    check('gui-protected-package', 'check-gui-protected-profile.py', '--in', args.compiler,
          '--out', args.out / 'gui-protected-package')
    check('keyboard-editing-models', 'check-keyboard-editing.py', '--in', args.compiler,
          '--out', args.out / 'keyboard-editing-models')
    for name, script in [('gui-protected-client-model', 'check-gui-protected-client.py'),
                         ('gui-protected-windows', 'check-gui-protected-windows.py'),
                         ('gui-protected-persistence', 'check-gui-protected-persistence.py'),
                         ('gui-protected-lifetime', 'check-gui-protected-lifetime.py'),
                         ('gui-protected-faults', 'check-gui-protected-faults.py')]:
        check(name, script, '--in', args.compiler, '--out', args.out / name, timeout=1200,
              interpreter=args.terminal_oracle_python)
    check('desktop-launcher', 'check-desktop-launcher.py', '--in', args.compiler,
          '--build-dir', args.out / 'desktop-launcher', timeout=900)
    check('desktop-font-coverage','check-desktop-fonts.py','--in',args.compiler,
          '--out',args.out / 'desktop-font-coverage')
    run('desktop-visual',['env','BUILD_DIR='+str(args.out / 'desktop-visual'),
                         'bash',ROOT / 'scripts/check-desktop-visual.sh'])
    run('desktop-damage', ['env', 'BUILD_DIR=' + str(args.out / 'desktop-damage'),
                           'KERNEL_BIN=' + str(args.out / 'images/kernel-standard.bin'),
                           'bash', ROOT / 'scripts/check-desktop-damage.sh'], dependency=built)
    check('gui-default', 'check-gui-default.py', '--in', args.compiler,
          '--out', args.out / 'gui-default', timeout=1200,interpreter=args.terminal_oracle_python)
    check('gui-default-faults', 'check-gui-default-faults.py', '--in', args.compiler,
          '--out', args.out / 'gui-default-faults', timeout=1200,interpreter=args.terminal_oracle_python)
    check('gui-default-persistence', 'check-gui-persistence.py', '--in', args.compiler,
          '--default-gui', '--out', args.out / 'gui-default-persistence', timeout=1200,interpreter=args.terminal_oracle_python)
    check('gui-default-lifecycle', 'check-gui-lifecycle.py', '--in', args.compiler,
          '--default-gui', '--observe', '--out', args.out / 'gui-default-lifecycle', timeout=1200,interpreter=args.terminal_oracle_python)
    check('standard-gui', 'check-standard-gui.py', '--in', args.compiler, '--build-dir', args.out / 'standard-gui')
    check('native-gui-apps', 'check-gui-apps.py', '--in', args.compiler, '--build-dir', args.out / 'gui-apps')
    check('gui-persistence', 'check-gui-persistence.py', '--in', args.compiler, '--out', args.out / 'gui-persistence')
    check('gui-lifecycle', 'check-gui-lifecycle.py', '--in', args.compiler, '--observe',
          '--out', args.out / 'gui-lifecycle', timeout=1200)
    for name, script in [('gui-canvas-profile', 'check-gui-canvas-profile.py'),
                         ('gui-window-layout', 'check-gui-window-layout.py'),
                         ('gui-window-contracts', 'check-gui-window-contracts.py'),
                         ('gui-window-replies', 'check-gui-window-replies.py'),
                         ('input-output', 'check-input-output.py')]:
        check(name, script, '--in', args.compiler)
    check('gui-canvas', 'check-gui-canvas.py', '--in', args.compiler,
          '--out', args.out / 'gui-canvas')
    check('gui-canvas-oom', 'check-gui-canvas.py', '--in', args.compiler,
          '--mode', 'oom', '--out', args.out / 'gui-canvas-oom')
    check('gui-readable-matrix', 'check-gui-windows.py', '--in', args.compiler,
          '--out', args.out / 'gui-readable-matrix')
    check('sci-byte-validation', 'check-sci-validation.py', '--in', args.compiler,
          '--out', args.out / 'sci-byte-validation',
          '--artifacts', *sorted((args.out / 'images').glob('*.sci')), dependency=built)
    for name, script in [('sci-bindings', 'check-sci-bindings.py'),
                         ('sci-admission', 'check-sci-admission.py')]:
        check(name, script, '--in', args.compiler, '--out', args.out / name)
    for cpu in ['qemu64', 'max']:
        check('user-context-' + cpu, 'check-user-context.py', '--in', args.compiler,
              '--cpu', cpu, '--out', args.out / ('user-context-' + cpu))
        check('sanitized-registers-' + cpu, 'check-user-initial-state.py', '--in', args.compiler,
              '--cpu', cpu, '--out', args.out / ('sanitized-registers-' + cpu))
    for variant in ['standard', 'minimal']:
        check('user-space-' + variant, 'check-user-space.py', '--in', args.compiler,
              '--root', variant, '--out', args.out / ('user-space-' + variant))
        check('user-space-claim-' + variant, 'check-user-space.py', '--in', args.compiler,
              '--root', variant, '--claim-failure-control',
              '--out', args.out / ('user-space-claim-' + variant))
    check('runtime-failure', 'check-runtime-failure.py', '--in', args.compiler, '--out', args.out / 'runtime-failure')
    check('user-budget', 'check-user-budget.py', '--in', args.compiler, '--out', args.out / 'user-budget')
    return finish()


if __name__ == '__main__':
    sys.exit(main())
