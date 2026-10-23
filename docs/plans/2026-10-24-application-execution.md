# Full application goal: execution checkpoint

The user explicitly requests continued implementation and real local application
testing until the full goal works. The authoritative destination and completion
matrix are [compatibility-coverage-goal.md](../compatibility-coverage-goal.md).
This checkpoint does not close that goal or narrow its required outcomes.

## Verified implementation

All evidence below comes from local execution, with source-built frozen
Inauguration0.9.324, SHA256
`43b5a2f166efb28ea3123e8030c549d1eac9e90ee7c642d013457ff7ade09168`.
It is not a claim of a single latest whole-tree regression run. Application
provenance and exact binaries live in `fixtures/applications` manifests; no
upstream payload was rewritten into a fixture to count as an application.

| Implementation | Actual evidence |
|---|---|
| Original Linux jq1.8.1 | `/tmp/space-linux-jq-clean-entry21/report.json`:81 app activations,21 repeated cycles, actual private CPL3 execution |
| Unmodified upstream Lua5.4.7 | `/tmp/space-linux-lua-clean-entry21/report.json`:222 app activations; `/tmp/space-linux-positional-lua21/report.json` adds actual pread/pwrite behavior and offset preservation |
| Unmodified upstream BusyBox1.36.1 | `/tmp/space-linux-busybox-clean-entry21/report.json`:100 app activations; echo/cat/wc/printf and basic ash scripts; source-built pinned static configuration |
| Unmodified upstream SQLite3.46.1 | `/tmp/space-linux-sqlite-clean-entry21/report.json`:31 app activations with in-memory SQL, JSON, Unicode, recursive/window queries, transactions, blobs and errors |
| Linux lifetime/security | Each corpus exercises21 cleanup cycles,105 actual guest CPU faults, live authority/pointer denials, same-VA other-domain witness and genuine IRQ-driven infinite-guest cancellation |
| Protected Windows | `/tmp/space-windows-{strict,files,write,application}-sanitize`:507/527/527/317 activations; private mappings and typed ABI/file handling; `/tmp/space-windows-nvme-sanitize`:six independent real NVMe boots |
| Protected Darwin | `/tmp/space-darwin-protected-release-final/report.json`:483 protected Mach-O/import runs; `/tmp/space-darwin-files-names-final/report.json`:464 read-only file/import runs, carry/errno and cleanup; integer-width extension under test |
| Native CLI/storage |11 scenarios; `/tmp/space-native-persistence-storage-final`:three NVMe boots; `/tmp/space-native-large-files-pwrite-final`:57391-byte partial/sparse/truncate/reclaim/remount checks; `/tmp/space-sparkfs-names-final2`:24/25-byte names/deep paths and rollback |
| Native GUI applications | Separate packaged calculator/editor in standard image; `/tmp/space-standard-gui-storage-final`, `/tmp/space-gui-storage-app-final` and `/tmp/space-gui-persistence-eight-byte-boundary`:real input/pixels, exact eight-byte persistence through five NVMe boots, denied storage leaves saved file unchanged |
| Native ephemeral ownership | `/tmp/space-native-lifecycle-private-foreign-2/report.json`:151 normal activations plus136 emitted allocation aborts with stable resources; private registry imports refused |
| Protected initial registers | `/tmp/space-user-initial-state-final/report.json`:16 actual guest activations, GP/XMM/x87/MXCSR sanitization and full kernel restoration; old trampoline independently fails GP/x87/XMM controls |
| Compiler | Full required Rust/native checks,119 conformance cases, Linux differential62 agreements/27 explicit refusals/zero disagreements or crashes, owned native/default CLI tests |
| Integrated lab checkpoint | `/tmp/space-application-lab-review-snapshot/report.json`:all14 then-integrated gates pass with source changes empty; source snapshot recorded separately |

These native SCI apps remain trusted CPL0. Clone page tables and cooperative
capability checks do not provide protection from malicious native code. Foreign
protected process tests run CPL3 with private mappings; they are a separate proof.

## Work continuing now

1. Native private image/global ownership and retained generation handles. The
   same-image baseline actually returned1 then2 and panicked for shared globals.
   Early private-image tests now return fresh independent state; require full
   lifecycle regression and two-live-instance/abort/stale-handle checks before
   treating this as integrated.
2. Retained GUI reclamation. The real standard-image baseline completes19
   sessions, then refuses session20. Require at least129 complete sessions with
   actual per-session input and exact pixels, alternating close order, peer
   survival, stale-handle denial and stable heap/frame/domain/capability/object/
   surface counts. Re-run persistence after integration.
3. SQLite database files. Implement truthful native inode/mount metadata,
   persisted permission updates, generic range leases and synchronous storage
   completion; translate POSIX locking and syscall structures at the Linux edge.
   Verify actual commit/query/close/reopen and then real NVMe reboot persistence.
   In-memory transactions do not complete this row.
4. BusyBox pipelines. The actual pipeline fails at unsupported pipe2. Add owned
   process/pipe/wait/signal execution contracts, partial transfers and descriptor
   cleanup before claiming a functioning shell pipeline. No zero-success shims.
5. Original macOS/Windows startup. Original jq binaries remain refused and
   unexecuted. Windows dependency inspection finds immediate GS/TEB access and
   three TLS callbacks; typed PE fixture success is not UCRT/startup coverage.
   Darwin requires broader Mach-O/dyld/relocation/libc/framework support.
6. Expand the application lab to all new suites and four upstream applications.
   Freeze a coherent source snapshot, run the full expanded set and retain exact
   failures. Source mutation during a run must invalidate integration evidence.
7. Continue the full matrix: protected native apps, real foreign software GUI,
   display/text/scale/input quality, two-instance independent app behavior,
   clipboard, file roots, process/network services and the named FLTK/NetSurf
   milestones. A fixture window does not complete these application outcomes.

## Review and remote delivery

Local review commits are on `compat/coverage-and-gui-foundation`. Generic compiler
changes are committed separately in Inauguration (`f93ba40d`,0.9.324). The user
has already authorized opening a draft PR. GitHub currently returns HTTP401
`Bad credentials`; pushing has also failed for missing usable authentication.
No remote draft PR has been created. This delivery blocker does not stop local
implementation or testing. Do not request authorization again or invent a PR URL.

Do not mark the project complete until every required acceptance row has actual
end-to-end evidence. Preserve unsupported behaviors as visible failures and
expand coverage by implementing their owning contracts.
