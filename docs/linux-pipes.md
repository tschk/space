# Protected Linux pipe adapter

`components/linux-process-pipes.in` translates ordinary Linux descriptors to
execution-owned native VFS stream endpoints. It belongs to the Linux personality;
it adds no foreign syscall or process policy to the nanokernel. The implementation
is exercised by `scripts/check-linux-pipes.py` and the separate unmodified
BusyBox pipeline probe. A working pipe does not establish a working shell pipeline.

## Ownership and authority

The native VFS owns four stream pairs, their two 4096-byte rings and endpoint
reference counts. The Linux adapter assigns one pair side to the read end and the
other side to the write end, enforcing one-way access. A private table records
which process family owns each pair and its generation identity. Each child must
also inherit an actual owned native endpoint reference; the family token alone
does not grant endpoint access. Guest descriptor values
index the execution's 16-slot descriptor table; they never expose native descriptor
numbers, pair addresses, ring addresses or privileged pointers.

Every alias owns a distinct native descriptor and one endpoint reference. `dup2`
reserves the source reference before closing an existing target, so replacement
works even when the native descriptor pool is full. The replaced binding is
closed, including a standard serial-output binding. Closing its replacement does
not restore the old binding. The private file-identity cache stays empty for pipes.

Creation, transfers, metadata changes and duplication require a live memory
capability. Private pipe operations require no storage grant. Close and teardown
remain possible after the capability is revoked. Process release closes every
owned native descriptor before retiring private pair ownership. Another native
client's pair remains independently owned and buffered.

## Bounded Linux contract

- `pipe2` accepts zero, `O_NONBLOCK` and `O_CLOEXEC`, rejecting other flags. It
  validates the entire writable eight-byte result range before publication.
- Read and write use private kernel scratch storage; native VFS never receives a
  guest address. The current per-call bound is 65536 bytes.
- Empty nonblocking reads return `EAGAIN` while a writer still exists. Buffered
  bytes drain before EOF after the final writer reference closes.
- `PIPE_BUF` and the actual ring capacity are 4096 bytes. Writes at most
  `PIPE_BUF` publish all bytes or none. Larger nonblocking writes may return an
  actual short count. Full rings return `EAGAIN` in nonblocking mode.
- Blocking operations now retain an owned pending syscall and suspend while
  another process can change the condition. Large writes retain their actual
  published prefix, then continue without duplicating bytes. A closed graph with
  no runnable producer/consumer terminates with explicit edge deadlock 125;
  genuine IRQ deadline remains 124, and admitted policy-work exhaustion 126.
  The low-level synchronous primitive's internal would-wait refusal is not a
  fabricated successful guest transfer. See [blocking tests](linux-blocking-tests.md).
- `dup`, `dup2`, `dup3`, `F_DUPFD` and `F_DUPFD_CLOEXEC` accept owned pipe sources;
  the descriptor adapter also owns regular-file/null duplication. Invalid descriptors return
  `EBADF`. `dup3` rejects a same-descriptor request, including flags zero.
- Nonblocking status belongs to the shared endpoint description. `F_SETFL` updates
  all of its aliases. Close-on-exec is per guest descriptor, and ordinary `dup`
  clears that bit. Copied children share native endpoint status while descriptor
  flags remain per process. Self-exec closes only that process's CLOEXEC bindings;
  see [protected children](linux-children.md) for the bounded execution contract.
- `F_GETPIPE_SZ` reports the actual native capacity. `F_SETPIPE_SZ` accepts
  requests which round to the existing one-page capacity; growth returns
  `ENOSYS`. No allocation or capacity growth is claimed.
- `fstat` reports FIFO mode, one link, the private pair generation identity and
  the actual 4096-byte block size. It never treats the native pair index as a
  filesystem pathname. Pipe seek/positional file operations are refused.

A write to a pipe with no readers requires real SIGPIPE behavior. The adapter
supports the kernel's four-word `rt_sigaction` layout for `SIGPIPE` only, with
`sigsetsize=8` and default/ignored dispositions. Default disposition terminates the
activation with status 141 and an explicit signal-13 cause, distinct from a CPU
#GP which happens to share the numeric status. Ignored disposition returns `EPIPE`.
Unimplemented signals and handlers return errors. The bounded child layer now
implements real clone, wait and self-exec; arbitrary handlers remain unsupported.

## Executable evidence

The synthetic NASM ELF checks ordinary Linux ABI calls on the host and then the
same bytes under strict Space CPL3. Separate modes leave descriptors open during
an actual CPU fault and IRQ timeout, verify default SIGPIPE and verify the explicit
blocking-wait refusal. Kernel-side checks cover capability revocation, capacity
failure without result publication, descriptor exhaustion and replacement, and
an unrelated buffered native pair. These fixtures are not upstream applications.

`--busybox` additionally runs the exact pinned, unmodified BusyBox ash pipeline
against a host output/status oracle. Its failure makes the command fail, even
when the separate pipe contract passes. The report preserves the actual next
unsupported syscall; a failed pipeline is never counted as compatibility coverage.

Completed pipe-slice evidence (before the child layer):

- `/tmp/space-linux-pipes-standard21-final2/report.json`: 110 actual protected
  activations and 21 ownership/capability/capacity cycles under the standard root.
- `/tmp/space-linux-pipes-minimal21-final/report.json`: 110 actual protected
  activations and 21 ownership/capability/capacity cycles, including integer
  syscall arguments with unrelated upper register bits.
- `/tmp/space-linux-busybox-after-pipes21/report.json`: unchanged upstream
  BusyBox applet/builtin corpus, all 12 cases and 100 actual activations pass.
- `/tmp/space-linux-pipes-busybox-next-final2/report.json`: the optional pipeline
  gate correctly **fails**. Both actual BusyBox activations create their pipe
  successfully, then receive `ENOSYS` from `clone` (56); `rt_sigprocmask` (14)
  remains unsupported. Ash exits 2 with “can't fork: Function not implemented”.
  The host oracle exits 0 with `6\n`. Open pipe endpoints are reclaimed after
  these failures, without changing the unrelated buffered native pair.

These historical reports describe specific fixtures and pinned upstream bytes.
The later child layer executes actual ash pipelines; its separate
[contract and receipts](linux-children.md) distinguish this progress from the
older clone-refusal evidence. The [blocking suite](linux-blocking-tests.md)
tracks genuine cross-capacity execution and its final repeated acceptance.
