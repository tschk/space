#!/usr/bin/env python3
"""Compare actual QEMU atlas rendering, clipping and blending to FreeType pixels."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import time

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args(); a.out = a.out.resolve()
if a.out.exists() and any(a.out.iterdir()): p.error('--out must be new or empty')
a.out.mkdir(parents=True, exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
inventory = {str(path.relative_to(ROOT)): sha(path)
    for directory in ('components', 'kernel', 'protocol', 'services', 'fixtures')
    for path in (ROOT/directory).rglob('*.in')}
report = dict(status='failed', compiler_sha256=sha(a.compiler), source_sha256=inventory,
              scope='native desktop renderer; no foreign application execution')
try:
    subprocess.run(['python3', str(ROOT/'scripts/build-desktop-fonts.py'), '--font-dir',
                    str(ROOT/'assets/fonts/desktop'), '--check'], check=True)
    expected = Image.new('RGB', (1920, 1080), (16,32,48))
    calls = []; fg=(233,219,173)

    def glyph(face, extent, cp, x, y, clip=(0,0,1920,1080)):
        font=ImageFont.truetype(str(ROOT/'assets/fonts/desktop'/face),14*extent//16)
        mask=Image.new('L',(extent,extent))
        ImageDraw.Draw(mask).text((0,13*extent//16),chr(cp),font=font,fill=255,anchor='ls')
        limit=max(1,int(font.getlength(chr(cp))+.5)) if face=='DejaVuSans.ttf' else extent
        box=mask.getbbox()
        if box and box[2]>limit:
            ink=mask.crop((0,0,box[2],extent)).resize((limit,extent),Image.Resampling.LANCZOS)
            mask=Image.new('L',(extent,extent));mask.paste(ink,(0,0))
        for row in range(extent):
            for col in range(extent):
                xx=x+col;yy=y+row
                if not (max(0,clip[0])<=xx<min(1920,clip[2]) and max(0,clip[1])<=yy<min(1080,clip[3])): continue
                cov=mask.getpixel((col,row))
                if cov:
                    old=expected.getpixel((xx,yy))
                    expected.putpixel((xx,yy), fg if cov==255 else tuple(
                        (src*cov+dst*(255-cov)+255)>>8 for src,dst in zip(fg,old)))

    for group,(extent,face,table) in enumerate([
        (16,'DejaVuSansMono.ttf','fb-font-aa16'),(16,'DejaVuSans.ttf','fb-font-sans-aa16'),
        (24,'DejaVuSansMono.ttf','desktop-font-mono24'),(24,'DejaVuSans.ttf','desktop-font-sans24')]):
        for cp in range(32,127):
            font=ImageFont.truetype(str(ROOT/'assets/fonts/desktop'/face),14*extent//16)
            advance=max(1,int(font.getlength(chr(cp))+.5)) if face=='DejaVuSans.ttf' else 5*extent//8
            face_id=1 if face=='DejaVuSans.ttf' else 0
            calls.append(f'if text-glyph-advance-raw({face_id},{cp},{extent//8})!={advance} || text-glyph-advance({face_id},{cp},{extent//8})!={advance}{{panic("desktop measured advance");}}')
            x=10+(cp-32)%32*(extent+4);y=10+group*120+(cp-32)//32*(extent+4)
            function='fb-draw-char-table-aa16' if extent==16 else 'desktop-font-draw24'
            calls.append(f'{function}({table},{x},{y},{cp},0xE9DBAD);')
            glyph(face,extent,cp,x,y)
    # Exercise partial left/top, right/bottom, clip and render offsets.
    calls += ['comp-render-dx=3;comp-render-dy=4;', 'comp-clip-set(2,500,19,520);',
              'desktop-font-draw24(desktop-font-sans24,-8,494,65,0xE9DBAD);',
              'comp-clip-clear();comp-render-dx=0;comp-render-dy=0;',
              'fb-draw-char-table-aa16(fb-font-aa16,1912,1070,87,0xE9DBAD);',
              'desktop-font-draw24(desktop-font-sans24,10,600,-1,0xE9DBAD);',
              'desktop-font-draw24(desktop-font-sans24,10,600,128,0xE9DBAD);']
    glyph('DejaVuSans.ttf',24,65,-5,498,(2,500,19,520))
    glyph('DejaVuSansMono.ttf',16,87,1912,1070)
    calls += ['if text-set-scale(3)!=1 || text-term-cell-w()!=15 || text-term-baseline()!=19 || text-face-baseline(FONT-FACE-SANS,3)!=19{panic("desktop large terminal metrics");}',
        'if text-set-scale(2)!=1 || text-term-cell-w()!=10 || text-term-baseline()!=13 || text-face-baseline(FONT-FACE-SANS,2)!=13{panic("desktop terminal metrics");}',
        'let utf8=alloc(8);store8(utf8,65);store8(utf8+1,195);store8(utf8+2,169);store8(utf8+3,226);store8(utf8+4,130);store8(utf8+5,172);store8(utf8+6,90);store8(utf8+7,0);',
        'if text-measure-run(TEXT-ROLE-TERM-MONO,utf8,7)!=40 || text-caret-x(TEXT-ROLE-TERM-MONO,utf8,3)!=20 || text-caret-x(TEXT-ROLE-TERM-MONO,utf8,6)!=30 || text-hit-test-byte(TEXT-ROLE-TERM-MONO,utf8,12)!=1 || text-hit-test-byte(TEXT-ROLE-TERM-MONO,utf8,22)!=3 || text-hit-test-byte(TEXT-ROLE-TERM-MONO,utf8,32)!=6{panic("desktop UTF8 metrics");}',
        'comp-draw-label(10,650,utf8,0xE9DBAD,0x102030);']
    glyph('DejaVuSansMono.ttf',16,65,11,650)
    glyph('DejaVuSansMono.ttf',16,90,41,650)
    draw=ImageDraw.Draw(expected)
    for x in (20,30):
        for box in [(x,650,x+9,651),(x,662,x+9,663),(x,650,x+1,663),(x+8,650,x+9,663),(x+4,656,x+7,657)]:
            draw.rectangle(box,fill=fg)
    calls += ['if text-set-scale(3)!=1 || text-measure-run(TEXT-ROLE-TERM-MONO,utf8,7)!=60 || text-caret-x(TEXT-ROLE-TERM-MONO,utf8,3)!=30 || text-caret-x(TEXT-ROLE-TERM-MONO,utf8,6)!=45 || text-hit-test-byte(TEXT-ROLE-TERM-MONO,utf8,17)!=1 || text-hit-test-byte(TEXT-ROLE-TERM-MONO,utf8,32)!=3 || text-hit-test-byte(TEXT-ROLE-TERM-MONO,utf8,47)!=6{panic("desktop large UTF8 metrics");}',
              'comp-draw-label(10,720,utf8,0xE9DBAD,0x102030);']
    glyph('DejaVuSansMono.ttf',24,65,11,720)
    glyph('DejaVuSansMono.ttf',24,90,56,720)
    for x in (25,40):
        for box in [(x,720,x+14,722),(x,738,x+14,740),(x,720,x+2,740),(x+12,720,x+14,740),(x+6,729,x+11,731)]:
            draw.rectangle(box,fill=fg)
    # Use the real root initialization path for allocator/device setup.
    source=(ROOT/'kernel/kernel-root.in').read_text()
    source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(ROOT/m[1])),source)
    assert source.count('  shell(port)')==1
    source=source.replace('  shell(port)','  desktop-font-proof(port)\n  shell(port)')
    source+='\nfn desktop-font-proof(port:Int)->void{\nif fb-init(0)!=0{panic("font display init");}\nfb-clear(0x102030);\n'+ '\n'.join(calls)+'''
 serial-write-cstr(port,"desktop-font-proof: ready");serial-nl(port);
 while true{hlt();}return;
}
'''
    entry=a.out/'probe.in';entry.write_text(source)
    trampoline=a.out/'trampoline.bin';kernel=a.out/'kernel.bin'
    subprocess.run(['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(trampoline)],check=True)
    with (a.out/'compile.log').open('w') as log:
        subprocess.run([str(a.compiler.resolve()),'compile','--path',str(entry),'--entry','kernel-entry',
            '--emit','boot','--trampoline',str(trampoline),'--target','native','--target-triple',
            'x86_64-unknown-none','--linkage','static-lib','--out',str(kernel)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    monitor=a.out/'monitor.sock';serial=a.out/'serial.log';ppm=a.out/'pixels.ppm'
    command=['qemu-system-x86_64','-cpu','max','-kernel',str(kernel),'-m','512M','-vga','std',
        '-display','none','-no-reboot','-serial','file:'+str(serial),'-monitor','unix:'+str(monitor)+',server,nowait']
    with (a.out/'qemu.log').open('w') as log:
        process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+40
            while not serial.exists() or 'desktop-font-proof: ready' not in serial.read_text(errors='replace'):
                if process.poll() is not None or time.monotonic()>deadline: raise RuntimeError('render probe did not become ready')
                time.sleep(.1)
            with socket.socket(socket.AF_UNIX) as sock:
                sock.settimeout(5);sock.connect(str(monitor));sock.recv(4096)
                sock.sendall(('screendump '+str(ppm)+'\n').encode())
                while not ppm.exists() or ppm.stat().st_size<1920*1080*3:
                    if time.monotonic()>deadline: raise TimeoutError('screendump timeout')
                    time.sleep(.05)
        finally:
            process.terminate();process.wait(timeout=5)
    actual=Image.open(ppm).convert('RGB')
    expected.save(a.out/'expected.png');actual.save(a.out/'pixels.png')
    assert actual.size==expected.size and actual.tobytes()==expected.tobytes(), 'actual coverage/clipping differs from independent font oracle'
    assert sha(a.compiler)==report['compiler_sha256']
    assert all(sha(ROOT/name)==digest for name,digest in inventory.items()), 'source changed'
    report.update(status='passed', glyphs=380, exact_framebuffer_pixels=2073600,
        measured_advance_checks=380, native_utf8_caret_hit_testing='passed',
        clip_offset_and_edge_checks='passed', kernel_sha256=sha(kernel),
        qemu_command=command, source_integrity='passed')
except Exception as error:
    report['error']=str(error)
finally:
    (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['status'].upper()+': native desktop font pixel oracle; '+str(a.out/'report.json'))
raise SystemExit(0 if report['status']=='passed' else 1)
