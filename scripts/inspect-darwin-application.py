#!/usr/bin/env python3
"""Inspect checksum-pinned original macOS jq requirements without executing it."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parents[1]
def inspect(path):
    data=path.read_bytes()
    manifest=json.loads((ROOT/'fixtures/applications/jq-1.8.1.json').read_text())
    expected=next(row for row in manifest['apps'] if row['personality']=='darwin')
    digest=hashlib.sha256(data).hexdigest()
    assert digest==expected['sha256'] and len(data)==expected['size_bytes'],'original application checksum/size mismatch'
    magic,cpu,subtype,kind,count,extent,flags,reserved=struct.unpack_from('<8I',data)
    assert (magic,cpu,kind)==(0xfeedfacf,0x1000007,2)
    commands=[];dylibs=[];sections=[];symbols=[];entry=None;interpreter=None
    offset=32
    for _ in range(count):
        command,size=struct.unpack_from('<II',data,offset)
        assert size>=8 and size%8==0 and offset+size<=32+extent
        commands.append({'command':hex(command),'size':size})
        if command in [0xc,0x80000018,0x8000001f,0x80000023]:
            start=offset+struct.unpack_from('<I',data,offset+8)[0]
            assert offset<=start<offset+size
            dylibs.append(data[start:offset+size].split(b'\0',1)[0].decode())
        if command==0xe:
            start=offset+struct.unpack_from('<I',data,offset+8)[0]
            interpreter=data[start:offset+size].split(b'\0',1)[0].decode()
        if command==0x80000028:
            entry={'kind':'LC_MAIN','file_offset':struct.unpack_from('<Q',data,offset+8)[0],'stack_size':struct.unpack_from('<Q',data,offset+16)[0]}
        if command==0x19:
            nsects=struct.unpack_from('<I',data,offset+64)[0]
            assert size==72+nsects*80
            for i in range(nsects):
                s=offset+72+i*80
                sections.append({'segment':data[s+16:s+32].split(b'\0',1)[0].decode(),'section':data[s:s+16].split(b'\0',1)[0].decode(),'type':struct.unpack_from('<I',data,s+64)[0]&255})
        if command==2:
            symoff,nsyms,stroff,strsize=struct.unpack_from('<4I',data,offset+8)
            assert symoff+nsyms*16<=len(data) and stroff+strsize<=len(data)
            for i in range(nsyms):
                at=symoff+i*16;name,typ=struct.unpack_from('<IB',data,at)
                if typ&0xe==0 and typ&1 and name<strsize:
                    symbols.append(data[stroff+name:stroff+strsize].split(b'\0',1)[0].decode())
        offset+=size
    assert offset==32+extent
    return {'path':str(path.resolve()),'sha256':digest,'size':len(data),'executed':False,'entry':entry,'interpreter':interpreter,'dependencies':dylibs,'commands':commands,'sections':sections,'undefined_symbols':sorted(set(symbols)),'startup_profile':'refused: strict startup admits only two section-free segments and one entry command; dependency loading and initialization are absent'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('app',type=Path);p.add_argument('--out',type=Path)
    a=p.parse_args();result=inspect(a.app);text=json.dumps(result,indent=2)+'\n'
    if a.out:a.out.write_text(text)
    else:print(text,end='')
