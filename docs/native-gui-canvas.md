# Owned multipage native GUI canvas

The explicitly declared window profile allocates a 768×384 BGRA canvas with
3072-byte stride and 1179648-byte extent (288 pages). Its 64-byte version 1 Space
trailer carries exact magic, version, width, height, stride, extent, flags and a
zero reserved word. The loader accepts it only for retained mode 2 with exact
memory/display 20 or memory/display/storage 52 grants. Recognized malformed
fields, authority, lifetime and image mappings outside the first 4 GiB refuse
before allocation. Ordinary one-page clients retain their 4096-byte ABI.

Each canvas uses separately allocated physical frames. The guest maps them at
`0x70001000` with writable/user/NX leaves. A contiguous kernel server view starts
at `0x100000000 + domain * 0x40000000`, above the physical identity arena. Each
owned slot uses its own PDPT entry, allocated directory and allocated leaf table;
all unused entries stay unmapped. Other native clones copy only the first four
identity PDPT entries, so they do not inherit these views. Kernel view leaves are
writable/supervisor/NX. Capinfo exposes the guest address and exact extent; the
supervisor retains the server address. The historical `sci-sync-pixel-phys` name
holds that server address for this profile and a physical page for legacy clients.

The instance ledger records all 288 backing frames, the owned directory/table
and exact parent PDPT cell. Creation requires that cell to be empty. After route
withdrawal, ring drain and surface detach, generation-checked release verifies
exact mapping ownership, ignoring only hardware accessed/dirty bits. It clears
the parent entry and directory entry, flushes CR3, then returns backing, table,
directory and ledger frames. It restores no predecessor and retains no view
page tables. Observers capture the persistent parent cell before release rather
than dereferencing the freed directory afterward.

Canvas admission counts validated free-list frames and unused frame capacity
before any lifecycle allocation. Its conservative budget is 2864 plus rounded
image pages: at most 2048 leaf tables across four identity directories, six clone
root/directory frames, five state/cap/catalog ledger frames, 512 heap frames,
image backing, one shared page, 288 canvas pages, canvas ledger/directory/table,
and one shared kernel alias table. Both the image and non-kernel provider ranges
must fit within those four directories. This is a worst-case allocation bound,
not a minimum RAM requirement for the actual image. The first catalog frame is
reserved before entry, eliminating a later publication allocation.

The single-CPU retained launch wrapper masks interrupts through this fixed
allocation stream and restores the caller's IF before application entry. It
masks again for publication/cleanup and restores the original IF on return.
Admission refuses an active preemptor. These conditions prevent another kernel
allocator from consuming the checked capacity during the fixed stream. This
slice does not inject arbitrary allocator failures halfway through allocation
or promise recovery from arbitrary trusted CPL0 application service allocations.

The full ownership proof executes 70 cycles, 140 initial and 210 resumed SCI
activations. The client checks fresh backing, writes both ends of every page and
checks prior values on resume. The test fragments allocation while retaining
1024 canary frames, verifies every guest/server PTE and physical ledger target,
checks permissions, varies close order, resumes the peer and rejects stale
handles. Parent cells clear on release; free-frame count and heap/domain/cap/
object/export high water remain stable. Twelve malformed field, mapping,
authority and lifetime cases refuse before allocation.

The constrained-memory proof runs with 32 MiB RAM. After starting a peer, it holds
frames until available capacity is exactly one below the declared budget. Both
IF 0 and IF 1 launches refuse without changing heap/free-list/high-water values
or capability/domain bytes. The peer resumes; releasing held frames permits a
fresh valid launch, and the shell survives. This establishes refusal at the
admission boundary, rather than claiming total physical exhaustion recovery.

Run `scripts/check-gui-canvas.py --in /path/to/in --out /new/output` for ownership,
and add `--mode oom` for constrained admission. Receipts are
`/tmp/space-gui-canvas-highview-final2/report.json` and
`/tmp/space-gui-canvas-oom-final/report.json`. Readable rendering, input and
persistence have separate GUI supervisor gates. Native SCI remains trusted
CPL0; canvas ownership does not establish protected GUI execution or general
asynchronous scheduling.
