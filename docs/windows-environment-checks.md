# Owned Windows process environment

`windows-command-environment-run(image,size,serial,storage,line,bytes,env,envbytes)`
adds profile 5 with `GetEnvironmentVariableA`, `GetEnvironmentStringsW`,
`FreeEnvironmentStringsW` and `SetEnvironmentVariableW`. The native caller supplies
an explicit ASCII `NAME=value\0...\0\0` environment. Space never inherits a host
shell environment. Original SQLite and 7za remain refused before execution.

The bounded profile accepts at most 16 entries, 63-byte nonempty names, 255-byte
values and 2048 bytes including the double terminator. Names compare without
ASCII case and duplicates are refused. Names containing `=` are unsupported,
including Windows drive pseudo variables. Non-ASCII inputs are refused; the wide
APIs accept ASCII encoded as UTF16, not arbitrary Unicode. This is an explicit
compatibility boundary rather than a Unicode implementation.

The caller retains its input block. Activation copies it into native-only owned
frames; no canonical environment frame is mapped into the guest. Four distinct
read-only, nonexecutable guest pages hold sorted UTF16 snapshots. A later mutation
does not alter an outstanding snapshot. Free validates the exact active pointer;
interior pointers, unknown pointers and double frees return false/error 87.
Freed snapshot pages remain mapped until activation teardown and may be reused
only after logical free. This is a bounded allocation pool, without a claim that
using a freed Windows pointer is valid.

Get-variable size queries return the required size including NUL. Short buffers
remain unchanged and return that same required size. Successful copies return
length excluding NUL and preserve LastError, including an existing empty value.
Missing variables return zero/error 203. Set-variable copies and validates both
inputs, builds a complete candidate map, and commits only after it fits. Empty
values and deletion by NULL are distinct; deleting a missing variable succeeds.
Invalid spans produce error 998, unsupported Unicode 1113, oversized strings 206,
and exhausted entry/snapshot capacity 8. Mutation failures leave the map and
outstanding snapshots unchanged. No API allocates per call.

The executable gate is:

```sh
PATH=/workspace/toolchain/bin:/workspace/toolchain/usr/bin:$PATH \
python3 scripts/check-windows-environment.py \
  --in /workspace/toolchain/inauguration-0.9.324/in-cli/target/release/in \
  --out /tmp/space-windows-environment-proof
```

It performs 380 actual CPL3 executions and 11 malformed native configuration
refusals. These cover size/empty/missing/case semantics, snapshot independence and
sorting, four-slot exhaustion and reuse, atomic mutation denial, protected-page
write and execute faults, guest deadline termination, and a fresh configured map
after mutation/fault/deadline. After the first complete cycle, 20 repeated cycles
keep heap, free-frame count and domain count exact. It checks caller FS/GS,
borrowed grants and all environment state after teardown.

Public behavior was checked against Wine's environment tests and implementation
at `840a939ee526137639665ff5f587224d6a36403f`, particularly
[`dlls/kernel32/tests/environ.c`](https://github.com/wine-mirror/wine/blob/840a939ee526137639665ff5f587224d6a36403f/dlls/kernel32/tests/environ.c)
and [`dlls/ntdll/env.c`](https://github.com/wine-mirror/wine/blob/840a939ee526137639665ff5f587224d6a36403f/dlls/ntdll/env.c).
Those are read-only semantic references; no Wine implementation is vendored.
Profile 5 does not admit FILETIME or QPC. Prior profiles continue refusing the
new environment imports.
