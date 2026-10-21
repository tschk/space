#!/usr/bin/env python3
"""Verification suite for Space OS TrueType (.ttf) and OpenType (.otf) Font Platform.

Validates:
1. SFNT table container parser and bounds checks across TTF and OTF formats.
2. Refusal of corrupted, truncated, and invalid assets.
3. Accurate cmap Format 4 / 0 Unicode character-to-glyph mapping.
4. Horizontal metrics (hmtx/hhea) extraction and scaling.
5. TrueType quadratic Bezier curve subdivision and segment construction.
6. Fixed-point 4x supersampled scanline anti-aliasing (0..255 coverage).
7. Scalable dynamic glyph cache hits, misses, and invalidation.
8. Native compilation and execution of freestanding .in font engine.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
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


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd or ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc.returncode, proc.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="in_bin", default=None, help="Path to `in` compiler binary")
    args = parser.parse_args()

    in_compiler = resolve_in(args.in_bin)
    print(f"=== Space TrueType & OpenType Font Verification Suite ===")
    print(f"Compiler: {in_compiler}")

    # 1. Test pack-ttf-asset.py tool
    print("\n[1/4] Testing TTF/OTF asset packager & inspector...")
    pack_script = ROOT / "scripts/pack-ttf-asset.py"
    space_font = ROOT / "assets/fonts/SpaceSans.ttf"

    # Ensure font exists
    if not space_font.exists():
        rc, out = run([sys.executable, str(pack_script), "generate", "-o", str(space_font)])
        if rc != 0:
            print(f"FAIL: could not generate SpaceSans.ttf:\n{out}")
            return 1

    rc, out = run([sys.executable, str(pack_script), "verify", str(space_font)])
    if rc != 0:
        print(f"FAIL: SpaceSans.ttf verification failed:\n{out}")
        return 1
    print("  ok: SpaceSans.ttf verified successfully")

    # Check host fonts if present
    for host_font in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/STIXGeneral.otf",
    ):
        if os.path.exists(host_font):
            rc, out = run([sys.executable, str(pack_script), "verify", host_font])
            if rc != 0:
                print(f"FAIL: host font verification failed for {host_font}:\n{out}")
                return 1
            print(f"  ok: {os.path.basename(host_font)} verified ({'OTF' if host_font.endswith('.otf') else 'TTF'})")

    # 2. Test corrupted font rejection
    print("\n[2/4] Testing corrupted & malformed font refusal...")
    with tempfile.TemporaryDirectory(prefix="ttf-corrupt-") as tmpdir:
        tmppath = Path(tmpdir)
        # Truncated font
        (tmppath / "trunc.ttf").write_bytes(b"\x00\x01\x00\x00\x00\x04")
        rc, _ = run([sys.executable, str(pack_script), "verify", str(tmppath / "trunc.ttf")])
        if rc == 0:
            print("FAIL: accepted truncated font file")
            return 1
        print("  ok: refused truncated font")

        # Bad magic
        (tmppath / "badmagic.ttf").write_bytes(b"\xDE\xAD\xBE\xEF\x00\x01\x00\x00\x00\x00\x00\x00")
        rc, _ = run([sys.executable, str(pack_script), "verify", str(tmppath / "badmagic.ttf")])
        if rc == 0:
            print("FAIL: accepted bad magic font file")
            return 1
        print("  ok: refused bad magic font")

    # 3. Compile and execute native freestanding .in font engine tests
    print("\n[3/4] Compiling native freestanding .in TTF engine...")
    test_dir = ROOT / "build/test-ttf"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_in = test_dir / "test_ttf.in"

    heap_zeros = ",".join(["0"] * 98304)
    test_code = f"""
package space.test

var heap: [Int] = [{heap_zeros}];
var heap-cursor: Int = 1024;
var fb-ready: Int = 1;
var fb-width: Int = 1920;
var fb-height: Int = 1080;
var fb-pitch: Int = 7680;
var fb-addr: Int = 0;
var fb-font-scale: Int = 2;
var comp-render-dx: Int = 0;
var comp-render-dy: Int = 0;
var comp-clip-valid: Int = 0;
var text-utf8-bytes: Int = 1;

fn alloc(n: Int) -> Int {{
  let p = heap-cursor;
  heap-cursor = heap-cursor + n + 64;
  return p;
}}

fn load8(p: Int) -> Int {{
  return heap[p] & 255;
}}

fn load32(p: Int) -> Int {{
  let b0 = heap[p + 0] & 255;
  let b1 = heap[p + 1] & 255;
  let b2 = heap[p + 2] & 255;
  let b3 = heap[p + 3] & 255;
  return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24);
}}

fn load64(p: Int) -> Int {{
  let lo = load32(p) & 0xFFFFFFFF;
  let hi = load32(p + 4) & 0xFFFFFFFF;
  return lo | (hi << 32);
}}

fn store8(p: Int, v: Int) -> void {{
  heap[p] = v & 255;
  return;
}}

fn store32(p: Int, v: Int) -> void {{
  heap[p + 0] = v & 255;
  heap[p + 1] = (v >> 8) & 255;
  heap[p + 2] = (v >> 16) & 255;
  heap[p + 3] = (v >> 24) & 255;
  return;
}}

fn store64(p: Int, v: Int) -> void {{
  heap[p + 0] = v & 255;
  heap[p + 1] = (v >> 8) & 255;
  heap[p + 2] = (v >> 16) & 255;
  heap[p + 3] = (v >> 24) & 255;
  heap[p + 4] = (v >> 32) & 255;
  heap[p + 5] = (v >> 40) & 255;
  heap[p + 6] = (v >> 48) & 255;
  heap[p + 7] = (v >> 56) & 255;
  return;
}}

fn comp-clip-test(x: Int, y: Int) -> Int {{
  return 1;
}}

fn fb-fill-rect(x: Int, y: Int, w: Int, h: Int, c: Int) -> void {{
  return;
}}

fn text-utf8-decode(str: Int, idx: Int) -> Int {{
  let b = load8(str + idx);
  if b == 0 {{ text-utf8-bytes = 0; return 0; }}
  text-utf8-bytes = 1;
  return b;
}}

import "../../components/font-asset-spacesans.in"
import "../../components/font-ttf.in"

fn main() -> Int {{
  heap-cursor = 1024;

  // 1. Load SpaceSans TTF asset
  let font-buf = space-font-spacesans-init();
  if font-buf == 0 {{ return 1; }}
  let ok = ttf-load(font-buf, SPACE-FONT-SPACESANS-SIZE);
  if ok != 1 || ttf-font-valid != 1 {{ return 2; }}

  // 2. Verify font metrics (head, maxp, hhea)
  if ttf-upem != 1000 {{ return 3; }}
  if ttf-num-glyphs != 96 {{ return 4; }}
  if ttf-ascent != 800 || ttf-descent != -200 {{ return 5; }}

  // 3. Verify cmap character mapping
  let gid-A = ttf-map-char(65);
  let gid-space = ttf-map-char(32);
  let gid-missing = ttf-map-char(0x20AC);
  if gid-A != 34 {{ return 6; }}
  if gid-space != 1 {{ return 7; }}
  if gid-missing != 0 {{ return 8; }}

  // 4. Verify horizontal metrics (hmtx)
  let adv-A = ttf-glyph-advance(gid-A);
  let adv-space = ttf-glyph-advance(gid-space);
  if adv-A != 660 {{ return 9; }}
  if adv-space != 300 {{ return 10; }}

  // 5. Decode TrueType contours for 'A'
  let ncontours = ttf-decode-glyph(gid-A);
  if ncontours != 2 {{ return 11; }}
  let nsegs = ttf-build-segments(ncontours);
  if nsegs < 10 {{ return 12; }}

  // 6. Rasterize with 4x supersampling and verify anti-aliased coverage
  let cov = ttf-rasterize(16, 12, 16, adv-A);
  if cov == 0 {{ return 13; }}
  // Check that coverage buffer has non-zero values
  let sum-cov = 0;
  let has-aa = 0;
  let i = 0;
  while i < 12 * 16 {{
    let v = load8(cov + i);
    sum-cov = sum-cov + v;
    if v > 0 && v < 255 {{
      has-aa = 1;
    }}
    i = i + 1;
  }}
  if sum-cov <= 0 {{ return 14; }}
  if has-aa == 0 {{ return 15; }} // Must have anti-aliased edge values (0 < v < 255)

  // 7. Dynamic glyph cache verification
  let rec1 = ttf-get-glyph(65, 16);
  if rec1 == 0 {{ return 16; }}
  let hits-before = ttf-cache-hits;
  let rec2 = ttf-get-glyph(65, 16);
  if rec2 != rec1 || ttf-cache-hits <= hits-before {{ return 17; }} // Cache hit

  // Cache invalidation
  ttf-cache-invalidate();
  let misses-before = ttf-cache-misses;
  let rec3 = ttf-get-glyph(65, 16);
  if ttf-cache-misses <= misses-before {{ return 18; }} // Cache miss after invalidate

  // 8. OpenType CFF header validation test
  let cff-hdr = alloc(64);
  store32(cff-hdr + 0, 0x4F54544F); // 'OTTO'
  store8(cff-hdr + 4, 0);
  store8(cff-hdr + 5, 1);
  if ttf-load(cff-hdr, 8) != 0 {{ return 19; }} // Refuses truncated CFF

  return 42;
}}
"""
    test_in.write_text(test_code)

    print("  Compiling test_ttf.in with `in`...")
    out_bin = test_dir / "test_bin"
    rc, out = run([
        in_compiler,
        "compile",
        "--path",
        str(test_in),
        "--entry",
        "main",
        "--target",
        "jit",
        "--profile",
        "default",
        "--out",
        str(out_bin),
        "--json",
    ], cwd=test_dir)
    if rc != 0:
        print(f"FAIL: compilation failed (rc={rc}):\n{out}")
        return 1
    import json
    report = json.loads(out)
    eval_result = report.get("eval_result")
    if eval_result != {"Int": 42}:
        print(f"FAIL: unexpected eval_result: {eval_result}, report:\n{out}")
        return 1
    print("  ok: native .in TTF engine evaluated with code 42 (eval_result: 42)")

    print("\n[4/4] Summary")
    print("PASS: all TrueType & OpenType font tests green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
