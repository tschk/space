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
  Backspace. Tab switches between live clients; clicking outside them changes
  neither recipient nor content.
- Escape closes the focused application. The other app keeps its content and
  remains interactive. Closing both returns to the shell. `gui apps` opens fresh
  instances and fresh identity tokens again.

These intentionally small clients each have two eight-character lines on a
64×16 surface. Text is in memory only. They do not save files, provide full
calculator/editor windows, resize, or run foreign binaries. They use the same
existing typeface implementation as the desktop, with independently owned SCI
heap/font state and loader-granted pixel/ring pages.

The bounded session uses synchronous CPL0 clone domains; it does not prove
hostile-code isolation. Close detaches compositor references and retires tokens.
The loader retains instance/domain/page backing, so repeated sessions consume
resources. Launch refuses before the monotonic domain/capability tables cannot
admit all three instances. Reboot restores capacity. Physical reclaim requires
the ownership/alias ledger described in [compositor/client ownership](compositor-client-split.md).
The [full application goal](compatibility-coverage-goal.md) remains active.

## Build and test contract

Standard image kinds20/21 carry exact named `GuiCalc`/`GuiEditor` artifacts,
validated by `pack-gui-sci.py`; kind22 carries on-demand seat input. Existing
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
