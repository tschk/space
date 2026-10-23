# Owned Windows directory and wide file paths

Profile12 composes the prior UTF8/services profile with SetCurrentDirectoryW,
GetCurrentDirectoryW, CreateFileW and GetFileType. Its private native entry is
`windows-command-filesystem-run(image,size,config)`, using the explicit96-byte
launch descriptor. It requires live native Storage bound to the current direct,
synchronous SparkFS provider; asynchronous Volume RPC is refused. Serial and
memory grants retain their separate existing roles. No ambient native cwd is
changed. Earlier profiles retain their path/layout/admission behavior.

## Native and foreign ownership

[fs-path-normalize.in](../components/fs-path-normalize.in) is a separate reusable
native utility with explicit cwd/path byte lengths, output capacity and distinct
caller-owned scratch. It handles opaque non-NUL bytes, '/' and dotsegments.
It returns canonical length or an error, never allocates or truncates, and
commits output only after complete input processing succeeds. Inputs may alias
output; scratch must not alias either input or output. Scratch may change on
failure. Bounds and pointer arithmetic are checked before reading. This is a
native caller-buffer contract, not an untrusted guest-pointer API. Its fs-path-*
helpers are excluded from SCI lookup, with actual import denial before entry
or allocation.

The Windows edge in [windows-process-paths.in](../components/windows-process-paths.in)
owns drive/separator/device policy, strict UTF16/UTF8 input, live Storage checks,
owned cwd, native path buffers and foreign errors. Two native-only workspace
frames hold cwd, canonical candidate, input UTF8, scratch and path-pool pointers.
Four additional native frames provide one stable1024-byte path per handle slot.
These six frames are distinct from guest backing and are never guest mapped.
VFS borrows each owned path until the handle closes. All files close before any
path frame is released, including after faults, deadlines or revoked grants.
No per-call native heap allocation or additional guest page is introduced.

The declared C: namespace maps to the actually granted native filesystem root.
C:\\absolute, slash/backslash absolute paths, relative paths and C:relative use
one activation-local cwd, initially C:\\. Drive letters are ASCII insensitive;
native file components remain byte-exact and case-sensitive. This is not an
NTFS/casefold/ACL emulation claim. Strict UTF16 converts real supplementary
characters to UTF8; profile12 CreateFileA uses the same declared UTF8 namespace.
A/W opens canonicalize to the same share identity.

Paths are bounded to1023 UTF8 bytes including drive removal/cwd joining, with
1024 bytes for each stable NUL-terminated buffer. Every native component is
limited to24 UTF8 bytes by actual SparkFS representation. Native normalization
has a2048-byte scratch area, so intermediate cwd/path concatenation can be
processed before testing the final1024-byte output capacity. Unknown drives,
UNC/device prefixes, ASCII DOS device names, wildcard/control/colon forms,
trailing-dot/space components and unsupported syntax are refused. No directory
iteration or timestamp results are invented. Regular-file opens explicitly
refuse trailing separators with error123; they do not strip directory intent
and accidentally open an existing file prefix. SetCurrentDirectoryW still
accepts directory separators and dotsegments.

## Observable behavior and refusal

Every new path call checks its live provider authority before effects. Changing
cwd uses real fs-stat and publishes the new cwd only after confirming a native
directory. A regular file fails267, a missing path3, an unknown drive15, UNC/device
prefix50, forbidden filename syntax123, unrepresentable bounds206, malformed
Unicode1113 and inaccessible guest input998. Empty cwd input fails3; NULL fails87.
Failures preserve the previous owned cwd. Metadata/format caches used by native
lookup are not claimed to be a crash-atomic filesystem transaction.

GetCurrentDirectoryW converts actual owned cwd to UTF16 C:\\ form. A query or short
buffer returns required units including NUL, with no writes; success returns
units excluding NUL and preserves LastError. The entire declared writable span
is validated before writing, including unaligned/cross-page boundaries. Unused
output tail bytes are preserved. Invalid pointers fail87/998 and excessive
bounded capacity8. Missing/revoked Storage fails5. Revocation does not retract
already mapped process pages or prevent unconditional owned-handle cleanup.

CreateFileW and profile12 A opens share the existing real file access/share/
disposition implementation. Synchronous regular-file operations retain their
strict argument profile: read/write access, declared sharing0..3, no security
attributes/template, normal attributes0x80, and dispositions1..5 with write
required for create/truncate. Existing files, sharing conflicts and disk failures
retain their tested errors. No original API is made successful through a stub.
Regular VFS handles report FILE_TYPE_DISK; real owned stdout/stderr UART tokens
report FILE_TYPE_CHAR only with live serial authority. Invalid handles fail6.
Regular-file classification checks the live storage provider. Unknown resource
types and directory handles are unavailable.

The existing guest ledger remains87 pages for this fixture and at most1100 for
the largest admitted image, below1152 capacity. Six additional private frames
are reserved before activation: image pages+80+67+14+6. Cold caches independently
require exactly26912 bump bytes; free frames cannot fund that retained storage.
The new utility and profile add no CPU/runtime assembly changes.

## Executable acceptance

```bash
python scripts/check-fs-path-normalize.py --in /path/to/in --out /workspace/path-model
python scripts/check-windows-paths.py --in /path/to/in --out /workspace/path-guest
python scripts/check-windows-path-persistence.py --in /path/to/in --out /workspace/path-nvme
python scripts/check-windows-composed-dependencies.py --profile 12 --apps /tmp/windows-cli --out /workspace/path-dependencies
```

The independent native normalizer oracle passes233 cases each under default,
lean and harden: absolute/relative/root/dotsegments, byte-exact Unicode, boundary
capacities, scratch/input/output alias rules and output unchanged on refusal.
This source model is separate from actual guest execution.

The actual focused gate passes1326 CPL3 activations:63 regular cases repeated21
cycles, one exact cold recovery, one live-revoke case and one fresh activation.
It checks real file/directory/missing state, C:/relative/backslash/dot behavior,
Unicode filenames and supplementary pairs, case-sensitive names, query/short/
full cwd counts, output tails, bad/readonly/overflowing/unmapped pointers,
24/25-byte and exact Unicode component limits, >255-byte cwd, an exact1023-byte
wide/A file roundtrip,1024-byte refusal, A/W share conflict, private workspace
and borrowed-handle-path CPU read faults, held-file deadline and Storage revoke.

An observer compares native inode and bitmap bytes around directory operations
and denied file operations. Failed calls preserve cwd, owned handles and VFS
free descriptor state. Guest output snapshots catch failed/short partial writes
and successful output-tail changes. Each activation owns and releases all
resources, with exact repeated heap/free-frame/domain/caller-capability/FS/GS
invariants. A valid native SCI import of the new pointer helper is denied before
allocation. The cold test refuses177 frames unchanged, then recovers with178
and exactly26912 retained bump bytes. Initializers and filesystem workspaces are
explicitly warmed before this isolated admission measurement.

The NVMe gate creates one new owned64MiB disk and requires nvme-ready1,
sf-mem-disk0 and no Volume service. Only bootA formats it. The protected guest
uses CreateFileW/WriteFile/CloseHandle and CreateFileA/ReadFile/CloseHandle for
`/wp/é😀.txt`; bootsB/C read the same file in independent QEMU processes. Each
boot performs21 activations with stable ownership. A separate read-only raw-disk
oracle walks real nested directory entries and checks the byte-exact UTF8 name,
inode and16 content bytes. There is no host file forwarding, RAM fallback,
second format or fictional persistence claim. This demonstrates the synchronous
write/close/reopen contract; no journaling or crash-atomic guarantee is added.

Final local receipts are `/workspace/wpath/final/report.json` (1326 focused),
`/workspace/wpath/nvme-final/report.json` (63 activations/3boots),
`/workspace/wpath/model1/report.json` (233×3 source models),
`/workspace/wpath/cli-final/report.json` (546 original refusals), and
`/workspace/wpath/dependencies/report.json` (independent static dependencies).
Nineteen previous Windows gates passed under `/workspace/wpath/reg-*-final/`,
including prior Unicode/composition, six older NVMe boots and all old profiles.
The final trailing-separator guard affects only new profile12; focused/NVMe/CLI
receipts were rebuilt after that narrow review fix. The selected compiler is
frozen source-built0.9.324; hashes and classifications are recorded separately.

The frozen pre-guard kernel is also tested with the final fixture/oracles at
`/workspace/wpath/trailing-control/report.json`. It fails the new trailing-file
separator case60 with guest UD2/status134 rather than returning the expected
refusal. The corrected source passes the same case, including A/W and Unicode
variants. This is a preserved actual regression control, not a success fixture.

## Remaining original application boundary

The independent unchanged SQLite analysis now finds52 implemented imports out
of157, with105 unsupported. The new filesystem union's first unsupported name is
one-based slot5, FindClose; previous command/composed/Unicode diagnostics remain
unchanged. Structural entry/preferred base,946 image pages, directorymask0x46c
and the32-import execution bound remain intact. The actual original-app gate
retains546 allocation-free refusals across13 profiles. Original SQLite,7za and
jq still do not execute.

Next establish a real bounded native directory iterator before implementing
FindFirstFileW/FindNextFileW/FindClose. Wide deletion/directory creation, timestamp,
flush, mapping/module/locale and validated PE metadata remain separate contracts.
