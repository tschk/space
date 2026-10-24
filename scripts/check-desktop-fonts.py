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
    advances = {int(cp):int(adv) for cp,adv in re.findall(
        r'fb-font-sans-set\((\d+), (\d+),', (ROOT/'components/font.in').read_text())}
    expected = Image.new('RGB', (1920, 1080), (16,32,48))
    calls = []; fg=(233,219,173)

    def glyph(face, extent, cp, x, y, clip=(0,0,1920,1080)):
        font=ImageFont.truetype(str(ROOT/'assets/fonts/desktop'/face),14*extent//16)
        mask=Image.new('L',(extent,extent))
        ImageDraw.Draw(mask).text((0,13*extent//16),chr(cp),font=font,fill=255,anchor='ls')
        limit=advances[cp]*extent//8 if face=='DejaVuSans.ttf' else extent
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
        clip_offset_and_edge_checks='passed', kernel_sha256=sha(kernel),
        qemu_command=command, source_integrity='passed')
except Exception as error:
    report['error']=str(error)
finally:
    (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['status'].upper()+': native desktop font pixel oracle; '+str(a.out/'report.json'))
raise SystemExit(0 if report['status']=='passed' else 1)
