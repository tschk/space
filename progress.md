# Progress

## Status
In Progress

## Tasks
- [x] Register allocator: assign hot locals to R12–R15, skip trivial-arg push/pop

## Files Changed
- `in-cli/src/native_emit/x86_64_lower.rs` — register allocator, callee-saved regs, trivial-expr optimization

## Notes
All 743 compiler tests pass. Kernel boots with identical size (41KB).
