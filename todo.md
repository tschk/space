# Space TODO — Roadmap to OS Personalities

## Tagged: 0.0.1 — Nanokernel Foundation

Verified today: x86_64 boot, serial shell, memory domains, capabilities,
cooperative + preemptive scheduling, channels, the in-kernel SCI loader,
the Linux-personality demo, VFS, time service, network component RPC, and SCI
allow/deny policy. Display and input SCI components have automated QEMU proof.
NVMe format/write path passes under QEMU (`check-qemu-boot-nvme`). Volume SCI
on NVMe passes RPC + multi-file shell soak across reboot (`check-qemu-volume-nvme`,
`check-volume-soak`) on the volume-ready FS path. Second user SCI (`uecho` @
0x1b0000) loads under QEMU. Netstack: UDP sockets work; TCP is SYN-only connect
TX (no ACK/window/retransmit); DHCP DISCOVER TX; DNS A-query TX for space.test.

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

- [x] Linux compat layer (.in component translating POSIX syscalls)
  - [x] File syscalls: open, read, write, close, stat, lseek, fstat
  - [x] Process syscalls: fork, exec, wait, exit, getpid, kill
  - [x] Memory syscalls: mmap, munmap, brk
  - [x] Misc syscalls: getcwd, chdir
  - [x] Socket syscalls: socket, bind, listen, accept, connect, send, recv (UDP path; TCP SYN-only connect)
  - [x] Signal handling (minimal: SIGTERM, SIGKILL)
- [x] Darwin compat layer (Mach/BSD subset) — stub personality demos
- [x] Windows compat layer (Win32 subset) — stub personality demos

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

- [x] TCP/IP stack (SYN-only connect TX; no ACK/window/retransmit yet)
- [x] Socket API for user programs (UDP over e1000; TCP SYN_SENT/LISTEN)
- [x] DHCP client (DISCOVER/OFFER/REQUEST/ACK + lease)
- [x] DNS resolver (A query TX+RX parse; store dns-last-ip)
