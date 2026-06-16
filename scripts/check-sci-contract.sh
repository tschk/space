#!/usr/bin/env python3
# check-sci-contract.sh — Validate the compiled kernel's SCI metadata sidecar.
# Run as a script: python3 check-sci-contract.sh  (or chmod +x and run directly)
"""Validate compiled kernel SCI metadata against the sci-schema.md contract.

Usage:
    python3 check-sci-contract.sh [--kernel KERNEL_IN] [--in COMPILER] [--trampoline TRAMP]
"""
import json, os, subprocess, sys, tempfile

def check(label, ok):
    global passed, failed
    if ok:
        print(f"  ok: {label}")
        passed += 1
    else:
        print(f"  FAIL: {label}")
        failed += 1

passed, failed = 0, 0

def main():
    kernel_in = os.environ.get("KERNEL_IN",
        os.path.join(os.path.dirname(__file__) or ".", "..", "kernel", "kernel-root.in"))
    in_bin = os.environ.get("IN",
        os.path.join(os.path.dirname(__file__) or ".", "..", "..", "inauguration",
                     "in-cli", "target", "release", "in"))
    trampoline = os.environ.get("TRAMPOLINE", "/tmp/trampoline.bin")
    build_dir = os.environ.get("BUILD_DIR", "/tmp/space-sci-check")

    os.makedirs(build_dir, exist_ok=True)
    out_bin = os.path.join(build_dir, "kernel.bin")
    # Compiler replaces the .bin extension with .component-metadata.json
    meta_path = out_bin.replace(".bin", "") + ".component-metadata.json"

    print("[1/3] Compiling kernel to produce metadata sidecar...")
    for f in [out_bin, meta_path]:
        try: os.remove(f)
        except FileNotFoundError: pass

    result = subprocess.run([
        in_bin, "compile",
        "--path", kernel_in, "--entry", "kernel_entry", "--emit", "boot",
        "--trampoline", trampoline,
        "--target", "native", "--target-triple", "x86_64-unknown-none",
        "--linkage", "static-lib",
        "--out", out_bin,
    ], capture_output=True, text=True, timeout=60)

    if not os.path.exists(meta_path):
        print(f"FAIL: metadata sidecar not generated at {meta_path}")
        print(result.stderr)
        sys.exit(1)

    with open(meta_path) as f:
        meta = json.load(f)

    print("[2/3] Validating SCI metadata fields...")

    # Required top-level keys
    for key in ["component", "target", "entry", "imports", "exports",
                "capabilities_required", "object_schemas", "deterministic",
                "checkpoint", "code_size", "provenance"]:
        check(f"top-level key '{key}'", key in meta)

    # Type checks
    check("component is non-null string",
          isinstance(meta.get("component"), str) and len(meta["component"]) > 0)
    check("target is non-null string",
          isinstance(meta.get("target"), str) and len(meta["target"]) > 0)
    check("entry is non-null string",
          isinstance(meta.get("entry"), str) and len(meta["entry"]) > 0)
    check("deterministic is bool",
          isinstance(meta.get("deterministic"), bool))
    check("checkpoint is string",
          isinstance(meta.get("checkpoint"), str))
    check("code_size is positive int",
          isinstance(meta.get("code_size"), int) and meta["code_size"] > 0)

    # Capabilities
    caps = meta.get("capabilities_required", [])
    check(f"capabilities_required present (count={len(caps)})", len(caps) >= 0)
    for i, c in enumerate(caps):
        for field in ["name", "capability_type", "args"]:
            check(f"capability[{i}].{field}", field in c)

    # Object schemas
    schemas = meta.get("object_schemas", [])
    check(f"object_schemas present (count={len(schemas)})", len(schemas) >= 0)

    # Provenance
    prov = meta.get("provenance", {})
    check("provenance.compiler exists", "compiler" in prov)
    check("provenance.compiler_version exists", "compiler_version" in prov)

    # Exports
    exports = meta.get("exports", [])
    check(f"exports present (count={len(exports)})", len(exports) >= 1)

    print("[3/3] Checking loader-rule compatibility...")
    # Every capability used by kernel-root must be declared
    declared = {c.get("name") for c in caps}
    for expected in ["serial", "memory", "tables", "traps", "caps"]:
        check(f"declared capability '{expected}'", expected in declared)

    print(f"\n=== Results: {passed} passed, {failed} failed ===")
    if failed:
        print("FAIL: one or more SCI fields missing or malformed.")
        sys.exit(1)
    print("PASS: all SCI metadata fields valid.")

if __name__ == "__main__":
    main()
