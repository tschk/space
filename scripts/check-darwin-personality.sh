#!/usr/bin/env bash
# check-darwin-personality.sh — static markers for Darwin BSD/Mach subset personality.
# Honest: not full XNU; greps demo complete + open/write markers in source.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
SRC="$SPACE_DIR/components/darwin.in"

[ -f "$SRC" ] || { echo "MISSING: $SRC" >&2; exit 1; }

for marker in \
  "darwin: personality demo complete" \
  "darwin: open(darwin-hello.txt" \
  "darwin: write(fd, content," \
  "darwin: write(1, msg," \
  "darwin: unlink(darwin-hello.txt)" \
  "darwin: kill(invalid)" \
  "DARWIN-SYS-OPEN = 5" \
  "DARWIN-SYS-WRITE = 4" \
  "DARWIN-SYS-KILL = 37" \
  "fn darwin-dispatch(port: Int, num: Int, a0: Int, a1: Int, a2: Int, a3: Int)"; do
  grep -qF "$marker" "$SRC" || { echo "MISSING: $marker" >&2; exit 1; }
done

echo "PASS"
