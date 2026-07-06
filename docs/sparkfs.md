# SparkFS — Space nanokernel filesystem

SparkFS replaces the current flat 64-entry table with a small, modern,
block-structured filesystem. It is designed for the Space kernel: simple
enough to audit, rich enough to support a real directory tree, regular
files, and crash-safe metadata updates.

## Goals

- Hierarchical directories with path lookup.
- 256-byte inodes with metadata (size, mode, timestamps, type).
- 4 KiB blocks; files up to ~4 GB via single indirect blocks.
- Long filenames (up to 255 bytes) stored in directory entries.
- Block allocation bitmap with free-space tracking.
- Metadata journaling for format, create, write, delete, and rename.
- Compatible with the existing NVMe/ATA sector wrappers (`ata_read_sector`,
  `ata_write_sector`). The disk is still accessed as 512-byte sectors, but
  all on-disk structures are aligned to 4 KiB block boundaries.

## Non-goals

- POSIX permissions and full Unix semantics (uid/gid are stored but not
  enforced by the nanokernel).
- Hard links and symbolic links in the first version.
- Multi-device volumes, snapshots, compression, or encryption.

## On-disk layout

Sectors are 512 bytes. Blocks are 8 sectors = 4096 bytes. Block numbers
are sector numbers divided by 8.

| Region | Start (block) | Size |
|--------|--------------|------|
| Superblock | 0 | 1 block |
| Block bitmap | 1 | `bitmap_blocks` |
| Journal | `1 + bitmap_blocks` | `journal_blocks` |
| Inode table | `1 + bitmap_blocks + journal_blocks` | `inode_table_blocks` |
| Data area | after inode table | remainder |

### Superblock (4096 bytes)

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | magic: `0x53504146` ("SPAF") |
| 4 | 4 | version: 1 |
| 8 | 4 | block_size: 4096 |
| 12 | 8 | total_blocks |
| 20 | 4 | inode_count |
| 24 | 8 | bitmap_start_block |
| 32 | 8 | journal_start_block |
| 40 | 8 | inode_table_start_block |
| 48 | 8 | data_start_block |
| 56 | 4 | root_inode |
| 60 | 4 | journal_sequence |
| 64 | 4 | reserved1 |
| 68 | 4 | reserved2 |
| 72 | 16 | uuid |
| 88 | 4008 | reserved (zeroed) |

### Inode (256 bytes)

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | type (1=file, 2=dir) |
| 4 | 4 | mode |
| 8 | 4 | uid |
| 12 | 4 | gid |
| 16 | 8 | size |
| 24 | 8 | blocks_used |
| 32 | 8 | ctime |
| 40 | 8 | mtime |
| 48 | 8 | atime |
| 56 | 4 | nlink |
| 60 | 4 | reserved |
| 64 | 96 | direct_block[12] (8 bytes each) |
| 160 | 8 | single_indirect_block |
| 168 | 8 | double_indirect_block |
| 176 | 80 | reserved |

Maximum file size: 12 direct blocks + 1024 indirect blocks = 1036 blocks,
about 4 MiB with the first version. Double-indirect support can be added later
for larger files.

### Directory entry

Directory entries live in data blocks. Each entry is 8-byte aligned.

| Field | Size | Notes |
|-------|------|-------|
| inode | 4 | inode number |
| name_len | 1 | length of name |
| type | 1 | 1=file, 2=dir |
| name | name_len | not null-terminated |
| padding | 0..7 | align total to 8 bytes |

The last entry in a directory block has `inode = 0` and `name_len = 0`.

### Journal

Each journal entry is 64 bytes:

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | sequence |
| 4 | 4 | op (1=create, 2=write, 3=delete, 4=rename) |
| 8 | 4 | inode |
| 12 | 4 | parent_inode |
| 16 | 4 | name_len |
| 20 | 12 | name (padded, up to 12 bytes inline) |
| 32 | 8 | old_size |
| 40 | 8 | new_size |
| 48 | 8 | old_block |
| 56 | 8 | new_block |

On mount, the journal is replayed to restore incomplete metadata operations.
After replay, the journal is cleared and a fresh superblock is written.

## Runtime state

All on-disk state is kept in a few globals:

- `sf_super`: 4096-byte in-memory superblock copy.
- `sf_bitmap`: in-memory block bitmap.
- `sf_inodes`: in-memory inode table (size = inode_count * 256).
- `sf_block_buf`: one 4 KiB scratch block for disk I/O.
- `sf_dirty_blocks`: dirty bitmap blocks to flush on sync.
- `sf_dirty_inodes`: dirty inode table blocks to flush on sync.

## API

```in
fn sparkfs_init() -> void
fn sparkfs_format() -> void
fn sparkfs_sync() -> void
fn sparkfs_list(path: Int, port: Int) -> void
fn sparkfs_create(path: Int, is_dir: Int) -> Int
fn sparkfs_read(path: Int, buf: Int, max: Int) -> Int
fn sparkfs_write(path: Int, buf: Int, size: Int) -> Int
fn sparkfs_delete(path: Int) -> Int
fn sparkfs_rename(src: Int, dst: Int) -> Int
fn sparkfs_stat(path: Int, stat: Int) -> Int
```

A thin compatibility shim maps the old `fs_*` names to the new SparkFS
functions so the shell and process loader keep working without changes.

## Implementation plan

1. Add `kernel/fs2.in` with on-disk constants and low-level helpers:
   `sf_read_block`, `sf_write_block`, `sf_alloc_block`, `sf_free_block`,
   `sf_read_inode`, `sf_write_inode`, `sf_set_bitmap`, `sf_test_bitmap`.
2. Implement inode-level block lookup (`sf_inode_block`, `sf_set_inode_block`).
3. Implement directory read/append/entry lookup (`sf_dir_find`, `sf_dir_add`,
   `sf_dir_remove`).
4. Implement path resolution (`sf_lookup_path`).
5. Implement create, read, write, delete, list, and rename.
6. Implement journal record/replay and `sparkfs_sync`.
7. Wire the old `fs_*` API to SparkFS.
8. Update `fs_format` and `fs_init` callers; remove the flat table.
9. Add a shell `fsck` command for manual check/repair.
