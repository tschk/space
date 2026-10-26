# Original Helium and Firefox on Space

Both browsers are required real application targets. Completion means original
browser code executing inside Space, rendering actual HTML/CSS/JavaScript,
loading a controlled HTTP/HTTPS site with correct certificate/error behavior,
and responding to keyboard, pointer, focus, resize and close/reopen. Preserve
independent windows and resource cleanup. A small browser, terminal, host browser
or painted imitation does not satisfy either target.

Start with the already acquired original Linux x86_64 packages: Helium0.20.1.1
and Firefox158.0.1. Verify archive and complete executable hashes, inventory
ELF interpreter/dependency requirements, and attempt the actual protected Space
process path. A refusal is a failure to run, never application execution credit.

The current Linux edge accepts fixed-address static ET_EXEC only, refuses
PT_INTERP/PT_DYNAMIC and bounds source bytes to16MiB. Helium's original main
executable is294059232 bytes; Firefox's smaller launcher still needs a real
ELF interpreter and shared libraries. Do not patch their headers or replace
their engines. Increasing a size bound alone cannot make these browsers work.

First implement a reusable direct self-relocating ET_DYN entry profile over the
existing native UserAddressSpace. Use a deterministic checked load bias, actual
mapped program-header/entry auxv addresses, and original stack/exec ownership.
Do not relocate foreign code in the kernel. Refuse PT_INTERP until an explicitly
owned interpreter/dependency graph exists; refuse DT_NEEDED in the direct
profile. The original glibc runtime linker is an intermediate real workload,
not browser success. Add malformed segment/dynamic metadata, overflow, missing
entry, denied grants, own auxv/exec and repeated cleanup controls.

Then supply an owned executable/interpreter image pair with correct AT_BASE,
AT_ENTRY and AT_PHDR, native immutable dependency observations and actual
file-backed mapping. Drive subsequent VM/TLS/thread/futex/event/socket/display
contracts from the original runtime's observed failures. X11/Wayland and mature
text/rendering dependencies must translate to Space surface/seat services;
retain the native component/capability/object/execution graph. No success stubs,
ambient host pointers or foreign kernel in the nanokernel.

Retain exact original artifacts, compiler/source identities, command, real
execution-started state, output, status, logs and actual rendered evidence.
Keep the full compatibility goal and browser acceptance OPEN until reproduced.

The direct runtime-linker profile now passes63 original loader activations,
42 separately counted own auxv/self-exec/writev CPU entries and16 malformed
metadata refusals. Help, version and option-error output/status are compared
exactly. The host reference has AVX-enabled hardware; the declared QEMU max/Space
profile has no enabled AVX XSAVE state and reports only glibc-hwcaps v2. Preserve
both references and compare the complete output with only those two explicitly
different CPU labels. The first exact host comparison failed on that real
hardware difference, and remains preserved. The first harness compile also
failed on a nonexistent copy-helper name; its evidence remains unchanged.

The original loader's first execution exited0 despite losing help text to
unsupported writev. That exit alone is not acceptance. The new synchronous
writev edge reuses scalar serial/file writing, checks every vector before any
output and refuses pipes/retained terminals before effects. Own CPU controls
verify exact file bytes, self-exec/auxv, a late bad pointer leaving the offset
unchanged, count/length limits, zero vectors, invalid descriptors and unsupported
pipe vectors. Twenty-one cycles check stable warmed frames/heap/domains/caps
and supervisor restoration. Original browser entry remains zero: actual full
protected launch attempts return-8 without CPU entry or ownership mutation.

The glibc artifact is reproduced byte-for-byte by extracting the pinned official
Debian libc6 package. No browser or glibc source/binary is patched or copied into
the native implementation. Original binaries remain outside git. The standalone
`check-linux-dynamic-entry.py` prerequisite gate is separate from browser success
and does not inflate the existing complete app-lab receipt or gate counts.
