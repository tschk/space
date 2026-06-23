# Space TODO — Roadmap to OS Personalities

## Tagged: 0.0.1 — Nanokernel Foundation

Working today: x86_64 boot, serial shell, memory domains, capabilities,
cooperative + preemptive scheduling, channels, SCI loader, e1000 NIC,
PCI, deterministic execution, checkpoint/restore.

## Phase 1: Storage

- [x] ATA/PIO disk driver (read sectors from QEMU IDE disk)
- [x] Simple flat filesystem (read-only first, then write)
- [ ] VFS abstraction layer
- [ ] Load SCI components from disk at runtime

## Phase 2: Process Abstraction

- [x] Process struct (domain + caps + entry + lifecycle)
- [ ] Process loader (read SCI image from disk, create domain, map, jump)
- [x] Process lifecycle: spawn, exit, wait, kill
- [x] Process table and listing (`ps` command upgrade)

## Phase 3: Syscall Interface

- [x] Syscall trap handler (int 0x80 or syscall instruction)
- [x] Syscall dispatch table
- [x] Core syscalls: write, read, exit, yield, getpid
- [ ] Channel syscalls: send, recv, select
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
  - [ ] Mach port IPC mapping to Space channels
  - [ ] BSD syscall table
- [ ] Windows compat layer (Win32 subset)
  - [ ] Handle-based IPC mapping to capabilities
  - [ ] Win32 API table (CreateFile, ReadFile, WriteFile, etc.)
- [ ] Personality loader (select personality at process spawn time)

## Phase 6: Interactive Usability

- [ ] VGA framebuffer console (text mode at minimum)
- [ ] PS/2 keyboard driver
- [ ] Shell upgrade: pipe support, background processes, redirection
- [ ] Multi-terminal support

## Phase 7: Networking Stack

- [ ] TCP/IP stack (SYN/ACK, sliding window, retransmit)
- [ ] Socket API for user programs
- [ ] DHCP client
- [ ] DNS resolver

## Phase 8: Distribution

- [ ] Remote component loading (network → domain)
- [ ] Migration (checkpoint process, transfer, restore on another node)
- [ ] Distributed scheduling
