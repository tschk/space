#!/usr/bin/env bash
# Resolve Inauguration checkout: INAUGURATION_DIR, vendor/inauguration submodule, or ../inauguration.
inauguration_dir() {
  local space_dir="$1"
  if [ -n "${INAUGURATION_DIR:-}" ]; then
    printf '%s\n' "$INAUGURATION_DIR"
    return 0
  fi
  if [ -d "$space_dir/vendor/inauguration/in-cli" ]; then
    printf '%s\n' "$space_dir/vendor/inauguration"
    return 0
  fi
  printf '%s\n' "$(cd "$space_dir/.." && pwd)/inauguration"
}