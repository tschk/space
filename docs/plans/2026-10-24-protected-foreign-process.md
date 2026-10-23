# Protected foreign execution implementation slice

This implements the next boundary in the active full application goal. The
personality owns Mach-O validation and payload mappings; reusable user-domain
entry and page-table teardown belong to the native runtime. SCI remains the
native artifact contract. No foreign loader policy is added to the nanokernel.

The initial executable slice accepts a bounded import-free x86_64 Mach-O with
one RX text segment, one RW/NX data/BSS segment and LC_MAIN. It copies file bytes
into private physical pages, zeroes BSS, maps no kernel RAM as user-accessible,
and enters at CPL3 with IOPL0 through the existing transition mechanism. Entry
returns through the native exit capsule; ordinary macOS startup, dyld, imports,
threads and Darwin syscall execution remain subsequent implementation work.

The synchronous runner owns a bounded ledger of every payload/stack/exit-stub
frame. It retains one kernel context allocation, destroys inactive user page
tables before returning frames, and reuses retired domain slots. It borrows no
application authority: the initial guest has capability -1 and cannot read/write
through native privileged services. User faults return a status to the owning
invocation; kernel faults remain fatal. The strict entry must not inherit the
legacy SCI IOPL3 setting. Time slicing and arbitrary application execution are
not established by this synchronous fixture slice.

Acceptance uses actual QEMU execution and CPU faults: entry return42, BSS
zeroing and writable data; denied text writes, data/stack execution, kernel reads
and privileged I/O; malformed/overlapping/overflow segment refusal before any
allocation; repeated success/fault cycles with stable live frame/domain state.
Keep native SCI and trusted foreign fixture regressions while implementing this
path. Do not widen the trusted CPL0 loader to execute downloaded applications.


## Resumable Darwin ABI checkpoint

The private process installs a scoped syscall hook around strict CPL3 execution.
It accepts Darwin Unix-class write, getpid and exit, returns positive errno with
the saved IRET carry flag set on errors, and resumes after both SYSCALL and INT80.
Native capability remains empty; an explicitly borrowed serial capability is
checked per write. Every byte is translated through the current process's frame
ledger and the entire span is checked before output. No kernel guest pointer is
dereferenced. Unknown calls return ENOSYS (78).

`check-darwin-protected.py` now runs 399 actual invocations over 21 cycles,
including successful writes, getpid, explicit exit, unknown calls, kernel pointers,
partially mapped spans (no prefix may leak), bad descriptors and zero-length
writes, alongside all previous CPU denials. Final local receipt:
`/tmp/space-darwin-protected-services-final/report.json`. The first service run
exposed an oracle mistake: raw Unix write emits LF, while kernel log lines use
CRLF. The corrected oracle requires exactly 21 LF markers and no partial-span
sentinel. No runtime behavior or existing denial assertion was weakened.


## Typed imports and timer cancellation

The optional five-command profile admits one exact libSystem path and bounded
classic normal-bind opcodes. `_write`, `_exit` and optional `_error` resolve to
private RX guest trampolines, never host/kernel function pointers. Unsupported
symbols, ordinals, binding types, offsets, libraries and command fields fail
before allocation. `_write` translates kernel carry/errno to libc -1 and private
single-thread errno storage; `_error` returns that process-local address.
This is a strict loader profile, not a replacement dyld or arbitrary dylib loader.

The process now uses scoped PIT-driven CPL3 activation budgets. An actual guest
infinite loop exits with status124; finite execution, syscalls and faults return
through the same teardown. No timer deadline applies to trusted CPL0 native apps
or to time spent inside a kernel service. The watchdog does not establish threads
or concurrent scheduling.

`/tmp/space-darwin-protected-original-refusal/report.json` records 483 invocations
in21cycles, all previous denials, typed import/output/errno checks, 21 actual
infinite-loop cancellations and allocation-free refusal of SHA-pinned original
macOS jq. Source hashes remained unchanged during this run. Original jq remains
unexecuted: the limited profile cannot yet load its ordinary PIE/dyld startup.
The fixture is loaded independently at physical256MiB by QEMU, avoiding any
assumption that writable boot data always stays at2MiB.
