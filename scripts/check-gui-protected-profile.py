#!/usr/bin/env python3
"""Compile policy fixtures and check explicit protected GUI packaging, not execution."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--in', dest='compiler', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
out = args.out.resolve()
if out.exists() and any(out.iterdir()):
    parser.error('--out must be new or empty')
out.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location('gui_packer', ROOT / 'scripts/pack-gui-sci.py')
packer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packer)
report = {'status': 'running', 'scope': 'actual compiler artifacts and packaging policy; no protected GUI execution claim',
          'compiler': str(args.compiler.resolve()),
          'compiler_sha256': hashlib.sha256(args.compiler.read_bytes()).hexdigest(),
          'sources': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in (ROOT / 'scripts/pack-gui-sci.py', Path(__file__),
                                   ROOT / 'protocol/gui-canvas.in', ROOT / 'protocol/native-protected.in')},
          'artifacts': [], 'refusals': []}


def refused(label, image, metadata, protected=True):
    original = bytes(image)
    declarations = copy.deepcopy(metadata)
    try:
        packer.translate(image, metadata, protected)
    except ValueError:
        assert bytes(image) == original and metadata == declarations
        report['refusals'].append(label)
        return
    raise AssertionError(f'invalid protected GUI accepted: {label}')


def changed(image, metadata, mutate):
    """Forged matching checksum is insufficient to bypass structural policy."""
    raw, meta = bytearray(image), copy.deepcopy(metadata)
    mutate(raw, meta)
    meta['sci_layout']['artifact_sha256'] = hashlib.sha256(raw).hexdigest()
    return raw, meta


for profile in ('default', 'lean', 'harden'):
    for editor in (False, True):
        name = 'GuiProtectedWindowEditor' if editor else 'GuiProtectedWindowCalc'
        directory = out / (profile + '-' + name)
        directory.mkdir()
        storage = 'capability storage: GuiNoteFile(read, write)' if editor else ''
        note_imports = '''interrupt fn gui-note-read(buffer:Int,maximum:Int)->Int{}
interrupt fn gui-note-write(buffer:Int,size:Int)->Int{}''' if editor else ''
        note_calls = 'result += gui-note-read(0x69000000,8); result += gui-note-write(0x69000000,0);' if editor else ''
        # This bounded artifact policy fixture is not a product GUI client.
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
 capability display: GuiDisplay(present, window)
 {storage}
}}
interrupt fn chan-page-send-frame(endpoint:Int,object:Int,opcode:Int,arg0:Int,arg1:Int)->Int{{}}
interrupt fn chan-page-recv-frame(endpoint:Int,message:Int)->Int{{}}
{note_imports}
var counter:Int=40;
fn client-entry(info:Int)->Int{{
 counter += 1;
 let result = chan-page-send-frame(0x70000000,1,0,0,0);
 result += chan-page-recv-frame(0x70000000,0x69000100);
 {note_calls}
 return counter + result;
}}
'''
        path, artifact = directory / 'policy-fixture.in', directory / 'raw.sci'
        path.write_text(source)
        result = subprocess.run([str(args.compiler.resolve()), 'compile', '--path', str(path),
                                 '--entry', 'client-entry', '--target', 'native', '--target-triple',
                                 'x86_64-unknown-none', '--emit', 'sci', '--base', hex(packer.PROTECTED_BASE),
                                 '--profile', profile, '--out', str(artifact), '--json'],
                                capture_output=True, text=True, timeout=30)
        (directory / 'compile.json').write_text(result.stdout)
        (directory / 'compile.stderr').write_text(result.stderr)
        assert result.returncode == 0 and json.loads(result.stdout)['success'], (result.stdout, result.stderr)
        raw = artifact.read_bytes()
        metadata = json.loads(artifact.with_suffix('.component-metadata.json').read_text())
        layout = metadata['sci_layout']
        original = bytearray(raw)
        before = copy.deepcopy(metadata)
        packed = packer.translate(original, metadata, True)
        assert bytes(original) == raw and metadata == before
        assert len(packed) == len(raw) + 128
        assert struct.unpack_from('<Q', packed, 8)[0] == (52 if editor else 20)
        assert struct.unpack_from('<Q', packed, 24)[0] == len(packed)
        assert packed[:8] == raw[:8] and packed[16:24] == raw[16:24] and packed[32:len(raw)] == raw[32:]
        assert struct.unpack_from('<8Q', packed, len(raw)) == packer.CANVAS
        assert struct.unpack_from('<8Q', packed, len(raw) + 64) == (
            packer.NATIVE_PROTECTED_MAGIC, 1, 3, len(raw), layout['text_size'],
            layout['data_offset'], layout['data_size'], 0)
        destination = directory / 'protected.sci'
        destination.write_bytes(packed)
        report['artifacts'].append({'name': name, 'profile': profile,
                                    'raw_sha256': hashlib.sha256(raw).hexdigest(),
                                    'packed_sha256': hashlib.sha256(packed).hexdigest(),
                                    'raw_size': len(raw), 'packed_size': len(packed)})
        prefix = profile + '/' + name + '/'
        refused(prefix + 'implicit-protected-mode', raw, metadata, False)
        refused(prefix + 'double-pack', packed, metadata)
        for field, value in (('component', 'space.app.gui/GuiWindowCalc'), ('entry', 'main'), ('target', 'other')):
            invalid = copy.deepcopy(metadata)
            invalid[field] = value
            refused(prefix + field, raw, invalid)
        for field, value in (('version', True), ('text_size', -1), ('data_offset', layout['data_offset'] + 1),
                             ('data_size', len(raw)), ('binding_offset', layout['binding_offset'] + 1),
                             ('binding_size', layout['binding_size'] + 1), ('load_base', 0x48000000),
                             ('artifact_sha256', None)):
            invalid = copy.deepcopy(metadata)
            invalid['sci_layout'][field] = value
            refused(prefix + 'layout-' + field, raw, invalid)
        for field in ('sci_layout', 'code_sections', 'data_sections', 'memory'):
            invalid = copy.deepcopy(metadata)
            invalid.pop(field)
            refused(prefix + 'missing-' + field, raw, invalid)
        invalid = copy.deepcopy(metadata)
        invalid['capabilities_required'][1]['args'].append('arbitrary_pool')
        invalid['capabilities_exported'] = copy.deepcopy(invalid['capabilities_required'])
        refused(prefix + 'authority-widening', raw, invalid)
        invalid = bytearray(raw)
        invalid[layout['data_offset']] ^= 1
        refused(prefix + 'modified-raw-data', invalid, metadata)
        refused(prefix + 'wrong-entry-bytes', *changed(raw, metadata,
            lambda image, meta: struct.pack_into('<Q', image, 16, packer.PROTECTED_BASE + 65)))
        imports = struct.unpack_from('<Q', raw, 56)[0]
        name_offset, site = struct.unpack_from('<2Q', raw, imports)
        refused(prefix + 'import-outside-text', *changed(raw, metadata,
            lambda image, meta: struct.pack_into('<Q', image, imports + 8, layout['data_offset'])))
        refused(prefix + 'already-patched-import', *changed(raw, metadata,
            lambda image, meta: struct.pack_into('<i', image, 64 + site + 1, 1)))
        refused(prefix + 'unsafe-import-even-with-matching-sha', *changed(raw, metadata,
            lambda image, meta: image.__setitem__(slice(name_offset, name_offset + 5), b'out8\0')))
        if not editor:
            refused(prefix + 'storage-import-without-storage', *changed(raw, metadata,
                lambda image, meta: image.__setitem__(slice(name_offset, name_offset + 14), b'gui-note-read\0')))
        # A canvas or execution descriptor is never accepted as compiler bytes.
        extra = raw + struct.pack('<8Q', *packer.CANVAS)
        refused(prefix + 'canvas-appended-before-sha-validation', extra, metadata)

report['status'] = 'pass'
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(f"PASS protected GUI packaging: six actual SCI artifacts, {len(report['refusals'])} refusal controls; no execution claim")
