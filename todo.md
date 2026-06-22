# Space TODO

## Remaining Ponytail Audit Items

These items were deferred due to Inauguration 0.3.0 .in syntax compatibility issue:

- Inline determinism module into kernel-root.in - Currently separate due to compiler syntax limitations
- Simplify slot-limited object graph edges - Current 2-slot limitation is documented and functional for requirements

## Inauguration Compatibility

Inauguration 0.3.0 introduced breaking change with .in syntax:
```
.in: unknown top-level syntax `fn`
```

This affects both original and simplified Space code. The 0.3.0 release focused on:
- Zig eval fixes
- F# bytecode compilation  
- Go module checksum verification
- pip install behavior
- Allowlist updates

None of these changes should have affected .in parsing, suggesting an unintended regression that needs to be resolved before remaining simplifications can be tested.
