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

if grep -nE 'invoke1\(load64\(0x4060\)' \
  components/*.in kernel/*.in >/dev/null; then
  fail "kernel still invokes published cr3_write at 0x4060"
fi

if grep -nE 'required & \(-1 \^ realm-grants\)' \
  components/process.in >/dev/null; then
  fail "sci-load-file uses realm-grants instead of SCI-GUEST-GRANTS"
fi

# sys-cap-mint must stay a stub that denies userspace minting, and every
# gated syscall must keep its own capability guard inside its function —
# a file-wide match would let one syscall's guard satisfy another's check.
python3 - "$SPACE_DIR/components/syscall.in" <<'PY' || fail "syscall capability guards are missing or file-wide only"
import pathlib, re, sys

text = pathlib.Path(sys.argv[1]).read_text()


def body(name: str) -> str | None:
    pattern = "fn " + re.escape(name) + r"\([^)]*\) -> \w+ \{(.*?)\n\}"
    m = re.search(pattern, text, re.S)
    return m.group(1) if m else None


def check(label: str, ok: bool) -> None:
    if not ok:
        print(f"  missing: {label}", file=sys.stderr)
        sys.exit(1)


m = re.search(r"fn sys-cap-mint\([^)]*\) -> Int \{\n  return -1\n\}", text)
check("sys-cap-mint returns -1", bool(m))
m = re.search(r"fn sys-cap-revoke\([^)]*\) -> Int \{\n  return -1\n\}", text)
check("sys-cap-revoke returns -1", bool(m))

serial_guarded = ("sys-write", "sys-read")
for fn in serial_guarded:
    b = body(fn)
    check(f"{fn} exists", b is not None)
    check(f"{fn} consults cap-serial", "cap-require(cap-serial())" in b)

graph_guarded = ("sys-chan-create", "sys-chan-send", "sys-chan-recv", "sys-chan-close")
for fn in graph_guarded:
    b = body(fn)
    check(f"{fn} exists", b is not None)
    check(f"{fn} consults cap-graph", "cap-require(cap-graph())" in b)
PY

if ! grep -qF "clone the 4 GiB identity map" architecture.md; then
  fail "architecture.md no longer states that kernel-linked services clone the 4 GiB identity map"
fi

echo "PASS: architecture boundaries"
