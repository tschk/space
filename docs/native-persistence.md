# Native application persistence check

`scripts/check-native-persistence.py` drives the actual `notes` and `sum`
applications on Space across three independent QEMU processes sharing one
owned raw NVMe image. It requires a built standard image and a new/empty output
directory; it never accepts a host disk or overwrites an existing raw file.

```sh
INAUGURATION_DIR=/path/to/inauguration BUILD_DIR=/tmp/space-persistence-build \
  bash scripts/build-images.sh --variant standard
python3 scripts/check-native-persistence.py \
  --in /path/to/inauguration/in-cli/target/release/in \
  --image /tmp/space-persistence-build/standard.bin --out /tmp/space-persistence
```

The first boot explicitly formats the test's newly created blank 64 MiB image
through Space's shell, opens the actual notes editor, types the pinned text,
saves, closes and reopens it. Every editor redraw is compared byte for byte.
A separate `sum` process must report the exact byte count and host-computed
CRC32. The VM halts, the host closes QEMU, and a read-only SparkFS parser locates
`notes.txt` through the actual superblock/root directory/inode and checks exact
persisted bytes. No host-side file seed supplies that content.

The second boot mounts the same raw disk without formatting, verifies reopened
content, edits the saved note using the actual End key and appends ` v2`, then
saves and checks both the separate-process checksum and raw disk content again.
The third boot verifies that updated content after another VM restart. QEMU uses
`cache=writethrough`; the owned disk and all boot logs/input traces/expected
content/file hashes are retained for review. The checker requires the actual
NVMe-ready marker and independently verifies bytes on the raw disk, so a RAM
filesystem fallback cannot pass.

This is native application and real disk persistence evidence. It does not
certify foreign application file APIs, hardware power-loss durability, journal
replay, crash consistency, user/domain isolation, multi-user permissions or
async Volume SCI behavior. The standard image uses the current direct SparkFS
NVMe path. The read-only oracle covers current root directory entries and
inline/direct/single-indirect file data; it rejects unsupported layouts rather than guessing.

Fresh 2026-10-24 (Australia/Melbourne) results: all three boots passed at
`/tmp/space-native-persistence-storage-final/report.json` using frozen Inauguration
0.9.324 after the storage fixes below; the first independent run passed at
`/tmp/space-native-persistence-baseline/report.json`. The original save was 63
bytes; its edited form was 66 bytes, with persisted SHA256
`933f0ebdb46e99a74a91e69b9c8c34bab5c63ae24befaf9e09b3549f9bb46c9b` after both
later boots. The initial small inline-file checkpoint needed no filesystem changes; later
large-file testing exposed and repaired the allocation/truncation defects below. The check remains a fresh-run gate; a saved receipt does not replace
rerunning it after runtime/storage changes.

A negative control at `/tmp/space-native-persistence-no-nvme/report.json`
removes the emulated NVMe device from the QEMU invocation. The guest reaches its
shell using the RAM fallback, but this checker correctly fails with `real NVMe
backend unavailable` before formatting or editing. The owned raw disk's initial
and final hashes remain identical. The control wrapper is retained at
`/tmp/space-persistence-no-nvme-qemu`; it is a test failure control, not a supported
persistence result.

## Multi-block and indirect files

`check-native-large-files.py` adds a separate trusted native filesystem
regression over actual NVMe, with no foreign application compatibility claim:

```sh
python3 scripts/check-native-large-files.py \
  --in /path/to/inauguration/in-cli/target/release/in --out /tmp/large-files
python3 scripts/check-sparkfs-block-slots.py \
  --in /path/to/inauguration/in-cli/target/release/in
```

It explicitly formats an owned blank image and writes a deterministic 57,391
byte file, forcing direct and single-indirect allocation. It compares every
byte, patches 37 bytes across the first 4 KiB boundary, checks a partial read,
then grows one 48-byte inline file with a positional append and another with a
whole-file replacement. Every operation checks the actual raw superblock remains
intact. It also fills sparse gaps with zero bytes and repeats sparse extensions
without allocating fresh scratch after warmup. A second QEMU process mounts the
same disk, verifies the existing files, allocates another indirect file, then
rechecks the earlier files. A third process mounts again and verifies all files.
A host read-only SparkFS parser independently
checks every persisted byte after each boot. Input/expected bytes enter guest
RAM through QEMU's loader; only Space's filesystem writes the disk.

Actual original jq input testing exposed the underlying defect: an empty inode
slot returned zero while file writers allocate only for a negative result. A
new multi-block write consequently targeted block zero, corrupting the
superblock. The pre-fix NVMe regression reproduces that failure at
`/tmp/space-native-large-files-baseline/report.json`. Zero direct and indirect
slots now return the documented unallocated result, invalid slot indices and
zero block installation are refused, and directory growth consumes the same
contract. Inline promotion preserves the old bytes and clears every old inline
word before those fields become block pointers, for positional appends and
whole-file replacement alike.

The owning-function check covers direct/indirect empty slots, final slot/bounds,
read failure and zero-block refusal across default, lean and harden profiles.
Its baseline source control fails on the first empty direct slot. Earlier
filesystem initialization and Volume preservation checks also pass unchanged.
The real-disk final proof is retained at
`/tmp/space-native-large-files-pwrite-final/report.json`; its logs and generated kernel
sources retain the runtime path and exact assertions rather than accepting a
host model as persistence evidence.


## Allocation ownership and exact replacement

A separate actual remount control at
`/tmp/space-native-large-files-bitmap-baseline/report.json` reproduced a second
bug: new files reused live blocks because allocation bitmap reservations had
not reached disk. Allocation now persists its reservation before zeroing and
publishing the block, and restores the caller's zero-buffer contract after the
bitmap flush. Reserved blocks may leak on an interrupted operation; this is
ordered allocation, not a journal or a claim of crash-atomic replacement.

Whole-file replacement now detaches unused direct/indirect pointers, commits
the exact inode size, and only then releases those block reservations. A retained
reclamation list and zero-fill buffer follow SparkFS's existing synchronous,
nonreentrant owner contract. Tests shrink a 57,391-byte file to 53,255 bytes
(retaining its indirect table), then 8,193 bytes (dropping that table), reextend
it with a positional write, and truncate to zero. Three large/zero cycles must
return exactly the same number of free blocks without heap growth. A final
32-byte inline shrink survives two remounts and another file's allocations.

The same gate creates, reads and deletes `/cycle.bin` repeatedly. The original
path/name/directory-result scratch leaked 1,056 heap bytes per cycle, reproduced
at `/tmp/space-native-create-delete-baseline/report.json`. Retaining name and
parent scratch exposed a remaining 16-byte directory-removal allocation at
`/tmp/space-native-large-files-all-final/report.json`. One owned workspace per
operation now bounds this scratch after warmup; the exact heap and free-block
invariants pass in the final three-boot receipt. These global workspaces do not
establish concurrent filesystem request support.

Unchanged initialization preservation, Volume preservation and block-slot
checks passed again after replacement changes. Their logs are
`/tmp/space-sparkfs-init-storage-final.log`,
`/tmp/space-volume-preservation-storage-final.log`, and
`/tmp/space-block-slots-storage-final.log`.


Positional writes preserve suffix bytes when a short prefix overwrites a large
file, and a zero-byte write past EOF does not grow it or reserve blocks. Bounds
are checked before adding offset and count; negative values, the file limit
and integer overflow are rejected. Data/block-pointer/inode I/O failures return
an error. A precise control restoring only the previous prefix-conversion
condition fails on real NVMe with `got 32 expected 57391`, retained at
`/tmp/space-native-pwrite-prefix-control/report.json`; the unchanged expanded
suite passes with the correction. `--file-source` accepts an explicit alternate
SparkFS file owner for such isolated controls and records its source hash.
