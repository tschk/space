#!/usr/bin/env python3
"""Compile real SCI declarations and verify exact named canvas packaging policy."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('gui_packer', root / 'scripts/pack-gui-sci.py')
packer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packer)
constants = {name: int(value, 0) for name, value in re.findall(
    r'^const (SCI-CANVAS-[A-Z-]+) = (0x[0-9a-fA-F]+|[0-9]+)$',
    (root / 'protocol/gui-canvas.in').read_text(), re.MULTILINE)}
assert tuple(constants['SCI-CANVAS-' + name] for name in
             ('MAGIC', 'VERSION', 'WIDTH', 'HEIGHT', 'STRIDE', 'BYTES', 'FLAGS')) + (0,) == packer.CANVAS
assert constants['SCI-CANVAS-TRAILER-BYTES'] == struct.calcsize('<8Q')


def refused(image, metadata):
    try:
        packer.translate(image, metadata)
    except ValueError:
        return
    raise AssertionError('invalid GUI declaration/image accepted')


with tempfile.TemporaryDirectory(prefix='space-gui-canvas-policy-') as directory:
    directory = Path(directory)
    for name in ('GuiCalc', 'GuiEditor', 'GuiWindowCalc', 'GuiWindowEditor'):
        window = 'Window' in name
        editor = name.endswith('Editor')
        display = 'present, window' if window else 'present'
        storage = 'capability storage: GuiNoteFile(read, write)' if editor else ''
        source = f'''package space.app.gui
interface GuiMemory{{fn map()->void}}
interface GuiDisplay{{
 fn present()->void
 fn window()->void
}}
interface GuiNoteFile{{
 fn read(buffer:Int,maximum:Int)->Int
 fn write(buffer:Int,size:Int)->Int
}}
component {name}{{
 target "x86_64-unknown-none"
 capability memory: GuiMemory(map)
 capability display: GuiDisplay({display})
 {storage}
}}
fn client-entry(info:Int)->Int{{return 42;}}
'''
        path, image = directory / (name + '.in'), directory / (name + '.sci')
        path.write_text(source)
        result = subprocess.run([a.compiler, 'compile', '--path', str(path), '--entry', 'client-entry',
                                 '--target', 'native', '--target-triple', 'x86_64-unknown-none',
                                 '--emit', 'sci', '--base', '0x48000000', '--out', str(image)],
                                capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, (result.stdout, result.stderr)
        original = image.read_bytes()
        metadata = json.loads(image.with_suffix('.component-metadata.json').read_text())
        packed = packer.translate(original, metadata)
        assert struct.unpack_from('<Q', packed, 8)[0] == (52 if editor else 20)
        assert struct.unpack_from('<Q', packed, 24)[0] == len(packed)
        assert len(packed) == len(original) + (64 if window else 0)
        assert packed[64:len(original)] == original[64:]
        if window:
            assert struct.unpack_from('<8Q', packed, len(packed) - 64) == packer.CANVAS
        refused(packed, metadata)  # No double packaging/implicit mask widening.
        for field, value in (('component', 'space.app.gui/Other'), ('entry', 'other'), ('target', 'other')):
            invalid = copy.deepcopy(metadata)
            invalid[field] = value
            refused(original, invalid)
        invalid = copy.deepcopy(metadata)
        invalid['capabilities_required'][1]['args'].append('arbitrary_pool')
        invalid['capabilities_exported'] = copy.deepcopy(invalid['capabilities_required'])
        refused(original, invalid)
        invalid = copy.deepcopy(metadata)
        invalid['capabilities_required'][1]['args'] = ['present'] if window else ['present', 'window']
        invalid['capabilities_exported'] = copy.deepcopy(invalid['capabilities_required'])
        refused(original, invalid)
        invalid = bytearray(original)
        struct.pack_into('<Q', invalid, 24, len(invalid) + 1)
        refused(invalid, metadata)
        print(f'PASS {name}: actual SCI artifact exact grants/profile; unknown identity/target/entry, widened/mismatched declarations, bad extent and repeated packaging refused')
