# Protected Darwin startup slice

This next step advances the macOS/Rosemary goal through a separately admitted
startup ABI. Space native components still use SCI; Mach-O and Darwin startup
policy remain in the personality, above generic owned user CPU contexts.

Reference: Rosemary commit
`f845f21842c85f6863cfa8a7a749cb945b88994a`, inspected locally, particularly
`crates/machish/src/image/entry.rs` and `crates/rosemary/src/startup.rs`.
No reference code is copied or linked. `LC_MAIN` denotes a main function after
dyld/libSystem preparation; `LC_UNIXTHREAD` specifies a process entry state.
Treating both as a zero-argument function is insufficient.

## Bounded implementation goal

Add `darwin-process-startup.in` as an explicit, trusted personality provider.
Keep the existing `darwin-protected-entry` and its old fixture profiles intact.
A new strict startup validator accepts only two bounded RX/RW segments and one
entry command, with no sections, dependency imports, constructor tables or TLS
metadata. Admit `LC_MAIN` and a tightly constrained x86_THREAD_STATE64
`LC_UNIXTHREAD` as distinct contracts. Reject mixed/duplicate entry commands,
nonzero unsupported thread state, malformed command sizes and unowned entry or
stack requests before allocating execution resources.

Caller startup data consists of explicit bounded NUL-terminated argv, envp and
apple vectors inside a trusted caller-owned input span. Validate every pointer,
terminator, count and aggregate size before copying; never put caller pointers
into CPL3 memory. Copy vectors and strings into invocation-owned RW/NX pages.
The profile exposes no ambient host arguments, environment or apple strings.

For `LC_MAIN`, provide argc/argv/envp/apple in RDI/RSI/RDX/RCX under the x86_64
SysV ABI, RSP modulo16=8, and an invocation-owned RX return/exit stub. For
`LC_UNIXTHREAD`, provide the process stack beginning with argc followed by
argv/null, envp/null and apple/null; do not invent an LC_MAIN return convention.
Use generic `user-context-init`/`user-context-resume`, owned private mappings,
existing scoped Darwin syscall translation and typed stop cleanup. No CPU ABI
policy belongs in this module. FS/GS begin zero and caller state is restored by
the generic context mechanism.

Initialization order for this first profile is validation, owned mapping and
copy, zeroed private errno state, context preparation, then guest entry. The
absence of constructor/dependency/TLS metadata is an admission condition, not a
claim that dyld, libSystem initialization, Objective-C, TLV, destructors or
atexit exist. Unknown imports/frameworks remain refused. A fixture main is a
standalone no-dependency contract; it does not establish original macOS app
startup compatibility.

## Required evidence

New genuine Mach-O fixtures must execute at CPL3 and inspect argument registers,
vector termination, exact string bytes, stack layout/alignment and owned return
or explicit exit behavior. Exercise argument input denials, bad image entry
metadata, guest access outside owned startup memory, CPU fault and actual IRQ
deadline. Repeat at least21 cycles and assert stable heap/frame/domain/capability
and descriptor ownership after warmup. Keep old protected Darwin483 and file548
cases unchanged. Use scoped test-only controls only when an injected denial
cannot be produced from ordinary startup input.

Separately trace the checksum-pinned original macOS jq's load commands, entry
and dependencies. Preserve its refusal until the actual startup, dependency and
API requirements work; accepted fixture layout is not original jq execution.
