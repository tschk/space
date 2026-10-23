# FLTK application workload

The full application goal names upstream FLTK 1.3.9 `fluid` on Linux, Darwin
and Windows. The [manifest](../fixtures/applications/fltk-1.3.9.json) now pins
the acquired official source archive, its recorded revision, license, Linux
build configuration and measured binary. No upstream application source was
patched. The checksum is measured acquisition evidence, not a separately
authenticated upstream checksum. Darwin and Windows builds remain required.

The Linux build uses FLTK's real X11 backend and static FLTK libraries with
dynamic system C/C++/X11 dependencies. OpenGL and optional X11 extensions are
disabled explicitly; this does not make it a Space port. Local development
headers and test display packages were extracted into an owned directory, with
their package hashes retained in the host report. Build logs include the initial
missing-library failure and subsequent complete library/application build.

The host reference at
`/workspace/real-apps/fltk-1.3.9/host-reference/report.json` records actual
software display, pointer and keyboard interaction: open upstream `test/resize.fl`,
double-click its box, replace its label with `SpaceGUIReference42`, save using
Ctrl+S, exit using Ctrl+Q, then reopen the saved file in a fresh process and
inspect the exact label. `edited.fl`, its content hash and screenshots are
retained. This is a partial host reference, with resize, independent instances
and crash recovery still required. It is not Space GUI execution.

The original binary is ELF PIE and needs `libX11.so.6`, `libstdc++.so.6`,
`libm.so.6` and `libc.so.6`, plus their transitive dependencies. Space's current
protected Linux loader accepts fixed-address static ELF. Its actual validator
refuses this exact binary with -8 twice, before heap/resource mutation:
`/workspace/fluid-admission-third/report.json`. The512MiB guest independently checks every injected payload byte with a
host-derived FNV-1a oracle before validation. The payload is never entered.
The initial diagnostic failed to link the process validator into its probe;
`/workspace/fluid-admission-first` retains that harness failure separately.
The second diagnostic used only256MiB RAM for an injection at256MiB; its
receipt is explicitly invalidated. The corrected third run adds sufficient RAM
and the full byte oracle, and is the only valid admission receipt.

```sh
python3 scripts/check-linux-gui-admission.py --in "$IN" \
  --app /path/to/fluid --out /tmp/fluid-admission
```

This diagnostic intentionally exits nonzero while the application is blocked;
a successful refusal check is not an application pass. It records exact source,
compiler and artifact hashes and detects changes during the run. Use
`--source-root` to select an immutable source checkpoint.

Next work requires real protected dynamic-loader/dependency initialization and
an owned Linux GUI contract. Preserve the original X11 program as a foreign
compatibility target. A separately configured native backend would be a port
with its own profile. Either route must present actual client pixels, edit and
save/reopen the project, resize, route focused input between independent
instances, and reclaim resources after close/fault. No fake X11 API success or
host-forwarded workload counts toward the Space acceptance matrix.
