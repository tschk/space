#!/usr/bin/env bash
# Run all OS personality quality gates (SCI contract + Windows + Darwin QEMU demos + trusted Mach-O fixture).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> SCI contract"
bash "$SCRIPT_DIR/check-sci-contract.sh"

echo "==> Windows personality (QEMU)"
bash "$SCRIPT_DIR/check-windows-personality.sh"

echo "==> Darwin personality (QEMU)"
bash "$SCRIPT_DIR/check-darwin-personality.sh"

echo "==> Darwin trusted Mach-O fixture (QEMU)"
bash "$SCRIPT_DIR/check-darwin-macho.sh"

echo "==> Foreign ELF/Mach-O/PE fixtures (QEMU)"
bash "$SCRIPT_DIR/check-foreign-syscalls.sh"

echo "PASS: all personality gates green"
