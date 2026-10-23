#!/usr/bin/env python3
"""Launch and reopen native GUI applications from the distributable standard image."""

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--in", dest="compiler", required=True)
parser.add_argument("--build-dir", type=Path, default=Path("/tmp/space-standard-gui"))
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
out = args.build_dir.resolve()
out.mkdir(parents=True, exist_ok=True)
compiler = Path(args.compiler).resolve()
compiler_hash = hashlib.sha256(compiler.read_bytes()).hexdigest()
(out / "compiler.json").write_text(
    json.dumps(
        {
            "path": str(compiler),
            "sha256": compiler_hash,
            "version": subprocess.check_output(
                [str(compiler), "--version"], text=True
            ).strip(),
        },
        indent=2,
    )
    + "\n"
)
sources = [p for folder in ("components", "kernel", "protocol") for p in (root / folder).rglob("*.in")]
sources += [root / "boot/multiboot.asm", root / "scripts/build-images.sh", root / "scripts/pack-gui-sci.py", root / "scripts/pack-spdp-sci.py", Path(__file__).resolve()]
snapshot = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
import os
images = out / "images"
environment = dict(os.environ, IN=str(compiler), BUILD_DIR=str(images))
with (out / "build.log").open("w") as log:
    subprocess.run(["bash", str(root / "scripts/build-images.sh"), "--variant", "all"], env=environment, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)

def image_kinds(path):
    blob = path.read_bytes()
    table = struct.unpack_from("<Q", blob, 0xF00)[0] - 0x100000
    magic, count = struct.unpack_from("<QQ", blob, table)
    assert magic == 0x5350414345424F4F
    result = {}
    for i in range(count):
        kind, physical, size, reserved = struct.unpack_from("<QQQQ", blob, table + 16 + i * 32)
        assert kind not in result and reserved == 0 and physical + size < 0x300000
        result[kind] = blob[physical - 0x100000:physical - 0x100000 + size]
    return result

standard, minimal = image_kinds(images / "standard.bin"), image_kinds(images / "minimal.bin")
assert all(kind in standard and kind not in minimal for kind in (20, 21, 22))
assert 3 not in standard, "on-demand GUI seat must not auto-start as boot input"
assert struct.unpack_from("<Q", standard[20], 8)[0] == 20
assert struct.unpack_from("<Q", standard[21], 8)[0] == 52
assert struct.unpack_from("<Q", standard[22], 8)[0] == 3
serial_path, monitor_path = out / "serial.sock", out / "monitor.sock"
for path in (serial_path, monitor_path):
    if path.exists():
        path.unlink()


def connect(path):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        channel = socket.socket(socket.AF_UNIX)
        try:
            channel.connect(str(path))
            channel.settimeout(0.2)
            return channel
        except OSError:
            channel.close()
            time.sleep(0.05)
    raise AssertionError(f"no QEMU socket: {path}")


with (out / "qemu.log").open("w") as log:
    qemu = subprocess.Popen(
        [
            "qemu-system-x86_64",
            "-kernel",
            str(images / "standard.bin"),
            "-m",
            "256M",
            "-no-reboot",
            "-vga",
            "std",
            "-display",
            "none",
            "-serial",
            f"unix:{serial_path},server=on,wait=on",
            "-monitor",
            f"unix:{monitor_path},server=on,wait=off",
        ],
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    serial = monitor = None
    data = bytearray()
    try:
        serial, monitor = connect(serial_path), connect(monitor_path)

        def wait(marker, start=0):
            deadline = time.monotonic() + 30
            while marker.encode() not in data[start:] and time.monotonic() < deadline:
                try:
                    chunk = serial.recv(65536)
                    if not chunk:
                        raise AssertionError("serial closed")
                    data.extend(chunk)
                except socket.timeout:
                    pass
            (out / "serial.log").write_bytes(data)
            assert marker.encode() in data[start:], data[-3000:]

        wait("space interactive shell")
        boot_domains = data.count(b"SCI: domain created")
        serial.sendall(b"gui apps\n")
        ready = "gui: calculator left, text editor right; click or Tab to focus, Escape closes focused app"
        wait(ready)
        import re
        glyphs = {}
        for match in re.finditer(r"fb-font-set\(([^)]+)\)", (root / "components/font.in").read_text()):
            try:
                values = [int(value.strip(), 0) for value in match.group(1).split(",")]
            except ValueError:
                continue
            if len(values) == 9:
                glyphs[values[0]] = values[1:]

        def pixels(name, texts):
            path = out / f"{name}.ppm"
            path.unlink(missing_ok=True)
            monitor.sendall(f"screendump {path}\n".encode())
            deadline = time.monotonic() + 5
            while (not path.exists() or path.stat().st_size < 1920 * 1080 * 3 + 17) and time.monotonic() < deadline:
                time.sleep(0.05)
            header = path.read_bytes().split(b"\n", 3)
            assert header[:3] == [b"P6", b"1920 1080", b"255"]
            rgb = header[3]
            for slot, text in enumerate(texts):
                left = 40 + slot * 120
                for y in range(79, 97):
                    for x in range(left - 1, left + 65):
                        color = bytes((0, 0, 128))
                        if 80 <= y < 96 and left <= x < left + 64 and text is not None:
                            color = bytes((32, 32, 32))
                            row, column = y - 80, x - left
                            line = text[row // 8].ljust(8)
                            bits = glyphs.get(ord(line[column // 8]), [0] * 8)[row % 8]
                            if bits & (128 >> (column % 8)):
                                color = bytes((255, 255, 255))
                        actual = rgb[(y * 1920 + x) * 3: (y * 1920 + x) * 3 + 3]
                        assert actual == color, (name, slot, x, y, actual, color)

        count = 0
        codes = {"ret": 10, "backspace": 8, "shift-8": 42, "shift-equal": 43, "slash": 47, "esc": 27, "tab": 9, "ctrl-s": 19}
        def key(value):
            global count
            count += 1
            start = len(data)
            monitor.sendall(f"sendkey {value}\n".encode())
            code = codes[value] if value in codes else ord(value)
            marker = f"gui: app rendered key {code}\n"
            if value == "esc": marker = "gui: focused app closed, retired token refused"
            if value == "tab": marker = "gui: focus "
            wait(marker, start)
            time.sleep(0.12)

        pixels("initial", [("", ""), ("", "edit")])
        for value in ("6", "shift-8", "7", "ret"):
            key(value)
        pixels("answer-42", [("6*7", "42"), ("", "edit")])
        for _ in range(25):
            monitor.sendall(b"mouse_move -100 -100\n")
            time.sleep(0.025)
        for dx, dy in [(100, 80), (70, 8)]:
            monitor.sendall(f"mouse_move {dx} {dy}\n".encode())
            time.sleep(0.1)
        monitor.sendall(b"mouse_button 1\n")
        count += 1
        wait("gui: pointer focused app ")
        monitor.sendall(b"mouse_button 0\n")
        for value in ("n", "o", "t", "e", "backspace", "e", "s"):
            key(value)
        pixels("edited-notes", [("6*7", "42"), ("notes", "edit")])
        key("ctrl-s")
        pixels("save-without-nvme-refused", [("6*7", "42"), ("notes", "no disk")])
        key("esc")
        pixels("editor-closed", [("6*7", "42"), None])
        for value in ("backspace", "8", "ret"):
            key(value)
        pixels("answer-48-survivor", [("6*8", "48"), None])
        for value in ("backspace", "backspace", "backspace", "1", "slash", "0", "ret"):
            key(value)
        pixels("divide-zero-refused", [("1/0", "err"), None])
        for value in ("backspace", "backspace", "backspace", "6", "shift-equal", "7", "ret"):
            key(value)
        pixels("answer-13-recovered", [("6+7", "13"), None])
        assert count == 31
        assert b"gui: both applications closed" not in data
        key("esc")
        wait("gui: both applications closed; stable session counters; returning to shell")
        wait("space> ")
        pixels("both-closed", [None, None])
        # Same standard image, fresh tokens and clients after logical retirement.
        start = len(data)
        serial.sendall(b"gui apps\n")
        wait(ready, start)
        pixels("reopened", [("", ""), ("", "edit")])
        key("tab")
        key("a")
        pixels("reopened-editor", [("", ""), ("a", "edit")])
        key("esc")
        key("esc")
        wait("gui: both applications closed; stable session counters; returning to shell", start)
        pixels("reopened-both-closed", [None, None])
        assert data.count(b"SCI: domain created") == boot_domains + 6
        # Existing ordinary CLI application still works after both GUI sessions.
        start = len(data)
        serial.sendall(b"runapp calc\n")
        wait("calc: integer REPL", start)
        serial.sendall(b"2+3*4\n")
        wait("calc: 2+3*4 = 14", start)
        serial.sendall(b"q\n")
        wait("runapp: app-calc returned", start)
        assert data.count(b"gui: both applications closed;") == 2
        assert b"gui: native session unavailable or failed" not in data
    finally:
        (out / "serial.log").write_bytes(data)
        if serial:
            serial.close()
        if monitor:
            monitor.close()
        qemu.terminate()
        try:
            qemu.wait(timeout=3)
        except subprocess.TimeoutExpired:
            qemu.kill()
            qemu.wait()
# Minimal contains no optional GUI imports/artifacts and refuses the same command.
minimal_path = out / "minimal.sock"
minimal_path.unlink(missing_ok=True)
with (out / "minimal-qemu.log").open("w") as log:
    process = subprocess.Popen(["qemu-system-x86_64", "-kernel", str(images / "minimal.bin"), "-m", "256M", "-display", "none", "-no-reboot", "-serial", f"unix:{minimal_path},server=on,wait=on", "-monitor", "none"], stdout=log, stderr=subprocess.STDOUT)
    channel = None
    minimal_data = bytearray()
    try:
        channel = connect(minimal_path)
        def minimal_wait(marker):
            deadline = time.monotonic() + 30
            while marker not in minimal_data and time.monotonic() < deadline:
                try: minimal_data.extend(channel.recv(65536))
                except socket.timeout: pass
            assert marker in minimal_data, minimal_data[-2000:]
        minimal_wait(b"space interactive shell")
        channel.sendall(b"gui apps\n")
        minimal_wait(b"unavailable in minimal image")
        assert b"SCI: loading gui-" not in minimal_data
    finally:
        (out / "minimal-serial.log").write_bytes(minimal_data)
        if channel: channel.close()
        process.terminate()
        try: process.wait(timeout=3)
        except subprocess.TimeoutExpired: process.kill(); process.wait()
assert snapshot == {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}, "source changed during build/run"
(out / "source-hashes.json").write_text(json.dumps(snapshot, indent=2) + "\n")
(out / "image-hashes.json").write_text(json.dumps({name: hashlib.sha256((images / name).read_bytes()).hexdigest() for name in ("standard.bin", "minimal.bin")}, indent=2) + "\n")
assert compiler_hash == hashlib.sha256(compiler.read_bytes()).hexdigest()
print("PASS distributable standard image: real native calculator/editor launch, keyboard/pointer/Tab focus, exact glyph pixels, calculation/error recovery/edit/close/reopen; minimal refuses optionalGUI")
