#!/usr/bin/env bash
# Host-side architecture boundary gate. Uses grep (available on GitHub
# runners); do not depend on ripgrep.
set -euo pipefail

SPACE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SPACE_DIR"

fail() {
  echo "$1" >&2
  exit 1
}

if grep -nE 'store64\([^)]*cap-info \+ (0|8), (cap-count|cap-table-base)' \
  components/*.in kernel/*.in >/dev/null; then
  fail "component startup ABI exposes the kernel capability table"
fi

if grep -nE 'sci-(load|volume-rpc|load-runtime-component)\([^)]*(0x180000|0x190000|0x1a0000|0x1b0000|0x1e0000|0x220000)' \
  kernel/*.in components/*.in >/dev/null; then
  fail "kernel component loading bypasses the boot image table"
fi

if grep -nE 'domain-map\([^)]*, 0x7\)' \
  components/sci-loader.in components/process.in >/dev/null; then
  fail "SCI mapping bypasses executable/data permission helpers"
fi

python3 - "$SPACE_DIR/components/syscall.in" <<'PY' || fail "userspace capability minting is enabled"
import pathlib, re, sys
text = pathlib.Path(sys.argv[1]).read_text()
if not re.search(r"fn sys-cap-mint\([^)]*\) -> Int \{\n  return -1\n\}", text):
    sys.exit(1)
PY

echo "PASS: architecture boundaries"
