# Linux static application process slice

Implement an actual unmodified x86_64 static ELF CLI application inside a private
CPL3/IOPL0 domain. The initial pinned workload is jq 1.8.1 with ordinary Linux
argv/environment/auxv and a bounded single-threaded process profile. ELF remains
a foreign payload; native SCI/compiler contracts are unchanged.

The Linux personality owns ELF PT_LOAD validation, private backing pages,
startup stack, Linux syscall/error/structure translation and per-instance state.
The domain runtime owns strict entry, syscall context transitions and inactive
page-table teardown. The personality releases backing frames only after that
teardown and restores the host FS base and syscall hook on exit/fault.

Support is driven by observed Linux behavior, not command-specific result
stubs. Implement real brk mappings, RELRO mprotect, FS/TLS setup, bounded guest
copies, serial-output descriptors, cwd and own-executable readlink. Unsupported
rseq/thread/file operations return explicit errors. Hardware RDRAND supplies
actual bytes for startup AT_RANDOM and bounded getrandom; unsupported hardware
returns ENOSYS rather than invented bytes. Futex wake can report
zero in the declared single-thread profile; blocking waits remain unsupported.
No host filesystem or computation is substituted for the application.

Tests verify official binary SHA256, reference outputs separately, actual QEMU
application output/status, malformed ELF refusal, pointer/authority denial,
repeated launch/fault cleanup and unchanged kernel/other-domain memory. The
first query is `jq -nc '[range(10)] | add'`; success requires the actual jq code
to print `45` and exit0 through Linux SYSCALL.

## Implemented and locally verified

`components/linux-process.in` executes the official, SHA-pinned Linux static
jq 1.8.1 binary at CPL3/IOPL0. It maps each PT_LOAD into private zeroed frames,
honors RX/R/RW and NX permissions, builds Linux argc/argv/environment/auxv,
and translates real SYSCALL entries. Its bounded heap grows with real frames;
shrinking revokes mappings before freeing frames and regrowth returns zeroed
pages. RELRO mprotect changes actual PTE permissions. Guest copies walk the
owned-page ledger before reading or writing. Exit and faults restore kernel
FS/hook state and release the private page tables and backing pages.
The first entry explicitly initializes FS and GS bases to zero before the
application installs its own FS TLS. Nonzero caller bases are restored after
finite execution, hardware faults and timer cancellation. Independent actual
FS:[0] and GS:[0] probes seed the caller base with the valid guest ELF address:
an inherited base would read successfully and exit42, whereas a fresh zero
base faults at null. Independent FS and GS negative-control snapshots removing
only the corresponding initialization fail exactly142-versus42. Every real corpus launch also
runs with nonzero caller FS/GS canaries; the added probes make seven actual
hardware fault executions per negative cycle.

The profile has three arguments, `LC_ALL=C`, `HOME=/`, a 1 MiB private stack, an 8 MiB
maximum brk region, 4096 total owned-page slots, and owned serial stdout/stderr.
Private anonymous mmap/munmap uses a separate 16 MiB virtual region and the
same total page budget. It creates real zeroed NX pages, supports read-only or
read/write protection, revokes mappings before freeing frames, reuses holes
and clears reused memory. File/shared/fixed/executable mappings remain
unsupported. Both actual glibc allocation and source-built compiler arrays
use this Linux ABI rather than a Space-specific allocation shortcut.
The launch authority must grant memory and serial; writes recheck serial
authority. Optional file input requires a live storage grant. The file adapter
uses real VFS open/read/seek/close/stat semantics with execution-owned guest
descriptor mappings, bounded path slots and a 4 KiB kernel copy buffer. Guest
pointers and descriptor numbers are never passed directly into VFS. An input
file may be duplicated into stdin; its caller-owned descriptor remains open
and shares its normal VFS open-file offset. Guest-opened paths use bounded
activation-owned storage through `vfs-open-borrowed-path`, avoiding repeated
bump allocations. All owned descriptors close on exit/fault, including when
storage authority has been revoked. The currently allowed filesystem backend
is synchronous RAM SparkFS or direct synchronous NVMe SparkFS; asynchronous
Volume RPC returns ENOSYS. An offline direct controller returns an I/O error.

Each launch has a configurable budget of 1–10000 guest PIT ticks (100 by
default). Real CPL3 timer interrupts cancel an infinite jq computation with
status124, restore kernel execution and release all owned resources. This is
distinct from the host gate's outer QEMU deadline. Kernel syscall-handler time
does not consume this guest CPU tick budget.

Regular files may also open write-only or read/write, create, exclusively
create, truncate and append. Writes pass through VFS using the same owned
handles and bounded copy buffer and recheck storage authority. The existing
filesystem performs real truncation, growth and sparse zero-hole filling.
Bounded pread64/pwrite64 perform actual VFS I/O at the requested offset and
restore the shared open-file offset after short, successful or failed I/O.
This uses the declared single active process and synchronous IF0 service
context; a concurrent provider will need native positional operations.
Actual Lua write/seek/readback covers a 4 KiB block boundary, new-file creation,
truncate then 9000-byte growth, append after a seek to zero, and sparse writes.
Creation accepts native permission bits0000–0777 under fixed profile umask022,
persists the resulting inode mode and reports it through actual metadata.
SQLite journal0600 and ordinary fopen0666→0644 therefore have distinct real
stored permissions.
The path buffer holds at most255 bytes, and each component must fit the current
SparkFS directory format's24 bytes. Longer components receive ENAMETOOLONG
before filesystem mutation; the translator does not accept silent truncation.
Read-only directory handles use real VFS bindings; reads return EISDIR and
writable directory opens are refused. O_DIRECTORY rejects regular files.
O_NOFOLLOW accepts the native filesystem's current regular-file/directory
types, which contain no symlinks. F_OK queries actual existence; permission
queries remain unsupported while process identity is not modeled.

There is no dynamic linker, threads, blocking futex waits or signals. It is a single active process component;
per-instance handles and a supervisor-owned concurrent activation boundary
remain future work. The test root imports this component explicitly; the
normal desktop does not yet launch arbitrary Linux applications.

Reproduce with an actual downloaded release file (its manifest is in
`fixtures/applications/jq-1.8.1.json`):

```sh
python3 scripts/check-linux-real-app.py \
  --in /path/to/source-built/in \
  --app /path/to/jq-linux-amd64 \
  --out /tmp/linux-real-jq \
  --suite --input-suite
```

The gate separately runs the Linux host reference, verifies the binary SHA256,
then boots the same bytes into Space through QEMU's raw loader. Space performs
all jq computation. Nine real queries cover arithmetic, larger allocations,
objects/sort, strings, regex, recursion, UTF-8, and application errors with
nonzero exit codes. Six additional input scenarios exercise actual JSON from
SparkFS-backed stdin and filename-based openat/read, including files larger
than the 4 KiB copy buffer and multi-document input. The gate compares those
outputs with separately run host references. The default 21 repetitions check stable heap high-water,
free-frame count, filesystem block ownership, domain count/ownership, FS and
syscall-hook state. Operation transitions run once before this baseline so
bounded SparkFS scratch buffers are initialized. Each cycle
also runs labelled synthetic ELF hardware faults (UD2, kernel-memory read,
read-only code write, NX stack execution and privileged port I/O), malformed
ELF and pointer/authority denials, RELRO permission checks, and brk revoke/
regrow zeroing. File tests additionally verify pointer failures preserve VFS
offsets, unknown descriptor denial, read-only buffers, seek errors, storage
revocation and closure of intentionally unclosed file handles. An actual
infinite original jq query must be cancelled by its guest interrupt budget;
finite original jq queries must then execute successfully. A held second
domain maps the same virtual ELF address to a sentinel frame; its contents
and PTE permissions must survive every application/fault cycle, and its
resources are explicitly released after the check. The test leaves
the interactive shell running. A `--root minimal` option checks the same
execution/VFS contracts without optional desktop/network/personality imports;
the standard root remains the default integration gate.

The shared gate is `scripts/check-linux-corpus.py`; the original jq script is
a compatibility entry point. The second real application is stock Lua 5.4.7,
built as an ordinary static Linux executable from its verified, unmodified
upstream release. Its manifest records the source archive and build provenance
in `fixtures/applications/lua-5.4.7.json`. Run the same gate with
`--application lua --app /path/to/lua --suite --input-suite`. It compares math,
table sorting, formatting, UTF-8, garbage collection (including a 100000-entry
table exercising real mmap/munmap), coroutines, environment, caught/uncaught
errors, exit status, and real VFS stdin/file reads and bounded writes. GNU ELF
OSABI3 and System V OSABI0 both use the supported Linux static ABI; other ABI
tags are rejected. Lua's optional SIGINT installation receives honest ENOSYS;
there is no simulated successful signal registration. Real interrupt-budget
cancellation still bounds an infinite Lua computation and allows subsequent
finite application execution.

BusyBox 1.36.1 is a third upstream static ELF, built from the pinned official
source using the recorded minimal applet configuration. Twelve cases cover
echo, Unicode arguments, printf, cat/wc stdin and files (including 10902-byte
input), ash arithmetic, loops and exit23. F_GETFL reports actual access and
append flags from owned descriptor bindings. Unsupported pipe2 prevents ash
pipelines; the failed real pipeline probe is retained separately from passing
cases. Signal setup and several identity calls still return ENOSYS.

The fourth upstream static ELF is SQLite 3.46.1. Nine in-memory cases cover
its version, table insertion/order/grouping, recursive CTEs, JSON, Unicode,
rollback, blobs, window functions and syntax errors. An infinite recursive
query is cancelled by actual guest timer interrupts. Five more cases execute
real synchronous RAM database transactions, reopen the same database in a
separate process, store a9000-byte blob across filesystem blocks, reopen it,
and roll back an18000-byte update. These use native inode/mount identities,
persisted journal0600 permissions, O_NOFOLLOW, actual positional I/O, owned
native byte-range leases, RAM regular/directory sync and journal unlink.
The earlier failed file probe remains evidence of the missing newfstatat
baseline; no host database computation is substituted for Space execution.

Native leases are bounded provider state, not successful fcntl stubs. F_SETLK
translates shared/exclusive/release ranges and reports real conflicts; direct
tests cover a second owner, shared-to-exclusive upgrade, partial unlock,
pointer refusal and closure after authority revocation. Any close of an owned
binding releases that process's leases for the same native inode; exit/fault/
deadline releases the remaining owner state. Blocking commands and unsupported
range conventions remain refused. Stat structures carry actual native mount
and inode identities, consistent between path and descriptor queries.

Unlink refuses a file with any open native VFS binding because VFS currently
resolves paths rather than retaining an open inode; identity checks include
relative/absolute aliases. Directory removal is not exposed through unlink.
Successful RAM fsync means that synchronous memory writes have completed.
Direct NVMe fsync writes filesystem bitmap metadata and consumes a real
namespace FLUSH with matched command/queue identity and successful controller
completion; errors propagate. Asynchronous Volume RPC remains refused.

`scripts/check-linux-persistence.py` runs the original reproducible SQLite ELF
across three independent QEMU processes on one owned disposable64MiB NVMe disk.
Only the first boot formats it. The first transaction stores42 and a9000-byte
blob, consuming eight checked FLUSH completions. The next boot reopens the
database and commits an update to43, consuming four. The third boot reopens43,
rolls back an update to99 and retains43; that rollback requires no FLUSH and
none is claimed. Fifteen actual application activations include repeated read
processes and resource cleanup checks. A read-only raw-disk oracle extracts
the16384-byte database after each stopped boot; separate host SQLite integrity
checks succeed, journals are absent and the database hashes before/after the
rollback boot match exactly. These are controlled close/halt/reboot tests,
not arbitrary power-loss or crash-recovery guarantees.

The current generic runner captures a read-only source snapshot and records
its receipt alongside the exact compiler and application hashes. It uses that
snapshot for compilation, so concurrent development cannot silently change
the tested imports. Host controls use the declared LC_ALL=C, HOME=/, cwd=/ and
umask022 profile. On the strict-entry register-confidentiality boot, 21-cycle
gates passed jq81, Lua222, BusyBox100 and SQLite31 actual activations, each with
105 synthetic hardware faults, authority/pointer refusal, other-domain and
resource witnesses, and an original-app infinite computation cancellation.
These counts describe the selected corpus, not arbitrary Linux compatibility.
The subsequent FS/GS-scoped gates retain all four activation counts and check
147 actual hardware fault probes per application suite (seven per cycle).
SQLite's canonical executable now has reproducible relative-source build
provenance; the earlier absolute-path build hash is retained as historical
evidence in its manifest. The canonical executable also passes the latest
21-cycle FS/GS suite. Corpus `file_slot` explicitly shares a logical file
between configured cases, allowing a transaction and a separate process
reopen to operate on the same real file without a private fake filesystem.
The runner warms bounded native lease and create/delete scratch once before
measuring exact resource stability, and checks the native lease count alongside
heap, frames, filesystem blocks, domains and owned file descriptor availability.

The Linux translator consumes low32 bits for int file descriptors, whence,
open flags, fcntl commands and other implemented int arguments. Signed values
such as low32 FFFFFFFF become negative descriptors, not large positive handles.
Linux x86_64 syscall dispatch numbers are also int32, as independently verified
by a real host getpid syscall with nonzero upper register bits. Pointers,
size_t and off_t retain their64-bit values; the bounded profile still refuses
oversized I/O and unsupported offsets rather than truncating them.
`fixtures/linux-process/int-width.asm` is a labelled synthetic ELF executed
separately from the original-app count. It performs actual protected SYSCALLs
with nonzero upper bits and checks descriptor, flags, seek, stat and error
behavior. `int-width-host.py` separately exercises real Linux syscall widths,
including a safe45-byte short read with a4GiB count. Host F_GETFL also reports
O_LARGEFILE, so its access mode is compared explicitly. A negative-control
snapshot omitting FD narrowing fails the actual guest probe with101 instead
of42; pointer/count/offset width is checked independently.

The explicit home is the Space profile's root directory; host controls receive
the exact same environment. Without HOME, the first real SQLite memory probe
computed the correct queries but emitted a missing-home warning while its
unsupported identity/passwd lookup failed, so that comparison was recorded as
failed. Supplying the declared home avoids inventing identity syscall results.
Repeated path separators are collapsed by the Linux adapter so
`//.sqliterc` remains an actual missing-file lookup and returns ENOENT.

Coverage goal: retain these real-execution gates while adding more complete
file metadata/permissions and more unmodified static applications, dynamic ELF linking and
then GUI protocol/client execution. New support must increase observed real
application coverage and preserve the negative/cleanup tests; admission or
host-reference success alone is insufficient.
