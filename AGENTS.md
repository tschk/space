# AGENTS

Space is a separate OS repository. Keep Space-specific source, examples, schemas, boot plans, and component contracts here.

## Relationship To Inauguration

Use `../inauguration` as the compiler/toolchain repository. Do not add Space-branded targets, Space product policy, or Space-only source trees to `../inauguration`.

Allowed Inauguration work:

- generic freestanding target support such as `x86_64-unknown-none`
- generic SCI or component-image emitters when they are not Space-branded
- generic capability/interface/object-schema metadata extraction from `.in`
- generic x86_64 native lowering, object emission, relocations, linker support, and QEMU harnesses
- generic compiler tests under `in-cli`, `scripts`, `docs`, or `apps` when they are not named after Space

Space-owned work:

- Space design notes
- Space component examples
- Space SCI profile and loader policy
- Space nanokernel object/capability vocabulary
- Space boot-image layout and QEMU expectations
- Space-specific runtime services and component graphs

## Workflow

When a Space task needs compiler work:

1. Update the Space plan or example first.
2. Implement the generic compiler capability in `../inauguration`.
3. Verify the generic compiler behavior with Inauguration tests.
4. Return to Space and update the Space-facing plan or artifact.

Do not make Inauguration depend on this repository.

## Required Checks

For Space-only documentation or examples:

```bash
git diff --check
```

For Inauguration compiler changes, run from `../inauguration`:

```bash
cargo fmt --check --manifest-path in-cli/Cargo.toml
cargo check -q --manifest-path in-cli/Cargo.toml
bash scripts/check-target-matrix.sh
in update
in test --owned-native
in test
git diff --check
```

If a change only touches a narrow compiler area, run the focused tests first, then the full gates before push.

## Boundaries

- Do not claim the kernel is implemented in `.in` until QEMU enters `.in`-compiled code.
- Do not claim SCI is implemented until there is an emitted artifact and loader-side validation.
- Do not use ELF as the native Space contract. ELF may be an intermediate or boot substrate only.
- Do not add POSIX compatibility before the native component model boots.
- Do not add placeholders or TODO prose as a substitute for an executable plan.
