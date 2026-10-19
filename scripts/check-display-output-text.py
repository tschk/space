#!/usr/bin/env python3
"""Verify Space display-output and display-text contracts across model/JIT/native
profiles and real QEMU BGA modes (1024x768, 1280x720, 1920x1080) and scales (2x, 3x).
"""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time

if "/opt/homebrew/bin" not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{os.environ.get('PATH', '')}:/opt/homebrew/bin"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, timeout=60):
    command = [str(a) for a in command]
    res = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    return {
        "command": command,
        "exit": res.returncode,
        "stdout": res.stdout,
        "stderr": res.stderr,
    }


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--in", dest="compiler", type=Path, required=True)
parser.add_argument("--out", type=Path, default=Path("/tmp/space-output-text-check"))
a = parser.parse_args()
a.compiler = a.compiler.resolve()
a.out = a.out.resolve()
if a.out.exists():
    for child in a.out.glob("*"):
        if child.is_file() or child.is_symlink():
            child.unlink()
a.out.mkdir(parents=True, exist_ok=True)

root = Path(__file__).resolve().parents[1]
inputs = [
    root / "components" / name
    for name in (
        "font.in",
        "display-output.in",
        "display-text.in",
        "display-layout.in",
        "display-commandbar.in",
        "display.in",
    )
]
input_hashes = {str(p.relative_to(root)): sha256(p) for p in inputs}
combined_text = "\n".join(p.read_text() for p in inputs)


def extract_fn(name: str) -> str:
    marker = "fn " + name + "("
    start = combined_text.index(marker)
    end = combined_text.index("\n}", start) + 2
    return combined_text[start:end]


constants = "\n".join(
    line
    for line in combined_text.splitlines()
    if line.startswith("const ")
    and not line.startswith("const COMP-TERM-")
    and not line.startswith("const VBE-")
)

harness_base = (
    "var heap:[Int]=[" + ",".join(["0"] * 32768) + "];\n"
    """
var fb-addr:Int=0;
var fb-pitch:Int=7680;
var fb-width:Int=1920;
var fb-height:Int=1080;
var fb-bpp:Int=32;
var fb-size:Int=8294400;
var fb-ready:Int=1;
var fb-font-scale:Int=2;
var fb-font:Int=0;
var fb-font-aa:Int=0;
var fb-font-sans:Int=0;
var fb-font-sans-adv:Int=0;
var fb-font-sans-aa:Int=0;
var comp-backbuf:Int=0;
var comp-windows:Int=0;
var comp-surf-sizes:Int=0;
var comp-count:Int=0;
var comp-focused:Int=-1;
var comp-dragging:Int=-1;
var comp-drag-mode:Int=-1;
var comp-full-redraw:Int=0;
var comp-render-dx:Int=0;
var comp-render-dy:Int=0;
var comp-clip-valid:Int=0;
var comp-clip-x0:Int=0;
var comp-clip-y0:Int=0;
var comp-clip-x1:Int=0;
var comp-clip-y1:Int=0;
var out-id:Int=1;
var out-generation:Int=0;
var out-format:Int=1;
var out-transform:Int=0;
var out-scale-num:Int=100;
var out-scale-den:Int=100;
var out-origin-x:Int=0;
var out-origin-y:Int=0;
var out-logical-w:Int=1920;
var out-logical-h:Int=1080;
var out-work-x:Int=0;
var out-work-y:Int=28;
var out-work-w:Int=1920;
var out-work-h:Int=1024;
var text-ui-face:Int=1;
var text-utf8-bytes:Int=1;
var text-cache-keys:Int=0;
var text-cache-vals:Int=0;
var text-cache-gen:Int=1;
var text-cache-hits:Int=0;
var text-cache-misses:Int=0;
var text-cache-evictions:Int=0;
var heap-cursor:Int=256;
var fallback-draws:Int=0;
fn alloc(n:Int)->Int{let p=heap-cursor;heap-cursor=heap-cursor+n+16;return p;}
fn load8(p:Int)->Int{return heap[p]&255;}
fn load32(p:Int)->Int{return heap[p];}
fn load64(p:Int)->Int{return heap[p];}
fn store8(p:Int,v:Int)->Void{heap[p]=v&255;}
fn store32(p:Int,v:Int)->Void{heap[p]=v;}
fn store64(p:Int,v:Int)->Void{heap[p]=v;}
fn comp-win-base(i:Int)->Int{return comp-windows+i*COMP-WIN-SIZE;}
fn comp-dmg-clear()->Void{return;}
fn comp-dmg-full()->Void{return;}
fn comp-clip-test(x:Int,y:Int)->Int{return 1;}
fn fb-fill-rect(x:Int,y:Int,w:Int,h:Int,c:Int)->Void{return;}
fn fb-draw-char(x:Int,y:Int,ch:Int,c:Int)->Void{return;}
"""
    + constants
    + "\n"
    + "\n".join(
        extract_fn(fn_name)
        for fn_name in (
            "fb-font-set",
            "fb-font-sans-set",
            "fb-build-aa-table",
            "fb-font-aa-init",
            "fb-font-sans-init",
            "fb-font-init",
            "out-effective-phys-w",
            "out-effective-phys-h",
            "out-validate-mode",
            "out-generation-valid",
            "out-logical-to-phys-x",
            "out-logical-to-phys-y",
            "out-phys-to-logical-x",
            "out-phys-to-logical-y",
            "out-damage-phys-x0",
            "out-damage-phys-y0",
            "out-damage-phys-x1",
            "out-damage-phys-y1",
            "out-tile-col-x",
            "out-tile-col-w",
            "out-clamp-windows",
            "out-commit-mode",
            "text-init",
            "text-cache-invalidate",
            "text-validate-asset",
            "text-role-face",
            "text-set-ui-face",
            "text-term-cell-w",
            "text-term-cell-h",
            "text-term-baseline",
            "text-face-baseline",
            "text-is-supported-cp",
            "text-glyph-advance-raw",
            "text-glyph-advance",
            "text-utf8-decode",
            "text-measure-run",
            "text-caret-x",
            "text-hit-test-byte",
            "text-set-scale",
        )
    )
    + "\n"
)

cases = [
    (
        "output-mode-and-transform-matrix",
        harness_base
        + """
fn main()->Int{
  comp-windows = alloc(COMP-MAX-WINDOWS * COMP-WIN-SIZE);
  comp-count = 2;
  let b0 = comp-win-base(0);
  store32(b0 + 4, 32); store32(b0 + 8, 48); store32(b0 + 12, 900); store32(b0 + 16, 950); store32(b0 + 20, 1);
  let b1 = comp-win-base(1);
  store32(b1 + 4, 1400); store32(b1 + 8, 600); store32(b1 + 12, 500); store32(b1 + 16, 420); store32(b1 + 20, 1);

  // 1. Standard landscape resolutions: 1920x1080, 1280x720 (with padded pitch), 1024x768.
  let g1 = out-commit-mode(1920, 1080, 32, 7680, 100, 100, OUT-TRANSFORM-NORMAL);
  if g1 != 1 || out-generation-valid(g1) != 1 || out-work-w != 1920 || out-work-h != 1024 { return 1; }

  let g2 = out-commit-mode(1280, 720, 32, 5376, 100, 100, OUT-TRANSFORM-NORMAL);
  if g2 != 2 || fb-pitch != 5376 || fb-size != 5376 * 720 || out-work-w != 1280 || out-work-h != 664 { return 2; }
  // Window 1 (was x=1400, w=500) must be clamped inside 1280x720 work area.
  if load32(b1 + 4) + load32(b1 + 12) > 1280 - 16 { return 3; }
  if load32(b0 + 8) + load32(b0 + 16) + COMP-TITLE-BAR-H > 720 - COMP-TASKBAR-H - 8 { return 4; }

  let g3 = out-commit-mode(1024, 768, 32, 4096, 100, 100, OUT-TRANSFORM-NORMAL);
  if g3 != 3 || out-work-w != 1024 || out-work-h != 712 { return 5; }
  if load32(b1 + 4) + load32(b1 + 12) > 1024 - 16 { return 6; }

  // 2. Portrait logical geometry via 90-degree rotation (1920x1080 rotated -> 1080x1920 logical).
  let g4 = out-commit-mode(1920, 1080, 32, 7680, 100, 100, OUT-TRANSFORM-ROT90);
  if g4 != 4 || out-logical-w != 1080 || out-logical-h != 1920 || out-work-w != 1080 || out-work-h != 1864 { return 7; }

  // 3. Fractional scale 150% (150/100) on 1920x1080 -> logical 1280x720, font scale 3.
  let g5 = out-commit-mode(1920, 1080, 32, 7680, 150, 100, OUT-TRANSFORM-NORMAL);
  if g5 != 5 || out-logical-w != 1280 || out-logical-h != 720 || fb-font-scale != 3 { return 8; }
  if out-generation-valid(g4) != 0 || out-generation-valid(g5) != 1 { return 9; }

  // 4. Outward damage rounding & negative multi-output origin transforms.
  out-origin-x = -400;
  out-origin-y = -200;
  let px = out-logical-to-phys-x(-200);
  let lx = out-phys-to-logical-x(px);
  if px != 300 || lx != -200 { return 10; }
  out-origin-x = 0;
  out-origin-y = 0;
  // At 150% (150/100), logical x0=1 -> phys floor 1; logical x1=3 -> phys ceil 5.
  if out-damage-phys-x0(1) != 1 || out-damage-phys-x1(3) != 5 { return 11; }

  // 5. Shared tile-edge continuity across 3 columns on odd width 1921.
  let c0x = out-tile-col-x(0, 3, 1921, 16, 16);
  let c0w = out-tile-col-w(0, 3, 1921, 16, 16);
  let c1x = out-tile-col-x(1, 3, 1921, 16, 16);
  let c1w = out-tile-col-w(1, 3, 1921, 16, 16);
  let c2x = out-tile-col-x(2, 3, 1921, 16, 16);
  let c2w = out-tile-col-w(2, 3, 1921, 16, 16);
  if c0x != 16 || c0x + c0w + 16 != c1x || c1x + c1w + 16 != c2x || c2x + c2w != 1921 - 16 { return 12; }

  // 6. Invalid / overflow mode refusal must preserve g5 (1920x1080 @ 150%) untouched.
  if out-commit-mode(320, 200, 32, 1280, 100, 100, 0) != 0 { return 13; }
  if out-commit-mode(1920, 1080, 24, 7680, 100, 100, 0) != 0 { return 14; }
  if out-commit-mode(1920, 1080, 32, 4000, 100, 100, 0) != 0 { return 15; }
  if out-commit-mode(1920, 1080, 32, 7682, 100, 100, 0) != 0 { return 16; }
  if out-commit-mode(4096, 4096, 32, 16384, 100, 100, 0) != 0 { return 17; }
  if out-commit-mode(1024, 768, 32, 4096, 400, 100, 0) != 0 { return 18; }
  if out-generation != g5 || fb-width != 1920 || fb-height != 1080 || out-scale-num != 150 { return 19; }
  return 42;
}
""",
    ),
    (
        "typeface-roles-utf8-and-asset-validation",
        harness_base
        + """
fn main()->Int{
  fb-font-init();
  text-init();
  text-set-scale(2);

  // 1. Two genuinely distinct faces: Space UI Sans (proportional) vs Space Term Mono (fixed).
  let s = alloc(32);
  // "TERMINAL 1"
  store8(s+0,84);store8(s+1,69);store8(s+2,82);store8(s+3,77);store8(s+4,73);
  store8(s+5,78);store8(s+6,65);store8(s+7,76);store8(s+8,32);store8(s+9,49);store8(s+10,0);

  let ui-w2 = text-measure-run(TEXT-ROLE-UI-BODY, s, 10);
  let term-w2 = text-measure-run(TEXT-ROLE-TERM-MONO, s, 10);
  if term-w2 != 10 * 18 { return 1; }
  if ui-w2 >= term-w2 || ui-w2 <= 0 { return 2; }

  // Proportional glyph advances in Space UI Sans: 'I' (73) < 'A' (65) < 'M' (77).
  let adv-I = text-glyph-advance(FONT-FACE-SANS, 73, 2);
  let adv-A = text-glyph-advance(FONT-FACE-SANS, 65, 2);
  let adv-M = text-glyph-advance(FONT-FACE-SANS, 77, 2);
  if !(adv-I < adv-A && adv-A < adv-M) { return 3; }
  if text-glyph-advance(FONT-FACE-MONO, 73, 2) != 18 || text-glyph-advance(FONT-FACE-MONO, 77, 2) != 18 { return 4; }

  // Glyph bitmaps are also distinct between Space UI Sans and Space Term Mono ('I' row 0: 0x60 vs 0x3C; '0' row 2: 0x88 vs 0x6E).
  if load8(fb-font-sans + 73 * 8 + 0) == load8(fb-font + 73 * 8 + 0) { return 5; }
  if load8(fb-font-sans + 48 * 8 + 2) == load8(fb-font + 48 * 8 + 2) { return 6; }

  // 2. Terminal cell metric invariants hold when UI face changes.
  let cw-before = text-term-cell-w();
  let ch-before = text-term-cell-h();
  let bl-before = text-term-baseline();
  text-set-ui-face(FONT-FACE-MONO);
  if text-term-cell-w() != cw-before || text-term-cell-h() != ch-before || text-term-baseline() != bl-before { return 7; }
  text-set-ui-face(FONT-FACE-SANS);
  if text-role-face(TEXT-ROLE-UI-BODY) != FONT-FACE-SANS || text-role-face(TEXT-ROLE-TERM-MONO) != FONT-FACE-MONO { return 8; }

  // 3. UTF-8 decoding, multi-byte codepoints, caret & hit-testing on character boundaries.
  // "A" (1B) + U+00E9 (0xC3 0xA9, 2B) + U+20AC (0xE2 0x82 0xAC, 3B) + "Z" (1B)
  let u = alloc(16);
  store8(u+0, 65);
  store8(u+1, 0xC3); store8(u+2, 0xA9);
  store8(u+3, 0xE2); store8(u+4, 0x82); store8(u+5, 0xAC);
  store8(u+6, 90);
  store8(u+7, 0);
  if text-utf8-decode(u, 0) != 65 || text-utf8-bytes != 1 { return 9; }
  if text-utf8-decode(u, 1) != 0xE9 || text-utf8-bytes != 2 { return 10; }
  if text-utf8-decode(u, 3) != 0x20AC || text-utf8-bytes != 3 { return 11; }
  if text-utf8-decode(u, 6) != 90 || text-utf8-bytes != 1 { return 12; }
  // 4-glyph run in monospace (not 7 bytes!): width must be 4 * 18 = 72.
  if text-measure-run(TEXT-ROLE-TERM-MONO, u, 7) != 4 * 18 { return 13; }
  if text-caret-x(TEXT-ROLE-TERM-MONO, u, 3) != 2 * 18 { return 14; }
  if text-caret-x(TEXT-ROLE-TERM-MONO, u, 6) != 3 * 18 { return 15; }
  // Hit-testing inside the 2nd glyph (x=25) and 3rd glyph (x=45) must return UTF-8 codepoint start bytes (1 and 3, never 2 or 4).
  if text-hit-test-byte(TEXT-ROLE-TERM-MONO, u, 20) != 1 { return 16; }
  if text-hit-test-byte(TEXT-ROLE-TERM-MONO, u, 40) != 3 { return 17; }
  if text-hit-test-byte(TEXT-ROLE-TERM-MONO, u, 60) != 6 { return 18; }

  // Invalid / overlong UTF-8 byte returns replacement character 0xFFFD and advances 1 byte.
  let bad = alloc(8);
  store8(bad+0, 0xC0); store8(bad+1, 0xAF); store8(bad+2, 0);
  if text-utf8-decode(bad, 0) != TEXT-CP-REPLACEMENT || text-utf8-bytes != 1 { return 19; }

  // 4. Scale change (2x -> 3x) updates measurements, invalidates cache, refuses invalid scale.
  let gen-before = text-cache-gen;
  if text-set-scale(3) != 1 || fb-font-scale != 3 || text-cache-gen <= gen-before { return 20; }
  if text-measure-run(TEXT-ROLE-TERM-MONO, s, 10) != 10 * 26 { return 21; }
  if text-set-scale(0) != 0 || text-set-scale(9) != 0 || fb-font-scale != 3 { return 22; }
  text-set-scale(2);

  // 5. Untrusted font asset validation (valid asset vs truncated / bad magic / color emoji).
  let asset = alloc(1200);
  store32(asset + 0, TEXT-ASSET-MAGIC);
  store32(asset + 4, TEXT-ASSET-VERSION);
  store32(asset + 8, FONT-FACE-SANS);
  store32(asset + 12, TEXT-ASSET-FLAG-PROP);
  store32(asset + 16, 128);
  store32(asset + 20, 8);
  store32(asset + 24, 8);
  store32(asset + 28, 7);
  let ch = 32;
  while ch < 127 {
    store8(asset + 32 + 1024 + ch, load8(fb-font-sans-adv + ch));
    ch = ch + 1;
  }
  if text-validate-asset(asset, 1184) != 1 { return 23; }
  // Truncated asset refused
  if text-validate-asset(asset, 800) != 0 { return 24; }
  // Color/emoji flag refused
  store32(asset + 12, TEXT-ASSET-FLAG-PROP | TEXT-ASSET-FLAG-COLOR);
  if text-validate-asset(asset, 1184) != 0 { return 25; }
  store32(asset + 12, TEXT-ASSET-FLAG-PROP);
  // Out-of-bounds glyph advance refused
  store8(asset + 32 + 1024 + 65, 24);
  if text-validate-asset(asset, 1184) != 0 { return 26; }

  return 42;
}
""",
    ),
]

receipt = {
    "complete": False,
    "compiler": str(a.compiler),
    "compiler_sha256": sha256(a.compiler),
    "component_sha256": input_hashes,
    "model_checks": [],
    "qemu_checks": {},
}

for name, source in cases:
    path = a.out / f"{name}.in"
    path.write_text(source)
    for target in ("jit", "native"):
        for profile in ("default", "lean", "harden"):
            out_bin = a.out / f"{name}-{target}-{profile}"
            comp = run(
                [
                    a.compiler,
                    "compile",
                    "--path",
                    path,
                    "--entry",
                    "main",
                    "--target",
                    target,
                    "--profile",
                    profile,
                    "--out",
                    out_bin,
                    "--json",
                ]
            )
            assert comp["exit"] == 0, comp
            report = json.loads(comp["stdout"])
            assert report.get("success") and not report.get("external_invocations"), report
            if target == "jit":
                assert report.get("eval_result") == {"Int": 42}, report
            else:
                exe = run([out_bin], timeout=15)
                assert exe["exit"] == 42, exe
            receipt["model_checks"].append(
                {"name": name, "target": target, "profile": profile, "status": "PASS"}
            )

print(f"PASS: {len(receipt['model_checks'])} model/native/JIT checks across default/lean/harden")

# --- Part 2: Real QEMU BGA Resolution, Scale, Dual-Typeface & Fallback Verification ---
subprocess.run(
    ["nasm", "-f", "bin", str(root / "boot/multiboot.asm"), "-o", str(a.out / "trampoline.bin")],
    check=True,
)
assert (a.out / "trampoline.bin").stat().st_size == 4096

compile_res = run(
    [
        a.compiler,
        "compile",
        "--path",
        root / "kernel/kernel-root.in",
        "--entry",
        "kernel-entry",
        "--emit",
        "boot",
        "--trampoline",
        a.out / "trampoline.bin",
        "--target",
        "native",
        "--target-triple",
        "x86_64-unknown-none",
        "--linkage",
        "static-lib",
        "--out",
        a.out / "kernel.bin",
    ],
    timeout=180,
)
assert compile_res["exit"] == 0, compile_res

serial_path = a.out / "serial.sock"
monitor_path = a.out / "monitor.sock"
for p in (serial_path, monitor_path):
    if p.exists():
        p.unlink()


def connect(path: Path) -> socket.socket:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        sock = socket.socket(socket.AF_UNIX)
        try:
            sock.connect(str(path))
            sock.settimeout(0.2)
            return sock
        except OSError:
            sock.close()
            time.sleep(0.05)
    raise AssertionError(f"QEMU socket unavailable: {path}")


log = bytearray()
with (a.out / "qemu.log").open("w") as qlog:
    qemu = subprocess.Popen(
        [
            "qemu-system-x86_64",
            "-kernel",
            str(a.out / "kernel.bin"),
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
        stdout=qlog,
        stderr=subprocess.STDOUT,
    )
    serial = monitor = None
    try:
        serial = connect(serial_path)
        monitor = connect(monitor_path)

        def wait(marker: str, start: int = 0):
            deadline = time.monotonic() + 35
            while marker.encode() not in log[start:] and time.monotonic() < deadline:
                try:
                    chunk = serial.recv(65536)
                    if not chunk:
                        raise AssertionError("QEMU serial closed")
                    log.extend(chunk)
                except socket.timeout:
                    pass
            (a.out / "serial.log").write_bytes(log)
            assert marker.encode() in log[start:], f"missing {marker}: {log[-2000:]!r}"

        def command(text: str):
            if text.startswith("sendkey "):
                text += " 30"
            monitor.sendall((text + "\n").encode())
            time.sleep(0.15)
            try:
                monitor.recv(65536)
            except socket.timeout:
                pass

        def key(text: str):
            for ch in text:
                command("sendkey " + ("spc" if ch == " " else ch))
                time.sleep(0.08)

        def capture(name: str, exp_w: int, exp_h: int) -> bytes:
            import struct
            import zlib
            path = a.out / f"{name}.ppm"
            if path.exists():
                path.unlink()
            command(f"screendump {path}")
            deadline = time.monotonic() + 5
            expected_min = exp_w * exp_h * 3 + 14
            while (not path.exists() or path.stat().st_size < expected_min) and time.monotonic() < deadline:
                time.sleep(0.05)
            data = path.read_bytes()
            header = data.split(b"\n", 3)
            assert header[0] == b"P6", header[:3]
            assert header[1] == f"{exp_w} {exp_h}".encode(), (header[1], exp_w, exp_h)
            assert header[2] == b"255", header[:3]
            raw = header[3]
            assert len(raw) == exp_w * exp_h * 3
            row_bytes = exp_w * 3
            raw_rows = b"".join(b"\x00" + raw[y * row_bytes : (y + 1) * row_bytes] for y in range(exp_h))
            def chunk(tag: bytes, body: bytes) -> bytes:
                return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)
            png = (
                b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", struct.pack(">IIBBBBB", exp_w, exp_h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw_rows, 6))
                + chunk(b"IEND", b"")
            )
            (a.out / f"{name}.png").write_bytes(png)
            return raw

        wait("space interactive shell")

        # 1. Default 1920x1080 @ scale=2 (100%): verify concurrent Space UI Sans & Space Term Mono + UTF-8 fallback box + caret
        start = len(log)
        serial.sendall(b"desktop\n")
        wait("space: compositor frame ready", start)
        px_1080_before = capture("desktop-1920x1080-scale2", 1920, 1080)

        # Type 'utf8' into TERMINAL 1 (without pressing Enter first) to observe caret movement, then press Enter.
        key("utf8")
        time.sleep(0.5)
        px_1080_typed = capture("desktop-1920x1080-utf8-typed", 1920, 1080)
        assert px_1080_typed != px_1080_before, "typing into terminal did not move caret or render characters"
        command("sendkey ret")
        time.sleep(0.6)
        px_1080_utf8 = capture("desktop-1920x1080-utf8-fallback", 1920, 1080)
        assert px_1080_utf8 != px_1080_typed, "pressing Enter on utf8 did not render fallback line"

        # Verify UTILITIES window renders both Space UI Sans and Space Term Mono rows distinctly
        def row_signature(pixels: bytes, w: int, x0: int, y0: int, x1: int, y1: int) -> int:
            dark = 0
            for yy in range(y0, y1):
                base = (yy * w + x0) * 3
                for xx in range(x1 - x0):
                    r = pixels[base + xx * 3]
                    if r < 60:
                        dark += 1
            return dark

        # In UTILITIES at 1920x1080 (x=976, content-y=76, lh=21):
        # "SPACE UI SANS" is at ty = 76 + 21 + 4 + 21*3 + 10 + 21 = 195
        # "SPACE TERM MONO" is at ty = 216
        sans_ink = row_signature(px_1080_utf8, 1920, 1136, 190, 1450, 214)
        mono_ink = row_signature(px_1080_utf8, 1920, 1136, 214, 1450, 238)
        assert sans_ink > 100 and mono_ink > 100 and sans_ink != mono_ink, (sans_ink, mono_ink)

        # Exit desktop to test mode refusal and mode switches
        start = len(log)
        command("sendkey esc")
        wait("space: compositor exited", start)

        # 2. Refused invalid modes preserve 1920x1080
        start = len(log)
        serial.sendall(b"fb mode 320 200\n")
        wait("space: output mode refused 320x200", start)
        start = len(log)
        serial.sendall(b"fb mode 8192 8192\n")
        wait("space: output mode refused 8192x8192", start)
        start = len(log)
        serial.sendall(b"fb scale 9\n")
        wait("space: text scale refused 9", start)

        # 3. Switch to 1280x720 and scale=3 (150% large text)
        start = len(log)
        serial.sendall(b"fb mode 1280 720\n")
        wait("space: output mode 1280x720 pitch=5120", start)
        start = len(log)
        serial.sendall(b"fb scale 3\n")
        wait("space: text scale 3", start)

        start = len(log)
        serial.sendall(b"desktop\n")
        wait("space: compositor frame ready", start)
        px_720_scale3 = capture("desktop-1280x720-scale3", 1280, 720)

        # Verify keyboard and pointer interaction at 1280x720 @ scale=3:
        # Summon command bar via Tab, verify panel appears around center (x=1280/2-360=280..1000)
        start = len(log)
        command("sendkey tab")
        wait("space: launcher opened", start)
        time.sleep(0.5)
        px_720_launcher = capture("desktop-1280x720-scale3-launcher", 1280, 720)
        panel_px = sum(
            px_720_launcher[(y * 1280 + x) * 3 : (y * 1280 + x) * 3 + 3] == bytes((27, 24, 24))
            for y in range(44, 268)
            for x in range(280, 1000)
        )
        assert panel_px > 30000, f"1280x720 launcher panel missing: {panel_px}"
        start = len(log)
        command("sendkey esc")
        wait("space: launcher dismissed", start)
        start = len(log)
        command("sendkey esc")
        wait("space: compositor exited", start)

        # 4. Switch to 1024x768 @ scale=2 (100%) and verify tiling geometry
        start = len(log)
        serial.sendall(b"fb scale 2\n")
        wait("space: text scale 2", start)
        start = len(log)
        serial.sendall(b"fb mode 1024 768\n")
        wait("space: output mode 1024x768 pitch=4096", start)

        start = len(log)
        serial.sendall(b"desktop\n")
        wait("space: compositor frame ready", start)
        px_768 = capture("desktop-1024x768-scale2", 1024, 768)

        # Tile windows via command bar at 1024x768
        start = len(log)
        command("sendkey tab")
        wait("space: launcher opened", start)
        key("tile")
        time.sleep(0.5)
        start = len(log)
        command("sendkey ret")
        wait("space: command TILE WINDOWS", start)
        time.sleep(0.5)
        px_768_tiled = capture("desktop-1024x768-tiled", 1024, 768)
        assert px_768_tiled != px_768, "tiling at 1024x768 did not update framebuffer"

        start = len(log)
        command("sendkey esc")
        wait("space: compositor exited", start)
        serial.sendall(b"halt\n")

        receipt["qemu_checks"] = {
            "1920x1080_scale2": "PASS",
            "utf8_fallback_and_caret": "PASS",
            "dual_typefaces_sans_and_mono": {"sans_ink": sans_ink, "mono_ink": mono_ink},
            "invalid_mode_and_scale_refusal": "PASS",
            "1280x720_scale3_launcher": {"panel_px": panel_px, "status": "PASS"},
            "1024x768_scale2_tiled": "PASS",
        }
        receipt["complete"] = True
        (a.out / "results.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(f"PASS: QEMU BGA modes (1920x1080, 1280x720, 1024x768), scales (2x, 3x), dual typefaces, UTF-8 fallback, and tiling verified ({a.out})")
    finally:
        (a.out / "serial.log").write_bytes(log)
        if monitor:
            try:
                monitor.sendall(b"quit\n")
            except OSError:
                pass
            monitor.close()
        if serial:
            serial.close()
        try:
            qemu.wait(timeout=5)
        except subprocess.TimeoutExpired:
            qemu.kill()
            qemu.wait()
        for p in (serial_path, monitor_path):
            if p.exists():
                p.unlink()
