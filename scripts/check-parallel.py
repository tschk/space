#!/usr/bin/env python3
"""Multi-threaded parallel verification runner for Space.

Executes host/JIT/native model & contract suites concurrently across a worker
thread pool, followed by isolated parallel QEMU verification waves.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def resolve_in(explicit: str | None) -> str:
    if explicit and os.path.isfile(explicit) and os.access(explicit, os.X_OK):
        return explicit
    env_in = os.environ.get("IN")
    if env_in and os.path.isfile(env_in) and os.access(env_in, os.X_OK):
        return env_in
    candidates = [
        "/Users/undivisible/.codex/worktrees/compiler-loop-continuation/inauguration/in-cli/target/release/in",
        str(ROOT.parent / "inauguration/in-cli/target/release/in"),
        os.path.expanduser("~/.cargo/bin/in"),
    ]
    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    found = shutil.which("in")
    if found:
        return found
    raise RuntimeError("Could not locate `in` compiler binary")


def run_task(name: str, cmd: list[str], env_overrides: dict[str, str]) -> tuple[str, bool, float, str]:
    t0 = time.monotonic()
    env = os.environ.copy()
    env.update(env_overrides)
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    elapsed = time.monotonic() - t0
    ok = proc.returncode == 0
    return name, ok, elapsed, proc.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Space verification suites in parallel threads")
    parser.add_argument("--in", dest="in_bin", default=None, help="Path to `in` compiler binary")
    parser.add_argument("--workers", type=int, default=12, help="Worker thread count for host checks")
    parser.add_argument("--qemu-workers", type=int, default=4, help="Worker thread count for QEMU checks")
    parser.add_argument("--skip-qemu", action="store_true", help="Run only fast host/JIT/contract checks")
    args = parser.parse_args()

    in_bin = resolve_in(args.in_bin)
    inaug_dir = os.environ.get(
        "INAUGURATION_DIR",
        str(Path(in_bin).resolve().parent.parent.parent.parent),
    )
    base_env = {
        "IN": in_bin,
        "INAUGURATION_DIR": inaug_dir,
        "PATH": f"/opt/homebrew/bin:{os.path.expanduser('~/.cargo/bin')}:{os.environ.get('PATH', '')}",
    }

    run_root = Path(tempfile.mkdtemp(prefix="sv-", dir="/tmp"))
    t_start = time.monotonic()
    try:
        for sub in ("sci-contract", "time-comp", "mmap", "boot-data", "local-stream", "ps2-mouse"):
            (run_root / sub).mkdir(parents=True, exist_ok=True)

        host_tasks: list[tuple[str, list[str], dict[str, str]]] = [
            ("architecture-boundaries", ["bash", "scripts/check-architecture-boundaries.sh"], {}),
            ("kernel-contracts", ["bash", "scripts/check-kernel-contracts.sh"], {}),
            ("personality-abi", ["bash", "scripts/check-personality-abi.sh"], {}),
            ("process-vfs", ["bash", "scripts/check-process-vfs.sh"], {}),
            ("runtime-honesty", ["bash", "scripts/check-runtime-honesty.sh"], {}),
            ("spdp-protocol", ["bash", "scripts/check-spdp-protocol.sh"], {}),
            ("image-formats", ["bash", "scripts/check-image-formats.sh"], {}),
            ("sparkfs-init", ["bash", "scripts/check-sparkfs-init.sh"], {}),
            ("volume-preservation", ["bash", "scripts/check-volume-preservation.sh"], {}),
            ("sci-contract", ["bash", "scripts/check-sci-contract.sh"], {"BUILD_DIR": str(run_root / "sci-contract")}),
            ("time-component", ["bash", "scripts/check-time-component.sh"], {"BUILD_DIR": str(run_root / "time-comp")}),
            ("channel-capacity", ["python3", "scripts/check-channel-capacity.py", "--in", in_bin], {}),
            ("darwin-pipe-lifetime", ["python3", "scripts/check-darwin-pipe-lifetime.py", "--in", in_bin], {}),
            ("display-allocation", ["python3", "scripts/check-display-allocation.py", "--in", in_bin], {}),
            ("posix-wait-status", ["python3", "scripts/check-posix-wait-status.py", "--in", in_bin], {}),
            ("sci-resume", ["python3", "scripts/check-sci-resume.py", "--in", in_bin], {}),
            ("sci-seat", ["python3", "scripts/check-sci-seat.py", "--in", in_bin], {}),
            ("spdp-lifetime", ["python3", "scripts/check-spdp-lifetime.py", "--in", in_bin], {}),
            ("spdp-page-frames", ["python3", "scripts/check-spdp-page-frames.py", "--in", in_bin], {}),
            ("vfs-shared-offset", ["python3", "scripts/check-vfs-shared-offset.py", "--in", in_bin], {}),
            ("windows-wait-result", ["python3", "scripts/check-windows-wait-result.py", "--in", in_bin], {}),
            ("mmap-lifetime", ["python3", "scripts/check-mmap-lifetime.py", "--in", in_bin, "--output-dir", str(run_root / "mmap")], {}),
            ("boot-data-reservation", ["python3", "scripts/check-boot-data-reservation.py", "--in", in_bin, "--out", str(run_root / "boot-data")], {}),
            ("commandbar", ["python3", "scripts/check-commandbar.py", "--in", in_bin, "--out", str(run_root / "commandbar")], {}),
            ("local-stream", ["python3", "scripts/check-local-stream.py", "--in", in_bin, "--build-dir", str(run_root / "local-stream")], {}),
            ("ps2-mouse-init", ["python3", "scripts/check-ps2-mouse-init.py", "--in", in_bin, "--out", str(run_root / "ps2-mouse")], {}),
            ("ttf-font-engine", ["python3", "scripts/check-ttf-font.py", "--in", in_bin], {}),
        ]

        print(f"=== Wave 1: Running {len(host_tasks)} Host/JIT/Contract Suites across {args.workers} parallel threads ===")
        failures = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = [
                pool.submit(run_task, name, cmd, {**base_env, **extra})
                for name, cmd, extra in host_tasks
            ]
            for fut in concurrent.futures.as_completed(futs):
                name, ok, elapsed, out = fut.result()
                status = "PASS" if ok else "FAIL"
                print(f"  [{status}] {name:<24} ({elapsed:.2f}s)")
                if not ok:
                    failures += 1
                    print(out)

        if failures > 0:
            print(f"Wave 1 failed ({failures} suite(s))")
            return 1

        if not args.skip_qemu:
            kernel_bin = str(run_root / "sci-contract" / "kernel.bin")
            for sub in ("smoke", "visual", "damage", "darwin", "win", "macho", "out-text", "launcher"):
                (run_root / sub).mkdir(parents=True, exist_ok=True)

            qemu_tasks: list[tuple[str, list[str], dict[str, str]]] = [
                ("qemu-smoke", ["bash", "scripts/check-qemu-smoke.sh"], {"BUILD_DIR": str(run_root / "smoke"), "KERNEL_BIN": kernel_bin}),
                ("desktop-visual", ["bash", "scripts/check-desktop-visual.sh"], {"BUILD_DIR": str(run_root / "visual")}),
                ("desktop-damage", ["bash", "scripts/check-desktop-damage.sh"], {"BUILD_DIR": str(run_root / "damage"), "KERNEL_BIN": kernel_bin}),
                ("darwin-personality", ["bash", "scripts/check-darwin-personality.sh"], {"BUILD_DIR": str(run_root / "darwin")}),
                ("windows-personality", ["bash", "scripts/check-windows-personality.sh"], {"BUILD_DIR": str(run_root / "win")}),
                ("darwin-macho", ["bash", "scripts/check-darwin-macho.sh"], {"BUILD_DIR": str(run_root / "macho")}),
                ("display-output-text", ["python3", "scripts/check-display-output-text.py", "--in", in_bin, "--out", str(run_root / "out-text")], {}),
                ("desktop-launcher", ["python3", "scripts/check-desktop-launcher.py", "--in", in_bin, "--build-dir", str(run_root / "launcher")], {}),
            ]

            print(f"\n=== Wave 2: Running {len(qemu_tasks)} QEMU Integration Suites across {args.qemu_workers} parallel threads ===")
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.qemu_workers) as pool:
                futs = [
                    pool.submit(run_task, name, cmd, {**base_env, **extra})
                    for name, cmd, extra in qemu_tasks
                ]
                for fut in concurrent.futures.as_completed(futs):
                    name, ok, elapsed, out = fut.result()
                    status = "PASS" if ok else "FAIL"
                    print(f"  [{status}] {name:<24} ({elapsed:.2f}s)")
                    if not ok:
                        failures += 1
                        print(out)

        total_elapsed = time.monotonic() - t_start
        if failures > 0:
            print(f"\nFAIL: {failures} suite(s) failed in {total_elapsed:.2f}s")
            return 1
        print(f"\nPASS: all parallel verification suites green in {total_elapsed:.2f}s")
        return 0
    finally:
        shutil.rmtree(run_root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
