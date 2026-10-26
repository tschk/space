#!/usr/bin/env python3
"""Compile real SCI and reject mismatched protected-native packaging metadata."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_pack', root / 'scripts/pack-native-protected-sci.py')
pack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pack)
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--immutable-in', required=True)
p.add_argument('--paged-in', required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
out = a.out.resolve()
if out.exists() and any(out.iterdir()):
    p.error('--out must be new or empty')
out.mkdir(parents=True, exist_ok=True)
receipts = []
for immutable, compiler in [(True, a.immutable_in), (False, a.paged_in)]:
    for profile in ['default', 'lean', 'harden']:
        folder = out / (('immutable-' if immutable else 'paged-') + profile)
        folder.mkdir()
        artifact = folder / 'client.sci'
        with (folder / 'compile.log').open('w') as log:
            subprocess.run([compiler, 'compile', '--path', str(root / 'fixtures/native-protected/client.in'),
                            '--entry', 'native-entry', '--emit', 'sci', '--base', '0x60000000',
                            '--target', 'native', '--target-triple', 'x86_64-unknown-none',
                            '--profile', profile, '--out', str(artifact)], stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=180)
        raw = artifact.read_bytes()
        metadata = json.loads(artifact.with_suffix('.component-metadata.json').read_text())
        packed = pack.translate(raw, metadata, immutable)
        (folder / 'protected.sci').write_bytes(packed)
        refused = []

        def reject(name, edit_metadata=None, edit_image=None, rehash=False):
            data = bytearray(raw)
            meta = copy.deepcopy(metadata)
            if edit_metadata:
                edit_metadata(meta)
            if edit_image:
                edit_image(data)
            if rehash and not immutable:
                meta['sci_layout']['artifact_sha256'] = hashlib.sha256(data).hexdigest()
            try:
                pack.translate(data, meta, immutable)
            except (ValueError, TypeError):
                refused.append(name)
            else:
                raise AssertionError('accepted tamper: ' + name)

        for field, values in [('component', ['', ' ', None, 4, 'a\0b']),
                              ('target', ['native', None]), ('entry', ['other-entry', None]),
                              ('capabilities_required', [None, {}, [False]]),
                              ('capabilities_exported', [None, [], {}])]:
            for index, value in enumerate(values):
                reject(f'{field}-{index}', lambda meta, f=field, v=value: meta.__setitem__(f, v))
        reject('duplicate-capability', lambda meta: [meta[key].append(copy.deepcopy(meta[key][0]))
                                                    for key in ['capabilities_required', 'capabilities_exported']])
        for key in ['name', 'capability_type', 'args']:
            reject('capability-' + key, lambda meta, k=key: [meta[field][0].__setitem__(k, 'unknown')
                                                            for field in ['capabilities_required', 'capabilities_exported']])
        for offset, value in [(0, 0), (8, 0), (8, 7), (16, 0x60000048), (24, len(raw) - 1),
                              (32, 0), (32, 129), (40, len(raw)), (48, 129), (56, 0)]:
            reject(f'header-{offset}-{value}', edit_image=lambda data, o=offset, v=value: struct.pack_into('<Q', data, o, v), rehash=True)
        exports, export_off, imports, import_off = struct.unpack_from('<4Q', raw, 32)
        reject('export-name-pool', edit_image=lambda data: struct.pack_into('<Q', data, export_off, 0), rehash=True)
        reject('entry-export-offset', edit_image=lambda data: struct.pack_into('<Q', data, export_off + 8, len(raw)), rehash=True)
        if imports:
            site = struct.unpack_from('<Q', raw, import_off + 8)[0]
            reject('import-name-pool', edit_image=lambda data: struct.pack_into('<Q', data, import_off, 0), rehash=True)
            reject('import-site-range', edit_image=lambda data: struct.pack_into('<Q', data, import_off + 8, len(raw)), rehash=True)
            reject('import-instruction', edit_image=lambda data: data.__setitem__(64 + site, 0x90), rehash=True)
        if not immutable:
            for field in metadata['sci_layout']:
                if field == 'artifact_sha256':
                    reject('layout-hash', lambda meta: meta['sci_layout'].__setitem__(field, '0' * 64))
                else:
                    reject('layout-bool-' + field, lambda meta, f=field: meta['sci_layout'].__setitem__(f, True))
            for field in ['version', 'image_size', 'load_base', 'page_size', 'text_offset', 'text_size',
                          'data_offset', 'data_size', 'binding_offset', 'binding_size']:
                reject('layout-range-' + field, lambda meta, f=field: meta['sci_layout'].__setitem__(f, -1))
            for field in ['code_sections', 'data_sections']:
                reject(field + '-missing', lambda meta, f=field: meta.__setitem__(f, []))
                for item in ['name', 'flags', 'offset', 'size']:
                    reject(field + '-' + item, lambda meta, f=field, i=item: meta[f][0].__setitem__(i, 'bad'))
            reject('static-data-size', lambda meta: meta['memory'].__setitem__('static_data', 0))
            reject('static-data-bool', lambda meta: meta['memory'].__setitem__('static_data', True))
            reject('memory-missing', lambda meta: meta.__setitem__('memory', None))
            binding = metadata['sci_layout']['binding_offset']
            reject('binding-table-vs-layout', edit_image=lambda data: struct.pack_into('<Q', data, 40, binding + 8), rehash=True)
            reject('padding-not-zero', edit_image=lambda data: data.__setitem__(64 + metadata['sci_layout']['text_size'], 1), rehash=True)
            reject('unbound-image-byte', edit_image=lambda data: data.__setitem__(65, data[65] ^ 1))
        # Verify CLI failure preserves an existing output: malformed declarations cannot publish a partial artifact.
        invalid = copy.deepcopy(metadata)
        invalid['capabilities_exported'] = []
        (folder / 'invalid.json').write_text(json.dumps(invalid))
        destination = folder / 'sentinel.sci'
        destination.write_bytes(b'unchanged')
        result = subprocess.run(['python3', str(root / 'scripts/pack-native-protected-sci.py'), str(artifact),
                                 str(folder / 'invalid.json'), str(destination)] + (['--immutable-image'] if immutable else []),
                                capture_output=True, timeout=10)
        assert result.returncode != 0 and destination.read_bytes() == b'unchanged'
        receipts.append({'profile': 'immutable' if immutable else 'paged', 'compiler_profile': profile,
                         'compiler_sha256': hashlib.sha256(Path(compiler).read_bytes()).hexdigest(),
                         'raw_sha256': hashlib.sha256(raw).hexdigest(), 'packed_sha256': hashlib.sha256(packed).hexdigest(),
                         'refusals': refused, 'cli_output_preserved': True})
report = {'status': 'passed', 'actual_compiled_artifacts': len(receipts),
          'tamper_refusals': sum(len(item['refusals']) for item in receipts), 'artifacts': receipts}
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(f"PASS: {len(receipts)} actual artifacts, {report['tamper_refusals']} protected packaging refusals; {out}")
