# Native address-space execution gate

Run from Space with an explicit source-built compiler:

```sh
python3 scripts/check-user-space.py --in /path/to/in --out /new/output --root standard --repeat 10
python3 scripts/check-user-space.py --in /path/to/in --out /another/output --root minimal --repeat 10
```

The eight categories are `shared`, `bounds`, `faults`, `revocation`,
`quarantine`, `capacity`, `bridge`, and `reinitialize`. Repeated `--case`
arguments select an explicitly reported subset; the default preserves all eight.
One warmup cycle precedes ten measured cycles. Allocator high water, free-list
length, domain count/ownership and capability count must remain exact after
warmup. A source change during execution makes the overall result fail, even
though the immutable snapshot and artifact receipt remain available.

The final complete native-only receipts, including release-projection queries, are:

| Root | Report | Actual CPL3 entries |
| --- | --- | ---: |
| Standard | `/workspace/us-standard-release-final/report.json` | 143 |
| Minimal | `/workspace/us-minimal-release-final/report.json` | 143 |

Each root includes 33 genuine CPU page faults with checked vector/error codes,
11 real IRQ deadlines, and 11 actual syscall suspensions followed by distinct
shared-memory child/parent continuations. The child changes RBX/XMM15 while the
parent verifies its independent saved state. A separate copied VM changes its
own backing, and another VM retains its initial bytes. RO write, NX execution
and unmapped read produce actual #PF errors 7, 21 and 4. Every user entry checks
restored CR3, capability, logical domain, interrupt policy, FS/GS and syscall hook.

Before those final complete runs, both roots also passed eleven focused
quarantine/release cycles:
`/tmp/space-user-space-release-standard-final10/report.json` and
`/tmp/space-user-space-release-minimal-final10/report.json`. These report zero
CPL3 entries and explicitly identify the selected trusted-supervisor subset.
A genuine domain-reference decrement refusal returns -5 while retaining the
revoked binding token and its VM reference. After repair, retry returns -5 but
commits detachment; public `binding-phase` now returns -6 and `constructor-owned`
returns 0. The consumer recovers the remaining VM instead of releasing the
already-detached token again. A separate actual huge-PDE teardown refusal
verifies the same committed-detach projection. No private binding catalog walk
is used by this consumer flow.

Trusted supervisor proofs additionally cover full-span atomic refusal,
foreign/revoked/retargeted authority, stale generations, code/TLS-view revocation,
VM/binding/copy limits, raw wrong-owner teardown refusal and a genuine corrupted
huge-PDE quarantine. Last release retains all uncertain backing; repairing that
PDE allows exact-owner recovery. The active copy test reads/writes actual guest
bytes, crosses a page boundary with a 13-byte transfer, preserves failed-copy
canaries, and refuses both a sibling binding and another VM during an active
trap. A held borrow prevents mutation, entry and reference release; it can end
after capability revocation. Reinitializing a context for another VM cannot
redirect its old binding or make old release invalidate its new CPU image.

Cold preflight runs once before cache initialization: fewer than 64 available
frames, one missing metadata bump byte despite reusable frames, exhausted
generation and unavailable domain slots all refuse unchanged. Exactly the
retained cache bytes plus 64 genuine reusable frames admit a real owned domain.
These resource-bound proofs are trusted supervisor tests, not guest execution.

A separate `--claim-failure-control` run changes only the private source snapshot
of the native domain claim provider to refuse its first actual claim. Its report
is `provider-refusal-control-passed`, records the exact unified source delta and
original/compiled hashes, and claims zero CPL3 entries. It verifies discovery of
the retained constructor failure, unsuccessful recovery before owner repair,
then exact repair and destructive recovery. Both roots passed this control:
`/tmp/space-user-space-claim-standard/report.json` and
`/tmp/space-user-space-claim-first/report.json` (minimal). Production has no
fault-injection hook.

The structurally valid private SCI has a resolvable public serial import and an
unresolvable `user-space-resume` import. It must be denied before heap,
capability, domain or runtime-instance allocation, and its entry marker must
remain absent. The small SCI is loaded at physical `0x2f0000` within the existing
1–3 MiB boot-image ingress contract; the runner proves actual kernel load extent
and SCI extent do not overlap. The 4 KiB guest page is loaded separately at
physical 256 MiB under 512 MiB QEMU RAM, then copied into an allocated native
loader-owned buffer before population. No heap bound or loader assertion is
relaxed to admit the payload.

The first receipt `/tmp/space-user-space-shared-first/report.json` is retained
as an **invalid test setup**: it staged SCI above the boot-size ingress range,
which bypassed that bounded-loader preflight. It establishes no loader defect.
The corrected bounded receipt and both complete final suites pass the original
allocation-free assertion.

These tests establish a kernel-linked native ownership boundary. They do not
establish an isolated SCI service, Linux migration, vfork, general shared-VM
threads, or upstream application success. See `docs/user-address-space.md` for
the API and `docs/plans/2026-10-24-native-user-vm-vfork.md` for the next goal.
