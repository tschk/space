# Protected Windows TEB and static TLS startup

`windows-startup-run(image,size,serial,storage)` is a separate bounded startup
profile. The strict and general PE entry points keep their previous TLS refusal.
This profile advances an actual original-application startup prerequisite; it
still refuses the pinned original Windows jq because other directories and its
14-DLL/217-import dependency set remain unsupported. No UCRT function is stubbed.

The original jq entry reads `GS:[0x30]` and the resulting TEB stack base before
its CRT initializer. Its TLS directory has eight template bytes and three
callbacks. Inspection of the checksum-pinned original is recorded in the
[Windows process checkpoint](plans/2026-10-24-windows-protected-process.md).

## Owned startup state

`components/windows-pe-startup.in` validates the TLS directory before any domain,
frame or activation allocation. It accepts one main executable's static TLS,
up to 4096 template-plus-zero bytes and eight callbacks terminated by a null
pointer. Template bytes and callback arrays must be file-backed; callback targets
must be in admitted RX raw section bytes; the aligned DWORD index must lie in a
writable image section. Pointer overflow, unsupported alignment/reserved bits,
missing terminators and unmapped/non-executable callbacks refuse with `-8`.

Each activation owns four private RW/NX pages starting at `0x4e000000`:

| Page | Implemented fields |
| --- | --- |
| TEB | NT_TIB ExceptionList `-1`, stack base/limit, self at `0x30`, activation process/thread IDs, TLS vector at `0x58`, PEB pointer at `0x60`, LastErrorValue at `0x68` |
| PEB | Preferred image base at `0x10` |
| TLS vector | Slot zero points to the activation's TLS data page |
| TLS data | Copied initial template, zero-filled remainder, page aligned |

The private image's TLS index is initialized to zero. No original file bytes
are changed. The TEB/PEB are deliberately partial: there are no process
parameters, loader lists, Windows heap, SEH/unwind, dynamic TLS allocation or
thread creation. TEB-based profiles now synchronize `GetLastError`/`SetLastError`
with the owned TEB field; see the [identity/error checkpoint](windows-pe-view-checks.md).

A generated RX guest capsule calls the validated callbacks in order, then the
entry point. Every callback executes at CPL3 with RCX=image base,
EDX=`DLL_PROCESS_ATTACH`, R8=null, 32 bytes of shadow space and Win64 stack
alignment. A fault or deadline aborts the activation and prevents the remaining
startup sequence. There is no callback exception handler, detach callback or
Windows loader-lock emulation.

## CPU scope and cleanup

All protected Windows profiles save caller FS/GS bases, set initial FS to zero
and GS to zero or the owned startup TEB, then restore both immediately after
bounded execution returns, before releasing handles/pages/domain. The CPU
runtime owner confirmed the current kernel uses no GS-relative storage or
`SWAPGS`; the existing generic `rdmsr`/`wrmsr64` primitives suffice for this
synchronous path. Future kernel GS use requires redesigning this handoff.
Guests cannot write these MSRs. Writing a fake pointer into their writable TEB
does not widen their page tables or permit a kernel read.

Run with the explicit source-built compiler:

```sh
PATH=/workspace/toolchain/bin:/workspace/toolchain/usr/bin:$PATH \
python3 scripts/check-windows-startup.py \
  --in /workspace/toolchain/inauguration-0.9.324/in-cli/target/release/in \
  --out /tmp/space-windows-startup-final-evidence
```

The gate exercises 171 actual launches: callback arguments/order/CPL/shadow space,
GS self/stack/PEB/TLS loads, private initialization and writable TLS, template
zero fill through byte4095, NX TEB/TLS execution refusal, forged TEB pointer
kernel-read refusal, WRMSR denial, callback infinite-loop cancellation124,
fresh launch after failures and exact repeated heap/frame/domain invariants.
A caller FS base pointing at mapped guest image data must not become the guest's
initial FS; an actual `FS:[0]` load faults. Caller FS/GS canaries survive normal,
fault and deadline paths. Separate cases cover eight callbacks, ninth-callback
refusal, no callback array and TEB startup without a TLS directory. Malformed
admission checks require no heap/frame/domain ownership change.

## Public contract references

Read-only upstream inspection at the existing pinned revisions informed the
contracts; no implementation source was copied or vendored:

- [Wine loader](https://github.com/wine-mirror/wine/blob/840a939ee526137639665ff5f587224d6a36403f/dlls/ntdll/loader.c): `alloc_tls_slot`, `alloc_thread_tls`, and `call_tls_callbacks` establish template copying/zero fill, TLS vector/index and module/reason/null callback arguments. Wine source is LGPL; reference inspection does not grant permission to copy code under a different license.
- [ReactOS loader initialization](https://github.com/reactos/reactos/blob/e81244349554c4f98a97fdd7fb67d7a1b450eec5/dll/ntdll/ldr/ldrinit.c): `LdrpInitializeTls`, `LdrpAllocateTls` and process-attach callback ordering. ReactOS licensing is file-specific; no source reuse is claimed.

The next original-app work needs coherent dependency activation, UCRT/native API
contracts and real startup/stdio/heap behavior, plus explicit treatment of the
remaining exception/resource/relocation directories. Passing this fixture does
not establish original jq execution or Windows GUI compatibility.

Fresh verification uses the source-built 0.9.324 compiler (SHA256
`43b5a2f166efb28ea3123e8030c549d1eac9e90ee7c642d013457ff7ade09168`)
and boot source `5f0cc717cd1f57d20606964303cb061edf366778464efd639d7b64d52056495f`.
The new gate records source/kernel/fixture hashes and launch commands. Regression
reports are `/tmp/space-windows-{strict,files,write,application}-startup-regression/report.json`
(507/527/527/317 launches), plus `/tmp/space-windows-nvme-startup-regression/report.json`
(six independent NVMe boots). The original pinned jq retains structural entry
`0x140001400`, complete admission refusal `-8` before allocation and `executed:false`.

The separate [execution-local TLS/FLS profile](windows-local-checks.md) versions
the TEB to two pages and relocates its PEB; the older profiles retain the layout
above. All process entries now reserve their return address and 32-byte Win64
home area below the declared stack base. Static callbacks continue to use actual
CPL3 calls; dynamic FLS callbacks use saved generic user contexts.
