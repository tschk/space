#!/usr/bin/env bash
set -euo pipefail

SPACE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SPACE_DIR"

if rg -n 'store64\([^)]*cap-info \+ (0|8), (cap-count|cap-table-base)' components kernel --glob '*.in'; then
  echo "component startup ABI exposes the kernel capability table" >&2
  exit 1
fi

if rg -n 'sci-(load|volume-rpc|load-runtime-component)\([^\n]*(0x180000|0x190000|0x1a0000|0x1b0000|0x1e0000|0x220000)' kernel components --glob '*.in'; then
  echo "kernel component loading bypasses the boot image table" >&2
  exit 1
fi

if rg -n 'domain-map\([^\n]*, 0x7\)' components/sci-loader.in components/process.in; then
  echo "SCI mapping bypasses executable/data permission helpers" >&2
  exit 1
fi

if ! rg -Uq 'fn sys-cap-mint\([^)]*\) -> Int \{\n  return -1\n\}' components/syscall.in; then
  echo "userspace capability minting is enabled" >&2
  exit 1
fi

echo "PASS: architecture boundaries"
