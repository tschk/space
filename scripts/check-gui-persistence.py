#!/usr/bin/env python3
"""Actual GUI Ctrl-S save/reopen/reboot on one exclusively owned NVMe disk."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', required=True)
p.add_argument('--out', type=Path, required=True, help='New/empty evidence directory; creates its own disk')
p.add_argument('--default-gui', action='store_true', help='Test the distributable protected default; otherwise preserve the explicit trusted window baseline')
a = p.parse_args()
out = a.out.resolve()
if out.exists() and any(out.iterdir()):
    p.error('--out must be new or empty')
out.mkdir(parents=True, exist_ok=True)
compiler = Path(a.compiler).resolve()
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
sources = [x for folder in ('components','kernel','protocol') for x in (ROOT/folder).rglob('*.in')]
sources += [ROOT/'boot/multiboot.asm', ROOT/'scripts/build-images.sh', ROOT/'scripts/pack-gui-sci.py', ROOT/'scripts/gui-window-evidence.py', Path(__file__).resolve()]
snapshot = {str(x.relative_to(ROOT)): sha(x) for x in sources}
report = {'started_utc': datetime.now(timezone.utc).isoformat(), 'compiler': str(compiler), 'compiler_sha256':sha(compiler), 'boots': [], 'status':'running'}
images = out/'images'
environment = dict(os.environ, IN=str(compiler), BUILD_DIR=str(images), GUI_PROFILE='window')
if a.default_gui: environment.pop('GUI_PROFILE')
report['distributable_default_gui'] = a.default_gui
with (out/'build.log').open('w') as log:
    subprocess.run(['bash',str(ROOT/'scripts/build-images.sh'),'--variant','all'],env=environment,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
image = images/'standard.bin'
report['image_sha256'] = sha(image)
disk = out/'owned-nvme.raw'
with disk.open('xb') as file: file.truncate(64*1024*1024)
report['disk_origin'] = 'New exclusively owned blank64MiB raw file; guest GUI writes all tested content'
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('native_disk_oracle', ROOT/'scripts/check-native-persistence.py')
oracle = importlib.util.module_from_spec(spec); spec.loader.exec_module(oracle)
spec = importlib.util.spec_from_file_location('window_evidence', ROOT/'scripts/gui-window-evidence.py')
window_module = importlib.util.module_from_spec(spec); spec.loader.exec_module(window_module)
window_oracle = window_module.WindowEvidence(ROOT,protected=window_module.image_has_protected_canvas(image))
readable = window_module.image_has_canvas(image)
report['gui_profile'] = 'window' if readable else 'legacy'
glyphs = {}
for match in re.finditer(r'fb-font-set\(([^)]+)\)', (ROOT/'components/font.in').read_text()):
    try: values = [int(x.strip(),0) for x in match.group(1).split(',')]
    except ValueError: continue
    if len(values)==9: glyphs[values[0]]=values[1:]
READY = b'gui: calculator left, text editor right; click or Tab to focus, Escape closes focused app'
CLOSED = b'gui: both applications closed; stable session counters; returning to shell'

class Boot:
    def __init__(self, name, kernel):
        self.path=out/name; self.path.mkdir(); self.log=bytearray(); self.serial=None; self.monitor=None
        self.focused=0; self.live=[True,True]
        self.receipt={'name':name,'kernel_sha256':sha(kernel),'inputs':[],'screenshots':[]};report['boots'].append(self.receipt)
        self.qlog=(self.path/'qemu.log').open('w')
        serial,monitor=self.path/'serial.sock',self.path/'monitor.sock'
        command=['qemu-system-x86_64','-kernel',str(kernel),'-m','512M','-vga','std','-display','none','-no-reboot','-serial',f'unix:{serial},server=on,wait=on','-monitor',f'unix:{monitor},server=on,wait=off','-drive',f'file={disk},format=raw,if=none,id=owned,cache=writethrough','-device','nvme,drive=owned,serial=space-gui-persistence']
        self.receipt['command']=command
        self.process=subprocess.Popen(command,stdout=self.qlog,stderr=subprocess.STDOUT)
        try:
            self.serial=self.connect(serial);self.monitor=self.connect(monitor)
            self.wait(b'space interactive shell')
            assert b'nvme: storage component ready' in self.log, 'refuse RAM fallback as persistence evidence'
        except Exception:
            self.close();raise
    def connect(self,path):
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            channel=socket.socket(socket.AF_UNIX)
            try: channel.connect(str(path));channel.settimeout(.1);return channel
            except OSError: channel.close();time.sleep(.02)
        raise AssertionError(f'QEMU socket unavailable {path}')
    def wait(self,marker,start=0):
        deadline=time.monotonic()+30
        while marker not in self.log[start:]:
            if time.monotonic()>deadline: raise AssertionError((marker,self.log[-2500:]))
            try:
                data=self.serial.recv(65536)
                assert data,'QEMU serial closed'
                self.log.extend(data)
            except socket.timeout: pass
        (self.path/'serial.log').write_bytes(self.log)
        if marker != b'gui: native session unavailable or failed':
            assert b'gui: native session unavailable or failed' not in self.log, self.log[-2500:]
    def command(self,value,marker):
        if value=='gui apps':self.focused=0;self.live=[True,True]
        start=len(self.log); self.receipt['inputs'].append({'serial':value,'offset':start});self.serial.sendall(value.encode()+b'\n');self.wait(marker,start)
    def key(self,value):
        codes={'ret':10,'backspace':8,'shift-8':42,'shift-equal':43,'ctrl-s':19,'esc':27,'tab':9,'ctrl-g':7,'ctrl-o':15}
        code=codes[value] if value in codes else ord(value)
        marker=f'gui: app rendered key {code}\n'.encode()
        if value=='esc':marker=b'gui: focused app closed, retired token refused'
        if value=='tab':marker=b'gui: focus '
        if value in ('ctrl-g','ctrl-o'):marker=b'gui-window: mode '
        start=len(self.log);self.receipt['inputs'].append({'qemu_key':value,'offset':start});self.monitor.sendall(f'sendkey {value}\n'.encode());self.wait(marker,start);time.sleep(.12)
        if value in ('ctrl-g','ctrl-o'):self.wait(b'\n',self.log.index(marker,start))
        if value=='tab' and self.live[1-self.focused]:self.focused=1-self.focused
        if value=='esc':
            self.live[self.focused]=False
            self.focused=next((slot for slot in range(2) if self.live[slot]),-1)
    def editor_focus(self):
        self.focused=1
        if readable:
            receipt=window_oracle.focus_pointer(self.monitor,self.wait,self.log,1)
            self.receipt['inputs'].append({'pointer':receipt});return
        for _ in range(25):self.monitor.sendall(b'mouse_move -100 -100\n');time.sleep(.02)
        for x,y in ((100,80),(70,8)):self.monitor.sendall(f'mouse_move {x} {y}\n'.encode());time.sleep(.1)
        start=len(self.log);self.monitor.sendall(b'mouse_button 1\n');self.wait(b'gui: pointer focused app ',start);self.monitor.sendall(b'mouse_button 0\n');self.receipt['inputs'].append({'pointer':'clamp0,0 then170,88 leftpress/release'})
    def pixels(self,name,texts):
        if readable:
            path=self.path/(name+'.ppm');layout=window_oracle.layout(self.log)
            rgb=window_oracle.capture_checked(self.monitor,path,layout,texts,self.focused)
            self.receipt['screenshots'].append({'name':name,'sha256':sha(path),'expected':texts,'layout':layout,'focused':self.focused})
            return
        path=self.path/(name+'.ppm');self.monitor.sendall(f'screendump {path}\n'.encode())
        deadline=time.monotonic()+5
        while (not path.exists() or path.stat().st_size<1920*1080*3+17) and time.monotonic()<deadline:time.sleep(.02)
        header=path.read_bytes().split(b'\n',3);assert header[:3]==[b'P6',b'1920 1080',b'255'];rgb=header[3]
        for slot,text in enumerate(texts):
            left=40+slot*120
            for y in range(79,97):
                for x in range(left-1,left+65):
                    expected=bytes((0,0,128))
                    if text is not None and 80<=y<96 and left<=x<left+64:
                        row,column=y-80,x-left;line=text[row//8].ljust(8);bits=glyphs.get(ord(line[column//8]),[0]*8)[row%8]
                        expected=b'\xff\xff\xff' if bits&(128>>(column%8)) else bytes((32,32,32))
                    actual=rgb[(y*1920+x)*3:(y*1920+x)*3+3]
                    assert actual==expected,(name,slot,x,y,actual,expected)
        self.receipt['screenshots'].append({'name':name,'sha256':sha(path),'expected':texts})
    def close_both(self):
        start=len(self.log);self.key('esc');self.key('esc');self.wait(CLOSED,start)
    def close(self):
        (self.path/'serial.log').write_bytes(self.log)
        if self.serial:self.serial.close()
        if self.monitor:self.monitor.close()
        self.process.terminate()
        try:self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
        self.qlog.close()

def disk_check(expected):
    metadata,actual=oracle.read_disk_file(disk,'gui-note.txt')
    assert actual==expected,(actual,expected)
    report.setdefault('disk_files',[]).append(metadata)
    data=disk.read_bytes();table=struct.unpack_from('<Q',data,40)[0];start=table*4096+metadata['inode']*256
    return data[start:start+256]

try:
    boot=Boot('boot-a-save',image)
    try:
        boot.command('format',b'disk formatted')
        boot.command('gui apps',READY)
        for key in ('6','shift-8','7','ret'):boot.key(key)
        boot.editor_focus()
        for key in 'persist':boot.key(key)
        boot.key('8');boot.key('x')  # Full8byte field; ninth printable key is refused.
        boot.key('ctrl-s');boot.pixels('saved-persist', [('6*7','42'),('persist8','saved')])
        if readable:
            boot.key('ctrl-g');boot.key('ctrl-o')
            boot.pixels('saved-persist-after-scale-resize',[('6*7','42'),('persist8','saved')])
        boot.key('esc');boot.pixels('editor-closed-calc-alive',[('6*7','42'),None])
        for key in ('backspace','8','ret'):boot.key(key)
        boot.pixels('surviving-calc48',[('6*8','48'),None]);boot.key('esc');boot.wait(CLOSED)
        boot.command('gui apps',READY);boot.pixels('same-boot-reopen',[('',''),('persist8','loaded')]);boot.close_both()
    finally:boot.close()
    disk_check(b'persist8')
    boot=Boot('boot-b-reboot-shrink',image)
    try:
        boot.command('gui apps',READY);boot.pixels('reboot-persist',[('',''),('persist8','loaded')]);boot.editor_focus()
        for _ in range(5):boot.key('backspace')
        boot.key('ctrl-s');boot.pixels('saved-shorter-per',[('',''),('per','saved')]);boot.close_both()
    finally:boot.close()
    before_denied=disk_check(b'per')
    # Deliberate negative artifact: strip storage from only the editor manifest
    # after production packaging. This image cannot pass the named app policy.
    denied=bytearray(image.read_bytes());table=struct.unpack_from('<Q',denied,0xF00)[0]-0x100000;count=struct.unpack_from('<Q',denied,table+8)[0]
    for index in range(count):
        kind,physical,size,_=struct.unpack_from('<QQQQ',denied,table+16+index*32)
        if kind in (21,24):
            offset=physical-0x100000;assert struct.unpack_from('<Q',denied,offset+8)[0]==52;struct.pack_into('<Q',denied,offset+8,20);break
    else:raise AssertionError('editor missing from ordinary standard image')
    denied_image=out/'denied-storage.bin';denied_image.write_bytes(denied)
    report['negative_artifact']={'sha256':sha(denied_image),'mutation':'editor required mask52→20, intentionally outside production packaging policy'}
    boot=Boot('boot-c-storage-denied',denied_image)
    try:
        if kind == 24:
            boot.command('gui apps', b'gui: native session unavailable or failed')
            # Protected admission rejects the mismatched storage declaration
            # before entry and cleans the pending calculator; no fallback.
            assert b'gui: selected application profile unavailable; no fallback' in boot.log
        else:
            boot.command('gui apps',READY);boot.pixels('load-denied',[('',''),('','denied')]);boot.editor_focus()
            for key in 'attack':boot.key(key)
            boot.key('ctrl-s');boot.pixels('save-denied',[('',''),('attack','denied')]);boot.close_both()
    finally:boot.close()
    assert disk_check(b'per')==before_denied,'missing storage grant mutated target inode'
    boot=Boot('boot-d-reboot-empty',image)
    try:
        boot.command('gui apps',READY);boot.pixels('reboot-per-after-denial',[('',''),('per','loaded')]);boot.editor_focus()
        for _ in range(3):boot.key('backspace')
        boot.key('ctrl-s');boot.pixels('saved-empty',[('',''),('','saved')]);boot.close_both()
    finally:boot.close()
    disk_check(b'')
    boot=Boot('boot-e-reboot-empty',image)
    try:
        boot.command('gui apps',READY);boot.pixels('reboot-empty',[('',''),('','loaded')]);boot.close_both()
    finally:boot.close()
    disk_check(b'')
    changed = [str(x.relative_to(ROOT)) for x in sources if snapshot[str(x.relative_to(ROOT))] != sha(x)]
    assert not changed, 'source changed during run; rerun for consistent evidence: '+', '.join(changed)
    assert report['compiler_sha256']==sha(compiler)
    report.update(status='pass',finished_utc=datetime.now(timezone.utc).isoformat(),disk_final_sha256=sha(disk))
    (out/'source-hashes.json').write_text(json.dumps(snapshot,indent=2)+'\n')
except Exception as error:
    report.update(status='failed',error=str(error));raise
finally:
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS actual GUI Ctrl-S: owned NVMe fiveboots, exact saved/shortened/empty text reopen, calculator survival, denied storage leaves target inode/bytes unchanged')
