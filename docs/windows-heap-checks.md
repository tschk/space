# Owned Windows process heap

`windows-command-heap-run(image,size,serial,storage,memory,line,bytes)` adds
profile 7 with `GetProcessHeap`, `HeapAlloc`, `HeapFree`, `HeapReAlloc` and
`HeapSize`, alongside the command/identity imports. It borrows a native
`cap-memory()` grant. Previous profiles keep refusing heap imports. The unchanged
original Windows SQLite, 7za and jq still do not execute.

The pinned original SQLite initializes its process heap at `0x1402c91f8`, calls
HeapAlloc with flags 0 at `0x1402b3f96` and flags 8 at `0x1402b93d5`, and calls
HeapFree at `0x1402b3f22`. This slice implements those real operations, together
with bounded realloc/size behavior. It does not replace any unresolved original
import with a successful stand-in.

## Ownership and admitted contract

Each activation owns a 256KiB arena at `0x4d000000`, below the lowest admitted
application image base. Its 64 private pages are writable, nonexecutable CPL3
mappings, tracked by the existing protected-process frame ledger. A separate
native-only frame contains 128 allocation records; it is never guest-mapped.
The process heap handle is an opaque activation token, also placed in the partial
PEB ProcessHeap field. It changes every activation. A prior activation's handle
is rejected; the token is not a privileged pointer. Exhaustion of its bounded
31-bit generation space refuses launch rather than wrapping.

Admission checks the image/imports, command line and all borrowed grants before
allocating. Missing, weak or revoked memory authority yields `-13`; malformed
arguments `-22`; unsupported images `-8`; insufficient frame reservation or token
generation exhaustion `-12`. The existing frame admission includes 67 additional
frames for the heap arena, native ledger and mapping headroom. Preparation maps
all heap pages once. Allocator calls then use only the bounded native ledger and
arena, without native heap or frame allocation.

Every heap API rechecks the live memory grant. The grant authorizes heap service
operations; revocation does not retract already mapped arena pages while the
guest runs. Teardown always releases all native and guest frames even after
revocation, guest fault or guest deadline termination.

Allocations align to 16 bytes and preserve exact requested logical size for
HeapSize. Zero-byte requests receive a distinct live allocation with size zero.
First-fit allocation reuses released intervals. New allocations are zeroed,
including when callers do not request HEAP_ZERO_MEMORY; unspecified contents
therefore never expose a previous allocation's data. Allocation failure leaves
all existing records and payloads unchanged. Supported flags are:

| API | Supported flags |
| --- | --- |
| HeapAlloc | 0, HEAP_NO_SERIALIZE (1), HEAP_ZERO_MEMORY (8), or their combination |
| HeapReAlloc | The above plus HEAP_REALLOC_IN_PLACE_ONLY (16) |
| HeapFree / HeapSize | 0 or HEAP_NO_SERIALIZE (1) |

This synchronous single-threaded profile needs no concurrent allocator lock.
HEAP_GENERATE_EXCEPTIONS and other flags are refused; no SEH is synthesized.
HeapCreate, HeapDestroy and HeapValidate remain unsupported imports.

Realloc preserves the smaller of old/new logical sizes, clears newly exposed
bytes, shrinks or grows in place when possible, and otherwise allocates/copies
before releasing the old record. An in-place-only or allocation failure leaves
the original allocation unchanged. Realloc to zero keeps a valid zero-size
allocation. Realloc of NULL/interior/unowned pointers is refused. HeapFree(NULL)
is a successful no-op with a live grant, before heap-handle/flag validation. Other
free/size calls require the exact activation heap handle and exact live allocation
start; interior, kernel and already-freed unallocated pointers are never dereferenced.
Allocation addresses can be reused; there is no per-pointer generation or
promise to distinguish an old pointer from a later allocation at the same address.

HeapAlloc/ReAlloc return NULL on failure and preserve LastError, matching the
documented allocation API contract rather than inventing an error on OOM.
HeapFree returns BOOL and HeapSize returns SIZE_T (-1 on failure); their bounded
policy errors are 5 for revoked authority, 6 for invalid heap handles and 87 for
invalid flags/allocation pointers. GetProcessHeap returns zero/error 5 after
revocation. These are declared rejection policies, not emulation of Windows heap
corruption exceptions. Released intervals remain mapped until process teardown;
this allocator does not promise hardware detection of use-after-free or accesses
past an individual allocation inside its arena.

## Actual execution evidence

```sh
PATH=/workspace/toolchain/bin:/workspace/toolchain/usr/bin:$PATH \
python3 scripts/check-windows-heap.py \
  --in /workspace/toolchain/inauguration-0.9.324/in-cli/target/release/in \
  --out /tmp/space-windows-heap-proof
```

The focused gate performs 485 actual protected executions: 23 modes over 21
cycles, one live-revocation case and one fresh activation. Seven native admission
refusals cover grants, arguments, image, insufficient frames and token exhaustion.
Cases include alignment, zero-sized and multipage allocation, zero initialization,
full-arena and 128-record exhaustion, in-place/moving/shrinking/zero realloc,
atomic arena/record allocation failure, invalid flags, SIZE_MAX/oversized requests,
interior/kernel/double frees and stale heap tokens. A supervisor observer compares
the complete native ledger and payload canary on every failed heap API, checks
exact LastError preservation and verifies actual RW/NX page flags.

The guest triggers real CPU faults by executing its heap, reading its opaque heap
handle as a pointer, and reading the native ledger frame. The ledger address is
injected only by the test supervisor; production never publishes it. An infinite
guest is cancelled with status 124. Caller FS/GS, all borrowed state and owned
frames are restored after every result. After one complete warmup cycle, 20
additional cycles keep heap usage, free-frame count and domain count exact.

The public contracts were checked against Microsoft
[HeapAlloc](https://learn.microsoft.com/en-us/windows/win32/api/heapapi/nf-heapapi-heapalloc),
[HeapReAlloc](https://learn.microsoft.com/en-us/windows/win32/api/heapapi/nf-heapapi-heaprealloc)
and Wine's pinned
[heap tests](https://github.com/wine-mirror/wine/blob/840a939ee526137639665ff5f587224d6a36403f/dlls/kernel32/tests/heap.c),
including zero-size behavior and HeapFree(NULL). Wine's tests also document
observed Windows edge behavior beyond the narrower API documentation; this
profile explicitly states its unsupported/corruption boundaries. No Wine source
was copied or vendored.
