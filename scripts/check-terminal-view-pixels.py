#!/usr/bin/env python3
"""Compare a real QEMU terminal screenshot with independent pyte/Pillow output.

The oracle does not import the native parser, screen, glyph table or renderer.
It supports fixed ASCII cells, with optional ANSI16 colors.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import pyte
from PIL import Image, ImageDraw, ImageFont

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--capture',type=Path,required=True);p.add_argument('--stream',type=Path,required=True)
p.add_argument('--font',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
p.add_argument('--ansi-colors',action='store_true',help='Compare ANSI16 palette/bold brightness/reverse using independent pyte styles')
a=p.parse_args()
assert importlib.metadata.version('pyte')=='0.8.2'
assert hashlib.sha256(a.font.read_bytes()).hexdigest()=='54bf827eb99404e8f430c330ad30f063334f637eba0109b6a18d4f566a8e9dd8'
original=a.stream.read_bytes();assert all(byte<128 for byte in original)
normal=pyte.Screen(80,24);current=normal;stream=pyte.Stream(current)
for token in re.split(rb'(\x1b\[\?1049[hl])',original):
    if token==b'\x1b[?1049h':current=pyte.Screen(80,24);stream=pyte.Stream(current)
    elif token==b'\x1b[?1049l':current=normal;stream=pyte.Stream(current)
    else:stream.feed(token.decode('ascii'))
capture=Image.open(a.capture).convert('RGB');assert capture.size==(1024,768)
expected=Image.new('RGB',(768,384),(0x13,0x18,0x22))
font=ImageFont.truetype(str(a.font),14)
foreground=(0xd6,0xdc,0xe7);background=(0x13,0x18,0x22)
palette=[0x131822,0xd56b78,0x8ac79a,0xd4bc83,0x88b5ff,0xba9cd9,0x87c7cc,0xd6dce7,0x596474,0xef8f9a,0xa3dfae,0xf2d59a,0xa7caff,0xd4b9f0,0xa6e2e5,0xf3f5f8]
names=['black','red','green','brown','blue','magenta','cyan','white']
def color_index(name,default):
    if name=='default':return default
    if name.startswith('bright'):return names.index(name[6:])+8
    return names.index(name)
def rgb(index):
    value=palette[index];return ((value>>16)&255,(value>>8)&255,value&255)
for row in range(24):
    for column in range(80):
        cell=current.buffer[row][column]
        assert not cell.italics and not cell.underscore and not cell.strikethrough and not cell.blink
        fg=foreground;bg=background
        if a.ansi_colors:
            fi=color_index(cell.fg,7);bi=color_index(cell.bg,0)
            if cell.bold and fi<8:fi+=8
            if cell.reverse:fi,bi=bi,fi
            fg=rgb(fi);bg=rgb(bi)
        else:assert cell.fg=='default' and cell.bg=='default' and not cell.bold and not cell.reverse
        assert len(cell.data)==1 and 32<=ord(cell.data)<=126
        mask=Image.new('L',(9,16));ImageDraw.Draw(mask).text((0,13),cell.data,font=font,fill=255,anchor='ls')
        # Native integer alpha blending floors rather than rounding. Compute
        # it independently from mature raster coverage, never native data.
        pixels=bytes(channel for alpha in mask.tobytes() for channel in
                     tuple((f*alpha+b*(255-alpha))//255 for f,b in zip(fg,bg)))
        expected.paste(Image.frombytes('RGB',(9,16),pixels),(24+column*9,row*16))
if not current.cursor.hidden:
    x=24+min(current.cursor.x,79)*9;y=current.cursor.y*16+14
    ImageDraw.Draw(expected).rectangle((x,y,x+8,y+1),fill=(0x88,0xb5,0xff))
actual=capture.crop((128,192,896,576))
assert actual.tobytes()==expected.tobytes(),'actual protected SCI pixels differ from independent terminal/glyph oracle'
capture.save(a.capture.with_suffix('.png'))
rows=current.display
report=dict(status='passed',scope='Actual QEMU pixels; ASCII80x24 with '+('ANSI16/bold/reverse' if a.ansi_colors else 'default-color vi'),
            pixels_compared=768*384,stream_sha256=hashlib.sha256(original).hexdigest(),
            capture_sha256=hashlib.sha256(a.capture.read_bytes()).hexdigest(),
            content_sha256=hashlib.sha256(actual.tobytes()).hexdigest(),cursor=[current.cursor.x,current.cursor.y],rows=rows)
a.out.write_text(json.dumps(report,indent=2)+'\n')
print('PASS 294912 actual protected terminal pixels match independent pyte/DejaVu oracle')
