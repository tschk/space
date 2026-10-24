# Pinned mature terminal parser data

This directory contains the original VTE 0.13.1 state/action declarations and
transition-table rules at commit `89c12df969145ffb5084d1122627d7292c2c638f`.
The MIT option is selected and its complete notice is preserved. Provenance
records exact source hashes. This introduces an explicitly licensed dependency;
the earlier source-review-only checkpoint remains historical.

`scripts/build-terminal-vt-table.py` generates 4,096 transition bytes as compact
native `.in` data. It can compare every byte with a dump evaluated by the
unmodified upstream Rust macro. No host Rust runtime is used by Space. State
transitions alone are not a screen model, surface, text renderer or full VTE port.
The current 0.15 parser was also reviewed; this earlier table form makes the
exact finite native transition data independently reproducible while avoiding
an invented escape-state machine or an unsupported Rust runtime substitution.
