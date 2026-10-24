#!/usr/bin/env python3
"""Run executable personality/desktop gates and retain reproducible evidence.

A passing contract check is not guest execution. Reports distinguish source,
model, hardware guest and GUI evidence; a missing dependency is a failure.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    result = subprocess.run(["git", "-C", str(ROOT), *args],
                            capture_output=True, text=True, check=True)
    return result.stdout.strip()


def gates(compiler, output):
    def model(name):
        return [sys.executable, f"scripts/{name}.py", "--in", compiler]

    return [
        ("abi", "contracts", "source-contract", ["bash", "scripts/check-personality-abi.sh"]),
        ("architecture", "contracts", "source-contract", ["bash", "scripts/check-architecture-boundaries.sh"]),
        ("shared-offset", "model", "isolated-functions", model("check-vfs-shared-offset")),
        ("native-hex-format", "model", "isolated-app-function", model("check-hd-byte")),
        ("darwin-pipe", "model", "isolated-functions", model("check-darwin-pipe-lifetime")),
        ("local-stream", "model", "isolated-functions", model("check-local-stream") + ["--build-dir", str(output / "local-stream")]),
        ("posix-wait", "model", "isolated-functions", model("check-posix-wait-status")),
        ("windows-wait", "model", "isolated-functions", model("check-windows-wait-result")),
        ("mapping-lifetime", "model", "isolated-functions", model("check-mmap-lifetime")),
        ("command-model-jit", "model", "isolated-functions-jit", model("check-commandbar") + ["--target", "jit", "--out", str(output / "command-jit")]),
        ("command-model-native", "model", "isolated-functions-native", model("check-commandbar") + ["--target", "native", "--out", str(output / "command-native")]),
        ("runtime-failure", "runtime", "native-abort-and-user-fault-recovery", model("check-runtime-failure") + ["--out", str(output / "runtime-failure-evidence")]),
        ("user-syscall", "runtime", "strict-cpl3-resumable-syscall", model("check-user-syscall") + ["--out", str(output / "user-syscall-evidence")]),
        ("protected-darwin", "runtime", "private-cpl3-macho-imports-and-budget", model("check-darwin-protected") + ["--imports", "--out", str(output / "protected-darwin-evidence")]),
        ("protected-windows", "runtime", "private-cpl3-pe-imports-and-budget", model("check-windows-protected") + ["--out", str(output / "protected-windows-evidence")]),
        ("user-budget", "runtime", "actual-pit-cpl3-timeout", model("check-user-budget") + ["--out", str(output / "user-budget-evidence")]),
        ("linux-darwin-windows-guests", "runtime", "trusted-cpl0-guests", ["bash", "scripts/check-foreign-syscalls.sh"]),
        ("darwin-loader", "runtime", "trusted-cpl0-guest", ["bash", "scripts/check-darwin-macho.sh"]),
        ("darwin-translator", "runtime", "kernel-linked-translator", ["bash", "scripts/check-darwin-personality.sh"]),
        ("windows-translator", "runtime", "kernel-linked-translator", ["bash", "scripts/check-windows-personality.sh"]),
        ("desktop-interaction", "gui", "qemu-keyboard-pointer-pixels", model("check-desktop-launcher") + ["--build-dir", str(output / "desktop")]),
        ("sci-pixels", "gui", "sci-shared-pixels", model("check-spdp-sci") + ["--build-dir", str(output / "spdp")]),
        ("sci-keyboard", "gui", "bounded-sci-keyboard-pixels", model("check-spdp-input") + ["--build-dir", str(output / "input")]),
        ("independent-sci-clients", "gui", "trusted-cpl0-independent-input-pixels", model("check-gui-clients") + ["--build-dir", str(output / "gui-clients")]),
        ("native-gui-apps", "gui", "trusted-cpl0-native-gui-calculator-editor", model("check-gui-apps") + ["--build-dir", str(output / "gui-apps")]),
        ("sci-seat-denial", "gui", "isolated-functions", model("check-sci-seat")),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", choices=("contracts", "model", "runtime", "gui", "all"), default="all")
    parser.add_argument("--in", dest="compiler", type=Path)
    parser.add_argument("--out", type=Path, required=True,
                        help="New or empty directory for logs, artifacts and report.json")
    args = parser.parse_args()
    output = args.out.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error("--out must be new or empty; retain earlier evidence in its own directory")
    if args.tier != "contracts" and (args.compiler is None or not args.compiler.is_file()):
        parser.error("--in must name an explicit source-built compiler for this tier")
    compiler = str(args.compiler.resolve()) if args.compiler else ""
    output.mkdir(parents=True, exist_ok=True)
    paths = git("ls-files", "--cached", "--others", "--exclude-standard", "--",
                "components", "kernel", "boot", "fixtures", "protocol", "scripts").splitlines()
    hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
              for path in sorted(set(paths)) if (ROOT / path).is_file()}
    report = {
        "schema_version": 1,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "space_commit": git("rev-parse", "HEAD"),
        "space_dirty": bool(git("status", "--porcelain")),
        "source_sha256": hashes,
        "compiler": compiler or None,
        "compiler_sha256": hashlib.sha256(Path(compiler).read_bytes()).hexdigest() if compiler else None,
        "tier": args.tier,
        "scope": "Bounded fixtures and desktop proofs; no general foreign application compatibility claim.",
        "gates": [],
    }
    env = dict(os.environ)
    if compiler:
        env["IN"] = compiler
        # Existing shell gates resolve this layout before consulting IN.
        if Path(compiler).parts[-4:] != ("in-cli", "target", "release", "in"):
            parser.error("compiler must be at <checkout>/in-cli/target/release/in for shell gates")
        env["INAUGURATION_DIR"] = str(Path(compiler).parents[3])
    report_path = output / "report.json"
    def save():
        temporary = output / "report.json.tmp"
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(report_path)
    save()
    for name, tier, evidence, command in gates(compiler, output):
        if args.tier != "all" and args.tier != tier:
            continue
        artifact = output / name
        artifact.mkdir(exist_ok=True)
        gate_env = dict(env, BUILD_DIR=str(artifact))
        log_path = output / f"{name}.log"
        print(f"RUN {name} ({evidence})", flush=True)
        start = time.monotonic()
        entry = {"name": name, "tier": tier, "evidence": evidence,
                 "command": command, "log": str(log_path), "status": "running"}
        report["gates"].append(entry)
        save()
        with log_path.open("w") as log:
            try:
                result = subprocess.run(command, cwd=ROOT, env=gate_env,
                                        stdout=log, stderr=subprocess.STDOUT)
                code = result.returncode
            except OSError as error:
                log.write(str(error) + "\n")
                code = 127
        entry.update(status="passed" if code == 0 else "failed",
                     exit_code=code, elapsed_seconds=round(time.monotonic() - start, 3))
        save()
        print(f"{entry['status'].upper()} {name}: {log_path}", flush=True)
    failures = sum(gate["status"] != "passed" for gate in report["gates"])
    report.update(finished_utc=datetime.now(timezone.utc).isoformat(),
                  passed=len(report["gates"]) - failures, failed=failures)
    save()
    print(f"{report['passed']} passed, {failures} failed; {report_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
