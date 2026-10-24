# Native screen continuation

The original pinned BusyBox vi now accepts real PS/2 editing through native
terminal queues and retained CPU waits, saves exact bytes and reopens in a new
protected process. Its output is still an ANSI stream, not a desktop surface.
The full project goal remains active while this display path is implemented.

Use the MIT-licensed VTE 0.13.1 transition rules as reproducible native data,
checked against all 4,096 bytes evaluated by the original upstream Rust macro.
Keep parser state separate from screen policy and rendering. Bound parameters,
intermediates, strings, cell storage, cursor motion, alternate screens and
damage. Unknown sequences cannot become memory addresses or device operations.
The initial real application uses ASCII; Unicode/shaping and complete terminal
compatibility require their own executable evidence.

The client owns its screen and pixels. Present through existing surface/shared
buffer contracts, retaining focused seat ownership and native process lifetime.
Inspect actual QEMU pixels during keyboard edits, independently compare cells
with the original output stream, save/reopen, close and restore the parent
desktop. An image rendered by a host oracle is comparison evidence only.
