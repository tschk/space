#!/usr/bin/env bash
#
# check-tcp.sh — Boot with e1000 user net, run shell `tcp`, expect handshake.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=inauguration-dir.sh
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-tcp}"
IN="${IN:-$INAUG_DIR/in-cli/target/release/in}"

mkdir -p "$BUILD_DIR"

echo "[1/3] Building compiler, trampoline, kernel..."
[ -x "$IN" ] || cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"
nasm -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel-entry \
  --emit boot --trampoline "$BUILD_DIR/trampoline.bin" \
  --out "$BUILD_DIR/kernel.bin" >/dev/null

# Host TCP endpoint for guest 10.0.2.2:8080 (QEMU SLIRP host gateway).
python3 - "$BUILD_DIR/tcp-host.pid" <<'PY' &
import socket, sys, os
pid_path = sys.argv[1]
srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("0.0.0.0", 8080))
srv.listen(5)
srv.settimeout(60.0)
with open(pid_path, "w") as f:
    f.write(str(os.getpid()))
try:
    while True:
        try:
            c, _ = srv.accept()
        except socket.timeout:
            break
        try:
            c.recv(1024)
            c.sendall(b"HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\nok")
        finally:
            c.close()
except Exception:
    pass
finally:
    srv.close()
PY
HOST_PID=$!
cleanup() {
  kill "$HOST_PID" 2>/dev/null || true
  wait "$HOST_PID" 2>/dev/null || true
  if [ -f "$BUILD_DIR/tcp-host.pid" ]; then
    kill "$(cat "$BUILD_DIR/tcp-host.pid")" 2>/dev/null || true
    rm -f "$BUILD_DIR/tcp-host.pid"
  fi
}
trap cleanup EXIT

for _ in $(seq 1 50); do
  [ -f "$BUILD_DIR/tcp-host.pid" ] && break
  sleep 0.05
done

echo "[2/3] Booting with e1000 user net, running tcp..."
rm -f "$BUILD_DIR/serial.log" "$BUILD_DIR/tcp.in"
printf 'help\rtcp\rhalt\r' > "$BUILD_DIR/tcp.in"
qemu-system-x86_64 \
  -kernel "$BUILD_DIR/kernel.bin" -m 256M \
  -netdev user,id=n0 -device e1000,netdev=n0 \
  -serial stdio -display none -no-reboot < "$BUILD_DIR/tcp.in" > "$BUILD_DIR/serial.log" 2>/dev/null &
QPID=$!
for _ in $(seq 1 500); do
  if grep -qF "tcp: established" "$BUILD_DIR/serial.log" 2>/dev/null \
    && grep -qF "tcp: connect ok" "$BUILD_DIR/serial.log" 2>/dev/null; then
    break
  fi
  if grep -qF "tcp: connect failed" "$BUILD_DIR/serial.log" 2>/dev/null; then
    break
  fi
  kill -0 "$QPID" 2>/dev/null || break
  sleep 0.1
done
sleep 0.5
kill "$QPID" 2>/dev/null || true
wait "$QPID" 2>/dev/null || true
rm -f "$BUILD_DIR/tcp.in"

echo "--- tcp serial ---"
sed -n '/space> tcp/,/space>/p' "$BUILD_DIR/serial.log" 2>/dev/null || cat "$BUILD_DIR/serial.log"
echo "------------------"

if grep -qF "tcp: established" "$BUILD_DIR/serial.log" \
  && grep -qF "tcp: connect ok" "$BUILD_DIR/serial.log"; then
  echo "[3/3] PASS: TCP handshake + shell connect ok"
  grep -E "tcp: " "$BUILD_DIR/serial.log" || true
  exit 0
fi

echo "[3/3] FAIL: no tcp: established / connect ok"
grep -E "tcp: " "$BUILD_DIR/serial.log" || true
exit 1
