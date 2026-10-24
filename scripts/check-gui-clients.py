#!/usr/bin/env python3
"""Two retained SCI clients: focused actual keyboard/pointer input and owned pixels."""

from boot_fixture_layout import stage_fixture
import argparse
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
parser.add_argument("--build-dir", type=Path, default=Path("/tmp/space-gui-clients"))
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
    for folder in ("components", "kernel", "protocol", "fixtures/gui-clients")
    for p in (root / folder).rglob("*.in")
]
sources += [root / "boot/multiboot.asm", root / "scripts/pack-spdp-sci.py", Path(__file__).resolve()]
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
kernel_source = kernel_source.replace('  shell(port)', '  if gui-session-proof(port) != 1 { serial-write-cstr(port, "gui: FAIL"); serial-nl(port) }\n  shell(port)')
kernel_source = kernel_source.replace('package space.kernel', 'package space.kernel\nimport "' + str(root / 'fixtures/gui-clients/session.in') + '"', 1)
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
        "fixtures/gui-clients/client.in",
        "client-entry",
        ["--emit", "sci", "--base", "0x48000000"],
        "client.sci",
    ),
    (
        "fixtures/gui-clients/client.in", "client-entry",
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
    "space_spdp_pack", root / "scripts/pack-spdp-sci.py"
)
module = importlib.util.module_from_spec(spec)
sys.dont_write_bytecode = True
spec.loader.exec_module(module)
client_image = module.translate(
    (out / "client.sci").read_bytes(),
    json.loads((out / "client.component-metadata.json").read_text()),
)
right_image = module.translate((out / "right.sci").read_bytes(), json.loads((out / "right.component-metadata.json").read_text()))
image = bytearray((out / "kernel.bin").read_bytes())
assert len(image) < 0x1d0000, "retain kernel/injected image separation"
for physical, blob in [(0x2d0000, input_image), (0x2e0000, client_image), (0x2f0000, right_image)]:
    offset = physical - 0x100000
    assert (
        len(image) <= offset
        and len(blob) <= 0x10000
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

        wait("gui: two retained clients ready")

        def pixels(name, phases):
            path = out / f"{name}.ppm"
            path.unlink(missing_ok=True)
            monitor.sendall(f"screendump {path}\n".encode())
            deadline = time.monotonic() + 5
            while (not path.exists() or path.stat().st_size < 1920 * 1080 * 3 + 17) and time.monotonic() < deadline:
                time.sleep(0.05)
            header = path.read_bytes().split(b"\n", 3)
            assert header[:3] == [b"P6", b"1920 1080", b"255"]
            rgb = header[3]
            for slot, phase in enumerate(phases):
                left = 40 + slot * 120
                for y in range(79, 97):
                    for x in range(left - 1, left + 65):
                        color = bytes((0, 0, 128))
                        if 80 <= y < 96 and left <= x < left + 64 and phase >= 0:
                            color = bytes((128, 128, 128))
                            if phase == 1: color = bytes((255, 0, 0)) if x < left + 20 else bytes((0, 255, 0))
                            if phase == 2: color = bytes((0, 0, 255)) if x < left + 20 else bytes((255, 255, 0))
                        assert rgb[(y * 1920 + x) * 3: (y * 1920 + x) * 3 + 3] == color, (name, slot, x, y, phase)

        pixels("initial", [0, 0])
        monitor.sendall(b"sendkey a\n")
        wait("gui: key rendered 1")
        pixels("left-key", [1, 0])
        # Clamp the actual PS/2 device at top-left, then move in bounded packets.
        for _ in range(25):
            monitor.sendall(b"mouse_move -100 -100\n")
            time.sleep(0.025)
        for dx, dy in [(100, 80), (70, 8)]:
            monitor.sendall(f"mouse_move {dx} {dy}\n".encode())
            time.sleep(0.1)
        monitor.sendall(b"mouse_button 1\n")
        wait("gui: pointer focused right")
        monitor.sendall(b"mouse_button 0\n")
        pixels("right-pointer", [1, 1])
        monitor.sendall(b"sendkey b\n")
        wait("gui: key rendered 3")
        pixels("right-key", [1, 2])
        monitor.sendall(b"sendkey esc\n")
        wait("gui: right closed, stale token refused")
        pixels("right-closed", [1, -1])
        monitor.sendall(b"sendkey b\n")
        wait("gui: surviving left rendered, stable counters PASS")
        pixels("survivor", [2, -1])
        assert data.count(b"SCI: domain created") == 3
        assert b"gui: FAIL" not in data
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
print("PASS two independently executing retained SCI clients, keyboard/pointer focus, owned pixels, close/stale refusal/survivor and stable counters")
