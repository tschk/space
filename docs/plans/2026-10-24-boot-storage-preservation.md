# Preserve user files during ordinary boot

The full root ran `test-sci-loader` unconditionally after filesystem init. That
diagnostic writes a40-byte SCI to `test.sci`, then reads and executes it. An
ordinary boot of an existing NVMe volume therefore created or overwrote a user
file and changed disk metadata. A read-only directory-reopen experiment exposed
this real product behavior.

Automatic boot now runs the file-loader diagnostic only on the newly allocated
disposable RAM filesystem, with no Volume backend. Persistent NVMe and Volume
boots do not run it. The explicit shell `selftest` bundle retains its existing
mutating diagnostic behavior; this change governs ordinary boot, not that
explicit diagnostic command. The minimal root already omits this self-test.

Actual local evidence, frozen compiler0.9.325:

- `/workspace/native-directory-boot-preserve/report.json`: three independent
  NVMe boots,63 snapshots of1698 real entries,1697 independently checked file
  payloads and a user-owned `test.sci` sentinel. Only boot A formats. B/C leave
  every disk byte unchanged, including the sentinel. The ordinary boot path is
  present; no mutating boot call is removed in this experiment.
- `/workspace/boot-preserve-old-control/report.json`: the prior boot root with
  the same native provider, compiler, fixture and independent oracle fails with
  `ordinary boot changed user-owned test.sci`. The failure is retained.
- `/workspace/boot-preserve-names/report.json`: all three actual NVMe filename/
  deep-path/remount boots pass. The host oracle requires15 live inodes each
  boot, rather than accepting an extra boot-created diagnostic file.
- `/workspace/boot-preserve-qemu.log` and
  `/workspace/boot-preserve-execve.log`: ordinary RAM boot still passes the
  file-loader smoke test, and explicit POSIX SCI execution from the RAM
  filesystem still returns the real guest status.

The regression source is isolated at `/workspace/boot-preservation-source`,
with origin and its three explicit overrides recorded alongside it. The native
provider implementation is unchanged by the boot fix. This does not add crash
atomicity, arbitrary read-only mounts or foreign GUI application support.
