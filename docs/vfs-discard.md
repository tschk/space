# Native EOF source and discard sink

`components/vfs.in` provides an object with immediate EOF on read, a write
result equal to the requested count, and no backing pathname or file storage.
Linux translates `/dev/null` into this object at its edge; the native constructor
contains no POSIX pathname, device number, syscall, or errno policy.

The current implementation is trusted, kernel-linked VFS scaffolding, not a
separately isolated SCI provider. Its internal entry points are excluded from
the dynamic kernel import registry. The Linux edge validates the live memory
grant, descriptor ownership, access mode, and entire guest buffer range before
calling it. Native read/write methods do not accept or access a data pointer;
they must not be mistaken for guest-memory authorization. The generic trusted
`vfs-read`/`vfs-write` dispatches this object before pathname access. No storage
grant or backing filesystem is needed. This does not establish automatic
translation of compiler component-local capability ordinals into native grants.

## Contract

- `vfs-discard-open(mode)` accepts exactly 0 (read), 1 (write), or 2 (both).
  It returns a native descriptor, -9 without a descriptor table, -22 for an
  invalid mode, or -24 when its bounded descriptor/description pool is full.
- `vfs-discard-tagged` recognizes the private tag even when its data is invalid;
  `vfs-discard-valid` validates the row, access mode and bounded shared record.
  Invalid tagged rows are refused before any ordinary pathname fallback.
- `vfs-discard-read(fd,count)` returns 0, and
  `vfs-discard-write(fd,count)` returns count. Wrong access or invalid objects
  return -9; negative counts return -22. Zero counts are supported.
- `vfs-discard-seek(fd,offset,origin)` returns 0 for origins 0, 1 and 2;
  all offsets are ignored and the shared offset stays zero. Other origins
  return -22; invalid objects return -9.
- `vfs-discard-stat(fd,output)` writes exactly 64 bytes of native metadata to
  a trusted caller-owned buffer. Invalid objects return -9 and nonpositive
  output returns -14 without writing. Arbitrary positive kernel pointers are
  not validated here; an untrusted client must never invoke this raw interface.
- `vfs-dup-file`, `vfs-close`, `vfs-read`, `vfs-write` and `vfs-lseek` support
  the object. `vfs-dup-file-into(source,target)` replaces an owned native target
  in slots 3–15, retaining the source before releasing the target. It supports
  ordinary files and discard sources, including a full descriptor pool,
  self-duplication and two aliases of the same shared description. A stream
  target releases its endpoint; stream sources use their own duplication API.

The descriptor uses private tag 4 and opaque payload 0. Each independent open
owns one record in the existing bounded shared-description pool. Duplication
retains that record; final close releases it. Native stat fields are:

| Offset | Value |
| --- | --- |
| 0, 32-bit | Native kind 3 |
| 4, 32-bit | Object mode 0666 |
| 8, 64-bit | Size 0 |
| 16, 32-bit | Link count 1 |
| 24/32/40, 64-bit | Timestamps 0 |
| 48, 64-bit | Positive shared-description slot identity |
| 56, 64-bit | Mount identity 0: not a filesystem inode |

All other output bytes are zero. Aliases have the same description identity;
independent simultaneous opens have different identities. The identity can be
reused after final close and is not a persistent filesystem inode. Linux owns
its character-device metadata and `rdev` translation.

## Verification

Run with the frozen Inauguration 0.9.324 compiler:

```sh
python3 scripts/check-vfs-discard.py --in "$IN" --out /tmp/discard-owner
python3 scripts/check-vfs-discard-runtime.py --in "$IN" --out /tmp/discard-qemu
python3 scripts/check-vfs-shared-offset.py --in "$IN"
```

The owning-source gate executes production VFS functions in default, lean and
harden profiles, isolating storage with counted stubs. The actual QEMU gate
boots the full standard root without a storage disk and executes the same
fixture against real native memory and descriptor state. Both check EOF/count,
access/count/descriptor bounds, stat fields and canaries, identities and alias
flags, self/sibling/full-pool replacement, malformed-tag refusal, 63 cycles of
open/dup/close with no heap/reference drift, and 21 stream-target replacement
cycles with released endpoint ownership. The owner gate separately replaces
ordinary-file sources and targets and asserts zero storage calls for the
entire discard-only fixture. Existing shared-offset controls remain intact.

These gates establish the native object contract. The Linux original BusyBox
background-job and CPL3 descriptor gates establish the separate consumer and
live guest-authority behavior; native tests alone do not establish those claims.
