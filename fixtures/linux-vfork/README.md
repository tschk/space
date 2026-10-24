# Shared native VM vfork acceptance

`shared.asm` is an ordinary static Linux ELF, host42/Space42. It verifies shared
mutable data/brk/mmap, failed exec with a blocked parent, typed SIGILL wait,
and successful exec with parent wake before replacement exit. `deadline.asm`
uses a separate declared host-nontermination versus Space real-IRQ profile.
Neither binary imports Space functions or knows native object addresses.

`checks.in` is trusted supervisor evidence: real Suspend before clone-binding,
independent counted CPU references to one shared VM, foreign/revoked authority
and readonly copy refusal, peer survival, failed reference detach while parent
blocked, final huge-PDE quarantine/repair, and failed reference-add without an
uncounted child VM owner. It uses public native object projections. Trusted
fault injection changes actual native domain-reference counters/PDEs explicitly;
it never fabricates context phases, MAGIC, successful syscalls or a backing
ledger. Twelve extra direct CPU entries are counted separately per gate.

Run `scripts/check-linux-vm.py --vfork` or `--vfork-deadline` with the canonical
source compiler, an empty `--out`, and `--root standard` or `minimal`. The generic
runner also accepts `--manifest fixtures/applications/busybox-1.36.1-vfork.json`
with the unchanged matching `--case-config` for the separate pinned upstream
xargs ELF. It records the selected manifest bytes/hash instead of replacing the
completed default BusyBox profile.

The separate `check-linux-children.py --vfork-fd-profile` runs two explicit Space
resource profiles through actual syscall58: partial descriptor-copy rollback
and32 preparation admissions. Existing default case arrays remain unchanged.

Exact source freezes, receipt scope, preserved failures and limitations are in
[the vfork contract](../../docs/linux-vfork.md). General shared clone/thread
flags and arbitrary executable lookup remain refused; the overall goal is OPEN.
