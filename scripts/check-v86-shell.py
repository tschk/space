#!/usr/bin/env python3
"""Boot the website's actual i386 image and exercise persistent shell state."""

import argparse
import selectors
import subprocess
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--kernel", type=Path,
        default=Path(__file__).resolve().parents[1]
        / "website/public/v86/space-multiboot.bin",
    )
    args = parser.parse_args()
    kernel = args.kernel.resolve(strict=True)
    with subprocess.Popen(
        ["qemu-system-i386", "-kernel", str(kernel), "-m", "256M",
         "-display", "none", "-monitor", "none", "-serial", "stdio",
         "-no-reboot"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        bufsize=0,
    ) as process:
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)

                def prompt():
                    output = bytearray()
                    deadline = time.monotonic() + 15
                    while time.monotonic() < deadline:
                        if not selector.select(timeout=0.1):
                            continue
                        chunk = process.stdout.read(4096)
                        if not chunk:
                            break
                        output.extend(chunk)
                        if output.endswith(b"space$ "):
                            return output.decode("utf-8", errors="replace")
                    raise AssertionError(f"No shell prompt: {output!r}")

                def command(text, expected):
                    process.stdin.write(text.encode() + b"\r")
                    output = prompt()
                    assert expected in output, (text, expected, output)
                    print(output, end="", flush=True)

                boot = prompt()
                assert "Space v0.1.0 (32-bit v86)" in boot, boot
                print(boot, end="", flush=True)
                command("echo first", "\r\nfirst\r\n")
                command("echo second", "\r\nsecond\r\n")
                command("history", "1  echo first\r\n2  echo second\r\n3  history")
                command("uname", "Space v0.1.0 (v86 32-bit .in kernel)")
                print("\nPASS: website i386 shell boot and writable command history")
        finally:
            process.terminate()
            process.wait(timeout=5)


if __name__ == "__main__":
    main()
