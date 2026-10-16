#!/usr/bin/env python3
"""Two fixed SCI endpoints: actual PS/2 keyboard -> client pixels, synchronously."""

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
parser.add_argument("--build-dir", type=Path, default=Path("/tmp/space-spdp-input"))
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
    for folder in ("components", "kernel", "protocol", "fixtures/spdp-input")
    for p in (root / folder).rglob("*.in")
]
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
for source, entry, extra, output in [
    (
        "kernel/kernel-root.in",
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
        "fixtures/spdp-input/client.in",
        "client-entry",
        ["--emit", "sci", "--base", "0x48000000"],
        "client.sci",
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
image = bytearray((out / "kernel.bin").read_bytes())
for physical, blob in [(0x280000, input_image), (0x290000, client_image)]:
    offset = physical - 0x100000
    assert (
        len(image) <= offset
        and len(blob) <= 0x10000
        and physical + len(blob) < 0x300000
    )
    image += bytes(offset - len(image)) + blob
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

        wait("space interactive shell")
        serial.sendall(b"input app\n")
        wait("seat: two SCI endpoints ready")

        def pixels(phase):
            path = out / f"{phase}.ppm"
            monitor.sendall(f"screendump {path}\n".encode())
            deadline = time.monotonic() + 5
            while (
                not path.exists() or path.stat().st_size < 1920 * 1080 * 3 + 17
            ) and time.monotonic() < deadline:
                time.sleep(0.05)
            header = path.read_bytes().split(b"\n", 3)
            assert header[:3] == [b"P6", b"1920 1080", b"255"]
            data = header[3]
            for y in range(80, 96):
                for x in range(40, 104):
                    color = bytes((128, 128, 128))
                    if phase == "a":
                        color = bytes((255, 0, 0)) if x < 60 else bytes((0, 255, 0))
                    if phase == "b":
                        color = bytes((0, 0, 255)) if x < 60 else bytes((255, 255, 0))
                    assert data[(y * 1920 + x) * 3 : (y * 1920 + x) * 3 + 3] == color, (
                        phase,
                        x,
                        y,
                    )
            for x, y in [(39, 80), (104, 80), (40, 79), (40, 96)]:
                assert data[(y * 1920 + x) * 3 : (y * 1920 + x) * 3 + 3] == bytes(
                    (0, 0, 128)
                ), (phase, "bounds", x, y)

        pixels("initial")
        for key, code in [("a", 97), ("b", 98)]:
            start = len(data)
            monitor.sendall(f"sendkey {key}\n".encode())
            wait(f"seat: client pixels updated for key {code}\n", start)
            # Key release/empty polls must not deliver again; app sequence rejects replay.
            time.sleep(0.3)
            pixels(key)
        start = len(data)
        monitor.sendall(b"sendkey esc\n")
        wait("seat: exactly two deliveries, stable endpoints/counters PASS", start)
        assert data.count(b"seat: client pixels updated for key 97\n") == 1
        assert data.count(b"seat: client pixels updated for key 98\n") == 1
        assert (
            data.count(b"SCI: loading seat-input") == 1
            and data.count(b"SCI: loading seat-client") == 1
        )
        assert data.count(b"SCI: domain created") == 2
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
}
assert compiler_hash == hashlib.sha256(compiler.read_bytes()).hexdigest()
(out / "source-hashes.json").write_text(json.dumps(snapshot, indent=2) + "\n")
print(
    "PASS actual PS/2 a/b -> two distinct SCI-client pixel patterns exactly once; two stable endpoints and allocation counters"
)
