# Bounded native SCI validation

`components/sci-validate.in` implements an allocation-free byte-format validator.
The caller must supply an independently trusted readable extent; the size field
inside an image is not evidence that its backing memory exists. This module is
not yet wired into the loader. Existing raw-address loader entry points still
need migration to checked image views before this becomes an admission guarantee.

The bounded profile admits SCI v1/v2 images up to 2 MiB, with aligned virtual
image ranges below 4 GiB. V2 checks both 16-byte record tables, disjoint metadata,
bounded nonempty NUL-terminated names (255 bytes), export offsets into the payload,
and five-byte `call rel32` import patches wholly inside the payload. Import patch
sites cannot overlap. Counts are limited to 4096 exports and 512 imports; every
read is preceded by extent checks. Validation allocates and modifies nothing.

This is structural validation, not native code protection. The format does not
identify executable instruction boundaries or separate code and data sections.
The validator cannot authenticate code, prove arbitrary instruction safety, or
turn trusted CPL0 SCI applications into isolated processes. Capability/name
binding, displacement range, provider lifetime and optional GUI profile admission
remain separate loader responsibilities.

The first proof executes 63 cases in default, lean and harden compiler profiles:

```sh
python3 scripts/check-sci-validation.py --in /path/to/in \
  --out /tmp/sci-validation --artifacts /path/to/compiled.sci
```

`/tmp/space-sci-validation-first/report.json` records the exact tested source,
compiler and real compiled artifacts, including readable calculator/editor
images. Guarded loads independently detect reads outside the supplied extent.
Cases include truncated headers, negative and excessive counts, arithmetic/range
limits, overlapping tables and import patches, empty/unterminated/oversized
names, invalid opcodes, metadata-target exports and valid zero-table images.
All three profiles return the expected acceptance result without an out-of-extent
read. The result is an owning-function proof, not a booted-loader integration test.

Integration must carry boot-image table sizes alongside their pointers, and
require explicit readable sizes for separately staged test images. A mutable
global "last image size" is unsuitable when several images remain live. Run the
validator before symbol diagnostics, allocation, import patching or provider
registration. Self-contained library registration must also refuse imports.
