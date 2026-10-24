# Space TODO — Roadmap to OS Personalities

## Tagged: 0.0.1 — Nanokernel Foundation

Verified today: x86_64 boot, serial shell, memory domains, capabilities,
cooperative + preemptive scheduling, channels, the in-kernel SCI loader,
the Linux-personality demo, VFS, time service, network component RPC, and SCI
allow/deny policy. Display/input SCI load then `preempt-stop` so serial shell
lives on full runtime images (`check-runtime-components`, volume soak `image: full`).
Volume multi-file soak across reboot; user SCI `hello`/`uecho`; `exec` loads SCI
from sparkfs (`check-execve-sci`). Net: UDP; TCP handshake + PSH+ACK data path;
DHCP DORA lease; DNS dotted QNAME A parse (`check-dns`, e.g. example.com).
TCP window/congestion: MSS negotiation, slow-start, Go-Back-N retransmit
(`check-tcp`). Darwin/Windows M4 surface. Desktop via kernel `display.in` +
PS/2; kernel xHCI HID enum works (`usb.in`). Shell: cd/pwd, history up/down,
`>`/`|` redirect, nested paths. ELF load above global-data zero region.
18+ maintained checks green on `main`. See personalities docs.

SCI v2 dynamic linking: `--emit sci` artifacts carry export/import tables;
`components/libspace.in` (kind 7) is the first shared library; `hello`/`uecho`
bind to it at load time (`check-user-sci.sh`). Guest user stack moved to a
contiguous window (0x4F000000) with a param-spill page — fixes the pre-existing
CPL3 entry fault. Dynamic nanokernel: the boot image carries a kernel export
table (address in boot header `[40..48]`, ~676 symbols registered at boot);
loaded modules register their own exports so later modules chain against
libraries + kernel (kind 8 `dyn-mod`, `check-dynamic-modules.sh`); unknown
imports deny the module and boot continues. `display-standalone` dropped its
duplicated serial/PCI copies and binds kernel services as imports.

Space 0.1.0: `kernel-root-minimal.in` (core-only image, ~3x smaller) alongside
the full standard image (`check-image-variants.sh`). Preinstalled dynamic apps
`app-calc` (expression REPL), `app-notes` (persistent notes via the filesystem),
`app-hd` (file hexdump), `app-sysmon` (live uptime/heap/caps monitor), and
`app-bench` (deterministic prime-sieve benchmark, boot kinds 9-13) run on
demand via the shell `runapp` command in both images; `libspace` grew a shared
stateless `lib-readline`. A component entry that returns now parks its preempt
task instead of freezing the timer scheduler (`comp_invoke_stub` park loop).
NVMe probe fixed: QEMU's BAR0 is 16 KiB, the driver demanded 32 KiB
(`check-qemu-boot-nvme` green again).

## Phase 1: Storage

- [x] ATA/PIO disk driver (read sectors from QEMU IDE disk)
- [x] Simple flat filesystem (read-only, then write)
- [x] NVMe driver with MMIO
- [x] VFS abstraction layer
- [x] Load SCI components from disk at runtime

## Phase 2: Process Abstraction

- [x] Process struct (domain + caps + entry + lifecycle)
- [x] Process lifecycle: spawn, exit, wait, kill
- [x] Process table and listing (`ps` command)
- [x] Process loader (read SCI image from disk, create domain, map, jump)

## Phase 3: Syscall Interface

- [x] Syscall trap handler (int 0x80 or syscall instruction)
- [x] Syscall dispatch table
- [x] Core syscalls: write, read, exit, yield, getpid
- [x] Channel syscalls: create, send, recv, close
- [x] Capability syscalls: mint, revoke, check

## Phase 4: Userspace Runtime

- [x] Minimal libc in .in (print, open, read, write, close, exit)
- [x] Userspace heap (malloc/free on top of mmap)
- [x] String and memory utilities
- [x] Build user programs as SCI components

## Phase 5: OS Personalities

Roadmap (done vs M4–M6 gaps): [`docs/personalities-roadmap.md`](docs/personalities-roadmap.md).
Branch for translator work: `feat/personalities`.

- [x] Linux compat layer (.in component translating POSIX syscalls)
  - [x] File syscalls: open, read, write, close, stat, lseek, fstat
  - [x] Process syscalls: fork, exec, wait, exit, getpid, kill
  - [x] Memory syscalls: mmap, munmap, brk
  - [x] Misc syscalls: getcwd, chdir
  - [x] Socket syscalls: socket, bind, listen, accept, connect, send, recv (UDP path; TCP active open handshake)
  - [x] Signal handling (minimal: SIGTERM, SIGKILL)
- [x] Darwin compat layer (BSD translator: file/dir/cwd/lseek/fstat/stat/mmap/socket/pipe-lite/fork/execve/kill + Mach stubs; not full XNU)
- [x] Windows compat layer (file/dir/process/heap/env/console NT-shaped translator 1-30; not PE/CSRSS)

## Phase 6: Interactive Usability

- [x] VBE framebuffer console (1920×1080×32)
- [x] GNOME-style desktop compositor
- [x] X11-style arrow cursor
- [x] Window close, minimize, resize, drag, z-order
- [x] Taskbar window buttons (click to focus/restore)
- [x] USB HID keyboard (replaces PS/2)
- [x] Display server service (SPDP protocol)
- [x] Shell upgrade: pipe support, background processes, redirection (minimal echo demos)
- [x] Multi-terminal support (dual TERMINAL windows + focus)
- [x] Scrollable terminal content (32-line ring, PgUp/PgDn)

## Phase 7: Networking Stack

- [x] TCP/IP stack (MSS negotiation, window-aware segmented send, slow-start, Go-Back-N retransmit)
- [x] Socket API for user programs (UDP over e1000; TCP handshake + send/recv)
- [x] DHCP client (DISCOVER/OFFER/REQUEST/ACK + lease)
- [x] DNS resolver (A query TX+RX parse; store dns-last-ip)

## Minimal image app-console output restored (2026-10-24)

- [x] The core-only root now imports the actual CPU/domain/channel/scheduler
      contracts, owns the same explicit redirect globals as the standard root,
      and selects a core-only shell over the shared input/file/app dispatcher.
      The old image had omitted the globals consumed by `serial-put`; historical
      output-loss notes attributed the symptom to a stale temporary. The current
      source contract no longer depends on an undeclared redirect variable.
- [x] Standard and minimal images build with the source-built compiler and both
      pass the full application marker set in `check-image-variants.sh`.
      Calculator results, notes save/reopen, hex output, checksum and every shipped
      app's output are now required on minimal too; the reduced marker allowance
      has been removed. Actual native workflow runner passes 11/11 on minimal.
- [x] Minimal source closure excludes desktop/network/foreign personalities and
      real NVMe drivers. RAM SparkFS is the functional backend; unavailable device
      reads/writes return ENODEV instead of reporting successful I/O.
