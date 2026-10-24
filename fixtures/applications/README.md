# Real application corpus

This directory contains provenance and scenario manifests, not executable
payloads. Keep acquired binaries, build outputs and test evidence outside git.
The active [full goal](../../docs/compatibility-coverage-goal.md) requires actual
protected execution and workflows inside Space before application coverage is
counted. A fixture, a host reference run and a loader refusal have separate status.

The separate `busybox-vi-1.36.1.json` pins the upstream static vi build, without
replacing the existing CLI/xargs artifacts. [Its current workload](../../docs/linux-vi-workload.md)
passes EX edit/save and separate-process reopen on Space; interactive terminal
input remains open. Build using `scripts/build-busybox-corpus.py --manifest
fixtures/applications/busybox-vi-1.36.1.json --out <new-directory>`. The main lab
accepts `--busybox-vi <pinned-binary>` or the distinct `busybox-vi` cache entry.

## jq 1.8.1: original release binaries

`jq-1.8.1.json` pins the upstream x86_64 Linux ELF, macOS Mach-O and Windows PE
release bytes against upstream SHA256 values. The common target workflow is
`jq -nc '[range(10)] | add'`, with stdout `45\n` and exit 0. The runner verifies
hashes and sizes before executing the Linux host reference or admitting any file
to the QEMU probe. No binary is repackaged to fit the trusted fixture format.

```sh
python3 scripts/check-real-app-admission.py \
  --in /workspace/inauguration/in-cli/target/release/in \
  --apps-dir /workspace/real-apps/jq-1.8.1 \
  --out /tmp/space-real-jq-run --download
```

Each original image is supplied in full to its actual Space validation function,
with its true size, in two fresh QEMU boots. Validation happens before ordinary
kernel heap initialization can overwrite the loaded payload. The probe never
calls the foreign application entry point. It verifies the kernel subsequently
reaches its shell, retains serial/compiler/QEMU logs and emits `report.json`.

The command returns **1** for blocked, admitted-but-not-executed or test-error
applications. Correct refusal may pass the admission probe while application
status remains blocked. A future admitted payload must still run through a
protected process scenario before the application can pass. Host Linux jq output
is an independently labeled oracle; it does not count as execution inside Space.

Missing/corrupt artifacts remain test errors. Existing evidence directories are
refused so results cannot be silently overwritten. Acquisition checks upstream
artifacts but does not establish a redistribution decision: inspect jq and its
bundled dependency licenses before distributing compiled binaries.

## Native Space applications

Use `scripts/check-native-applications.py --image <standard.bin> --out <new-dir>`
to drive shipped SCI applications in QEMU, including calculator interactions,
notes save/reopen, cross-app file checks and application lifecycle. The report
records native application scenarios separately from foreign compatibility.

Build a standard image explicitly, then test it:

```sh
INAUGURATION_DIR=/workspace/inauguration \
  BUILD_DIR=/tmp/space-native-standard bash scripts/build-images.sh --variant standard
python3 scripts/check-native-applications.py \
  --image /tmp/space-native-standard/standard.bin --out /tmp/space-native-workflows
```

Retain the build command, compiler/source identities and image hash alongside
results. `scripts/build-images.sh` defaults to both standard and minimal images;
`--variant standard` or `--variant minimal` requests a narrower build explicitly.
A targeted build does not certify the other variant. Failure in the full/default
build remains a build failure even if another image was written successfully.
Testing that existing standard image must not turn the full build green.

The target corpus expands to the named CLI and GUI matrix in the full goal.
Pin artifact/build provenance and concrete expected outputs before adding a new
row, and preserve unsupported cases as blockers until their actual workflows run.
