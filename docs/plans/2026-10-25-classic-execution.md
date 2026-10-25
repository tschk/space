# Original macOS and Windows execution checkpoint

The full application/desktop goal remains **OPEN**. Frozen runtime source
`c76d83032af071a7bc70f3639de15dd0ba56f1ac` passes all21 focused QEMU checks.
The [machine receipt](2026-10-25-classic-evidence.json) records exact report,
compiler, image and application hashes. This does not widen the historical
163-gate full-matrix receipt.

Both original upstream macOS x86_64 Mach-O and Windows i386 PE32 assemblers run
inside Space. Each CPU profile (`max` and `qemu64`) passes65 original
activations per executable: own help, real source compilation,42 expected
compiler-error exits and21 steady ownership cycles. That is130 macOS and130
Windows activations. Both produce exactly `53706163650a0101020203030404` in
Space's filesystem from the macro/arithmetic source. Their original pinned
executable bytes are unchanged. The [manifest](../../fixtures/applications/fasmg.json)
pins upstream revision, license, archive and executable hashes.

The macOS original observes imports1–8 and11–13. Its declared mmap/munmap
imports9–10 are exercised separately by native provider controls, including
zeroing, cross-page copy, RO permissions, hint conflicts, denied flags and
exact owned-range teardown. Provider controls also verify real FILE item counts,
EOF, file bytes, absolute paths, seek/close failures and actual RTC timeval.
These controls receive zero original-application credit. The Windows original
observes imports1–18; import19 remains declared but unobserved by this workload.

Native low-view checks pass80 activations per CPU and a4103-page owned mapping.
Guest low writes cannot change the supervisor trampoline, boot state, IDT or
privilege-stack backing; null/RX/high-window faults, IRQ budgets and repeated
teardown pass. Existing compatibility32 and native64 context gates pass on both
CPUs. Old native UserAddressSpace checks pass on standard and minimal roots.
Actual Linux jq/Lua/SQLite corpus suites pass. Desktop launcher and damage gates
also pass. Both older318-entry Darwin high-address mapper roots and the
existing Windows PE32+/composed suites pass on the same frozen source. Native controls, regression apps and original assembler activations
remain separately counted in the receipt.

Failures are retained: first fixture compile helper typo, two low-entry hangs
caused by absolute interrupt-state accesses, a native store type mismatch, and
an expanded run invalidated by an input-source edit. None is relabelled as a
passing receipt; the subsequent frozen runs pass their original assertions.

These are synchronous private kernel-linked compatibility integrations over
native owned VM/CPU/VFS objects. They do not execute Apple's dyld/libSystem or
Windows kernel32 binaries. General dependencies, TLS/SEH/frameworks, graphical
apps, ordinary installed launch and cross-personality desktop integration remain
unfinished. Browser/Electron/Pulsar execution is not established.
