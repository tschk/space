# Space repo — all `ponytail:` comments in `.in` files

11 comments across 22 `.in` files (9 kernel, 5 services, 1 protocol).

```
kernel/fs.in:219:         // ponytail: 64 * 32 = 2048 — const-folding can't resolve global const names
kernel/linux.in:473:      // ponytail: real fork needs COW page tables + per-process address spaces;
kernel/linux.in:613:      // ponytail: allocates from kernel bump heap — no per-process VM yet.
kernel/fb.in:520:         // ponytail: test pattern removed — ~3KB of pixel-loop code that was only
kernel/kernel-root.in:132:// ponytail: unreachable after yield
kernel/net.in:106:        // ponytail: only e1000_rx_wait is called; e1000_rx_poll removed.
services/fs.in:3:         // ponytail: no kernel alloc, no hardware access. Files are Int values
services/gfx.in:2:        // ponytail: wraps kernel compositor. Surface management and blitting
services/proc.in:2:       // ponytail: wraps kernel process table with listing/lifecycle helpers.
services/net.in:2:        // ponytail: see kernel/net.in for the full driver. This service
services/time.in:2:       // ponytail: simple tick counter. Add RTC/HPET for wall-clock time.
```
