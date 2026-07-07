# Inauguration x86_64 codegen bugs blocking Space NVMe

**Status:** In progress  
**Owner:** Space kernel team  
**Upstream:** `../inauguration` generic x86_64 native lowering

## Problem

The Space nanokernel's in-kernel NVMe driver hit two codegen bugs in the Inauguration `x86_64` native lowering. Both bugs are generic and affect any `.in` program compiled for `x86_64-unknown-none` or the host JIT.

### Bug 1: 7th function argument is mis-passed

A function with 7 integer arguments does not receive the 7th argument correctly on the caller side or load it correctly on the callee side. The first 6 arguments pass in registers (System V ABI), and the 7th must be passed on the stack.

Space reproducer:

```in
package repro.arg7
module repro.arg7.main

fn seven(a: Int, b: Int, c: Int, d: Int, e: Int, f: Int, g: Int) -> Int {
  return g
}

fn main() -> Int {
  return seven(1, 2, 3, 4, 5, 6, 7)
}
```

Expected: `7`. Actual: wrong value or crash depending on surrounding code.

### Bug 2: `while` loop with variable condition flag is lowered incorrectly

A loop using a `done` flag inside the condition is not correctly compiled. The loop body updates `done`, but the condition is re-evaluated using stale state or the wrong comparison, causing wrong iteration count or infinite loops.

Space reproducer:

```in
package repro.loopdone
module repro.loopdone.main

fn main() -> Int {
  let done = 0
  let to = 0
  while done == 0 {
    to = to + 1
    if to >= 5 {
      done = 1
    }
  }
  return to
}
```

Expected: `5`. Actual: `0` or wrong count.

## Root-cause area

`in-cli/src/native_emit/x86_64_lower.rs` in `../inauguration`:
- Function call argument emission for stack arguments.
- Function prologue stack-parameter slot assignment vs. load/store helper sign convention.
- `Stmt::Loop` lowering for `LoopKind::While` with variable conditions.

## Fix plan

1. Implement generic fix in `../inauguration` so stack arguments are emitted and loaded at the correct `[rbp+16+(i-6)*8]` locations and `while` conditions are reloaded each iteration.
2. Add compiler tests in `in-cli/src/native_emit/lower/lower_tests.rs` or the `in test` suite for both cases.
3. Run `in test` and `in test --owned-native` in `../inauguration`.
4. Return to Space, remove the NVMe workarounds, and re-run `scripts/check-qemu-boot-nvme.sh`.

## Acceptance

- `in test` passes.
- The two reproducers above return the expected values when run with `in execute`.
- Space kernel NVMe driver no longer needs the 6-argument limit or `while to < N` loop rewrite.
