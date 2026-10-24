# Actual native application checks

`scripts/check-native-applications.py` drives the shipped applications through
serial input in an actual QEMU boot. It exercises calculator arithmetic and
error recovery, notes edit/save/reopen, checksum verification against a
host-computed CRC32, hex viewing, file creation/readback/deletion, manual output,
clock, sysinfo, sysmon, benchmark results and unknown-application refusal.
These are native Space runtime components; this gate does not certify foreign
ELF, Mach-O or PE compatibility or CPL3 isolation for `runapp`.

```sh
python3 scripts/check-native-applications.py --image /path/to/standard.bin --out /tmp/apps
python3 scripts/stress-native-applications.py --image /path/to/standard.bin --out /tmp/apps-stress --runs 10
```

Every stress iteration starts a fresh VM and retains its report and complete
serial output. Inputs are traced as exact bytes, receive offsets and elapsed
time. Failures retain the last awaited marker and render state. The notes check
verifies complete ANSI redraws, including all 22 rows, the status bar and cursor,
as well as typed text, saved file bytes, reopen and CRC32. A malformed redraw
retains `failed-render-actual.bin` and `failed-render-expected.bin` for comparison.
An earlier successful close cannot let the test continue typing shell commands
into a subsequently reopened editor that is still active.

## Notes UART repair, 2026-10-24

The editor previously sent terminal bytes with raw `outb` calls. Its render loop
could write while the UART transmit holding register was busy, dropping text
and parts of ANSI control sequences. Waiting for a text prefix alone frequently
missed damage elsewhere in the frame. Five fresh baseline boots passed that
older check; the complete redraw check exposed corrupt output in all five
fresh baseline boots, including the initial empty screen before any editor key
was sent. One captured frame had 382 bytes rather than the expected 409, with
parts of rows 14 and 15 missing.

The editor now polls the UART line-status transmit-ready bit before every
terminal byte, including CRLF, matching the kernel and shared library's existing
serial transport behavior. The application remains responsible for its terminal
presentation; no host delays or relaxed output assertions compensate for the
fault. Reports retain both baseline failures and fresh results:

- Original prefix check: `/tmp/space-notes-stress-baseline/report.json`.
- Full redraw baseline failures: `/tmp/space-notes-stress-baseline-complete/report.json`.
- Fixed image: 10/10 fresh boots, 110/110 application scenarios, with complete
  redraw and all application workflows:
  `/tmp/space-notes-stress-fixed-cursor-correct/report.json`.

The first stronger fixed-image run used an incorrect test expectation that a
reopened editor kept its previous cursor column; the editor resets to column
zero. That harness failure remains at `/tmp/space-notes-stress-fixed/`. The
corrected check continues to require identical saved content and exact redraw
bytes with the actual documented cursor position.
