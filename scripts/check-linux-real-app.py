#!/usr/bin/env python3
"""Compatibility entry point for the shared Linux application corpus gate."""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).with_name("check-linux-corpus.py")), run_name="__main__")
