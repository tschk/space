# Code Context — x86_64 Lowering & MIR Hook Point

## Files Retrieved

1. `inauguration/in-cli/src/native_emit/x86_64_lower.rs` (full file, 2446+ lines) — Core IR → x86_64 machine code lowering
2. `inauguration/in-cli/src/native_emit/x86_64.rs` (full file, 590 lines) — x86_64 instruction encoder helpers + CodeEmitter
3. `inauguration/in-cli/src/native_emit/lower.rs` (partial, ~1527+ lines) — AArch64 lowering (mirror of x86_64)
4. `inauguration/in-cli/src/native_emit/mod.rs` — module re-exports
5. `inauguration/in-cli/src/compiler/mir.rs` (full, ~145 lines) — Existing MIR type definitions (offset-deferred IR)
6. `inauguration/in-cli/src/compiler/mir_emit.rs` (full, ~117 lines) — MIR → machine code emitter (AArch64 only)
7. `inauguration/in-cli/src/native_emit/object.rs` — Native object emission (calls x86_64_lower::lower_module)
8. `inauguration/in-cli/src/main.rs` (cmd_emit_boot) — Boot image emission pipeline (parse → optimize → lower → sci_header)

## Key Code

### Entry point: `lower_module`

```rust
pub fn lower_module(module: &UnifiedModule, entry: &str) -> Result<X86_64CompileResult, String>
```

File: `x86_64_lower.rs:288`. Takes `UnifiedModule` + entry function name. Returns:

```rust
pub struct X86_64CompileResult {
    pub code: Vec<u8>,          // flat machine code bytes
    pub entry_offset: u32,      // offset of entry function
    pub exports: Vec<(String, u32)>,  // all function → offset
}
```

### Output format

`code: Vec<u8>` — flat x86_64 machine code. No relocation entries, no ELF/MachO wrapper. Pure raw bytes. Functions concatenated. Data section (string literals) appended after all functions. Call targets resolved via patching `call rel32` placeholders using `PendingCall` list.

### CodeEmitter

File: `x86_64.rs:38-90`. Simple byte accumulator:

```rust
pub struct CodeEmitter {
    pub bytes: Vec<u8>,
}
```

Methods: `emit_u8`, `emit_u16`, `emit_u32`, `emit_u64`, `emit_bytes`, `emit_insns`, `patch_u32`, `patch_u8`. No instruction abstraction — raw byte pushing. The x86_64 module provides instruction encoder functions (e.g., `prologue()`, `push_r(reg)`, `load_i64(reg, val)`, `mov_rr(dst, src)`, `call_rel32(off)`) that return `Vec<u8>`.

### Data flow

```
.in source
  → in_lang_parse::parse_in_source / parse_in_library_file
    → UnifiedModule (Core IR: Decl enum with Function, Struct, Global, Component variants)
      → [optional] core_opt::optimize (inlining, const folding)
        → x86_64_lower::lower_module
          → collect_functions → collect_structs → collect_globals → collect_string_literals
          → for each function: lower_function (emits prologue, allocs stack frame, lowers body)
            → lower_stmt (Stmt::Let/Return/If/Loop/Match/Assign/Call/Throw/Try)
              → lower_expr_into (Expr::IntLit/Ident/Binary/Call/Field/Index...)
          → resolve pending calls (patch call rel32, string literal abs64, function address refs)
          → append string data section
          → X86_64CompileResult { code, entry_offset, exports }
```

### How lowering works per function

1. **`lower_function`** (line ~565):
   - `LowerCtx::new` — allocates stack slots for params (first 6 in regs spilled to stack)
   - `alloc_declared_locals` — pre-allocate stack slots for `let` bindings found in body
   - Reserve error flag/value offsets for Throw/Try (24 bytes)
   - Emit prologue: `push rbp; mov rbp, rsp` (+ interrupt variant saves all GPRs)
   - Emit `sub rsp, frame_size` to allocate frame
   - Push register params to stack → zero-fill frame via `rep stosq` → pop and store params
   - Lower each statement in body
   - If no explicit return → emit default epilogue

2. **`lower_stmt`** (line ~705) — match on `Stmt` variants:
   - `Return` → evaluate expr into RAX, emit epilogue, set `emitted_return = true`
   - `Let` → allocate local, evaluate expr into RAX, store to stack slot
   - `Assign` → if global → `mov [abs], rax`; else load expr into RAX, store to local
   - `If` → `cmp rax, 0` + `jcc_near(je)` to else branch + `jmp_rel32` past else
   - `Loop` → forward/backward jumps with `jcc_near`/`jmp_rel8`/`jmp_rel32`
   - `Match` → cmp + jne chains for integer arms, default body fallthrough
   - `Throw` → store RAX to error_value slot, set error flag byte to 1
   - `Try` → save/clear error flag, lower body, check flag → jne handler → restore flag
   - `Call` (Expr) → push registers for arg preservation, evaluate args into RDI/RSI/etc, emit `call_rel32(0)` placeholder, stack cleanup

3. **`lower_expr_into`** (line ~983) — match on `Expr` variants, emit into target register:
   - `IntLit` → `mov ri64(target, value)`
   - `BoolLit` → `mov ri64(target, 0/1)`
   - `Ident` → global: `mov rax, [abs addr]`; function ptr: placeholder `mov ri64(target, 0xDEADBEEF)` patched later; local: `ldr64(target, stack_offset)`
   - `Binary` → eval lhs → push; eval rhs; pop → RBX; emit op-specific (add/sub/mul/cmp+setcc)
   - `Call` → intrinsics handled inline (hlt, outb, inb, outl, inl, cli, sti, load8/store8/etc, read_cr2/3, invlpg, lidt, invoke/invoke1/invoke2); regular calls → push arg regs, emit `call_rel32(0)`, push PendingCall
   - `StructInit` → eval each field, str64 to slot
   - `Field` → ldr64 from struct's field offset
   - `Unary` → neg, not, deref (`mov rax, [rax]`), address-of (no-op)
   - `Index` → base + index*8 → `mov rax, [addr]`
   - `StringLit` → placeholder `mov ri64(target, 0xDEADBEEF)`, PendingCall with `@str_` prefix

### Post-function resolution

After all functions lowered, `lower_module` (line ~325):
- Resolves `PendingCall` entries:
  - `@addr_<fn>` → write absolute function address at site (KERNEL_BASE + offset)
  - `@str_<content>` → collect, patch after string data appended
  - Regular call → `patch_u32(site+1, target_offset - site - 5)`
- Append string data section with 8-byte alignment

### Callers of x86_64_lower::lower_module

1. **`owned_compile.rs:579`** — JIT compilation (host x86_64), wraps result into `LoweredModule`
2. **`main.rs:1671`** — `cmd_emit_boot`: parse → optimize → lower → wrap in SCI header + trampoline → flat boot image
3. **`native_emit/object.rs:16`** — Object file emission (`X86_64_TRIPLE` / `x86_64-unknown-none`)

### Existing MIR layer

There is already a MIR (Machine IR) module at `compiler/mir.rs` and `compiler/mir_emit.rs`:

**`mir.rs`** defines:
- `MirOp` enum with ~30 opcodes (Mov, Load, Store, Lea, Add, Sub, ..., Call, Ret, Jmp, Jz, Cmp, Push, Pop, Prologue, Epilogue, etc.)
- `MirOperand` enum: Reg(VReg), Imm(i64), Mem{base, offset}, Label, Global
- `MirInst { op, operands, offset }`
- `MirFunction { name, instructions, vreg_count, frame_size }`
- `MirModule { functions, rodata, rodata_relocs }`

**`mir_emit.rs`** implements a minimal AArch64-only emitter:
- `emit_jit(module) -> (Vec<u8>, Vec<(name, start, size)>)`
- `load_jit(module, rt) -> Result`
- Only implements Mov, Add, Sub, Ret, Nop, Comment — other ops emit `brk #0`

Key insight: This MIR exists but is **not connected to the x86_64 lowering pipeline**. It's only used for AArch64 JIT. The x86_64 pipeline goes directly from Core IR → raw machine code.

## Architecture

```
┌─────────────────────────────────────────────────┐
│ .in source                                      │
└──────────────┬──────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────┐
│ in_lang_parse → UnifiedModule (Core IR)         │
│   Decl::Function, Struct, Global, Component     │
│   Stmt::Let/Assign/Return/If/Loop/Match/Call/   │
│         Throw/Try/Expr/Break                    │
│   Expr::IntLit/Ident/Binary/Call/Field/Index/   │
│         StructInit/StringLit/Unary/Closure      │
└──────────────┬──────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────┐
│ [optional] core_opt::optimize                    │
│   inlining, constant folding                    │
└──────────────┬──────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────┐
│ x86_64_lower::lower_module                      │
│   ↓                                             │
│   collect_functions / structs / globals / strings│
│   ↓                                             │
│   for each function: lower_function             │
│     → CodeEmitter (Vec<u8> byte accumulator)    │
│     → emits raw x86_64 bytes via helpers in     │
│       native_emit::x86_64 (prologue, push_r,    │
│       mov_rr, ldr64, str64, call_rel32, etc.)  │
│     → PendingCall list for deferred fixups      │
│   ↓                                             │
│   resolve pending calls (patch offsets)         │
│   ↓                                             │
│   append string data section                    │
│   ↓                                             │
│   X86_64CompileResult { code: Vec<u8>, ... }    │
└──────────────┬──────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────┐
│ Consumers:                                      │
│ 1. owned_compile.rs (JIT, wraps in LoweredModule)│
│ 2. main.rs cmd_emit_boot (SCI header + image)   │
│ 3. native_emit/object.rs (ELF/PE/archive)       │
└─────────────────────────────────────────────────┘
```

## Where MIR Would Hook In

**The natural insertion point is between Core IR (`UnifiedModule`) and `x86_64_lower::lower_module`.**

### Option A: Core IR → MIR → x86_64 emit (recommended)

```
UnifiedModule → mir::lower_core_to_mir() → MirModule → x86_64_mir_emit() → Vec<u8>
```

A new module `lower_core.rs` (or `x86_64_lower_mir.rs`) would:
1. Walk the `UnifiedModule` declarations
2. For each function, translate `[Stmt]` → `Vec<MirInst>` with virtual registers
3. Perform register allocation (map VReg → physical x86_64 reg or stack slot)
4. Emit MIR instructions → x86_64 encoding via the existing `CodeEmitter`

The existing `compiler/mir.rs` types are designed for this but currently only used for AArch64 JIT. The `MirOp` enum already covers x86_64 ops. Missing pieces:
- x86_64-specific opcodes (e.g., `IDiv`, `IMul` with specific flag semantics, `Shl`/`Shr` with `cl` register constraint)
- Register allocator (current code skips this, uses RAX/RBX/RCX/RDI/RSI directly)
- x86_64 MIR emitter (exists for AArch64 in `mir_emit.rs`)

### Option B: Rewrite x86_64_lower.rs to emit MIR first

Could restructure the existing `lower_stmt`/`lower_expr_into` to emit `MirInst` instead of calling `emitter.emit_insns()` directly, then add a second pass that encodes MIR → bytes. This gives relocation and JIT benefits.

### Option C: MIR as an optional pass

Insert MIR as an optional optimization/verification step:
```
UnifiedModule → x86_64_lower (current)
                ↕ mir_lower + mir_emit (new path, flag-gated)
```

### Constraints for MIR insertion

1. **Output contract**: `Vec<u8>` of raw x86_64 code + entry_offset + exports — MIR emit must produce same contract
2. **Pending calls**: Currently resolved in `lower_module` via `PendingCall` list. MIR would need equivalent relocation mechanism (`MirRelocation` already exists in `mir.rs`)
3. **String literals**: Appended after code section. MIR would need `.rodata` support
4. **Function address references**: Used for first-class function pointers. MIR `MirOperand::Global` covers this
5. **Callers expect `X86_64CompileResult`**: A MIR path must produce the same type (or convert)

## Start Here

Open `inauguration/in-cli/src/native_emit/x86_64_lower.rs`. Start at `lower_module` (line 288) and trace through `lower_function` (line 565), then `lower_stmt` (line 705), then `lower_expr_into` (line 983). These three functions contain the entire Core IR → x86_64 translation logic, ~1800 lines of the 2446-line file.

Then open `inauguration/in-cli/src/compiler/mir.rs` to understand the existing MIR type definitions that a new lowering path would target.

## Risks & Open Questions

- **Reg alloc**: Current x86_64 lower uses physical registers directly (RAX, RBX, RCX, RDI, RSI). MIR uses virtual registers → needs register allocator before emit. Current `mir_emit.rs` uses vreg numbers directly as AArch64 register numbers (no alloc).
- **Stack frame**: Current code calculates exact offsets during lowering. MIR would need frame layout pass before final emit.
- **Call ABI**: System V AMD64 calling convention is baked into the current lower. MIR would need spec-compliant arg lowering.
- **PendingCall resolution**: Currently a simple Vec of (site, target) pairs. MIR relocation system would need to match this capability.
- **The existing MIR is AArch64-only and incomplete** (only 5 opcodes implemented). Extending it to x86_64 is non-trivial but the type system supports it.
