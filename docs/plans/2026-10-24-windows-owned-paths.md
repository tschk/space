# Owned Windows paths and directory state

The next checkpoint is an explicit filesystem profile12 on the existing composed
UTF8 profile. It adds SetCurrentDirectoryW, GetCurrentDirectoryW, CreateFileW and
GetFileType only. Original SQLite imports these names; FindFirstFileW/FindNextFileW,
FindClose and timestamp/flush semantics remain refused until real native provider
contracts exist. The32-import and PE metadata admission guards remain unchanged.

Introduce a reusable native `fs-path-*` caller-buffer normalizer with explicit
cwd/path byte lengths, output capacity and a distinct caller-owned scratch span.
It normalizes '/' and dotsegments, never allocates, never truncates and never
changes output on failure. Inputs are opaque non-NUL native path bytes. Windows
UTF16 validation, drive/separator/device-name policy and cwd authority remain at
the foreign edge. The native pointer helper is excluded from public SCI lookup;
a valid SCI importing it must be refused before allocation.

Windows profile12 declares one C: namespace rooted at the actually granted
synchronous SparkFS storage. C:\\absolute, slash/backslash absolute paths, ordinary
relative paths and C:relative use the same execution-local cwd, initially root.
Unknown drives, UNC/device prefixes, reserved DOS device names, wildcard/control
characters, trailing-dot/space variants and unsupported syntax are refused.
Native SparkFS remains case-sensitive and limits each UTF8 component to24bytes;
this is not an NTFS compatibility claim. Full native path capacity is1023bytes.

Six native-only frames own cwd/candidate/UTF8 workspace, scratch and four stable
1024-byte-per-handle path pools. No guest page or per-call allocation is added.
Existing VFS borrowed-path ownership is retained until actual handles close;
file cleanup precedes releasing those buffers. Paths and cwd never mutate an
ambient native filesystem cwd. Profile12 A/W opens use one canonical path/share
identity; older profiles retain their existing behavior and limits.

All calls check live borrowed Storage before filesystem effects and full guest
pointer/UTF16/bounds validation before publication. SetCurrentDirectoryW changes
owned cwd only after real fs-stat confirms a directory. Files, missing paths,
invalid/denied names and malformed inputs leave cwd/handles/storage unchanged.
GetCurrentDirectoryW reports actual owned C:\\ UTF16 state with query/short/full
buffer count rules. CreateFileW delegates existing real access/share/disposition,
VFS handle and read/write/seek/close behavior through an owned UTF8 path, without
fake open success. GetFileType reports only real owned regular file/UART handles
with their live provider authority; unknown types remain unavailable.

Acceptance: native normalizer independent oracle under default/lean/harden;
actual private SCI denial; CPL3 directory/file/Unicode/drive/relative/dotsegment/
short/query/invalid/revoke cases; exact private ownership, bounds, no partial
writes and no failed cwd mutation; real create/write/close/reopen exact bytes on
NVMe and reboot persistence with no second format; repeated cleanup and all
older Windows gates. Original app diagnostics remain independent and explicit.

Implemented contracts, bounded deviations and separately classified native/
CPL3/NVMe receipts are recorded in [Windows path checks](../windows-path-checks.md).
The regular-file profile refuses trailing separators rather than erasing
directory intent; the exact pre-refusal kernel fails its new fixture control.
No directory enumeration or original-app execution is claimed.
