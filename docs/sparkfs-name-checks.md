# SparkFS directory-name boundaries

SparkFS's existing on-disk directory entry is 32 bytes: an 8-byte header and
24 bytes of name storage. A name now has to fit exactly. Creation and direct
directory insertion reject a 25-byte component instead of publishing a
24-byte alias and reporting success. The entry format is unchanged.

`sf-path-name-valid(path)` returns 1 when every component fits 24 bytes and the
complete NUL-terminated path fits the existing 1,023-byte normalization output
bound; otherwise it returns 0. Lookup, parent resolution, creation and rename
validate before allocating scratch or mutating ownership. Parent scratch now
holds 1,024 bytes, so a deep path exceeding 255 total bytes remains valid when
each component fits. `SF-NAME-MAX` remains the existing scratch-buffer capacity;
`SF-DIR-NAME-MAX` expresses the actual on-disk component limit. This change does
not alter normalization or the interpretation of relative paths.

Personalities translate this native representability predicate into their own
error vocabulary: Linux ENAMETOOLONG (36), Darwin ENAMETOOLONG (63) and Windows
ERROR_FILENAME_EXCED_RANGE (206). Native filesystem APIs retain their existing
success/error return convention; the filesystem does not adopt those foreign
errno values.

Creation also checks the directory insertion result. Before initializing a
free inode it saves that inode's exact prior bytes in retained owner scratch;
a refused insertion restores the inode in memory and on disk and returns an
error. No file data blocks belong to this fresh inode. This covers ordinary
prepublication refusal, not atomic recovery from arbitrary partial hardware
writes, failed rollback I/O or power loss. SparkFS remains synchronous and
nonreentrant with its existing global buffers; this is not journaling.

```sh
python3 scripts/check-sparkfs-names.py \
  --in /path/to/inauguration/in-cli/target/release/in \
  --out /tmp/sparkfs-names
```

The checker creates its own blank 64 MiB NVMe image and boots three independent
QEMU processes. It requires the actual NVMe backend and refuses RAM fallback.
The first boot explicitly formats the owned disk, creates a 24-byte filename,
then creates twelve nested directories and a file through a 325-byte path.
It writes and reopens exact content. A later boot reads that content, deletes
and recreates the deep file; the third boot reopens both files again.

Before each refusal, the guest snapshots every inode, the allocation bitmap
and every directory data block. Invalid create, read, stat, delete, rename,
direct directory insertion and oversized parent components must leave those
bytes and the heap pointer unchanged. A generated test-only directory wrapper
also refuses insertion before mutation, proving that creation propagates the
error and restores its selected free inode. Production code gains no fault
injection switch.

After each boot, an independent read-only host parser follows all thirteen
path components through raw directory entries and checks exact persisted
content. It checks the total live inode count and all data-block reservations,
so an orphan inode or leaked allocation cannot hide behind a failed pathname
lookup. The standard root's existing boot self-test creates a 40-byte
`test.sci` after remount; boots B/C explicitly validate and account for that
file rather than accepting an unexplained extra inode.

Fresh 2026-10-24 (Australia/Melbourne) evidence with frozen Inauguration 0.9.324:

- `/tmp/space-sparkfs-names-baseline/report.json` reproduces the original bug:
  a 25-byte write reports success instead of refusal on actual NVMe.
- `/tmp/space-sparkfs-name-rollback-control/report.json` restores only the old
  behavior of ignoring the directory insertion result. The same checker fails
  with inode 15 returned instead of an error after injected refusal.
- `/tmp/space-sparkfs-names-final2/report.json` passes all three boots, with
  `source_changed_during_run: []`, exact content, 13 directory data blocks and
  no orphan inode from refusal. Commands, source hashes, raw disk and logs are
  retained with the receipt.
- `/tmp/space-native-large-files-names/report.json` passes the existing
  three-boot large-file, sparse-write, truncate, reextension and repeated
  create/delete gate unchanged.

Initialization preservation, Volume preservation and block-slot checks also
pass unchanged; their logs are `/tmp/space-sparkfs-init-names.log`,
`/tmp/space-volume-preservation-names.log` and
`/tmp/space-block-slots-names.log`. The original storage baseline remains
commit `2784860`. Intermediate harness failures are retained: the first used
an unsupported constant expression for the new maximum, a second expected
mkdir's success to be zero instead of its returned inode, and the first raw
inode-count oracle failed to account for the standard boot self-test file.
