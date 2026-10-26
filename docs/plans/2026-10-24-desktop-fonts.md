# Desktop font and palette checkpoint

The desktop's synthetic smoothing of enlarged 8×8 bitmap glyphs produced hollow,
jagged text. The native desktop now uses offline FreeType coverage from pinned
DejaVu Sans and DejaVu Sans Mono at its two supported sizes. Utilities, window
borders, title bars, controls and terminal backgrounds use a consistent dark
palette; the gold focus indication and input/layout contracts remain explicit.

This stays in the current trusted display library. It does not establish a new
SCI font service, move rendering into the nanokernel, or change protected SCI
clients' own bitmap renderer. The assets, provenance, license, reproduction and
bounded encoding are in [the font directory](../../assets/fonts/desktop/README.md).
`font-desktop-atlas.in` owns static encoded masks; `font-desktop-render.in` adapts
the 24-pixel masks to existing clipping/pitch/offset rules. Existing 16-pixel
blending is reused. Missing glyphs retain the existing fallback policy. Only
ASCII is covered; complex shaping, richer editor content and integrated
concurrent foreign windows remain open.

The first two standard-image builds correctly refused the larger generated
store sequences at the unchanged heap-overlap guard. Packing the same coverage
as data fixes that failure. The normal protected standard image then builds at
2,011,728 bytes in the scoped receipt and passes its actual interaction test;
later source changes require their own image/checkpoint. No address limit or
performance threshold was raised. Failed build receipts remain intact.

Local verification with frozen Inauguration 0.9.325:

- `/workspace/desktop-font-pixels3/report.json`: all 380 ASCII glyphs across
  both faces/sizes match the independently rendered FreeType oracle, including
  all 2,073,600 framebuffer pixels, clipping, render offsets, screen edges and
  invalid-codepoint refusal.
- `/workspace/desktop-fonts-final-output-rle/results.json`: 12 native/JIT model
  checks and actual QEMU output/scale, UTF-8 fallback, tiling and input checks.
- `/workspace/desktop-fonts-final-launcher-rle`: real keyboard query/selection,
  pointer focus/resize, terminal input, minimize/restore and close checks pass.
- `/workspace/desktop-fonts-protected-default3/report.json`: the distributable
  protected GUI passes six sizes, keyboard/pointer input, exact client pixels,
  caret/status/hints, resize, close/survivor/reopen and later application launch.
- `/workspace/desktop-fonts-damage`: the existing opaque moving-window stress
  profile passes at 263 fps against the unchanged 30 fps threshold. This is not
  a benchmark of every anti-aliased desktop interaction.
- `/workspace/desktop-fonts-visual2`: actual `fetch` input/output and the full
  title match font/layout pixel oracles; the translucent dark surface matches
  its exact blend. The old full-colour pixel-count assertions described another
  font's stroke weight; exact text/content comparisons replace them. The earlier
  failed visual receipt remains preserved.

These are scoped focused results. They do not extend the historical 144-gate
integration receipt or complete the [full goal](../compatibility-coverage-goal.md).

## Measured desktop metrics

The later measured profile removes the old bitmap grid's excessive tracking.
UI advances come from the same pinned FreeType font used for coverage; terminal
cells are 10 pixels at 2x and 15 pixels at 3x, with 13/19-pixel baselines. Caret
measurement, hit testing and drawing use the same profile. Missing-glyph boxes
fit inside a terminal cell, including UTF-8 fallback at both scales. The terminal
caret is narrower. The profile is enabled during framebuffer initialization
before text-cache invalidation; there is no public live font-provider switch.
The controlled legacy bitmap model and protected clients keep their old metrics.

`/workspace/desktop-metrics-pixels3/report.json` checks 380 glyph/scale/face advance
cases through both raw and cached lookup, full-frame pixels, native baseline and
UTF-8 caret/hit/fallback behavior at both scales. The ordinary launcher, output
mode/scale, exact title/fetch pixel and protected default GUI checks also pass.
`/workspace/desktop-metrics-damage1` passes 250 fps against the same 30-fps bound;
this profile now renders the mature glyphs during stress rather than selecting
the legacy bitmap shortcut. Sources and receipts remain separate from the first
font checkpoint and the earlier151-gate source.


The measured profile is now integrated in the separate frozen `c408746`
152/152 passing application lab, with source/compiler/application integrity
passed. [QEMU captures and provenance](../screenshots/2026-10-24/README.md) are
checked into the draft for visual review. This result does not extend the older
font or integration receipts or cover the protected clients' bitmap typography.
