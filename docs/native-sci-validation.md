# Bounded native SCI validation

`components/sci-validate.in` implements an allocation-free byte-format validator.
The caller must supply an independently trusted readable extent; the size field
inside an image is not evidence that its backing memory exists. Boot discovery
now validates against the trusted boot-table extent before returning an image.
Known boot images are checked again before runtime lifecycle allocation; file
ingestion checks the actual bytes read. Supervisor-only tests may still use the
legacy raw-address staging helpers: those require trusted valid backing and do
not independently establish a readable extent.

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
read. This first result is an owning-function proof. Subsequent actual loader
integration is recorded below.

`runtime-image-view.in` looks up extent by the exact boot image address; it does
not retain a mutable "last size" when multiple images are live. The file edges
use their actual read count and compare the complete file header against any
previously sampled header before constructing a process. Shared library
registration refuses importing images: registering exports alone does not bind
dependencies or establish their initialization/lifetime.

`runtime-link-validation.in` resolves all imports and verifies signed rel32
displacements before the first patch or provider mapping. Owned allocator
overrides participate in that same target calculation. Known boot runtime
launches preflight before creating any component/cap/domain state. Existing
unresolved-symbol diagnostics are preserved. The independent binding model
passes all three compiler profiles, including exact signed limits, one-byte
overflow, unresolved later imports, null/negative targets and allocator overrides:
`/tmp/space-sci-bindings-valid-range/report.json`.

`/workspace/local-evidence/space-sci-admission-fourth/report.json` boots actual
production admission and runs fourteen malformed structure cases, two binding
denials, an importing-provider denial and a truncated-file denial. Each refuses
without changing lifecycle resource counters or free-list head. Valid sysinfo
runs before and after the denials, with an independent host xorshift result.
Source comes from the separately recorded438-file SCI integration snapshot;
it excludes concurrent CPU/counter/personality work. Earlier harness attempts
are preserved: the first used the runtime handoff offset in a file, and the
next selected an interactive app or assumed its return value. These were harness
errors; the final gate uses the packager's0xF00 handoff and the actual sysinfo ABI.

Actual regression proofs include151 normal/136 emitted-abort ephemeral
activations in `/workspace/local-evidence/space-native-lifecycle-checked-images-v2`,
retained ownership in `/workspace/local-evidence/space-native-retained-checked-images`,
and the readable standard GUI in `/workspace/local-evidence/space-standard-gui-checked-images`.
The earlier lifecycle run rejected its expected serial diagnostic after preflight
moved earlier; the production diagnostic was restored and the unchanged gate now
passes. These results do not establish protected native execution or validate
arbitrary legacy raw-address staging callers.
