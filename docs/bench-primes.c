/*
 * Reference implementation of Space's app-bench workload, in portable C,
 * for comparing against Linux and Windows on equivalent hardware.
 *
 * Algorithm (identical to components/app-bench.in):
 *   count primes < 100000 by trial division against odd divisors only,
 *   with the 2 special case.
 *
 * Build (Linux):   gcc -O2 -o bench-primes docs/bench-primes.c
 * Build (Windows): cl /O2 bench-primes.c   (or: gcc -O2 on MinGW)
 * Run:             ./bench-primes
 */
#include <stdio.h>
#include <time.h>

static int is_prime(int n) {
    if (n < 2) return 0;
    if (n == 2) return 1;
    if ((n & 1) == 0) return 0;
    for (int d = 3; d * d <= n; d += 2)
        if (n % d == 0) return 0;
    return 1;
}

int main(void) {
    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);

    int count = 0;
    for (int n = 2; n < 100000; n++)
        if (is_prime(n)) count++;

    clock_gettime(CLOCK_MONOTONIC, &t1);
    double ms = (t1.tv_sec - t0.tv_sec) * 1000.0 + (t1.tv_nsec - t0.tv_nsec) / 1000000.0;

    printf("primes=%d time=%.1fms\n", count, ms);
    return count == 9592 ? 0 : 1;
}
