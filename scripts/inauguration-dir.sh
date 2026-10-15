#!/usr/bin/env bash
# Resolve an Inauguration compiler for Space builds. Preference order:
#   1. $INAUGURATION_DIR — explicit checkout (set by CI)
#   2. sibling checkout at ../inauguration — compiler development
#   3. crates.io — `cargo install inauguration --locked`, exposed under
#      .inauguration/ with the in-cli/target/release layout the build
#      scripts expect. There is no vendor submodule; the compiler is a
#      published crate (https://crates.io/crates/inauguration).
inauguration_dir() {
  local space_dir="$1"
  if [ -n "${INAUGURATION_DIR:-}" ]; then
    printf '%s\n' "$INAUGURATION_DIR"
    return 0
  fi
  if [ -d "$space_dir/../inauguration/in-cli" ]; then
    printf '%s\n' "$(cd "$space_dir/.." && pwd)/inauguration"
    return 0
  fi
  local shim="$space_dir/.inauguration"
  if ! [ -x "$shim/in-cli/target/release/in" ]; then
    if ! command -v cargo >/dev/null 2>&1; then
      echo "inauguration: need \$INAUGURATION_DIR, ../inauguration, or 'cargo install inauguration'" >&2
      return 1
    fi
    cargo install -q inauguration --locked || return 1
    local bin
    bin="$(command -v in)" || return 1
    mkdir -p "$shim/in-cli/target/release"
    ln -sf "$bin" "$shim/in-cli/target/release/in"
  fi
  printf '%s\n' "$shim"
}
