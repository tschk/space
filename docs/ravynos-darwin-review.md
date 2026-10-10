# ravynOS reference for Space's Darwin personality

Reviewed 2026-10-10 against ravynOS `darwin` at `60aa4ff4b16a54ef8cc1a9ea656b8a827b3419b7`.
This is a source/contract review, not evidence of running macOS applications.

## What transfers

ravynOS aims at source compatibility and eventual binary compatibility. Its
[repository](https://github.com/ravynsoft/ravynos/tree/60aa4ff4b16a54ef8cc1a9ea656b8a827b3419b7) combines Darwin/FreeBSD foundations with runtime libraries
and frameworks. Space's native contract remains SCI; a Darwin personality is a
translator onto Space objects and capabilities.

| Reference surface | Space implication | Acceptance check |
| --- | --- | --- |
| [XNU errno definitions](https://github.com/ravynsoft/ravynos/blob/60aa4ff4b16a54ef8cc1a9ea656b8a827b3419b7/Kernel/xnu/bsd/sys/errno.h) | Translate backend errors at the personality boundary; ENOSYS is 78. | QEMU unknown-call result -78 and errno 78; internal -38 maps to -78. |
| [XNU syscall table](https://github.com/ravynsoft/ravynos/blob/60aa4ff4b16a54ef8cc1a9ea656b8a827b3419b7/Kernel/xnu/bsd/kern/syscalls.master) | wait4=7, recvfrom=29, lseek=199 already agree; getcwd=192 and getpagesize=276 are Space shims. | Keep raw ABI claims separate from shell dispatch tests. |
| [dyld](https://github.com/ravynsoft/ravynos/tree/60aa4ff4b16a54ef8cc1a9ea656b8a827b3419b7/Libraries/dyld) | Executing Mach-O requires validated segments and relocation/import handling, beyond recognizing a header. | First run a dependency-free x86_64 Mach-O fixture; reject malformed ranges before any mapping. |
| [Objective-C runtime](https://github.com/ravynsoft/ravynos/tree/60aa4ff4b16a54ef8cc1a9ea656b8a827b3419b7/Libraries/objc4) | Objective-C metadata, selectors and message dispatch are a separate compatibility layer. | A small compiled class/message-send fixture must run before claiming Objective-C support. |
| [Frameworks](https://github.com/ravynsoft/ravynos/tree/60aa4ff4b16a54ef8cc1a9ea656b8a827b3419b7/Frameworks) | Foundation/AppKit/CoreGraphics are substantial APIs beyond syscall translation. | A minimal Foundation fixture, then a window/input fixture through Space's display path. |

## Changes from this review

`components/darwin.in` now uses ENOSYS=78 and normalizes both negative dispatch
results and the errno slot. The existing QEMU demo checks the literal ABI values,
internal/native ENOSYS translation, and success-preserves-errno behavior.
The dispatcher also accepts x86_64 Unix-class numbers (`0x2000000 | number`),
verified against ravynOS's [syscall class definitions](https://github.com/ravynsoft/ravynos/blob/60aa4ff4b16a54ef8cc1a9ea656b8a827b3419b7/Kernel/xnu/osfmk/mach/i386/syscall_sw.h). Other classes and tagged local shims are rejected; this is `.in`
dispatch coverage, not a hardware SYSCALL/register ABI implementation.
`fcntl` now rejects unopened descriptors for F_GETFD and F_SETFD; the QEMU demo
checks both error results and errno.

## First Mach-O execution slice

`components/darwin-macho.in` validates a thin x86_64 MH_EXECUTE image with one
already resident RX segment and LC_MAIN. `fixtures/darwin-minimal-macho.asm`
contains a dependency-free entry returning 42. `scripts/check-darwin-macho.sh`
boots that image, exercises malformed-input rejection, and checks execution.
The layout follows [Mach-O format definitions](https://github.com/ravynsoft/ravynos/blob/60aa4ff4b16a54ef8cc1a9ea656b8a827b3419b7/Kernel/xnu/EXTERNAL_HEADERS/mach-o/loader.h);
no upstream implementation is imported.

This path uses the existing identity map and invokes trusted fixture code at
CPL0. It has no mapping, relocation, macOS entry stack, register syscall ABI,
imports, or dyld. General macOS applications remain unsupported. Next work must
establish the process entry and address-space contract before accepting broader
Mach-O files; generic compiler support belongs in Inauguration and runtime loader
policy belongs in Space.

No ravynOS source has been vendored. Its files carry different license terms;
review the exact files before considering reuse. ABI facts alone do not justify
importing XNU, dyld, or framework implementations.
