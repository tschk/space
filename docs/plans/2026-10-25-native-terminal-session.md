# Owned native terminal sessions

The full application/desktop goal remains active. The previous 152/152 result
is a frozen checkpoint, not completion or an instruction to stop implementation.

`components/terminal-session.in` now owns two generation-bearing raw-byte sessions
with separate input/output rings, geometry and mutation epochs. It reuses the
existing one-word page-ring implementation from `protocol/input.in`: each owned
4096-byte ring holds 507 bytes. No kernel buffer address is returned to a caller.
This is an explicitly imported, synchronous trusted native library, not an
isolated SCI TerminalSession service or a new IPC protocol.

Each session captures an exact Memory owner capability and Input seat capability
with their targets. Active operations revalidate both bindings. Revocation fences
future I/O; the original opaque token and exact owner ID still allow retirement
after `cap-revoke` clears the target. Retirement zeroes both rings and the record.
Two cached slots reuse their allocations without resetting the generation counter.
Full and empty queues return a native would-block result, never invented EOF.
Input is raw: canonical processing, echo, signals and foreign terminal encodings
are not silently accepted. Geometry changes and successful queue mutations
advance an epoch for the later supervisor wait contract.

`terminal-seat.in` separately owns the focused lease. Delivery revalidates the
exact session generation, owner and bound Input cap. Closing and reusing a slot
cannot replay an old focus lease into its replacement. Device decoding and
Linux/Darwin/Windows encoding remain above the raw queue object. Both private
prefixes are refused through SCI import resolution before entry.

## Executed checks

- `/workspace/terminal-session-model2/report.json`: 99 actual-provider controls
  with modeled memory/kernel context, using the real page-ring and cap functions.
  Covers isolation, aliases, revocation, stale focus, geometry, malformed state,
  backpressure/wrap, finite admission, overflow, zeroing and stable reuse. This
  is model evidence, not guest application execution.
- `/workspace/terminal-session-qemu1/report.json`: actual QEMU boot, 22 exact
  ring/focus/lifetime cycles, stable allocation/domain/cap/free-page witnesses,
  two real PS/2 keyboard deliveries to independent focused sessions and two
  emitted SCI import refusals with no entry or resource mutation. Native provider
  checks and denied imports confer zero foreign application execution credit.

The old model harness failed before compilation because its function extractor
assumed all cap helpers had multiline bodies; that receipt remains preserved.

## Active continuation

Retain a suspended protected activation when an owned terminal read or poll
cannot progress. Return to its supervisor with guest CPU budget, VM, descriptors
and context still owned. Deliver focused device events with the guest stopped,
then revalidate bindings and resume the saved context. Existing closed pipe-only
deadlock cancellation remains intact. A stopped terminal reader must not consume
CPU IRQ budget, run a host spin inside guest dispatch, or acquire global input.

Next connect actual original vi input/output and terminal modes/geometry, then a
screen model/parser and client-owned surface. Acceptance remains keyboard editing,
exact save/reopen, two sessions, focus, resize, close/crash cleanup and post-close
refusal. These provider tests do not complete that acceptance.
