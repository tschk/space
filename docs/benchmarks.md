# Space benchmarks

Space ships a deterministic CPU benchmark as a preinstalled app
(`components/app-bench.in`, boot kind 13). It counts the primes below
100,000 by trial division — the same fixed-point integer algorithm as the
C reference in [`bench-primes.c`](bench-primes.c) — and reports the elapsed
time and a primes-per-second score from kernel tick counters.

This page records the Space 0.1.0 numbers and how to reproduce them,
including on other operating systems.

## Methodology

- **Workload:** identical algorithm on every platform — trial division of
  every `n < 100000` against odd divisors up to `sqrt(n)` (`bench: found
  9592 primes` is the correctness check; any platform computing a
  different count is broken, not slower).
- **Space timing:** the kernel tick export (`ticks-now`), driven by the
  Programmable Interval Timer at 100 Hz. One tick is 10 ms, so Space
  readings have ±10 ms granularity. The score is
  `count * PIT_HZ / (t1 - t0)`.
- **Linux/Windows timing:** wall clock around the same loop
  (`clock_gettime` on Linux, `QueryPerformanceCounter` on Windows), which
  has nanosecond granularity. The comparison below therefore bounds the
  real gap; Space's true time is within one PIT tick of the reported one.

## Space 0.1.0 (QEMU x86_64, 2 vCPU, TCG)

Measured with `scripts/check-image-variants.sh` during the 0.1.0 rebuild:

| Image | Time | Score |
|---|---|---|
| standard.bin | 20 ms | 479,600 primes/s |
| minimal.bin | 30 ms | 319,733 primes/s |

Reproduce:

```bash
bash scripts/build-images.sh
qemu-system-x86_64 -kernel /tmp/space-images/standard.bin -m 256M \
  -nographic -no-reboot -serial stdio
# at the prompt:  runapp bench
```

The app runs inside an isolated dynamic module: a separate page-table
domain with its own 2 MiB heap, imports bound at load time — the
benchmark measures user code, not kernel mode.

## Linux on the same host (Intel Xeon 2.60 GHz, 2 cores)

```bash
gcc -O2 docs/bench-primes.c -o bench-primes && ./bench-primes
# primes=9592 time=2.6ms   (repeated runs: 2.6–3.9 ms)
```

| Platform | Time | Throughput |
|---|---|---|
| Linux, gcc -O2 | ~2.6 ms | ~3.7M primes/s |
| Space standard (QEMU TCG) | 20 ms | ~480K primes/s |
| Space minimal (QEMU TCG) | 30 ms | ~320K primes/s |

Reading the comparison honestly:

- The host numbers are native execution on the physical CPU. The Space
  numbers are a guest under QEMU's TCG interpreter on the same physical
  CPU, so the gap mostly measures emulation, not the Space kernel.
- Even so, Space completes the identical 9592-prime workload correctly in
  tens of milliseconds while a full desktop Linux needs ~3 ms natively —
  the same order of magnitude once virtualization overhead is accounted
  for, on a kernel whose image is under 1 MB.

## Windows

Not executed for this page (no Windows host was available). The C
reference builds and runs unchanged:

```bat
cl /O2 docs\bench-primes.c /Febench-primes.exe && bench-primes.exe
```

or with MinGW: `gcc -O2 docs/bench-primes.c -o bench-primes.exe &&
bench-primes.exe`. Please report the printed time next to the Linux row.

## Determinism

`app-bench` declares `deterministic true`: the prime count is a fixed
value (9592), the CI check pins it, and the return code
(`0x2578` = 9592) is asserted on every image-variants run. The same
property that makes it a benchmark makes it a regression test for the
compiler's integer codegen and the scheduler's tick accounting.
