# Protected Darwin file checks

`check-darwin-files.py` boots an owned 8 KiB Mach-O fixture in Space at CPL3.
The five-command profile has private RX text, RW/NX data and BSS, classic
`LC_DYLD_INFO_ONLY` bindings, and the exact `/usr/lib/libSystem.B.dylib` import.
It binds `_write`, `_exit`, `_error`, `_open`, `_read`, `_close` and `_lseek` to
guest RX trampolines. No imported pointer calls a native or host function.

```sh
python3 scripts/check-darwin-files.py \
  --in /path/to/inauguration/in-cli/target/release/in \
  --out /tmp/darwin-files
```

The output directory must be new or empty. The checker assembles the fixture,
compiles a full standard root, and loads the fixture separately at physical
`0x10000000`. Its generated boot check seeds an actual 8,192-byte SparkFS file
with a fixed alphabet and lends distinct serial and storage capabilities to
the Darwin process service. It requires the RAM SparkFS backend and direct
synchronous VFS; this gate does not claim NVMe persistence.

Twenty-one cycles exercise twenty-six modes each, followed by live revocation and
a fresh successful activation: **548 actual CPL3 executions**. Assertions cover:

- Exact 8 KiB contents, cross-4-KiB reads, seek offsets, bounded EOF reads and
  ordinary close/double-close behavior.
- Private guest descriptor translation. An independently open native host fd3
  remains valid with its original path and offset; a guest cannot read or
  close it by supplying the same integer before opening its own descriptor.
- Unmapped, RX-only and partially unmapped destination buffers. Failed reads
  preserve the file offset. Oversized reads and invalid seek origins fail.
- Missing paths, unsupported open flags, unterminated/overlong names and
  strings crossing an unmapped boundary. A known 24-byte basename opens and
  closes successfully; a 25-byte component returns raw carry/errno 63 or typed
  `_open` result `-1` with `_error` 63, before lookup can report ENOENT.
- Raw Darwin positive errno with carry set: EACCES (13), EFAULT (14), EBADF (9),
  EINVAL (22), ENOENT (2), ENAMETOOLONG (63) and ENOSYS (78). Successful calls clear carry.
- Typed C ABI success results and `-1` with private `_error` values 13/14/9.
  Every new imported-call instance begins with zero private errno.
- Missing borrowed storage authority, including refusal before dereferencing
  an invalid path, and revocation during an active process. A generated,
  test-only dispatcher handles the revocation request; production dispatchers
  gain no extra syscall. Closing an owned descriptor still works after revoke.
- Unclosed file cleanup after normal return, a genuine CPU protection fault
  (status 142) and an IRQ-driven budget cancellation (status 124). Heap use,
  free-frame count, domain slots, capabilities, hook/budget state and the host
  descriptor sentinel remain stable after initial workspace warmup.

Fresh 2026-10-24 (Australia/Melbourne) verification passed at
`/tmp/space-darwin-files-isolation-final/report.json` using frozen Inauguration 0.9.324
(SHA256 `43b5a2f166efb28ea3123e8030c549d1eac9e90ee7c642d013457ff7ade09168`).
The receipt records source/compiler/kernel/fixture hashes, exact compile and
QEMU commands and `source_changed_during_run: []`; serial and generated sources
are retained beside it. Earlier 338-execution raw syscall and 422-execution imported syscall
runs also passed at `/tmp/space-darwin-files-second/report.json` and
`/tmp/space-darwin-files-imports/report.json`. The first harness attempt used an
incorrect boolean comparison for SparkFS's RAM backing pointer and failed its
precondition before guest activation; its log remains at
`/tmp/space-darwin-files-first.log`.

The original 422-case suite also passed at
`/tmp/space-darwin-files-final/report.json`. The filename boundary adds two
modes per cycle while retaining every original case and resource assertion.

This is protected ABI fixture evidence. It does not certify an original macOS
application, dynamic dyld execution, general Mach services, file creation or
writes, concurrent libc errno, asynchronous Volume RPC or durable file storage.
The original macOS jq remains outside this Mach-O profile. Foreign ABI policy
stays in the Darwin provider; VFS retains native descriptor offsets and file
semantics, and guest pointers never reach VFS directly.


The later ABI/isolation extension retains all 464 preceding executions and adds
four modes per cycle. Raw and typed calls pass unspecified nonzero upper 32
argument bits for file descriptors, open flags and seek origins; only their
signed low 32 C integer values apply. A low 32 descriptor of 0xffffffff remains
EBADF (9). Buffer pointers, byte counts and file offsets retain 64-bit validation.
Before every activation the native test caller seeds FS/GS bases with distinct,
valid guest-data addresses. Separate actual `FS:[0]` and `GS:[0]` instructions
must fault when the provider clears those bases. The caller verifies its seeded
bases are restored after normal return, protection faults and IRQ cancellation,
then restores its original native bases. The final 548-execution receipt above
has no source changes during the run; the preceding 464-execution boundary
receipt remains at `/tmp/space-darwin-files-names-final/report.json`.
