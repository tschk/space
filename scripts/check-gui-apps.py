#!/usr/bin/env python3
"""Independent native calculator/editor SCI applications with real focused input."""

from boot_fixture_layout import stage_fixture
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
parser.add_argument("--build-dir", type=Path, default=Path("/tmp/space-gui-apps"))
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
sources = [
    p
    for folder in ("components", "kernel", "protocol", "fixtures/gui-apps")
    for p in (root / folder).rglob("*.in")
]
sources += [root / "boot/multiboot.asm", root / "scripts/pack-gui-sci.py", Path(__file__).resolve()]
snapshot = {
    str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sources
}
subprocess.run(
    [
        "nasm",
        "-f",
        "bin",
        str(root / "boot/multiboot.asm"),
        "-o",
        str(out / "trampoline.bin"),
    ],
    check=True,
)
kernel_source = (root / "kernel/kernel-root.in").read_text()
kernel_source = kernel_source.replace('import "../components/', 'import "' + str(root / "components") + '/')
kernel_source = kernel_source.replace('  shell(port)', '  if gui-apps-proof(port) != 1 { serial-write-cstr(port, "apps: FAIL"); serial-nl(port) }\n  shell(port)')
kernel_source = kernel_source.replace('package space.kernel', 'package space.kernel\nimport "' + str(root / 'fixtures/gui-apps/session.in') + '"', 1)
(out / "kernel-root.in").write_text(kernel_source)
for source, entry, extra, output in [
    (
        str(out / "kernel-root.in"),
        "kernel-entry",
        [
            "--emit",
            "boot",
            "--trampoline",
            str(out / "trampoline.bin"),
            "--linkage",
            "static-lib",
        ],
        "kernel.bin",
    ),
    (
        "components/input.in",
        "input-poll-entry",
        ["--emit", "sci", "--base", "0x50000000"],
        "input.sci",
    ),
    (
        "components/app-gui-calc.in",
        "client-entry",
        ["--emit", "sci", "--base", "0x48000000"],
        "client.sci",
    ),
    (
        "components/app-gui-editor.in", "client-entry",
        ["--emit", "sci", "--base", "0x49000000"], "right.sci",
    ),
]:
    with (out / (output + ".log")).open("w") as log:
        subprocess.run(
            [
                str(compiler),
                "compile",
                "--path",
                str(root / source),
                "--entry",
                entry,
                "--target",
                "native",
                "--target-triple",
                "x86_64-unknown-none",
                *extra,
                "--out",
                str(out / output),
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=180,
        )
    assert (out / output).is_file(), (out / (output + ".log")).read_text()
metadata = json.loads((out / "input.component-metadata.json").read_text())
assert (
    metadata["component"] == "space.input/Input"
    and metadata["entry"] == "input-poll-entry"
    and metadata["target"] == "x86_64-unknown-none"
)
assert [
    (c["name"], c["capability_type"], c["args"])
    for c in metadata["capabilities_required"]
] == [("serial", "DebugConsole", ["write"]), ("input", "InputDevice", ["publish"])]
input_image = (out / "input.sci").read_bytes()
assert struct.unpack_from("<Q", input_image, 8)[0] == 3
spec = importlib.util.spec_from_file_location(
    "space_spdp_pack", root / "scripts/pack-gui-sci.py"
)
module = importlib.util.module_from_spec(spec)
sys.dont_write_bytecode = True
spec.loader.exec_module(module)
client_image = module.translate(
    (out / "client.sci").read_bytes(),
    json.loads((out / "client.component-metadata.json").read_text()),
)
right_image = module.translate((out / "right.sci").read_bytes(), json.loads((out / "right.component-metadata.json").read_text()))
# Policy negatives use the actual emitted native application artifact/metadata.
raw_calc = (out / "client.sci").read_bytes()
calc_metadata = json.loads((out / "client.component-metadata.json").read_text())
for mutate in (
    lambda m: m.update(component="other/GuiCalc"),
    lambda m: m.update(entry="other-entry"),
    lambda m: m.update(capabilities_required=["invalid"]),
    lambda m: m["capabilities_required"][0].update(args=["map", "write-kernel"]),
    lambda m: m["capabilities_required"][0].update(capability_type="OtherMemory"),
    lambda m: m.update(capabilities_exported=[]),
):
    malformed = copy.deepcopy(calc_metadata)
    mutate(malformed)
    try:
        module.translate(raw_calc, malformed)
    except ValueError:
        pass
    else:
        raise AssertionError("native GUI packaging accepted a malformed declaration")
editor_metadata = json.loads((out / "right.component-metadata.json").read_text())
raw_editor = (out / "right.sci").read_bytes()
for mutate in (
    lambda m: m["capabilities_required"].pop(),
    lambda m: m["capabilities_required"][2].update(args=["write"]),
    lambda m: m.update(component="space.app.gui/GuiCalc"),
):
    malformed = copy.deepcopy(editor_metadata)
    mutate(malformed)
    malformed["capabilities_exported"] = copy.deepcopy(malformed["capabilities_required"])
    try:
        module.translate(raw_editor, malformed)
    except ValueError:
        pass
    else:
        raise AssertionError("native GUI policy silently dropped or widened storage authority")
image = bytearray((out / "kernel.bin").read_bytes())
assert len(image) < 0x1b0000, "retain kernel/injected image separation"
for physical, blob in [(0x2b0000, input_image), (0x2c0000, client_image), (0x2e0000, right_image)]:
    offset = physical - 0x100000
    assert (
        len(image) <= offset
        and len(blob) <= 0x20000
        and physical + len(blob) < 0x300000
    )
    image = bytearray(stage_fixture(image,blob,physical))
(out / "combined.bin").write_bytes(image)
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
            str(out / "combined.bin"),
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

        wait("apps: calculator and editor ready")
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
        def key(value):
            global count
            count += 1
            monitor.sendall(f"sendkey {value}\n".encode())
            wait(f"apps: rendered event {count}\n")
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
        wait(f"apps: editor focused event {count}\n")
        monitor.sendall(b"mouse_button 0\n")
        for value in ("n", "o", "t", "e", "backspace", "e", "s"):
            key(value)
        pixels("edited-notes", [("6*7", "42"), ("notes", "edit")])
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
        wait("apps: independent calculation/edit/close/survivor PASS")
        pixels("answer-13-recovered", [("6+7", "13"), None])
        assert count == 30
        assert data.count(b"SCI: domain created") == 3
        assert b"apps: FAIL" not in data
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
assert snapshot == {
    str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sources
}, "source changed during build/run; rerun for consistent evidence"
(out / "artifact-hashes.json").write_text(json.dumps({
    name: hashlib.sha256((out / name).read_bytes()).hexdigest()
    for name in ("kernel-root.in", "trampoline.bin", "kernel.bin", "input.sci", "client.sci", "right.sci", "combined.bin")
}, indent=2) + "\n")
(out / "source-hashes.json").write_text(json.dumps(snapshot, indent=2) + "\n")
assert compiler_hash == hashlib.sha256(compiler.read_bytes()).hexdigest()
print("PASS independent native SCI calculator 6*7=42 then 6*8=48, divide-zero error/recovery 6+7=13, editable text/backspace, actual keyboard/pointer focus, exact glyph pixels, close/stale refusal and survivor")
