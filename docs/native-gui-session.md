# Native GUI application session

The standard boot image includes two separately loaded SCI applications: a small
integer calculator and an editable text field. Launch them from the serial shell
with `gui apps`; this runs the real application session until both are closed.
The command is listed in full-image `help`. Minimal images deliberately exclude
the GUI artifacts/services and report the command unavailable.

Build and boot:

```bash
IN=/path/to/source-built/in BUILD_DIR=/tmp/space-images bash scripts/build-images.sh
qemu-system-x86_64 -kernel /tmp/space-images/standard.bin -m 256M -vga std -serial stdio -no-reboot
```

Type `gui apps` in the serial shell, then use the QEMU display's keyboard/mouse:

- The left surface is the calculator. Type `6*7`, press Enter and see `42` below
  the expression. Backspace edits; `+`, `-`, `*` and `/` work for one binary
  integer expression. Invalid syntax, excessive results and division by zero
  display `err`; editing and Enter recover in the same instance.
- Click the right surface or press Tab to focus the text field. Type and use
  Backspace. Ctrl-S saves the field to `/gui-note.txt` through its declared file
  API. The second row reports `saved`, `loaded`, `denied`, `no disk` or `error`.
  New sessions load the saved bytes. Tab switches between live clients;
  clicking outside them changes neither recipient nor content.
- Escape closes the focused application. The other app keeps its content and
  remains interactive. Closing both returns to the shell. `gui apps` opens fresh
  instances and fresh identity tokens again.

These intentionally small clients each have two eight-character lines on a
64×16 surface. The editor persists at most eight bytes in one fixed file; it
provides no arbitrary filename dialog or general filesystem access. Unsaved edits
are discarded on close. It does not provide full calculator/editor windows,
resize, or run foreign binaries. They use the same
existing typeface implementation as the desktop, with independently owned SCI
heap/font state and loader-granted pixel/ring pages.

Saving requires an attached NVMe disk with a formatted SparkFS filesystem;
RAM fallback is refused as durable storage. For a new exclusively owned blank
64 MiB image, attach it with `-drive file=/path/to/owned.raw,format=raw,if=none,id=owned,cache=writethrough -device nvme,drive=owned,serial=space-gui` and format
that new volume once from the shell with `format`. Subsequent boots reuse the
same disk without formatting. Without NVMe the apps remain usable and Ctrl-S
reports `no disk`.

The bounded session uses synchronous CPL0 clone domains; it does not prove
hostile-code isolation. Each private manager record captures an opaque runtime
generation handle. Close retires that exact instance, withdraws input routing,
drains its exchange and detaches compositor surfaces/pools before releasing its
owned image, heap, ring/pixel and clone-table backing. The other client remains
live. Closing both also retires/releases the input instance. Reopen reuses the
bounded manager/event storage and free runtime slots with fresh generations;
admission counts reusable capacity. See [compositor/client ownership](compositor-client-split.md).
The [full application goal](compatibility-coverage-goal.md) remains active.

## Build and test contract

Standard image kinds20/21 carry exact named `GuiCalc`/`GuiEditor` artifacts,
validated by `pack-gui-sci.py`; kind22 carries on-demand seat input. The calculator
requires only named memory/display rights (mask20). The editor explicitly adds
`GuiNoteFile(read, write)` storage authority (mask52). Packaging rejects a dropped,
renamed or widened declaration. `gui-note-store.in` checks the current domain's
storage capability before pointer/FS access, bounds buffers to eight bytes in
the SCI heap, and accepts only the actual NVMe backend. Its API names one fixed
file and reuses the existing `fs-read-file`/`fs-write-file` facade. Existing
kind3 remains asynchronous boot input and is not used for this session. The full
shell delegates to `gui-session.in`; it contains no application implementation.
The session requests explicit retained SCI activation, keeping its live endpoints
outside the ordinary synchronous application cleanup path.
Minimal imports no GUI session/manager and packs none of these three kinds.

```bash
python scripts/check-standard-gui.py --in /path/to/source-built/in
```

This builds the ordinary distributable images and launches `gui apps` through
the actual standard shell, without a temporary kernel root or injected fixtures.
It drives real PS/2 keyboard/pointer/Tab input, checks every client glyph pixel
and border, exercises calculations/error recovery/text editing, closes one client
while the other works, closes both, reopens, edits and closes again. It also boots
the ordinary minimal image and checks refusal. Evidence includes compiler/source
and image hashes, build/serial logs and screenshots in its build directory.
The synthetic retained-client proof, native temporary-root app gate and original
image-variant/application/desktop regressions remain independent checks.


The persistence gate creates its own blank disk and exercises five distinct QEMU
processes; it never writes test text from the host:

```bash
python scripts/check-gui-note-store.py --in /path/to/source-built/in
python scripts/check-gui-persistence.py --in /path/to/source-built/in --out /tmp/new-gui-persistence-evidence
```

It checks actual Ctrl-S saves at the eight-byte limit (a ninth typed character
is refused), same-boot reopen, independent calculator operation,
VM reboot/remount, shorter and empty replacement, and exact glyph pixels and disk
bytes. A deliberately modified negative image strips the editor's storage grant
after production packaging; load/save then render `denied` and the target inode
and bytes remain unchanged. That negative image is explicitly outside the named
production artifact policy. The service guard model also verifies denied, stale,
out-of-bounds and unavailable-backend cases cause no FS calls or allocations.

Authorized saves may allocate filesystem service cache/metadata. The session
accepts an allocation-baseline update only when its trusted file-service epoch
advances once for editor Ctrl-S; ordinary input and domain/capability counters
remain stable. A validated close updates the free-list baseline only when the
trusted lifetime epoch advances exactly once; the independent lifetime observer
checks actual reclaimed ownership and resource counts.

The lifetime gate runs at least129 same-boot standard sessions, with real input,
exact pixels, both close orders, survivor edits and fresh reopen. Its optional
private observer wraps the actual product functions in a temporary kernel root;
it checks reclaimed frames, retired authority, zero live ledgers after each
session, stable resource counts after warmup, stale handles against recycled
canary/new-client memory, wrong-owner and guest refusal, and kernel alias ABA.
The uninstrumented distributable session remains an independent gate.

```bash
python scripts/check-gui-lifecycle.py --in /path/to/source-built/in --out /tmp/new-gui-lifetime
python scripts/check-gui-lifecycle.py --in /path/to/source-built/in --observe --out /tmp/new-gui-ownership
```
