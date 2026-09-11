#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
export BUILD_DIR="${BUILD_DIR:-/tmp/space-check-all}"
mkdir -p "$BUILD_DIR"

bash "$SCRIPT_DIR/check-spdp-protocol.sh"
bash "$SCRIPT_DIR/check-architecture-boundaries.sh"
bash "$SCRIPT_DIR/check-sci-contract.sh"
KERNEL_BIN="${KERNEL_BIN:-$BUILD_DIR/kernel.bin}"
if [ ! -f "$KERNEL_BIN" ]; then
  KERNEL_BIN=""
fi
if [ -n "$KERNEL_BIN" ]; then
  KERNEL_BIN="$KERNEL_BIN" bash "$SCRIPT_DIR/check-qemu-boot.sh"
  KERNEL_BIN="$KERNEL_BIN" bash "$SCRIPT_DIR/check-audit-fixes.sh"
else
  bash "$SCRIPT_DIR/check-qemu-boot.sh"
  bash "$SCRIPT_DIR/check-audit-fixes.sh"
fi
echo "PASS: check-all"
