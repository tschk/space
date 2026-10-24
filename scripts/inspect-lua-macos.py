#!/usr/bin/env python3
"""Read-only inspection of pinned, unmodified LuaBinaries Mach-O artifacts."""
import argparse,hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--app',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
manifest=json.loads((ROOT/'fixtures/applications/lua-5.2.4-macos.json').read_text());expected=next(x for x in manifest['files'] if x['name']==a.app.name);data=a.app.read_bytes();digest=hashlib.sha256(data).hexdigest();assert digest==expected['sha256'] and len(data)==expected['size_bytes']
magic,cpu,subtype,kind,count,extent,flags,reserved=struct.unpack_from('<8I',data);assert (magic,cpu,kind)==(0xfeedfacf,0x1000007,2)
out={'path':str(a.app.resolve()),'sha256':digest,'size_bytes':len(data),'executed':False,'architecture':'x86_64','commands':[],'dependencies':[],'undefined_symbols':[],'version_strings':[],'manifest':manifest};offset=32
for _ in range(count):
 command,size=struct.unpack_from('<II',data,offset);assert size>=8 and size%8==0 and offset+size<=32+extent;out['commands'].append({'command':hex(command),'size':size})
 if command in [0xc,0xe]:
  at=offset+struct.unpack_from('<I',data,offset+8)[0];assert offset<=at<offset+size;name=data[at:offset+size].split(b'\0')[0].decode()
  if command==0xc:out['dependencies'].append(name)
  else:out['interpreter']=name
 if command==2:
  symoff,nsyms,stroff,strsize=struct.unpack_from('<4I',data,offset+8);assert symoff+nsyms*16<=len(data) and stroff+strsize<=len(data)
  for i in range(nsyms):
   name,typ=struct.unpack_from('<IB',data,symoff+16*i)
   if typ&14==0 and typ&1:
    assert name<strsize;out['undefined_symbols'].append(data[stroff+name:stroff+strsize].split(b'\0')[0].decode())
 if command==0x24:
  minimum,sdk=struct.unpack_from('<II',data,offset+8);version=lambda v:f'{v>>16}.{(v>>8)&255}.{v&255}';out['minimum_macos']=version(minimum);out['sdk']=version(sdk)
 if command==0x80000028:out['entry']={'kind':'LC_MAIN','file_offset':struct.unpack_from('<Q',data,offset+8)[0]}
 if command==0x80000022:out['fixup_profile']='LC_DYLD_INFO_ONLY classic rebase/bind/lazy-bind; not the implemented chained-format6 profile'
 offset+=size
assert offset==32+extent
for raw in data.split(b'\0'):
 if raw.startswith(b'Lua 5.'):out['version_strings'].append(raw.decode(errors='replace'))
assert any('Lua 5.2.4 ' in s for s in out['version_strings'])
out['admission']='unsupported: broader segments/sections, classic fixups and additional dependencies; inspection only'
a.out.write_text(json.dumps(out,indent=2)+'\n');print(f'INSPECTED {a.app.name}: {len(out["undefined_symbols"])} undefined imports; not executed')
