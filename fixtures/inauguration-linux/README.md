# Synthetic compiler → ordinary Linux ABI → Space corpus

These are compiler regression programs, separate from the unmodified upstream
jq/Lua corpus. They contain no Space interface or compiler policy. Inauguration
emits ordinary static x86_64 Linux ELF executables for Default, Lean and Harden;
the exact same bytes run on the host and in Space's strict CPL3/IOPL0 process.

The cases cover mutable globals/calls, UTF-8 string and array payload relocations,
Rust array value copies through owned mmap/memcpy, and nonreturning owned abort.
Normal exit statuses must match the host oracle exactly. Abort must issue Linux
exit_group (231), return 134, and produce no CPU-fault marker. The independent
CLI negative control must fault on the host (SIGSEGV) and in Space (#GP, status
141), proving guest code cannot disable interrupts.

Run from the Space checkout on Linux x86_64:

```sh
python3 scripts/check-inauguration-linux.py --in /path/to/source-built/in \
  --out /tmp/compiler-linux-standard
python3 scripts/check-inauguration-linux.py --in /path/to/source-built/in \
  --root minimal --out /tmp/compiler-linux-minimal
```

Each root runs 15 compiler artifacts, warms every artifact once, then performs
21 complete cycles: 330 actual activations, comprising 198 normal exits,
66 intended aborts and 66 hardware negative controls. The minimal test bootstrap
explicitly imports the Linux component; this does not add a personality to the
production minimal root.

The gate snapshots all source inputs, records compiler/ELF hashes, checks RX code,
RW data and NX stack, and supplies ELF bytes with high physical QEMU loaders
outside the boot layout's reported range. It requires real successful mmap
results for array cases. Every measured activation must restore heap/free-list,
domain records/owned bits, current capability, FS base, syscall hook, interrupt
budget state and process ledger. A separate same-VA domain sentinel must survive.
Failures retain report.json, compiler output, source snapshots and serial logs.

This establishes the tested compiler/Linux ABI slice. It does not establish
upstream application passes, GUI rendering, general libc, threads or borrowed
Rust slice execution.
