# Preserved122-gate failures and focused harness repairs

The immutable122-gate run at `/workspace/lab122/report.json` uses committed
`eea9cce` (649 tracked files) and source-built Inauguration0.9.325. The run is
still active. Its first three failures are preserved, with the exact original
logs and generated artifacts. Focused repair receipts do not rewrite that run.

## Compiler corpus: omitted fixture dependency

Both `compiler-linux-standard` and `compiler-linux-minimal` compiled all15
compiler-produced ELF artifacts and passed their native Linux host oracles,
then failed before building a guest kernel. Their privately frozen fixture tree
copied `fixtures/linux-process/checks.in` but omitted its new imported
`fixtures/linux-vm/direct.in` after the native VM migration.

`check-inauguration-linux.py` now copies that dependency. The copied source,
compiler profiles,15 host artifacts,21 measured cycles and all runtime/resource
assertions are unchanged. From `/workspace/compiler-corpus-fixed-source`, based
on the exact122 committed source plus the runner repair:

- `/workspace/compiler-corpus-122-fixed-standard/report.json`: passed15 host
  artifacts and330 actual guest activations.
- `/workspace/compiler-corpus-122-fixed-minimal/report.json`: the same counts
  pass on the minimal root.

All original15 ELF name/SHA256 pairs match the failed reports exactly. Separate
keyboard-editing-source regressions also pass330 activations per root; those
are separately scoped and do not establish exact122 kernel identity.

## Windows environment: socket exists before listen

`windows-environment` built successfully, then got `ConnectionRefusedError`
connecting to the QEMU Unix socket. Pathname existence did not prove the bound
socket was already listening. No guest test ran in that failed invocation.

`check-windows-environment.py` now retries only absent/refused socket connection
within the original10-second readiness deadline, closing each failed candidate.
An early QEMU exit or readiness timeout still fails. The120-second runtime
limit and all380 execution/resource assertions are unchanged.

`/workspace/windows-env-122-socket-fixed/report.json` passes380 actual CPL3
executions. Root independently compared the original and repaired kernel,
fixture and combined-image SHA256 values: all are identical. The combined hash
is `09527a5cc349a7a8c846c6211caaef93c3c09c8cbf58e04f98e9bb1100fee758`.
The adjacent `/workspace/compiler-corpus-fixed-source.manifest.json` records
the exact committed base and two checker overrides.
