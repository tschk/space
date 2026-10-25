#!/usr/bin/env python3
"""Drive original editors and terminals on a private host X11 display.

This is a host reference, never a Space application pass. Editors must save
exact text, exit, reopen in a fresh process, append through actual key events
and save exact bytes again. WezTerm must run a real shell command. Warp's
bounded scenario is only a visible window; it does not claim a usable session.
Requires Pillow, Xvfb, xdotool and their local runtime dependencies.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def stop(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--x11-prefix', type=Path, required=True)
    parser.add_argument('--display', type=int, default=93)
    parser.add_argument('--app', action='append', choices=['lite-xl', 'pulsar', 'zed', 'wezterm', 'warp'])
    args = parser.parse_args()
    args.out = args.out.resolve(); args.out.mkdir(parents=True, exist_ok=False)
    prefix = args.x11_prefix.resolve()
    assert 1 <= args.display <= 999 and not Path('/tmp/.X11-unix/X' + str(args.display)).exists(), 'display already in use'
    env = dict(os.environ)
    env.update(DISPLAY=':' + str(args.display), XKB_CONFIG_ROOT=str(prefix / 'usr/share/X11/xkb'),
               LD_LIBRARY_PATH=str(prefix / 'usr/lib/x86_64-linux-gnu'),
               PATH=str(prefix / 'usr/bin') + ':' + env['PATH'])
    pins = {app['id']: app for app in json.loads((ROOT / 'fixtures/applications/desktop-corpus.json').read_text())['apps']}
    paths = {app['id']: Path(app['binary']).resolve() for app in json.loads(args.index.read_text())['apps']}
    report = dict(scope=__doc__, status='running', original_space_entries=0,
                  harness_sha256=sha(Path(__file__).resolve()), applications=[])

    def save():
        (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')

    def xdo(*words, check=True):
        return subprocess.run([str(prefix / 'usr/bin/xdotool'), *map(str, words)],
                              env=env, text=True, capture_output=True, check=check, timeout=10)

    def windows():
        return set(xdo('search', '--onlyvisible', '--name', '.', check=False).stdout.split())

    def key(chord):
        xdo('key', '--clearmodifiers', chord)

    def type_lines(text):
        for number, line in enumerate(text.splitlines()):
            if number:
                key('Return')
            xdo('type', '--clearmodifiers', '--delay', '2', line)

    def exact_file(path, expected):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if path.exists() and path.read_text() == expected:
                return
            time.sleep(.05)
        raise AssertionError('saved bytes differ: ' + repr(path.read_text() if path.exists() else None))

    server = None
    save()
    try:
        command = [str(prefix / 'usr/bin/Xvfb'), ':' + str(args.display), '-screen', '0', '1280x800x24',
                   '-nolisten', 'tcp', '-ac', '-fp', str(prefix / 'usr/share/fonts/X11/misc')]
        report['xvfb_command'] = command
        report['xvfb_sha256'] = sha(prefix / 'usr/bin/Xvfb')
        report['xdotool_sha256'] = sha(prefix / 'usr/bin/xdotool')
        with (args.out / 'xvfb.log').open('w') as log:
            server = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.monotonic() + 10
        while not Path('/tmp/.X11-unix/X' + str(args.display)).exists():
            assert time.monotonic() < deadline and server.poll() is None, 'Xvfb startup failure'
            time.sleep(.05)
        from PIL import ImageGrab
        for name in args.app or ['lite-xl', 'pulsar', 'zed', 'wezterm', 'warp']:
            folder = args.out / name; folder.mkdir()
            app = paths[name]
            row = dict(id=name, status='running', artifact_sha256=sha(app), stages=[])
            report['applications'].append(row); save()
            process = None
            try:
                assert row['artifact_sha256'] == pins[name]['sha256'] and app.stat().st_size == pins[name]['size_bytes']
                tenv = dict(env)
                tenv.update(XDG_CONFIG_HOME=str(folder / 'config'), XDG_CACHE_HOME=str(folder / 'cache'),
                            XDG_DATA_HOME=str(folder / 'data'), ATOM_HOME=str(folder / 'atom'),
                            PULSAR_HOME=str(folder / 'pulsar'))
                runtime = folder / 'runtime'; runtime.mkdir(mode=0o700)
                tenv['XDG_RUNTIME_DIR'] = str(runtime)
                document = folder / 'project.txt'; document.write_text('Original project\n')
                text = 'Space desktop editor trial\nOpen a real project, edit multiple lines and save.\nIndependent text survives a fresh process.\n'
                command = [str(app)]
                if name == 'pulsar':
                    command += ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage', '--safe',
                                '--user-data-dir=' + str(folder / 'electron-profile'), str(document)]
                elif name == 'lite-xl':
                    command += [str(document)]
                elif name == 'zed':
                    command += [str(document)]; tenv['ZED_ALLOW_EMULATED_GPU'] = '1'
                elif name == 'wezterm':
                    config = folder / 'wezterm.lua'
                    config.write_text('return {front_end="Software",enable_tab_bar=false,check_for_updates=false}')
                    command += ['--config-file', str(config), 'start', '--always-new-process', '--', '/bin/sh']
                row['command'] = command
                for stage in (['edit', 'reopen'] if name in ['lite-xl', 'pulsar', 'zed'] else ['visible']):
                    before = windows()
                    with (folder / (stage + '.log')).open('w') as log:
                        process = subprocess.Popen(command, env=tenv, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                    deadline = time.monotonic() + 25
                    visible = set()
                    while time.monotonic() < deadline:
                        visible = windows() - before
                        if visible or process.poll() is not None:
                            break
                        time.sleep(.1)
                    assert visible, 'no visible window; process return ' + str(process.poll())
                    window = next(iter(visible)); xdo('windowfocus', '--sync', window)
                    time.sleep(3)
                    if name == 'pulsar':
                        for _ in range(3):
                            if 'project.txt' in xdo('getwindowname', window).stdout:
                                break
                            key('ctrl+w'); time.sleep(1)
                        assert 'project.txt' in xdo('getwindowname', window).stdout, 'project editor not focused'
                    if name == 'zed':
                        # This directory contains only our own generated text,
                        # with no project configuration or executable hooks.
                        if stage == 'edit':
                            key('Return'); time.sleep(1)
                        xdo('mousemove', 300, 125); xdo('click', 1)
                    if name in ['lite-xl', 'pulsar', 'zed']:
                        if stage == 'edit':
                            key('ctrl+a'); type_lines(text)
                        else:
                            exact_file(document, text)
                            key('ctrl+End'); type_lines('Cold reopen confirmed.')
                            text += 'Cold reopen confirmed.\n'
                        key('ctrl+s'); exact_file(document, text)
                        row['saved_sha256'] = sha(document); row['saved_bytes'] = document.stat().st_size
                    elif name == 'wezterm':
                        result = folder / 'shell-result.txt'
                        xdo('type', '--clearmodifiers', '--delay', '2', "printf 'SpaceTerminal42\\n' > " + str(result))
                        key('Return'); exact_file(result, 'SpaceTerminal42\n')
                    capture = folder / (stage + '.png')
                    ImageGrab.grab(xdisplay=env['DISPLAY']).save(capture)
                    row['stages'].append(dict(stage=stage, window_title=xdo('getwindowname', window).stdout.strip(),
                                              screenshot=str(capture), screenshot_sha256=sha(capture)))
                    if name in ['lite-xl', 'pulsar', 'zed']:
                        key('ctrl+q')
                        deadline = time.monotonic() + 5
                        while time.monotonic() < deadline and window in windows():
                            time.sleep(.05)
                        row['stages'][-1]['graceful_close'] = window not in windows()
                        assert row['stages'][-1]['graceful_close'], 'editor did not close after saved Ctrl+Q'
                    stop(process); process = None
                row['status'] = ('passed-edit-save-fresh-process-reopen' if name in ['lite-xl', 'pulsar', 'zed'] else
                                 'passed-real-shell-command' if name == 'wezterm' else 'visible-window-only')
                assert sha(app) == pins[name]['sha256'], 'artifact changed during run'
            except Exception as error:
                row.update(status='failed', error=str(error))
                ImageGrab.grab(xdisplay=env['DISPLAY']).save(folder / 'failed.png')
            finally:
                if process is not None:
                    stop(process)
                save()
            print(name + ': ' + row['status'], flush=True)
        report['status'] = 'failed' if any(row['status'] == 'failed' for row in report['applications']) else 'passed-host-reference'
    except Exception as error:
        report.update(status='failed', error=str(error))
    finally:
        if server is not None:
            stop(server)
        save()
    return 0 if report['status'] == 'passed-host-reference' else 1


if __name__ == '__main__':
    raise SystemExit(main())
