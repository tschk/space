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

## Memory model (OS, volume, apps)

**Rule:** User code never runs from NVMe/SparkFS block storage directly. Persistent bytes → **copy into RAM** → execute or map.

| Tier | What | Today | Target |
|------|------|--------|--------|
| Kernel | boot image | Loaded by bootloader; heap from `0x300000` | — |
| Volume | SparkFS | **mem:** `sf_mem_disk` 1 MiB in RAM. **nvme:** per-block ATA read/write | NVMe: heap **block cache** |
| Files | apps, data | `sparkfs_pread` → caller buffer | VFS + optional preload |
| Running apps | SCI / ELF | Read image to `load_addr` on heap → `domain_map` → `invoke1` | Dedicated **load arena** |
| Boot blob | `0x180000` | Optional SCI in RAM before FS | Keep separate from volume |

**Memdisk:** whole OS tree lives in RAM (`sf_mem_disk`); fast, ephemeral on reset.

**NVMe:** tree on device; kernel + **relevant apps** still loaded into RAM before run (same SCI/exec path).

**Apps you run:** shell/linux open+read (buffers), `sci_load_file` / execve (full image in RAM), compositor assets → read then blit (future).

### Phases

- **P1** Load arena for SCI/exec (not `heap_next` between memdisk and guests).
- **P2** NVMe block cache in `sf_read_block`/`sf_write_block`.
- **P3** Boot log: mem volume address or nvme + cache stats.
- **P4** `vfs_open` path strdup.

## Agent handoff (copy with task)

**Repo:** `/Users/undivisible/projects/space` — read `AGENTS.md`. Compiler only if generic freestanding need; else Space-only.

**Already done:** P0 VFS on SparkFS (`kernel/vfs.in`, `sparkfs_pread`/`pwrite` in `fs2_file.in`, `linux.in` stat/execve/mmap).

**Do in order (one PR or series):**

1. **P1 Load arena** — `memory.in` or `process.in`: `load_arena_alloc(size)` below memdisk reservation; `sci_load_file` + `linux_sys_execve` use it instead of raw `heap_next` for guest images. Acceptance: `check-qemu-boot.sh` PASS; serial still shows SCI + linux hello.txt.
2. **P2 NVMe block cache** — only when `sf_mem_disk == 0`; small fixed N-entry cache in `fs2_block.in`. Acceptance: boot PASS on QEMU (no nvme ok); no regression memdisk path.
3. **P3 Boot log** — after `fs_init`, print mem volume base (`sf_mem_disk`) or `sparkfs nvme`.
4. **P4 vfs_open strdup** — copy pathname to heap on open; store copy in fd slot 0.

**Touch:** `kernel/memory.in`, `kernel/process.in`, `kernel/kernel-root.in` (sci_load), `kernel/linux.in`, `kernel/fs2_block.in`, `kernel/vfs.in`, `kernel/fs2_layout.in` (sizes if memdisk grows).

**Verify every phase:**
```bash
cd /Users/undivisible/projects/space
git diff --check
bash scripts/check-qemu-boot.sh
```

**Do not:** change inauguration package paths; revive `v86-kernel.in` FS; claim full OS product.

## Follow-ups (not done)

- Path copies in FD table for dynamic paths (alloc+cstr_copy on open) — **P4 above**.
- `sci_load_file` could use VFS fds instead of direct sparkfs (optional).
- Journal recovery tests, larger mem disk, trim dead `v86-kernel.in` FS from tree or move to `examples/`.