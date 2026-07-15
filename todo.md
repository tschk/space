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
Still not full TCP window/congestion. Darwin/Windows are translator subsets
(VFS/process/serial), not full XNU/NT ABIs — see docs/personalities.md.

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

- [x] TCP/IP stack (active open + best-effort data path; no window/congestion)
- [x] Socket API for user programs (UDP over e1000; TCP handshake + send/recv)
- [x] DHCP client (DISCOVER/OFFER/REQUEST/ACK + lease)
- [x] DNS resolver (A query TX+RX parse; store dns-last-ip)
