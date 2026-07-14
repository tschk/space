# Space TODO — Roadmap to OS Personalities

## Tagged: 0.0.1 — Nanokernel Foundation

Verified today: x86_64 boot, serial shell, memory domains, capabilities,
cooperative + preemptive scheduling, channels, the in-kernel SCI loader,
the Linux-personality demo, VFS, and time service. Display and input SCI
components have manual QEMU proof. NVMe-backed storage, network runtime,
component deny-policy enforcement, and the remaining component split are not
yet verified.

## Phase 1: Storage

- [x] ATA/PIO disk driver (read sectors from QEMU IDE disk)
- [x] Simple flat filesystem (read-only, then write)
- [x] NVMe driver with MMIO
- [ ] VFS abstraction layer
- [ ] Load SCI components from disk at runtime

## Phase 2: Process Abstraction

- [x] Process struct (domain + caps + entry + lifecycle)
- [x] Process lifecycle: spawn, exit, wait, kill
- [x] Process table and listing (`ps` command)
- [ ] Process loader (read SCI image from disk, create domain, map, jump)

## Phase 3: Syscall Interface

- [x] Syscall trap handler (int 0x80 or syscall instruction)
- [x] Syscall dispatch table
- [x] Core syscalls: write, read, exit, yield, getpid
- [x] Channel syscalls: create, send, recv, close
- [ ] Capability syscalls: mint, revoke, check

## Phase 4: Userspace Runtime

- [x] Minimal libc in .in (print, open, read, write, close, exit)
- [x] Userspace heap (malloc/free on top of mmap)
- [x] String and memory utilities
- [ ] Build user programs as SCI components

## Phase 5: OS Personalities

- [x] Linux compat layer (.in component translating POSIX syscalls)
  - [x] File syscalls: open, read, write, close, stat, lseek, fstat
  - [x] Process syscalls: fork, exec, wait, exit, getpid, kill
  - [x] Memory syscalls: mmap, munmap, brk
  - [x] Misc syscalls: getcwd, chdir
  - [ ] Socket syscalls: socket, bind, listen, accept, connect, send, recv
  - [ ] Signal handling (minimal: SIGTERM, SIGKILL)
- [ ] Darwin compat layer (Mach/BSD subset)
- [ ] Windows compat layer (Win32 subset)

## Phase 6: Interactive Usability

- [x] VBE framebuffer console (1920×1080×32)
- [x] GNOME-style desktop compositor
- [x] X11-style arrow cursor
- [x] Window close, minimize, resize, drag, z-order
- [x] Taskbar window buttons (click to focus/restore)
- [x] USB HID keyboard (replaces PS/2)
- [x] Display server service (SPDP protocol)
- [x] VRO text editor
- [ ] Shell upgrade: pipe support, background processes, redirection
- [ ] Multi-terminal support
- [ ] Scrollable terminal content

## Phase 7: Networking Stack

- [ ] TCP/IP stack (SYN/ACK, sliding window, retransmit)
- [ ] Socket API for user programs
- [ ] DHCP client
- [ ] DNS resolver
