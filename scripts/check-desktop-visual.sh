#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=inauguration-dir.sh
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-desktop-visual}"
IN="$INAUG_DIR/in-cli/target/release/in"
SERIAL_BASE="$BUILD_DIR/serial"
SERIAL_IN="$SERIAL_BASE.in"
SERIAL_OUT="$SERIAL_BASE.out"
SERIAL_LOG="$BUILD_DIR/serial.log"
MONITOR="$BUILD_DIR/qemu-monitor.sock"
PPM="$BUILD_DIR/desktop.ppm"
PNG="$BUILD_DIR/desktop.png"

mkdir -p "$BUILD_DIR"
rm -f "$SERIAL_IN" "$SERIAL_OUT" "$SERIAL_LOG" "$MONITOR" "$PPM" "$PNG"

echo "[1/4] Building compiler..."
[ -x "$IN" ] || cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"

echo "[2/4] Compiling kernel..."
NASM="${NASM:-nasm}"
"$NASM" -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"
[ "$(wc -c < "$BUILD_DIR/trampoline.bin")" -eq 4096 ] || { echo "trampoline size error" >&2; exit 1; }
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel-entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/kernel.bin"

echo "[3/4] Capturing desktop..."
mkfifo "$SERIAL_IN" "$SERIAL_OUT"
qemu-system-x86_64 -kernel "$BUILD_DIR/kernel.bin" -m 256M -no-reboot \
  -vga std -display none -serial "pipe:$SERIAL_BASE" \
  -monitor "unix:$MONITOR,server,nowait" -daemonize

timeout 30 cat "$SERIAL_OUT" > "$SERIAL_LOG" &
CATPID=$!
for _ in $(seq 1 200); do
  grep -qF "space interactive shell" "$SERIAL_LOG" 2>/dev/null && break
  sleep 0.1
done
grep -qF "space interactive shell" "$SERIAL_LOG" || { echo "shell did not start" >&2; exit 1; }

printf 'desktop\n' > "$SERIAL_IN"
for _ in $(seq 1 100); do
  grep -qF "space: compositor running" "$SERIAL_LOG" 2>/dev/null && break
  sleep 0.1
done
grep -qF "space: compositor running" "$SERIAL_LOG" || { echo "desktop did not start" >&2; exit 1; }

for _ in $(seq 1 200); do
  grep -qF "space: compositor frame ready" "$SERIAL_LOG" 2>/dev/null && break
  sleep 0.1
done
grep -qF "space: compositor frame ready" "$SERIAL_LOG" || { echo "desktop did not paint" >&2; exit 1; }

for key in f e t c h ret; do
  printf 'sendkey %s\n' "$key" | nc -U "$MONITOR" >/dev/null
  sleep 0.5
done
sleep 5
printf 'screendump %s\n' "$PPM" | nc -U "$MONITOR" >/dev/null
sleep 1
printf '\033' > "$SERIAL_IN"
for _ in $(seq 1 100); do
  grep -qF "space: compositor exited" "$SERIAL_LOG" 2>/dev/null && break
  sleep 0.1
done
grep -qF "space: compositor exited" "$SERIAL_LOG" || { echo "desktop did not exit" >&2; exit 1; }
printf 'halt\n' > "$SERIAL_IN"
if [ -S "$MONITOR" ]; then printf 'quit\n' | nc -U "$MONITOR" >/dev/null || true; fi
kill "$CATPID" 2>/dev/null || true
rm -f "$SERIAL_IN" "$SERIAL_OUT" "$MONITOR"

echo "[4/4] Checking pixels..."
python3 - "$PPM" "$SPACE_DIR" <<'PY'
from collections import Counter
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont

data = Path(sys.argv[1]).read_bytes()
parts = []
i = 0
while len(parts) < 4:
    j = data.find(b"\n", i)
    line = data[i:j].strip()
    i = j + 1
    if line and not line.startswith(b"#"):
        parts.extend(line.split())

if parts[0] != b"P6" or int(parts[1]) != 1920 or int(parts[2]) != 1080:
    raise SystemExit("unexpected screendump format")

pixels = data[i:]
counts = Counter(tuple(pixels[n:n + 3]) for n in range(0, len(pixels), 3))
width = int(parts[1])
height = int(parts[2])
area = width * height

# Palette from current display.in:
#   COMP-COLOR-DESKTOP  0x0B0909 = (11,9,9)
#   COMP-COLOR-PANEL    0x1B1818 = (27,24,24)
#   FB-COLOR-GREEN      0x00FF00 = (0,255,0)
#   COMP-COLOR-TERM-TEXT 0xF5F4F4 = (245,244,244)
#   COMP-COLOR-TERM-BG  0x151519 = (21,21,25)
desktop_rgb = (11, 9, 9)
panel_rgb = (27, 24, 24)
term_rgb = (245, 244, 244)
term_bg_rgb = (21, 21, 25)

required = {
    "desktop bg": (desktop_rgb, area // 12),
    "panel (top/taskbar)": (panel_rgb, width * 16),
    "prompt green": ((0, 255, 0), 100),
    "term bg": (term_bg_rgb, width * 40),
}
for label, (rgb, minimum) in required.items():
    found = counts[rgb]
    if found < minimum:
        raise SystemExit(f"{label} color missing: {found} < {minimum}")

# Verify fetch glyphs: count text-colored pixels in left terminal content area.
# Terminal 1 spans approx x=32..960 y=48..1032. History/output appears below
# the title strip (y > ~80). After typing 'fetch' + Enter, the info banner
# and prompt should produce many text pixels.
text_px = 0
for y in range(80, 900):
    row = y * width * 3
    for x in range(48, 900):
        c = tuple(pixels[row + x * 3:row + x * 3 + 3])
        if c in (term_rgb, (255, 255, 255), (0, 255, 0), (0, 255, 255), (248, 189, 56)):
            text_px += 1
# Exact fetch/input/output glyph checks below replace the old threshold, whose
# fully saturated pixel count depended on the legacy bitmap's stroke weight.

# Verify per-window translucency: the UTILITIES window (x 976..1920, y 48..~540)
# uses alpha=232. Check the exact dark surface blend independently, retaining
# the translucency check rather than accepting an opaque replacement.
surface = (32, 32, 39)
blend_rgb = tuple((s * 232 + d * 23 + 255) >> 8 for s, d in zip(surface, desktop_rgb))
blend_px = 0
for y in range(80, 520):
    row = y * width * 3
    for x in range(1120, 1900, 2):
        c = tuple(pixels[row + x * 3:row + x * 3 + 3])
        if c == blend_rgb:
            blend_px += 1
if blend_px < 500:
    raise SystemExit(f"translucent blend missing: {blend_px} < 500 pixels")
# Compare the complete title against a real font/layout oracle. The old
# arbitrary gray-pixel threshold described a different synthetic bitmap face.
root = Path(sys.argv[2])
title = 'TERMINAL 1'
font = ImageFont.truetype(str(root/'assets/fonts/desktop/DejaVuSans.ttf'), 14)
advances = {ord(ch):max(1,int(font.getlength(ch)+.5)) for ch in title}
bg = (48, 48, 58)
reference = Image.new('RGB', (sum(advances[ord(c)] for c in title), 16), bg)
cursor = 0
for ch in title:
    mask = Image.new('L', (16, 16))
    ImageDraw.Draw(mask).text((0, 13), ch, font=font, fill=255, anchor='ls')
    advance = advances[ord(ch)]
    box = mask.getbbox()
    if box and box[2] > advance:
        ink = mask.crop((0, 0, box[2], 16)).resize((advance, 16), Image.Resampling.LANCZOS)
        mask = Image.new('L', (16, 16)); mask.paste(ink, (0, 0))
    for y in range(16):
        for x in range(min(16, advance)):
            cov = mask.getpixel((x, y))
            color = (255, 255, 255) if cov == 255 else tuple((255*cov+c*(255-cov)+255)>>8 for c in bg)
            if cov: reference.putpixel((cursor+x, y), color)
    cursor += advance
actual_title = b''.join(pixels[((54+y)*width+44)*3:((54+y)*width+44+reference.width)*3] for y in range(16))
if actual_title != reference.tobytes():
    raise SystemExit('native title coverage/advance differs from independent FreeType oracle')
mono = ImageFont.truetype(str(root/'assets/fonts/desktop/DejaVuSansMono.ttf'), 14)
def check_terminal(text, x0, y0, foreground):
    background = (21, 21, 25)
    expected = Image.new('RGB', (len(text)*10, 16), background)
    for index, ch in enumerate(text):
        mask = Image.new('L', (16, 16))
        ImageDraw.Draw(mask).text((0, 13), ch, font=mono, fill=255, anchor='ls')
        for y in range(16):
            for x in range(16):
                cov = mask.getpixel((x, y))
                if cov:
                    color = foreground if cov == 255 else tuple(
                        (src*cov+dst*(255-cov)+255)>>8 for src,dst in zip(foreground,background))
                    expected.putpixel((index*10+1+x, y), color)
    actual = b''.join(pixels[((y0+y)*width+x0)*3:((y0+y)*width+x0+expected.width)*3] for y in range(16))
    if actual != expected.tobytes():
        raise SystemExit('native terminal glyph/content oracle differs: '+text)
check_terminal('fetch', 48, 116, term_rgb)
check_terminal('SPACEOS', 48, 145, (0,255,255))
check_terminal('0.2.0', 138, 145, term_rgb)
print(f"PASS: desktop visual pixels present (text_px={text_px}, blend_px={blend_px}, exact_title_pixels={reference.width*16})")
PY

if command -v sips >/dev/null 2>&1; then
  sips -s format png "$PPM" --out "$PNG" >/dev/null
  echo "  screenshot: $PNG"
else
  echo "  screenshot: $PPM"
fi
