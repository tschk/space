# Original Windows compiler executing in Space

The original upstream Windows i386 `fasmg.exe` at fasmg commit
`905f6791f6777e35baec182e6843e2ada30cedd0` executes in Space's genuine CPL3
compatibility mode. Its bytes are unchanged. It prints its own help, reads
filesystem source, evaluates macros/arithmetic, writes exact output and emits
its own invalid-source/missing-file diagnostics.

Both `max` and `qemu64` pass 65 original activations, including 42 actual error
exits and 21 repeated resource cycles each. The generated 14-byte file is
`53706163650a0101020203030404`. Space verifies every byte after the app writes
it; no output file is supplied by the host. Heap high water, free frames,
domain/capability counts and descriptor availability remain stable. Six
malformed-image controls use a separate test copy and are not app entries.

The [frozen evidence](2026-10-25-pe32-evidence.json) binds every receipt/hash to
its exact source. Runtime is `fd9a48b`; the Windows harness at `c8b4e13` corrects
only parsing of a prefix-free native diagnostic. Earlier receipts stay failed:
those runs completed all 65 app activations, then the host receipt parser failed.

All eleven affected regressions pass: new32 and existing64 CPU contexts on both
CPU profiles; original Linux jq/Lua/SQLite suites with file I/O; owned address
spaces on both roots; desktop launcher/damage. These checks do not widen the
earlier 163-gate frozen receipt or claim a new complete full-matrix run.

The nineteen-function PE32 profile observed eighteen imports in these app
scenarios. This does not independently cover every API branch. It requires
explicit memory/storage/serial/clock grants, uses owned RW/NX heap pages and
stopped CPU services, and preserves strict import/metadata admission. Existing
PE32+ behavior stays separate. This is a private kernel-linked integration;
ordinary installation/launch, other DLLs, TLS, SEH and Windows GUI remain open.

The full goal remains **OPEN**. The original macOS executable still requires
low-address mapping and classic Mach-O/libSystem work. See the
[continuation](2026-10-25-original-cross-os-execution.md).
