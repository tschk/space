# Protected Darwin startup checks

`components/darwin-process-startup.in` supplies a separate bounded Mach-O
startup profile over generic owned user CPU contexts. The existing protected
Darwin profile and its entry convention remain unchanged. This implements the
[next startup slice](plans/2026-10-24-darwin-startup.md) of the
[Rosemary reference plan](rosemary-macos-reference.md), without copying or
linking reference code.

## Admission and startup contract

The new profile accepts exactly three load commands: ordered RX and RW/NX
`LC_SEGMENT_64` mappings with no sections, then one entry command. It retains
the protected profile's fixed guest address window, 64-KiB segment bounds,
file/VM bounds, nonoverlap and W^X checks. Dependencies, imports, constructors,
TLS/TLV sections and arbitrary dyld metadata are refused.

`LC_MAIN` uses the old strict validator with the additional ordered-segment
condition. Its entry receives argc/argv/envp/apple in RDI/RSI/RDX/RCX,
RSP modulo 16 equal to 8, and an owned RX return stub which invokes Darwin exit
with the returned status. No privileged host function pointer enters the guest.

`LC_UNIXTHREAD` is a distinct admission: command size 184, x86_THREAD_STATE64
flavor 4, count 42, and all state words zero except a validated RIP in file-backed
RX bytes. A nonzero requested source RSP is refused. The provider chooses a
private, 16-byte-aligned process stack beginning with argc, then argv/null,
envp/null and apple/null. Initial argument registers remain zero as requested
by this constrained thread state. There is no main-style return address on this
stack; the fixture exits with a genuine Darwin syscall. Arbitrary saved thread
states, nonzero source registers and legacy executable startup remain unsupported.

`darwin-startup-run(image,size,input,bytes,serial,storage,budget)` is a trusted
supervisor interface, excluded with all `darwin-startup-*` helpers from dynamic
kernel imports. This is kernel-linked personality scaffolding, not an isolated
SCI service. A personality-hub import supplies the protected mapping/dispatch
provider; the startup module explicitly imports generic user contexts. Native
components still deploy as SCI. No declarative component capability-ordinal
translation or ordinary untrusted SCI launch binding is claimed here.

The caller owns a stable, readable startup span throughout the synchronous
invocation. It must provide the span itself through trusted memory; this raw
CPL0 interface does not validate arbitrary caller page mappings. Within that
span, all pointer arithmetic, vector extents, NUL termination, counts and string
bytes are checked before execution allocation. No pointers outside the span are
read. The first 48 bytes contain six 64-bit words:

| Offset | Meaning |
| --- | --- |
| 0/8 | argc / argv pointer |
| 16/24 | env count / envp pointer |
| 32/40 | apple count / apple pointer |

The span is 48–4096 bytes, each count is 0–16, each string is at most 255 bytes
plus NUL, and the sum including all NULs is at most 3072 bytes. Every vector has
an explicit terminating NULL. Overlapping source strings are allowed and are
copied into separate owned storage. No caller argument/environment is supplied
implicitly. The provider copies vectors and bytes into private RW/NX mappings
before entering CPL3; the guest never receives source pointers.

Initialization order is complete image/input validation, owned mapping, startup
copy, zeroed context and reserved private errno word, then guest execution. The
reserved word at 0x4F004000 is proven initially zero; the new profile has no
`_error` import, no libSystem initialization and no TLS/TLV runtime. FS/GS start
zero, with caller FS/GS and CPU state restored by the generic context mechanism.
The old profile's typed `_error` behavior remains a separate tested contract.
No constructor, destructor, atexit or framework success stub was added.

The protected frame ledger owns text/data, stack, startup and return-stub pages;
one existing busy guard prevents concurrent reuse. Terminal exit, actual CPU
fault and IRQ deadline reclaim the invocation's pages/domain and scoped file
bindings. The descriptor table and borrowed native serial/storage authorities
remain caller-owned. The bounded context and mapping ledgers are retained once
and reused; repeated invocations do not allocate new scratch state.

## Reproduction and evidence

With frozen Inauguration 0.9.324 and QEMU/NASM available:

```sh
python3 scripts/check-darwin-startup-owner.py --in "$IN" --out /tmp/startup-owner
python3 scripts/check-darwin-startup.py --in "$IN" --out /tmp/startup-qemu \
  --app /path/to/jq-macos-amd64
python3 scripts/check-darwin-protected.py --in "$IN" --out /tmp/darwin-old \
  --imports --app /path/to/jq-macos-amd64
python3 scripts/check-darwin-files.py --in "$IN" --out /tmp/darwin-files-old
```

The owner gate executes actual image/input validators in default, lean and
harden profiles over byte-addressed fixtures. The old parser's string literal
is materialized as model memory; no parser branch is replaced. It checks 53
malformed UNIXTHREAD/header/segment/state mutations, source vector bounds and
terminators, exact 255-byte strings and exact 3072-byte aggregate limits.

The runtime gate freezes its complete source tree, assembles genuine Mach-O
fixtures, checks their command layout independently on the host, and executes
344 actual CPL3 invocations. These comprise 336 executions over 21 cycles of
both profiles (normal return/exit, unmapped access, actual IRQ deadline,
startup/stack bounds, FS/GS isolation, caller-memory denial) plus four positive
empty/max 16 vector cases, two exact first-use cache recovery cases and two
maximum-size segment cases. It verifies exact argument bytes and
termination, distinct register/process-stack conventions, reserved errno zero,
caller FS/GS restoration, actual typed stops and stable heap/frame/domain/
capability/descriptor ownership after warmup. Refused image/input/authority
cases do not allocate process resources. Actual registry lookup also refuses the
raw startup entry. The old suites still pass 483 and 548 cases respectively.

Local receipts:

- `/tmp/space-darwin-startup-preflight-checkpoint/report.json`: frozen actual QEMU gate.
- `/tmp/space-darwin-startup-owner-checkpoint/report.json`: all three owner profiles.
- `/tmp/space-darwin-startup-preflight-old483/report.json` and
  `/tmp/space-darwin-startup-preflight-old548/report.json`: unchanged existing gates.
- `/tmp/space-darwin-startup-rcx-control/report.json`: only a generated source
  snapshot omits RCX/apple; actual first-case guest access faults and the ABI
  assertion fails. Production source and successful receipts are untouched.

An intermediate boundary fixture failed because its test setup reused the
prior maximum-vector pointers when resetting the next profile to empty input.
The refused input was correct; the fixture now resets the pointers. Its failure
receipt remains under `/tmp/space-darwin-startup-boundaries`.

## First-use allocation and exit-stub review

The startup reserve counts cached bump allocations separately from free frames.
Missing protected ledgers consume 1056 bytes, the aligned generic CPU context
784 bytes, and first-use protected file scratch 8320 bytes. Each is included
only when absent and needed. Insufficient bump bytes return -12 before any
allocation, even if the free-frame list contains enough pages. The 65-frame
reserve is then counted from complete heap pages after those bytes, plus actual
free-list frames. Free frames cannot stand in for bump-allocator capacity.

A conservative setup bound is 56 frames: 39 backing pages (two maximum 16-page
segments, six stack/startup pages and one exit page), four initial page tables,
at most six user leaf tables (two per segment and one each for stack and exit),
at most five supervisor leaf tables (trampoline, two IDT pages and a possibly
unaligned 64-KiB kernel stack), and at most two additional directory tables for
physical addresses in 2–4 GiB. All native physical allocations are below 4 GiB;
the initial user tree already supplies the two lower directories. The reserve
of 65 leaves nine additional frames after that conservative bound. First-use
bump bytes are excluded independently, so they do not consume this slack.
The gate executes both entry profiles with maximum 64-KiB segments, reads the
last RX byte and writes/reads the last RW byte.

`darwin-protected-take-frame` returns zero at its ledger bound. The admitted
maximum of 39 owned frames is below its production bound of 64, while the
underlying frame allocator returns a nonzero frame or panics. The exit-stub
path nevertheless checks zero locally, reports -12 and releases the partially
mapped domain instead of storing through address zero.

Actual QEMU pressure tests put 65 real frames on the free list, then temporarily
reduce the trusted test root's bump limit. Zero bump bytes refuse without
changing heap, free-list head, domains or caches; exactly 1840 bytes recover
through real CPL3 startup. With file scratch absent, 8304 bytes refuse and
exactly 8320 recover. The normal heap limit is restored after each call.
A generated-source regression control restoring the original free-frame-only
preflight reproduces a real `heap exhausted` panic in the first pressure case:
`/tmp/space-darwin-startup-preflight-legacy-control/report.json`.

The reproducible `--ledger-limit-control` option changes only the frozen test
copy's ledger limit from 64 to 8. Two image pages and six data pages then fill
the real ledger before exit-stub allocation. The provider returns -12 and
reclaims its domain/pages over 21 cycles with stable resources. No guest is
entered or counted as a CPL3 success in this control:
`/tmp/space-darwin-startup-stub-zero-checkpoint/report.json`.

```sh
python3 scripts/check-darwin-startup.py --in "$IN" --out /tmp/startup-stub-zero \
  --ledger-limit-control
```

## Original macOS jq requirements

`inspect-darwin-application.py` independently inspects checksum-pinned jq 1.8.1
without executing it. The original image has 17 load commands, 10 sections,
`LC_MAIN` file offset 2144, `/usr/lib/dyld`, one
`/usr/lib/libSystem.B.dylib` dependency, and 136 undefined symbols. These include
stdio objects/functions, allocator functions, stack protection, locale/math,
`___error`, pthread creation/join/once and thread-specific keys. A startup
argument fixture supplies none of those dependencies by implication.

```sh
python3 scripts/inspect-darwin-application.py /path/to/jq-macos-amd64 \
  --out /tmp/macos-jq-requirements.json
```

The runtime gate with `--app` also injects that exact pinned image and proves
actual allocation-free refusal (-8) by the new startup admission. It is not
entered. Original macOS jq and GUI/framework applications remain unexecuted;
a separate [finite eager adapter](darwin-eager-checks.md) now supplies a bounded
import preparation contract. Wider dependency support and actual required API
implementations remain driven by the captured original application imports.
