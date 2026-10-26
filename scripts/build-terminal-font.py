#!/usr/bin/env python3
"""Bake a bounded ASCII terminal face from the existing pinned DejaVu font."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, __version__

root = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');a=p.parse_args()
font_path=root/'assets/fonts/desktop/DejaVuSansMono.ttf'
digest=hashlib.sha256(font_path.read_bytes()).hexdigest()
assert digest=='54bf827eb99404e8f430c330ad30f063334f637eba0109b6a18d4f566a8e9dd8'
font=ImageFont.truetype(str(font_path),14)
atlas=bytearray()
for code in range(32,127):
    left,top,right,bottom=font.getbbox(chr(code),anchor='ls')
    assert left>=0 and right<=9 and top+13>=0 and bottom+13<=16,(code,(left,top,right,bottom))
    image=Image.new('L',(32,32));ImageDraw.Draw(image).text((0,13),chr(code),font=font,fill=255,anchor='ls')
    box=image.getbbox()
    assert box is None or (box[2]<=9 and box[3]<=16),(code,box)
    atlas.extend(image.crop((0,0,9,16)).tobytes())
padded=atlas+bytes((-len(atlas))%8)
words=[int.from_bytes(padded[i:i+8],'little',signed=True) for i in range(0,len(padded),8)]
source='''package space.terminal
// Generated with the existing pinned DejaVuSansMono.ttf, 14px / 13px baseline.
// License: assets/fonts/desktop/DejaVu-LICENSE.txt. ASCII 32..126, 9x16 cells.
var terminal-font-data:[Int]=[WORDS]
fn terminal-font-coverage(code:Int,x:Int,y:Int)->Int{
  if code<32 || code>126 || x<0 || x>=9 || y<0 || y>=16{return 0;}
  let index=(code - 32)*144+y*9+x;
  return (terminal-font-data[index/8]>>((index%8)*8))&255;
}
'''.replace('WORDS',','.join(map(str,words)))
receipt=json.dumps(dict(source_sha256=digest,pillow=__version__,cell=[9,16],font_pixels=14,baseline=13,
    coverage='ASCII 32..126 only',coverage_sha256=hashlib.sha256(atlas).hexdigest()),indent=2)+'\n'
for path,text in [(root/'components/terminal-font.in',source),(root/'assets/terminal/font.json',receipt)]:
    if a.check: assert path.read_text()==text
    else:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
print('PASS terminal glyph bounds and pinned face')
