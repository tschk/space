# Space repo — all `ponytail:` comments in `.in` files

13 comments across 14 `.in` files (10 kernel, 1 service, 1 protocol, 2 boot-adjacent).

```
kernel/fs.in:219:         — (resolved) was const-fold 2048; now uses FS_MAX_FILES * FS_ENTRY_SIZE
kernel/linux.in:476:      // ponytail: real fork needs COW page tables + per-process address spaces;
kernel/linux.in:707:      // ponytail: allocates from kernel bump heap — no per-process VM yet.
kernel/fb.in:476:         // ponytail: 2px padding between chars and 3px between lines for readability.
kernel/fb.in:553:         // ponytail: test pattern removed — ~3KB of pixel-loop code that was only
kernel/kernel-root.in:135: // ponytail: unreachable after yield — ctxsw does not return
kernel/kernel-root.in:771: — (resolved) sys_chan_close calls heap_free via channel deallocation PR #23
kernel/fb.in:553:         — (resolved) fb_test_pattern restored; shell command `fb test`
kernel/net.in:106:        — (resolved) e1000_rx_poll restored; e1000_rx_wait delegates to poll
kernel/compositor.in:69:  // ponytail: backbuffer at top of heap avoids alloc/heap_next (optimizer crash).
kernel/compositor.in:282: // ponytail: subtract taskbar to prevent window overlap
kernel/compositor.in:301: // ponytail: flat color desktop (stripes were 20 loops per frame)
kernel/compositor.in:330: // ponytail: white cursor, no outline (outline was 256 extra pixel calls)
kernel/compositor.in:1008:// ponytail: pause briefly to avoid burning CPU. hlt wakes on interrupt.
```

**Services:** only `services/display.in` remains (Wayland-inspired display server over channel IPC).
Deleted stubs (`fs`, `gfx`, `net`, `proc`, `time`) were vestigial wrappers; real logic lives in `kernel/`.