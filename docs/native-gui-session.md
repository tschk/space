# Native GUI application session

The protected default now selects client-owned DejaVu mono/sans coverage at
14/21px for the existing2/3 text configurations. Labels use measured advances;
field/caret cells stay10/15px wide. Each SCI client decodes its own bounded
atlas and paints its granted canvas. Legacy bitmap clients retain their old
provider. This remains an ASCII profile and the editor still holds eight bytes.
See the [typography continuation](plans/2026-10-25-protected-client-typography.md)
for ownership and exact visual verification.

The standard boot image includes readable calculator and notes windows, each
executing as its own retained SCI component. Type `gui apps` in the serial shell;
the session runs until both applications close. Full-image `help` lists the
command. Minimal images exclude the optional GUI applications/services and
report the command unavailable.

```bash
IN=/path/to/source-built/in BUILD_DIR=/tmp/space-images bash scripts/build-images.sh
qemu-system-x86_64 -kernel /tmp/space-images/standard.bin -m 512M -vga std -serial stdio -no-reboot
```

Use the QEMU display's keyboard and mouse:

- The left window is the calculator. Type `6*7` and press Enter for `42`.
  Backspace edits. One binary integer expression with `+`, `-`, `*` or `/` is
  supported, bounded to eight input characters. Invalid syntax, excessive
  results and division by zero display `err`; editing and Enter recover.
- Click a window or press Tab to focus it. The focused window has a blue border
  and a visible caret. Notes accepts eight printable ASCII characters, with
  append/backspace editing at the end. Ctrl-S saves to `/gui-note.txt`; status
  reports `saved`, `loaded`, `denied`, `no disk` or `error`. Selection, multiline
  editing and arbitrary filenames are not implemented. Unsaved edits are
  discarded on close.
- Ctrl-G switches between the existing 2×/3× text sizes. Ctrl-O cycles 1024×768,
  1280×720 and 1920×1080 output modes. Both shortcuts are visible inside each
  window. Resize preserves expression, answer, notes, status and focus; both
  windows stay onscreen, including 1024×768 at 3× text.
- Escape closes the focused app. The other app keeps its content and remains
  interactive. Closing both returns to the shell. `gui apps` opens fresh
  instances and identity generations again.

The clients paint their own backgrounds, titles, labels, content, status and
caret using existing Space UI Sans and Space Term Mono assets. The supervisor
owns output-relative placement, focus and validated scalar configuration events.
These are bounded native applications, not foreign GUI adapters or a complete
desktop window manager.

Saving requires NVMe with a formatted SparkFS filesystem; RAM fallback is refused
as durable storage. For a new exclusively owned blank 64 MiB image, attach
`-drive file=/path/to/owned.raw,format=raw,if=none,id=owned,cache=writethrough -device nvme,drive=owned,serial=space-gui`
and format that new volume once with the shell's `format` command. Subsequent
boots reuse the disk without formatting. Without NVMe the apps remain usable
and Ctrl-S reports `no disk`.

## Artifact, authority and lifetime

Standard kinds 20/21 carry exact named `GuiWindowCalc`/`GuiWindowEditor` artifacts;
kind 22 carries on-demand input. Their declarations explicitly request
`GuiDisplay(present, window)`. The calculator's exact mask is 20; the editor adds
`GuiNoteFile(read, write)` storage, mask 52. Packaging rejects dropped, renamed or
widened declarations. The version 1 canvas trailer declares 768×384 maximum BGRA
extent, 3072-byte stride and 1179648 bytes. The runtime validates the profile and
grants before mapping 288 individually owned frames; no physical contiguity is
assumed. A kernel-only view above 4 GiB provides contiguous server access. Actual
configured visible dimensions are bounded to the current output.

The editor's checked file API verifies current domain/capability before pointer,
filesystem or allocation work; buffers stay within its SCI heap and at most
eight bytes. The fixed-file API reuses existing FS read/write services. Missing
storage authority refuses without changing the target inode or contents.

Each private manager record captures an exact runtime generation handle. Close
retires that instance, withdraws input routing, drains its exchange and detaches
surface/pool references before releasing owned image, heap, ring, pixel and
clone-table backing. Closing both also releases input. Reopen reuses bounded
supervisor storage and free runtime slots with fresh generations. Admission
checks reusable slots and a conservative fixed-allocation frame budget.

Execution remains synchronous trusted CPL0 with identity-map clones. Startup
borrows a supervisor-owned 48-byte visual configuration read-only through
`cap-info+64`; clients copy scalar fields and retain no pointer. Later updates
use versioned SPDP configure/ACK/focus frames. This convention does not establish
hostile-code isolation; protected startup will require an owned bounded copy.
No manager-record, private-capability or runtime-handle pointer is passed to apps.

The original 64×16 `GuiCalc`/`GuiEditor` and synthetic clients remain independent
one-page protocol fixtures. `GUI_PROFILE=legacy` explicitly builds that test
profile; the default standard product uses readable windows. Minimal imports
no optional GUI manager/session and packs none of kinds 20/21/22. Existing kind 3
asynchronous boot input is separate from this on-demand session.

## Actual checks

Use an explicit source-built compiler and new evidence directories:

```bash
python scripts/check-standard-gui.py --in /path/to/in --build-dir /tmp/new-standard-gui
python scripts/check-gui-windows.py --in /path/to/in --out /tmp/new-window-matrix
python scripts/check-gui-lifecycle.py --in /path/to/in --observe --out /tmp/new-window-lifetime
python scripts/check-gui-persistence.py --in /path/to/in --out /tmp/new-window-persistence
```

The matrix drives real PS/2 input across all six output/text sizes, checks exact
two-face glyphs, borders, caret, status and shortcut hints, and verifies live
resize, pointer focus, close/survivor/reopen and ordinary CLI execution afterward.
The lifetime gate requires 129 sessions. Its private observer wraps actual product
functions in a temporary root and checks reclaimed frames, zero live ledgers,
stable counts after warmup, stale generations against recycled/new-client
memory, wrong-owner/guest refusal and removed server mappings. Ordinary mode
tests the unchanged distributable image independently.

Persistence uses its own new NVMe disk and five distinct QEMU processes, without
host-seeded text. It checks saved eight-byte text and a refused ninth key, saved
status/content through live scale/resize, same-boot reopen, VM reboot/remount,
shorter and empty replacement, and exact disk bytes. A deliberate negative image
strips only the editor's storage grant after production packaging; load/save
render `denied` and the full target inode and bytes stay unchanged. This negative
image is explicitly outside named production packaging policy.

Focused declaration, geometry, input, configure/reply and raster-bound models
remain separate from the actual rendering/runtime checks. See the
[readable GUI plan](plans/2026-10-24-readable-native-gui.md),
[canvas ownership](native-gui-canvas.md) and
[full application goal](compatibility-coverage-goal.md) for evidence and remaining
platform work.
