# Space Nanokernel Audit

- **Date**: 2026-08-13
- **Scope**: `kernel/kernel-root.in`, `boot/multiboot.asm`, all `components/*.in`, `protocol/display.in`, `scripts/check-*.sh`
- **Method**: Full read of boot trampoline, kernel root, loader, domain/capability/scheduler/driver/netstack/FS subsystems; targeted greps to verify claims (CPL0 GDT, RST handling, xHCI init call sites, cap-mint call sites, frame-alloc bounds). No source files modified. Check scripts read; QEMU runs not repeated (boot tests exercised recently per repo history).

## Fix status

Fixed on 2026-08-13 (commit `c57702e`, plus the compiler fix `ea23033` in `../inauguration`):

- **CRITICAL #4 (syscall buffer/channel guards)**: partially hardened — `sys_write`/`sys_read` reject `len<=0 | len>4096 | buf==0`; `chan-new` rejects `cap<=0`; `chan-send/recv/count` sanity-check the handle header before dereferencing. Full isolation still requires the domain rework (#1/#2).
- **HIGH #10 (memory corruption)**: `frame-alloc` bounds against `heap-end`; NVMe I/O rejects `count<=0` and clamps to 8 sectors.
- **HIGH #11 (sys_exit halts OS)**: `sys-exit`/`posix-sys-exit` now reap via `proc-exit` for guest tasks instead of `cli(); hlt()`.
- **HIGH #8 (DNS)**: parser bounds all reads against the message length and the reply is accepted only from 10.0.2.3 with matching query id.
- **HIGH #5 (TCP)**: RST now returns -1 and fails the socket; `sock-send` returns the acked byte count instead of reporting success on an unacked drop.
- **MEDIUM #14 (cap-mint overflow)**: bounded by the table capacity.
- **MEDIUM #11 (domain table full)**: `domain-create` returns -1 (callers updated).
- **MEDIUM #18 (thr-create)**: bounded by `thread-max`.
- **MEDIUM #13 (dsp-run leak / OOB)**: message buffer hoisted out of the loop; pool sizes tracked and surface reads bounded.
- **Compiler bug found while fixing**: `in` DCE dropped unused `let` bindings whose initializer was a call, silently eliding side-effecting code (`dsp demo` never ran). Fixed in Inauguration `ea23033` (core_opt: `expr_has_call`).
- New gates: `scripts/check-audit-fixes.sh` (hardening assertions), `scripts/check-spdp-composite.sh` (SPDP surface path), `scripts/check-desktop-damage.sh` (moving-window renderer bench).

Open items (not yet fixed): real per-domain page tables (#1), CPL3 execution (#2), capability enforcement at the syscall boundary (#3), TCP FIN/close + ISN randomness, USB HID unification, PCI BAR validation, SparkFS disk-field trust.

Read files: `kernel-root.in`, `multiboot.asm`, `sci-loader.in`, `supervisor.in`, `process.in`, `domain.in`, `memory.in`, `object.in`, `syscall.in`, `channel.in`, `sched.in`, `preempt.in`, `interrupts.in`, `time.in`, `pci.in`, `nvme.in`, `storage.in`, `net.in`, `netstack.in`, `network.in`, `dhcp.in`, `dns.in`, `usb.in`, `input.in`, `mouse.in`, `display.in` (+`display-standalone.in`), `fs2-{block,file}.in`, `vfs.in`, `posix.in` (execve), `shell.in` (input path), `protocol/display.in`, and 24 check scripts.

---

## Ranked Findings

### CRITICAL

#### [CRITICAL] memory/domain — Component "isolation" copies the full 4 GiB identity map; every component can read/write all kernel memory and MMIO
`create-domain-pml4` (components/domain.in:42-67) builds each new domain by *copying* the kernel's PML4 → PDPT[0..3] → the four page directories. The boot trampoline identity-maps the whole first 4 GiB with 2 MiB pages (boot/multiboot.asm:68-103), so the "isolated" component domain maps kernel code/data, every byte of RAM, and every device's MMIO, all read-write-execute. The SCI loader then maps the image and heap into that domain (components/sci-loader.in:87-100), but that is *additional* mapping on top of an already-total map — it grants nothing and hides nothing. The shared-page machinery (`domain-create-shared-page`, domain.in:104-115) is unnecessary given both sides already see the same physical memory. A component can trivially read kernel globals (e.g. `cap-table-base`, `proc-table`) or overwrite the kernel image.

- **Evidence**: domain.in:42-67 (copies PDPT[0..3]); boot/multiboot.asm:68-103 (identity map, `0x83` flags); sci-loader.in:88,99,106 (image/heap/shared mapped into the same domain).
- **Repro**: In any SCI component, `load64(0x200000)` reads the kernel's compiler global area; `store64(cap-table-base, 0)` (value read via cap-info) zeroes the cap table.
- **Check**: NONE — needs check.

#### [CRITICAL] capability — Components run at ring 0; there is no privilege boundary, so CR3 switching is cosmetic
The GDT only contains DPL0 segments (boot/multiboot.asm:416-419). Nothing in the tree ever switches to CPL3; `idt-set-user` sets the int 0x80 gate to DPL3 (components/syscall.in:164-175, interrupts.in:91-93) but no code executes below CPL0. Components can execute `cli`, `lgdt`, `lidt`, `wrmsr`, and directly reprogram `CR3` because the stubs `cr3_read`/`cr3_write` are published at fixed low addresses (boot/multiboot.asm:162-169, 399-410) that every domain maps. Even with correct per-domain page tables, a component could call `cr3_write(kernel_pml4)` and return to kernel context. Memory isolation is therefore page-table-only, and even that is escapable by design.

- **Evidence**: boot/multiboot.asm:418-419 (DPL0); boot/multiboot.asm:405-410 (`cr3_write` sets CR3 from arg); components/domain.in:32 (`invoke1(load64(0x4060), kernel-pml4)` — kernel itself uses this escape hatch).
- **Repro**: Component calls `invoke1(load64(0x4060), <kernel pml4 phys>)`, then reads kernel memory.
- **Check**: NONE — needs check.

#### [CRITICAL] capability — Guest is handed the kernel capability table base and can mint/revoke capabilities for any object via int 0x80
`sci-load-runtime-component` and `sci-load` write `cap-info[0] = cap-count` and `cap-info[8] = cap-table-base` — the physical address of the *kernel's* capability table — into the guest's cap-info block (components/sci-loader.in:122-130, 563-568). The manifest "required caps" check (sci-loader.in:67-73, 531-537) only tests that the manifest's self-declared bits are a subset of a grant mask the component image itself supplies, and every grant mask (SCI-GUEST-GRANTS=1, SCI-INPUT-GRANTS=3, sci-loader.in:12-15) is a fixed constant. Meanwhile syscalls 9/10 (`sys-cap-mint`, `sys-cap-revoke`, components/syscall.in:96-106) are exposed to any caller with no authorization: a guest can `cap-mint(some_object_ptr, 0xFF)` on any object pointer. The `cap-check` helper (object.in:98-112) exists but nothing in the kernel consults it before acting.

- **Evidence**: sci-loader.in:123-124, 563-568 (cap table base to guest); syscall.in:96-106, 143-153 (unauthorized mint/revoke/check); object.in:89-96 (`cap-mint` unbounded, no caller check).
- **Repro**: Guest executes `int 0x80, rax=9, rdi=<ptr to any kernel object>, rsi=0xFF`.
- **Check**: NONE — needs check.

#### [CRITICAL] memory-safety — sys_read/sys_write/sys_chan_* validate no buffer addresses; guest can read or corrupt arbitrary kernel memory
`sys-write` (components/syscall.in:15-26) and `sys-read` (30-45) dereference the caller-supplied `buf` directly with no check that it lies in the caller's mapped/owned region. `chan-send`/`chan-recv` (components/channel.in:62-103) treat the channel handle `c` as a raw pointer and index `c + 48 + wpos` with a caller-controlled capacity; a guest passing a kernel address as `ch` performs an arbitrary read/write of that address, and `cap=0` yields `% 0` → #DE. Because all domains share the identity map, these are effective kernel read/write primitives.

- **Evidence**: syscall.in:21-24 (write loop); channel.in:70-72 (`buf[wpos] = msg`), channel.in:84-95 (`buf[rpos]`), 72 (`(wpos + 1) % cap` — div-by-zero on cap 0).
- **Repro**: Guest: `int 0x80 rax=0 rdi=1 rsi=0x200000 rdx=0x1000` dumps the kernel global area to serial.
- **Check**: NONE — needs check.

### HIGH

#### [HIGH] syscall — sys_exit unconditionally halts the entire OS
`sys-exit` (components/syscall.in:49-61) runs `cli()` + infinite `hlt()` regardless of which thread/process called it. Any guest component that calls `exit()` (or a personality translation that maps to it) kills the whole nanokernel — a trivial DoS, and it halts rather than reaping the process table row.

- **Evidence**: syscall.in:56-59; `sys-exit` has no `current-task != 0` guard.
- **Repro**: `echo` a user SCI that returns via `sys_exit(0)`.
- **Check**: NONE (check-user-sci.sh only uses return-value SCI images).

#### [HIGH] sched/preempt — preempt-stop freezes display/input components permanently; the compositor and input channel go dead after boot
`preempt-start` (components/preempt.in:70-95) installs the preemptive timer gate and builds task contexts; `sci-load-runtime-component` registers display/input as preempt tasks (sci-loader.in:138-141). After a 3-second grace window the kernel calls `preempt-stop` (preempt.in:113-123), which replaces IDT vector 32 with the non-switching timer stub and zeroes the scheduler pointer at 0x4028. `schedule-tick` is the *only* mechanism that ever resumes a preempt context (via `isr_timer_preempt` → `comp_invoke_stub`, boot/multiboot.asm:254-289, 355-375); with it disabled, display/input are suspended forever in their saved contexts. The `hlt()` loops in `dsp-run`/`input-entry` (display.in:1840-1841, input.in:990-992) do **not** help: the timer IRQ returns to whichever context is current, and after `preempt-stop` the current context is always the kernel/shell. This is why `preempt-stop` exists (comment at kernel-root.in:391-399: "stop the timer scheduler so the serial shell owns the CPU"), but the consequence is that the display server and input publisher never run again after boot. The runtime check passes because all asserted markers print during the grace window.

- **Evidence**: kernel-root.in:379-399; preempt.in:113-123; boot/multiboot.asm:254-289, 355-375; display.in:1840-1841.
- **Repro**: After shell prompt, `netstat`/mouse events never update; `check-runtime-components.sh` passes regardless.
- **Check**: check-runtime-components.sh (maintained, but passes despite the freeze — does not assert post-grace behavior).

#### [HIGH] netstack — TCP has no RST handling, no FIN/close, fixed ISN=1, fixed retransmit, and silent data loss
`tcp-parse-data` returns 0 when the RST flag (0x04) is set — an RST is silently ignored and the caller keeps polling to timeout (network.in:448-450). `sock-close` frees the table slot without sending FIN or RST (netstack.in:446-459). `build-tcp-syn-impl` hardcodes the SYN sequence number to 1 (network.in:302-303), and `sock-connect` hardcodes local seq=2 after the handshake (netstack.in:436-438) — no ISN randomization, so sequence numbers are trivially predictable. On retransmit, `sock-send` retries exactly once, and if the retry is not acked it **still advances `sent` and returns `len`** — data is silently dropped while the API reports success (netstack.in:193-237).

- **Evidence**: network.in:448-450 (RST ignored); netstack.in:446-459 (no FIN); network.in:299-303 (ISN=1); netstack.in:215-237 (silent loss).
- **Repro**: Send > 1 segment to a peer that stops acking; the call returns the full length.
- **Check**: check-tcp.sh (maintained — asserts handshake + one connect; no RST/close/retransmit coverage).

#### [HIGH] netstack — TCP/UDP connection state is global, so multiple sockets corrupt each other
`tcp-last-seq`, `tcp-last-ack`, `tcp-local-seq`, `tcp-remote-ack`, `tcp-rx-buf`, `tcp-rx-len`, `tcp-peer-wnd`, `tcp-peer-mss`, `tcp-send-wnd` are all globals (network.in:41-50). `sock-table` allows up to 16 sockets (netstack.in:6-7) but only one connection's seq/ack/buffer state exists. A second connection's ACK data overwrites the first's `tcp-rx-buf` (network.in:476-488), and `tcp-peer-wnd` is overwritten by whichever packet arrived last. Effectively only one TCP connection can be live.

- **Evidence**: network.in:41-50; netstack.in:154-240, 242-300.
- **Repro**: Open two TCP sockets to two peers; ACK traffic from socket B advances/clobbers socket A's sequence bookkeeping.
- **Check**: NONE — needs check.

#### [HIGH] netstack — DNS reply parser has unbounded OOB reads and validates no query ID
`dns-skip-name` (components/dns.in:7-19) walks labels with no bound against the packet end (`off = off + 1 + lab`, lab up to 63, no `off < dlen` guard). `dns-parse-a` (dns.in:22-43) only checks `dlen >= 12`, then reads ancount/type/class/rdlen and `rdlen` bytes with no per-record bounds; a malformed reply can walk far past the frame into adjacent mapped memory (never faults because the identity map covers everything, so it silently reads garbage and can loop). The parser also never verifies the DNS transaction ID matches the query (query ID fixed at 0x1234, network.in:714-715), and the accept filter is only "UDP to port 12345" (dns.in:93-94) — no source address or ID check.

- **Evidence**: dns.in:7-19, 26-43; dns.in:93-97; network.in:714.
- **Repro**: Feed a crafted UDP reply on port 12345 with a huge `ancount` / poison length.
- **Check**: check-dns.sh (maintained — only asserts *a* `dns:` line is printed; a crash-free OOB walk passes).

#### [HIGH] memory — frame-alloc has no heap-end bound; storage path can DMA 65536 sectors into one 4 KiB page
`frame-alloc` (components/memory.in:63-72) bumps `heap-next` without checking against `heap-end` — unlike `alloc` which panics (memory.in:3-12) — so any of its 44 call sites can silently allocate beyond physical RAM (within the 4 GiB identity map, so it corrupts whatever RAM is there). In the NVMe path, `nvme-io-submit` stores `(count - 1) & 0xFFFF` as the transfer length (components/storage.in:198) and always uses `PRP1 = storage-data-phys`, a single 4 KiB page (storage.in:190-192, 439-441). A `count == 0` request yields NLB=65535 → the controller DMAs 32 MB into a 4 KiB page, and any `count > 8` overruns it. The mailbox loop `while load64(storage-mailbox + STORAGE-OP-OFF) != 0 {}` (nvme.in:62-64) spins forever if the storage component stalls.

- **Evidence**: memory.in:63-72; storage.in:190-198, 439-441; nvme.in:62-64.
- **Repro**: `nvme-read(lba, 0, buf)` from any FS/RPC path; or force a `frame-alloc` burst past RAM.
- **Check**: check-qemu-boot-nvme.sh / check-qemu-volume-nvme.sh (maintained — exercise only the count=8 happy path).

### MEDIUM

#### [MEDIUM] domain — domain table full silently returns kernel domain id 0
`domain-create` returns `0` when the table is full (components/domain.in:69-70), but 0 is the valid kernel-domain id. Callers happen to treat 0 as failure (`sci-loader.in:74-79`, `process.in:74-75`), but the function contract is wrong and any caller that forgets the check runs its component in the kernel domain.

- **Evidence**: domain.in:69-77.
- **Repro**: Create 64+ domains, then `domain-create()` returns 0 and `domain-switch(0)`.
- **Check**: NONE — needs check.

#### [MEDIUM] object — cap-mint has no capacity bound; cap table overflow corrupts the heap
`cap-table-init(64)` allocates 64 slots (kernel-root.in:177, object.in:83-87), but `cap-mint` (object.in:89-96) increments `cap-count` with no bounds check, writing slots past the 1024-byte table into adjacent heap. `sys-cap-mint` (syscall.in:96-98) exposes this to any caller.

- **Evidence**: object.in:89-96; kernel-root.in:177; syscall.in:96-98.
- **Repro**: Guest loops `cap-mint` until the table overflows the following allocation.
- **Check**: NONE — needs check.

#### [MEDIUM] channel — single-waiter wait queues lose wakeups when a second thread blocks
`chan-send`/`chan-recv` register one waiter in a single slot and overwrite it on the next blocker (components/channel.in:62-79, 84-103). With two senders on a full channel, the second overwrites the first's id; when the receiver consumes and wakes the last-registered waiter, the earlier sender stays blocked forever with `wait_send == -1`. The comment "safe because .in has no preemption" (channel.in:55-59) is only true for the cooperative scheduler; with the preemptive scheduler active the register-then-block window is interruptible and the wake can be consumed before the thread actually blocks (lost wakeup).

- **Evidence**: channel.in:64-67, 85-88, 97-101.
- **Repro**: Two cooperative threads `chan-send` to a full channel (capacity 1) while one receiver drains; the first sender deadlocks.
- **Check**: NONE — needs check.

#### [MEDIUM] sched — thr-switch leaves current-task stale, corrupting channel wait slots and thread state
`thr-switch` sets `current-task = t` but never restores it when returning to the kernel (components/sched.in:92-96). `net-component-step` / `net-chan-recv` call `thr-switch(net-component-tid)` (net.in:49-56), so after the first network RPC `current-task` is the network thread for the rest of the session. Any later `chan-send`/`chan-recv` (which store `current-task` as the waiter, channel.in:65, 86), `thr-yield`/`thr-block`/`thr-exit` (sched.in:98-108) then update the wrong thread's state/stack slot.

- **Evidence**: sched.in:92-96; net.in:49-56, 119, 131; channel.in:65, 86.
- **Repro**: Run a channel demo after a `net` shell command; observe wakeups targeting the network thread.
- **Check**: NONE — needs check.

#### [MEDIUM] display — compositor backbuffer is a fixed address inside the kernel heap region
`comp-init` (components/display.in:485-491) places the ~8 MB backbuffer at `0x0FFE0000 - size` with no reservation or guard. The kernel heap bump pointer (`heap-next`, memory.in) can reach past the backbuffer start as filesystem, load-arena, memdisk, and RPC allocations accumulate, so the compositor's blits (display.in:1259-1267) silently overwrite kernel heap data. The in-kernel path (shell `desktop`) is the only user; the SCI display component never calls `comp-init`.

- **Evidence**: display.in:485-491, 1259-1267.
- **Repro**: Grow the heap (soak FS + shell) then run `desktop`; heap corruption is silent because the region is mapped.
- **Check**: check-desktop-visual.sh / check-crepus-desktop.sh (maintained — short runs, small heap).

#### [MEDIUM] display — dsp-run leaks 32 bytes per loop iteration; heap exhaustion leads to a null deref
`dsp-run` allocates a message buffer inside the infinite loop (components/display.in:1822-1823: `let msg = alloc(SPDP-MSG-SIZE)`), never freed. The standalone display heap is 2 MiB (sci-loader.in:31-32); at timer-wakeup rate this exhausts in minutes, after which the standalone `alloc` returns 0 (display-standalone.in:57-64) and `store64(msg + 0, ...)` writes to address 0.

- **Evidence**: display.in:1822-1824; display-standalone.in:57-64.
- **Repro**: Boot `combined.bin` with the display component and wait; serial shows no error until page-0 corruption or a #PF.
- **Check**: check-runtime-components.sh (short run; leak undetected).

#### [MEDIUM] display — SPDP surface composite performs OOB reads of the heap pool
`dsp-surface-attach`/`dsp-surface-geometry` take pool id, buffer offset, w, h from client messages with no check that `pool + offset + w*h*4` stays within the pool (components/display.in:1854-1878, 1725-1756). `dsp-shm-create-pool` allocates `size` bytes from an untrusted message arg and stores a possibly-0 pool pointer (display.in:1845-1852). A client can read arbitrary heap bytes into the framebuffer. (No SPDP client exists yet, but the wire protocol is defined and channel-accessible.)

- **Evidence**: display.in:1736-1748, 1845-1852.
- **Repro**: Send SPDP `SHM_CREATE_POOL` then `SURFACE_ATTACH` with a large w×h and small pool.
- **Check**: NONE — needs check.

#### [MEDIUM] netstack — UDP ignores rip/rport; build-udp reads an unbounded C string past the TX frame
`sock-sendto` passes the caller's `buf`/rip/rport to `build-udp-impl`, which hardcodes source/dest port 9999 and dest 10.0.2.2 (network.in:269-272) and measures the payload with `cstr-len-impl` (network.in:250) with no length cap and no MTU bound. A long or non-NUL-terminated payload walks past `nic-tx-buf` (a 4 KiB frame) while copying (network.in:273), corrupting adjacent memory. `sock-sendto` silently ignores its own rip/rport arguments (netstack.in:317-329).

- **Evidence**: network.in:248-275; netstack.in:302-330.
- **Repro**: `sock_sendto(fd, big_buffer, 60000, ip, port)` — overflow writes beyond the frame.
- **Check**: check-network.sh (default short payload only).

#### [MEDIUM] drivers — PCI BARs are used without type/size validation
`pci-find-and-enable-e1000` masks the BAR but never checks it is a memory BAR or non-zero (components/pci.in:32-36); the NVMe init maps `mmio-phys .. +0x8000` into the storage domain regardless of the actual BAR length and treats a 32-bit BAR as 64-bit-capable without validating the type bits (storage.in:264-288); the display VGA BAR scan has the same 64-bit assumption (display.in:211-225); `xhci-read-bar64` reads BAR1 unconditionally (input.in:283-287, usb.in:81-85). A zero/bogus BAR yields MMIO access at an arbitrary physical address. `e1000-init-impl` maps 64 KiB of MMIO with `map-page` (network.in:86-90) without checking the BAR size either.

- **Evidence**: pci.in:27-39; storage.in:264-288; display.in:211-225; network.in:86-90.
- **Repro**: Boot under a machine model where a BAR is I/O-space or zero-sized.
- **Check**: NONE — needs check.

#### [MEDIUM] filesystem — on-disk superblock/inode values are trusted; malformed disk causes unbounded allocs and OOB block I/O
`sparkfs-init` sizes the bitmap and inode table from disk fields `total`/`ino-count` with no sanity caps (components/fs2-file.in:31-57), so a corrupted NVMe superblock can exhaust the heap via `alloc` (panic) or allocate a giant bitmap. `sf-read-block`/`sf-write-block` compute `sf-mem-disk + bno * SF-BLOCK-SIZE` with no `bno` bound (fs2-block.in:81-89, 119-128); block numbers taken from on-disk inodes (fs2-file.in:282-306, 374-401) can point anywhere in the identity map. `sf-alloc-block` iterates to `total` (fs2-block.in:193-207) without validating against the disk size.

- **Evidence**: fs2-file.in:31-57; fs2-block.in:81-89, 119-128, 193-207.
- **Repro**: Write a crafted superblock to NVMe LBA 65536, reboot, mount.
- **Check**: check-volume-deep-soak.sh / check-volume-soak.sh (maintained — well-formed disks only).

#### [MEDIUM] drivers — all device I/O is polled with multi-million-iteration spin loops and no interrupts
PIC remap masks every IRQ except IRQ0 (components/interrupts.in:62-63); e1000, NVMe, and xHCI never enable device interrupts and instead spin on 2–5 million-iteration loops (`nvme-admin-submit`/`nvme-io-submit` 5M, storage.in:151,209; `xhci-wait-event` 2M, input.in:361; `e1000-rx-wait-impl` 3M, network.in:143). On a quiet device these burn the whole guest CPU for seconds and block the shell; there is also no storm protection because interrupts are simply never used. Design trade-off, but worth recording alongside the "interrupt storm" audit item: the answer is polling, not storm handling.

- **Evidence**: interrupts.in:53-65; storage.in:148-166, 206-231; network.in:142-152; input.in:360-381.
- **Check**: NONE (behavioral; QEMU tolerance is why it boots).

#### [MEDIUM] usb/input — xHCI driver is duplicated (in-kernel usb.in vs input.in) and the input-component copy is dead code
The entire xHCI stack (~300 lines each) exists twice: kernel-linked `components/usb.in` and inside the standalone `components/input.in`. In `input.in`, `xhci-init`/`usb-kbd-init` are defined but **never called** (confirmed: only definitions at input.in:483,540; `input-entry` only calls `ps2-kbd-init`/`mouse-init` then loops on `usb-kbd-ready()`, which stays 0). So the input component's USB keyboard path is unreachable, and if it were enabled it would pass heap-allocated *virtual* addresses (COMP-HEAP-VIRT = 0x80000000+, sci-loader.in:31-32) as xHCI DMA addresses — physical 0x80000000+ is above the 512 M RAM of every test config, so DMA would be lost and the enum would time out. The kernel's usb.in path is the working one; the two copies also mean a controller reset from one interferes with the other's active devices (git history shows a prior "dual init" fix).

- **Evidence**: input.in:209-692 (driver), 932-995 (entry, no xHCI init call); sci-loader.in:31-32; check-runtime-components.sh (`-m 512M`, asserts only the PS/2 marker).
- **Repro**: Attach a USB keyboard in QEMU; the input component never delivers key events (kernel usb.in path may, untested).
- **Check**: NONE — no check exercises USB keyboard key delivery.

#### [MEDIUM] posix — "ELF execve" is a ring-0 jump into the load arena with no segment mapping or BSS
`posix-elf-exec-image` validates ELF bounds then `invoke1(entry, 0)` into the raw load-arena buffer (components/posix.in:247-268): PT_LOAD segments are never copied to their vaddrs, `.bss` (memsz > filesz) is never zeroed, and the image executes at CPL0 in kernel address space with full privileges. `check-linux-elf.sh` feeds a flat `mov eax,42; ret` blob whose `entry` equals its file address — it validates the trampoline, not a real ELF. `posix-sys-execve` (posix.in:294-321) caps `pages * 4096` against the load arena but the arena itself panics on exhaustion (memory.in:164-172).

- **Evidence**: posix.in:240-292; scripts/check-linux-elf.sh (embedded flat blob).
- **Check**: check-linux-elf.sh / check-execve-sci.sh (maintained — toy payloads only).

### LOW

#### [LOW] capability — cap-check is never consulted on any kernel path
`cap-check` (object.in:98-112) is reachable only as syscall 11; every kernel-internal operation (channel, driver, FS, domain) uses objects without consulting capabilities. The capability system is metadata, not enforcement. Folded into the CRITICAL capability findings, but tracked here for completeness.

- **Evidence**: object.in:98-112; syscall.in:104-106, 150-153; no other callers.
- **Check**: NONE.

#### [LOW] drivers — PS/2 wait loops have no timeout; boot hangs on a dead controller
`mouse-wait-output`/`mouse-wait-input` spin forever (components/mouse.in:35-46; input.in:710-719). On hardware without a working PS/2 controller, `mouse-init` blocks boot indefinitely. QEMU always provides PS/2, so tests pass.

- **Evidence**: mouse.in:35-46, 56-68.
- **Check**: NONE (QEMU always has PS/2).

#### [LOW] display — standalone shim `serial-has-byte` returns 0 always
`display-standalone.in` stubs `serial-has-byte` to return 0 (display-standalone.in:133-136), so the display server can never see serial keyboard input — relevant only to the standalone component path (which is frozen after `preempt-stop` anyway).

- **Evidence**: display-standalone.in:133-136; display.in:1606-1611.
- **Check**: check-runtime-components.sh (does not exercise it).

#### [LOW] memory — boot zeroes a hardcoded global-data window at 0x200000
`kernel-entry` clears `0x200000 .. 0x210000` on the assumption that the compiler emits globals there (kernel-root.in:155-159; comment in memory.in:45-47). If the compiler's global placement changes, boot silently corrupts unrelated memory. Fragile contract between boot and compiler.

- **Evidence**: kernel-root.in:155-159; memory.in:45-51.
- **Check**: check-qemu-boot.sh (indirect — catches it only if boot breaks).

#### [LOW] sched — thr-create has no bounds check on thread-count
`thr-create` writes `thread-sp + t*8` with `t = thread-count` unbounded (components/sched.in:69-85); exceeding the `max`-sized arrays (sched.in:57-67) overflows the heap. Same class as cap-mint overflow. Low because callers create few threads.

- **Evidence**: sched.in:69-85.
- **Check**: NONE.

#### [LOW] input — duplicate/incomplete scancode and HID usage maps
`ps2-scancode-ascii` maps PageUp/PageDown twice (0x48/0x49 → 128, 0x4B/0x51 → 129, mouse.in:234-241) and has no numpad handling; `hid-to-ascii` (input.in:590-644) omits many usages (e.g. backspace/enter beyond 0x28) and drops modifiers other than shift. Cosmetic but noted.

- **Evidence**: mouse.in:228-289; input.in:590-644, 647-682.
- **Check**: NONE.

---

## Check coverage matrix

| Subsystem | Check script | Status |
|---|---|---|
| Boot / kernel entry / shell | scripts/check-qemu-boot.sh | maintained |
| SCI metadata contract | scripts/check-sci-contract.sh | maintained (metadata only, not loader bounds) |
| SCI loading / guest return | scripts/check-user-sci.sh, scripts/check-execve-sci.sh | maintained (happy path only) |
| Memory domains / isolation | — | **MISSING** |
| Capability enforcement | — | **MISSING** |
| Syscall layer | — | **MISSING** |
| Cooperative scheduler / threads | (indirect via check-qemu-boot) | weak |
| Preemptive scheduler | scripts/check-runtime-components.sh | maintained, but passes despite the post-grace freeze |
| Cross-domain channel IPC | — | **MISSING** |
| Timer / PIT / interrupts | scripts/check-time-component.sh | build-only (compiles, doesn't boot) |
| NVMe | scripts/check-qemu-boot-nvme.sh, scripts/check-qemu-volume-nvme.sh | maintained |
| e1000 driver | scripts/check-network.sh | maintained |
| DHCP | scripts/check-dhcp.sh | maintained (lease or timeout) |
| DNS | scripts/check-dns.sh | maintained (weak: any `dns:` line passes) |
| TCP | scripts/check-tcp.sh | maintained (handshake + one connect only) |
| xHCI / USB keyboard | — | **MISSING** |
| PS/2 mouse / keyboard | marker in check-runtime-components.sh | weak |
| Display / compositor | scripts/check-desktop-visual.sh, scripts/check-crepus-desktop.sh | maintained (kernel-path compositor only) |
| SparkFS / volume RPC | scripts/check-fs-dirs.sh, scripts/check-volume-soak.sh, scripts/check-volume-deep-soak.sh, scripts/check-shell-redir.sh | maintained |
| VFS | (covered by fs + shell-redir checks) | maintained |
| Linux personality / execve | scripts/check-linux-elf.sh, scripts/check-execve-sci.sh, scripts/check-personalities.sh | maintained |
| Darwin / Windows personalities | scripts/check-darwin-personality.sh, scripts/check-windows-personality.sh | maintained |
| Shell / redir / stress | scripts/check-shell-stress.sh | maintained |
| PCI BAR validation | — | **MISSING** |

Subsystems with **no maintained check at all**: memory domains, capability enforcement, syscalls, channel IPC, USB/xHCI keyboard, PCI BAR validation. The preemptive-scheduler check exists but is ineffective (see HIGH finding).

---

## Top fixes (priority order)

1. **Give components real memory domains (CRITICAL #1).** Stop copying the 4 GiB identity map; `create-domain-pml4` should build fresh page tables mapping only: the component image, its 2 MiB heap, the shared page, and explicitly-granted device MMIO. Add NX to non-code mappings. Keep the identity map only in domain 0. *Effort: 2–3 days.* Gate: a check that a loaded component cannot read `0x200000` (kernel globals) or its peers' heap.

2. **Move components to CPL3 (CRITICAL #2).** Add DPL3 code/data segments, run component entry points at ring 3 (the int 0x80 gate already exists and is DPL3), and stop publishing `cr3_read`/`cr3_write`/`comp_invoke_stub` in low memory that every domain maps; route domain switches through the kernel only. *Effort: 2–4 days.* This and #1 together are the actual security boundary.

3. **Enforce capabilities at the syscall boundary (CRITICAL #3/#4).** Stop handing `cap-table-base`/`cap-count` to guests; give each domain its own small cap table; authorize `sys_cap_mint`/`sys_cap_revoke` against the caller's grants; validate `buf` addresses in `sys_read`/`sys_write`/`sys_chan_*` against the caller's mapped regions (and reject `ch` not in the caller's domain); make `sys_exit` reap the caller instead of halting. *Effort: 1–2 days.*

4. **Close the memory-corruption class (HIGH #10).** Add a `heap-end` bound to `frame-alloc`, clamp NVMe `count` to `[1,8]` and reject `count == 0`, and give `nvme-submit` a mailbox timeout. *Effort: half a day.*

5. **Make the checks that exist actually catch regressions.** Add: (a) a domain-isolation assertion (component reading kernel globals must fail after #1), (b) a post-grace assertion in `check-runtime-components.sh` that display/input still render/publish after `preempt-stop` (currently they freeze and the check passes), (c) negative DNS/TCP tests (crafted OOB reply, RST/close behavior, retransmit loss), (d) `cap-mint` overflow and `chan-alloc` overflow unit checks in `proc-selftest`-style in-kernel tests. *Effort: 1 day.*
