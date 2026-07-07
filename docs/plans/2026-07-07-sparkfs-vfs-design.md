# SparkFS + VFS unification (Space kernel)

**Status:** Implemented (P0)  
**Decision:** Single on-disk store = **SparkFS** (`docs/sparkfs.md`). Linux `hello.txt` and SCI `test.sci` live on SparkFS (mem-backed disk in QEMU when NVMe absent).

## Problem

- Boot uses `fs_init()` → SparkFS (`sf_disk_ready`, mem disk or NVMe).
- `vfs.in` used legacy `fs_entry` / `fs_disk_ready` (flat table from `v86-kernel.in`, not linked in `kernel-root.in`).
- Result: `fs_write_file` wrote SparkFS bytes; `vfs_read` read wrong layout → broken Linux open/read/stat and SCI magic failures.

## Design

| Layer | Role |
|-------|------|
| **SparkFS** | Block store, inodes, paths (`sparkfs_*`, `sf_*`) |
| **VFS** | FD table; fds 0–2 = serial; fd 3+ = path pointer + offset |
| **Linux** | Syscalls → VFS + `sparkfs_stat` for stat/fstat |

### FD entry (32 bytes)

- `[0..8]` path string address (NUL-terminated, stable for process lifetime — demo uses string literals)
- `[8..16]` file offset
- `[16..24]` open flags

### New helpers (`fs2_file.in`)

- `sparkfs_pread(path, buf, max, offset)` — offset-aware read
- `sparkfs_pwrite(path, buf, count, offset)` — offset-aware write / grow

### Removed from active path

- `fs_entry`, `fs_find`, `fs_disk_ready` in vfs/linux (v86 file remains unimported reference only).

### UX

- Shell/compositor storage line: `sparkfs mem` vs `sparkfs nvme` via `nvme_ready`.

## Acceptance

- `scripts/check-qemu-boot.sh` PASS (including `linux: open(hello.txt`, `test_sci_loader: PASS`).
- `hello.txt` created via Linux `open`/`write`/`read`/`stat` on SparkFS.

## Follow-ups (not done)

- Path copies in FD table for dynamic paths (alloc+cstr_copy on open).
- `sci_load_file` could use VFS fds instead of direct sparkfs (optional).
- Journal recovery tests, larger mem disk, trim dead `v86-kernel.in` FS from tree or move to `examples/`.