#!/usr/bin/env python3
"""Inspect PE32+ dependency contracts without executing or modifying its bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def inspect(path):
    data = Path(path).read_bytes()
    def u16(at): return struct.unpack_from('<H', data, at)[0]
    def u32(at): return struct.unpack_from('<I', data, at)[0]
    def u64(at): return struct.unpack_from('<Q', data, at)[0]
    assert data[:2] == b'MZ'
    pe = u32(60)
    assert data[pe:pe+4] == b'PE\0\0' and u16(pe+4) == 0x8664
    opt = pe+24
    assert u16(opt) == 0x20b and u16(pe+20) >= 240
    sections=[]
    for i in range(u16(pe+6)):
        at=opt+u16(pe+20)+i*40
        sections.append(dict(name=data[at:at+8].rstrip(b'\0').decode('ascii'),virtual=u32(at+8),rva=u32(at+12),raw_bytes=u32(at+16),raw_offset=u32(at+20),flags=hex(u32(at+36))))
    def offset(rva,count):
        for s in sections:
            delta=rva-s['rva']
            if 0 <= delta <= s['raw_bytes'] and count <= s['raw_bytes']-delta:
                at=s['raw_offset']+delta
                assert at+count <= len(data)
                return at
        raise ValueError(f'not file backed: {rva:#x}+{count}')
    def string(rva):
        at=offset(rva,1)
        end=data.index(0,at, min(at+4096,len(data)))
        offset(rva,end-at+1)
        return data[at:end].decode('ascii')
    dirs={str(i):dict(rva=u32(opt+112+i*8),size=u32(opt+116+i*8)) for i in range(16) if u64(opt+112+i*8)}
    imports={}
    if '1' in dirs:
        d=dirs['1']; found=False
        for i in range(min(d['size']//20,256)):
            at=offset(d['rva']+i*20,20)
            if data[at:at+20] == bytes(20): found=True;break
            dll=string(u32(at+12));lookup=u32(at) or u32(at+16); names=[]
            for n in range(8192):
                thunk=u64(offset(lookup+n*8,8))
                if not thunk: break
                names.append({'ordinal':thunk & 65535} if thunk >> 63 else string(thunk+2))
            else: raise ValueError('unterminated import names')
            imports[dll]=names
        assert found,'unterminated import descriptors'
    return dict(filename=Path(path).name,sha256=hashlib.sha256(data).hexdigest(),size_bytes=len(data),pe_offset=pe,section_count=len(sections),preferred_base=hex(u64(opt+24)),entry=hex(u64(opt+24)+u32(opt+16)),image_bytes=u32(opt+56),headers_bytes=u32(opt+60),dll_characteristics=hex(u16(opt+70)),sections=sections,directories=dirs,imports=imports,import_count=sum(map(len,imports.values())))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('image',type=Path)
    a=p.parse_args()
    print(json.dumps(inspect(a.image),indent=2))
