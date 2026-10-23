# Coherent native RTC time

The native `Time` service reads actual CMOS RTC ports and returns whole Unix
seconds in a declared UTC profile. Its source is nondeterministic: a hardware
clock is an external input. The service does not provide a high resolution
monotonic counter, time-zone conversion, leap-second representation or a
Windows FILETIME/QPC implementation.

A read accepts two identical complete samples, with update-in-progress clear
before and after each. At most256 attempts occur in one call. Busy or changing
hardware returns `-1`, preserving every last validated formatted field. This
is a bounded service refusal; callers must handle transient unavailability.
The shell time formatter prints an unavailable diagnostic instead of presenting
stale fields as a new sample. RTC SET/setup mode also refuses.

BCD digits, binary values,12/24-hour encoding, AM/PM, month/day/leap-year and
century fields are validated before publishing a timestamp. Supported complete
years are1970..9999. An absent century register (`0` or `0xff`) uses the explicit
1980..2079 window. Gregorian2000 is leap;2100 is not. Unix epoch zero is valid.
The existing native `clock` application has its own older direct-port reader;
these tests do not establish that its sampling contract has been upgraded.

`check-time-service.py` executes the unchanged owning functions under each
compiler profile against independently calculated Python UTC calendar values.
It includes53 calendar cases plus stuck UIP, UIP beginning mid-read, changing
samples/mode and a year-boundary retry. Failure must preserve all previously
published fields. The original implementation fails the independent stuck-UIP
control with result5001; the fixed owner passes all three profiles.

`check-time-rtc.py` compiles a small native hardware bootstrap using the same
service source and performs four actual QEMU boots with pinned UTC clocks:
1970 epoch,2000 leap rollover,2100 non-leap rollover and2026 year rollover. It
checks native timestamps and formatted fields against an independent host
calendar, observes at least two seconds of RTC progress, and writes RTC SET
mode to prove refusal and state preservation. It accepts bounded transient
unavailable reads while checking they never publish inconsistent state.
No host clock query supplies the guest result.

Fresh receipts with frozen Inauguration0.9.324:

- `/tmp/space-time-service-final/report.json`:53 calendar and5 cycle cases pass
  in default/lean/harden.
- `/tmp/space-time-uip-old-control/report.json`: original source fails5001.
- `/tmp/space-time-uip-fixed/report.json`: fixed source passes the isolated UIP
  case in all three profiles.
- `/tmp/space-time-rtc-fourth/report.json`:four actual RTC boots pass with the
  source unchanged. Earlier harness attempts retained a subtraction-token
  compile error and an incorrect assumption that every read during an RTC
  update should succeed; those failures remain separate from the final proof.

```sh
python3 scripts/check-time-service.py --in /path/to/in --out /new/model-output
python3 scripts/check-time-rtc.py --in /path/to/in --out /new/hardware-output
```
