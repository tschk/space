#!/usr/bin/env python3
"""Exercise real Helium and Firefox on host Linux; no Space execution credit.

Helium uses Playwright to verify input, JavaScript, exact canvas scanout and
localStorage across a full process restart. Firefox's narrower CLI scenario
renders the local page to an actual screenshot; it does not claim input or
persistence coverage. The fixture server listens only on loopback.
"""
import argparse
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_canvas_capture(path):
    from PIL import Image
    with Image.open(path) as image:
        assert image.size == (1200, 850)
        rgb = image.convert('RGB')
        assert rgb.getpixel((10, 10)) == (17, 23, 34)
        colors = rgb.getcolors(1200 * 850)
        for expected in [(154, 230, 205), (120, 152, 255)]:
            assert sum(count for count, color in colors if color == expected) > 19000, str(expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--browser', choices=['helium', 'firefox'], default='helium')
    args = parser.parse_args()
    args.out = args.out.resolve(); args.out.mkdir(parents=True, exist_ok=False)
    pins = json.loads((ROOT / 'fixtures/applications/desktop-corpus.json').read_text())['apps']
    pin = next(app for app in pins if app['id'] == args.browser)
    app = next(app for app in json.loads(args.index.read_text())['apps'] if app['id'] == args.browser)
    executable = Path(app['binary']).resolve()
    fixture = ROOT / 'fixtures/applications/browser-workload.html'
    shutil.copyfile(fixture, args.out / fixture.name)
    report = dict(scope=__doc__, status='running', browser=args.browser,
                  application_sha256=sha(executable), fixture_sha256=sha(fixture),
                  harness_sha256=sha(Path(__file__).resolve()), original_space_entries=0)
    report['pillow_version'] = importlib.metadata.version('Pillow')
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(args.out)))
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    origin = 'http://127.0.0.1:' + str(server.server_port) + '/'
    url = origin + fixture.name
    try:
        assert report['application_sha256'] == pin['sha256'] and executable.stat().st_size == pin['size_bytes']
        if args.browser == 'helium':
            from playwright.sync_api import sync_playwright
            report['playwright_version'] = importlib.metadata.version('playwright')
            text = 'Project notes\nReal browser editing, JavaScript, canvas and local storage.\n'
            options = dict(executable_path=str(executable), headless=True,
                           args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--disable-background-networking'],
                           viewport={'width': 1200, 'height': 850})
            report['host_launch_options'] = options
            with sync_playwright() as playwright:
                for stage in ['edit', 'reopen']:
                    context = playwright.chromium.launch_persistent_context(str(args.out / 'profile'), **options)
                    try:
                        context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(origin) else route.abort())
                        page = context.pages[0]; page.goto(url)
                        if stage == 'edit':
                            page.locator('#editor').fill(text)
                            page.locator('#save').click()
                            assert page.locator('#status').inner_text() == 'Saved ' + str(len(text)) + ' characters'
                        actual = page.locator('#editor').input_value()
                        report.setdefault('stages', []).append(dict(stage=stage, input_text=actual,
                            stored_text=page.evaluate('localStorage.getItem("space-reference")')))
                        assert actual == text, stage + ': ' + repr(actual)
                        reads = page.evaluate('[10,210].map(x=>Array.from(document.querySelector("canvas").getContext("2d").getImageData(x,10,1,1).data))')
                        report['stages'][-1]['canvas_readback'] = reads
                        # Helium deliberately adds canvas readback noise as a
                        # privacy measure. Record that API result; independently
                        # check the actual rendered colors in the screenshot.
                        page.screenshot(path=str(args.out / (stage + '.png')))
                        verify_canvas_capture(args.out / (stage + '.png'))
                        report['browser_version'] = context.browser.version
                    finally:
                        context.close()
            report.update(status='passed', typed_characters=len(text), verified=['input and button', 'JavaScript', 'exact colors in both canvas scanout regions', 'localStorage after full browser restart'])
        else:
            command = [str(executable), '--headless', '--no-remote', '--profile', str(args.out / 'profile'),
                       '--window-size', '1200,850', '--screenshot', str(args.out / 'render.png'), url]
            (args.out / 'profile').mkdir()
            env = dict(os.environ); env['MOZ_DISABLE_CONTENT_SANDBOX'] = '1'
            report['host_command'] = command
            with (args.out / 'browser.log').open('w') as log:
                subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=60)
            verify_canvas_capture(args.out / 'render.png')
            report.update(status='passed-partial-reference', verified=['actual Gecko page render', 'both canvas regions in actual screenshot'], not_tested=['keyboard/pointer', 'storage restart'])
        assert sha(executable) == pin['sha256'] and sha(fixture) == report['fixture_sha256']
        report['screenshots'] = {path.name: sha(path) for path in args.out.glob('*.png')}
    except Exception as error:
        report.update(status='failed', error=str(error))
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
        (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(report['status'].upper() + ': host ' + args.browser + '; no Space execution')
    return 0 if report['status'].startswith('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
