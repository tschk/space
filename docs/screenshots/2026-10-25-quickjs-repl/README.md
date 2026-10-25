# Actual original QuickJS on Space

These are lossless PNG conversions of actual1024x768 QEMU scanout captures from
the standard-root protected SCI terminal profile at frozen source
`47037aa19171a6afba575a06463cbb5566510210`. No prompts, engine output or pixels
were fabricated. The original static QuickJS artifact is SHA256
`916c0e3e85da7158dfd17d192a8704f0173b1e469dc1d379ee25d5dad48aa1ac`;
the source-built compiler is SHA256
`d2ac79b39f5ea98c5d776e88f550cf4327e89539ceaaf0d9ce591c53aa88ed75`.

- [First process](original-quickjs-0.png): actual interior keyboard editing,
  evaluation and file creation.
- [Second process](original-quickjs-1.png): saved file reopened in a fresh engine,
  fresh-process variable state and JSON evaluation.

The134 actual PS2 events, exact saved file bytes, original output stream,
CPU/VM restoration and stable warmed resources are asserted by the harness.
Each capture matches all294912 terminal pixels independently using pyte/Pillow
and the pinned DejaVu font, with ANSI16 color, bold and reverse support.

[Hashes and scope](../../plans/2026-10-25-quickjs-repl-evidence.json),
[exact visible-profile receipt](../../evidence/2026-10-25-quickjs-repl/original-quickjs-repl-view-receipt.json),
[actual serial log](../../evidence/2026-10-25-quickjs-repl/original-quickjs-repl-view.serial.txt),
[original byte stream](../../evidence/2026-10-25-quickjs-repl/original-quickjs-repl-view.output.bin).
Native CPU controls are separate from original application credit.

The dark background and fixed ASCII80x24 terminal are a finite native integration
profile. These captures do not establish browser, AppKit, Win32 or X11 support,
ordinary desktop launch, concurrent foreign windows or terminal resize.
