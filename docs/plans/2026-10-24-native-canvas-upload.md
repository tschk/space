# Native owned canvas upload before foreign framebuffer policy

The full desktop/application goal remains OPEN. Build an executable private
native provider before mapping Linux fbdev concepts onto it. This is a trusted
kernel-linked component library prototype, not an isolated SCI display service
or a new compositor. Import it explicitly in focused checks; do not change the
ordinary image or advertise an unavailable GUI launch action.

## Ownership and contracts

A generation-bearing native Canvas handle owns two private kernel buffers, one
accepted frame, an existing DSP surface/pool lease and a live Memory+Display
owner grant. At most two256x128 RGBX8888 canvases fit this initial profile.
Buffers and metadata are cached by the provider across close/reuse; callers
never receive those pointers. Source backing remains exclusively owned by the
existing UserAddressSpace object; do not add a backing ledger or physical-pointer
translation. Canvas binding records a borrowed generation-bearing VM handle and
its original memory grant. It never consumes the VM's constructor/reference.

The owner explicitly creates/binds/uploads/closes. Only logical domain0, native
kernel CR3 and no active user context/budget may call. Validate grant identity,
original target, generation, state and scene before memory access or presentation.
An upload accepts only a stopped native CPU binding to the exact borrowed VM.
Use public checked native copy-in in bounded chunks, convert RGBX to opaque ARGB,
and replace the accepted frame only after the entire copy and final authority/
scene checks succeed. Copy failure must preserve accepted frame/epoch/pixels.
No guest maps scanout, provider metadata, staging or accepted buffers.

Reuse display-spdp's attach/stride/geometry/commit/composite and lifetime rules.
The scene must be quiescent or contain only this provider's bounded objects;
refuse live external surfaces. Output configuration is fixed during a lease.
This private first slice does not prove tiling integration, multi-output,
interactive input or atomic physical scanout presentation. Existing parent
desktop restoration and launcher/damage gates remain required on integration.

Close fences new uploads, withdraws surface/pool references, then invalidates the
handle before reuse. Keep uncertain teardown ownership for explicit owner retry.
Closing a canvas never releases its borrowed VM. The display owner can withdraw
its surface after the separate source-memory grant is revoked. Repeated sessions
must reclaim all per-lease state and preserve bounded provider caches/resources;
old handles and cross-VM bindings refuse before data/presentation changes.

## Executable acceptance

Use real CPL3 producer code and the generic native VM object, not forged CPU
phases or a hosted renderer. Test actual source bytes and screen pixels for two
independent objects, RO/invalid/crossing sources, wrong/live-revoked grants,
wrong VM, unknown/stale handles, output changes, close/survivor and21 measured
resource/generation cycles. A partial-copy revocation/invariant control must
perform a genuine first read and then refuse further reads without publishing.
Add cold memory admission/refusal and raw SCI-import denial. Preserve all failed
receipts. Follow with the unchanged ordinary desktop and launcher/damage gates.

Only after this provider works, add a separate Linux edge binding: owned device
FDs, real fb_var/fb_fix UAPI conversion, bounded shared mappings backed by native
VM pages, and explicit presentation at the viewer's actual unmap boundary.
Unknown ioctls/flags, raw physical access and unsupported process combinations
remain refused before side effects. Do not fabricate VT/signal success.

## Healthy original reference

`/workspace/real-apps/fbv-linux-reference/report.json` records a healthy Debian
Linux6.1 framebuffer boot: original pinned fbv exits0 and its centered4x4 BMP
matches all3072000 RGB screenshot bytes on1280x800 output. The initramfs contains
only a small reference init, six actual DRM/bochs modules, the original static
viewer and the bitmap. Package, kernel, modules, init and frame hashes are kept.
This is reference execution only, with zero Space application/GUI credit.
The first headless-host/Space refusal and native fault evidence remain preserved.

## Actual focused evidence

`/workspace/native-canvas-final/report.json` passes132 genuine CPL3 producer
entries,22 real write-protection faults and21 measured resource cycles after
warmup. Two independent256x128 accepted surfaces and the cursor match five
entire1024x768 RGB screenshots byte for byte. The rendered two-surface frame
was inspected visually. Guest writes do not change accepted pixels; closing one
surface preserves the other, and fresh handles reject old generations.

Each cycle exercises two actual grant revocations after the first successful
4096-byte native copy: exactly one read attempt occurs, upload returns-2 and
accepted epoch/pixels remain unchanged. The test compiler copy substitutes one
call through a trusted fixture interposer, which always invokes real native
copy-in and then revokes the actual grant. Canonical/compiled provider hashes
and the exact substitution are recorded; production has no interposer/hooks.

A third mid-copy control changes the actual source VM PDE huge bit after one
read. The second real checked native read returns-5 and quarantines the VM;
accepted pixels/epoch survive. Canvas close retains no VM reference. Binding
and constructor detach commit separately, retain quarantine, and public recovery
reclaims it only after trusted page-table repair. No forged CPU phases are used.

Renderer pool uncertainty returns-5 with lifecycle phase2 and leaves its surface
and pointer untouched; uploads/new leases refuse until explicit repair/close.
An actual1024x768 ->1280x720 ->1024x768 output change rejects the old lease even
with the original dimensions restored. A raw SCI importing native-canvas-new is
denied before entry without changing heap, grants, domains or live instances.
The new private prefix is excluded from the real dynamic export registry.

Causal negative controls retain failures: `/workspace/native-canvas-read-control-evidence`
removes only per-read authority checks and fails on a second attempted read;
`/workspace/native-canvas-close-control-evidence` removes only association
preflight and incorrectly destroys the uncertain lease. First/intermediate
receipts are preserved, including hardening2's missing export restriction and
hardening4's test ordering error (output generation invalidated the lease before
the intended mid-copy fault). Neither is rewritten as a pass.

The ordinary desktop launcher/input/pointer/resize/restoration regression passes
at `/workspace/native-canvas-launcher`; the unchanged100-frame damage gate passes
at `/workspace/native-canvas-damage` with333fps/30 ticks (threshold30). These
checks do not give original foreign GUI application credit. The Linux edge and
product launch integration remain open.

## Next executable edge profile

Implement an explicit Linux framebuffer session around a caller-owned canvas,
with one protected process, one open device descriptor at a time and one shared
mapping per complete lease. Reopening after its completed unmap refuses-95;
this does not claim persistent remappable file backing. The first original workload uses `fbv -cery /fbv-test.bmp`: original nearest-
neighbor enlargement of the4x4 BMP to the whole canvas, no interactive TTY
request. Inspection/actual execution showed that even -y centers smaller images,
so the earlier proposed top-left profile was incorrect. Smaller fbv output
makes two simultaneous shared aliases; the native VM currently has no owned alias contract, so refuse
the second mapping rather than return the same address or copy disconnected
buffers. Genuine MAP_SHARED backing exists for the admitted single mapping;
closing its descriptor does not invalidate it. Commit pixels at exact whole
mapping unmap, before native page withdrawal, and retain mapping on failed copy.

Expose only FBIOGET_VSCREENINFO and FBIOGET_FSCREENINFO with actual canvas
geometry/stride/RGB bitfields. smem_start/mmio_start are zero: no physical mapping
is exposed. Unsupported ioctl, dup, device reads/writes, partial unmap/protection,
and fork/vfork/exec while the explicit session is armed must refuse. Unknown
paths retain existing behavior. No VT, signal, keyboard or terminal success is
fabricated. The first gate must compare actual original-app pixels with an
independent BMP oracle, check status/ownership and show no ambient device access.
This is a finite initial framebuffer profile, not general Linux fbdev/X11.


Ordinary Linux CLI builds import only a small private synchronous optional-device
contract. They do not import display/canvas/foreign GUI modules or allocate the
private request buffer. The framebuffer supervisor explicitly installs a raw
machine-ABI Int->Int callback and owned64-byte request before its sole process;
all policy remains in the separately imported framebuffer adapter. This trusted
kernel-linked call is not a second IPC service or SCI isolation. It cannot throw,
retain the request, reenter the adapter or accept guest-selected callback pointers.
The actual minimal CLI regression verifies that the display dependency is absent.
