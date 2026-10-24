#!/usr/bin/env python3
"""Real PS/2 editing in original vi through owned terminal waits; no GUI surface yet."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', type=Path, required=True)
p.add_argument('--app', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--root', choices=['standard','minimal'], default='standard')
p.add_argument('--view', action='store_true', help='Also execute the protected native terminal surface (standard root only)')
p.add_argument('--navigation',action='store_true',help='Real extended PS2 keys, interior insert/delete and home/right/end in original vi')
p.add_argument('--oracle-python',type=Path,help='Pinned pyte/Pillow interpreter for --view pixel comparison')
a = p.parse_args(); out = a.out.resolve(); compiler = a.compiler.resolve(); app = a.app.resolve()
assert not a.view or a.root == 'standard'
assert not a.view or a.oracle_python, '--view needs an independent pixel oracle interpreter'
assert not out.exists() or not any(out.iterdir()), 'preserve prior evidence'
out.mkdir(parents=True, exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = ROOT / 'fixtures/applications/busybox-vi-1.36.1.json'
pin = json.loads(manifest.read_text())['apps'][0]
assert sha(app) == pin['sha256'] and app.stat().st_size == pin['size_bytes']
paths = [x for d in ['components','kernel','protocol','services','fixtures/terminal-session']
         for x in (ROOT / d).rglob('*.in')]
paths += [ROOT / 'boot/multiboot.asm',manifest,Path(__file__).resolve()]
if a.view:
    paths += [ROOT / 'scripts/pack-gui-sci.py',ROOT / 'scripts/pack-sci-image.py',
              ROOT / 'scripts/check-terminal-view-pixels.py',ROOT / 'assets/fonts/desktop/DejaVuSansMono.ttf']
contents = {str(x.relative_to(ROOT)): x.read_bytes() for x in paths}
snapshot = out / 'source'
for name, data in contents.items():
    path = snapshot / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
report = {'status':'running','goal_status':'OPEN','original_application_entries':0,
    'scope':'Original pinned BusyBox vi, actual PS2 keyboard and saved-file oracles over private native terminal; no desktop ANSI renderer/surface, no resize claim',
    'compiler_sha256':sha(compiler),'application_sha256':sha(app),'manifest_sha256':sha(manifest),
    'root':a.root,
    'source_sha256':{name:hashlib.sha256(data).hexdigest() for name,data in contents.items()},'keyboard':[]}
if a.view:
    report['scope']='Original pinned vi, actual PS2 editing and protected native SCI terminal pixels; finite ASCII80x24, no resize or concurrent foreign process claim'
process = None; serial = None; monitor = None; received = bytearray()
def connect(path):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        channel = socket.socket(socket.AF_UNIX); channel.settimeout(.2)
        try: channel.connect(str(path)); return channel
        except (FileNotFoundError,ConnectionRefusedError): channel.close(); time.sleep(.02)
    raise AssertionError('QEMU socket unavailable')
def wait(marker):
    deadline = time.monotonic() + 180
    while marker not in received:
        if b'PANIC' in received or b'CPU EXCEPTION' in received:
            drain = time.monotonic()+.3
            while time.monotonic()<drain:
                try: received.extend(serial.recv(65536))
                except socket.timeout: pass
        assert b'PANIC' not in received and b'CPU EXCEPTION' not in received, received[-4000:]
        assert process.poll() is None, 'QEMU exited'
        assert time.monotonic() < deadline, (marker,received[-4000:])
        try:
            block = serial.recv(65536); assert block; received.extend(block)
        except socket.timeout: pass
try:
    if a.navigation:
        fixture=snapshot/'fixtures/terminal-session/vi-checks.in'
        text='import "../../components/linux-terminal-keyboard.in"\n'+fixture.read_text()
        text=text.replace('key > 127 || terminal-seat-deliver(seat,key) != 0','linux-terminal-deliver-key(seat,key) != 0')
        text=text.replace('keys != 14','keys != 22').replace('keys != 13','keys != 16')
        fixture.write_text(text)
        report['navigation']=True
    if a.view:
        fixture = snapshot / 'fixtures/terminal-session/vi-checks.in'
        text = fixture.read_text()
        text = 'import "../../components/terminal-view.in"\nvar terminal-vi-view:Int=0\n' + text
        text += '''
fn terminal-vi-view-refusals(port:Int,image:Int)->void{
  let kind=0
  while kind<4{
    let token=terminal-view-open(port,image,runtime-instance-image-boot-size(image))
    if token<=0 || terminal-view-send(token+100000,129,0,0)!=0 || gui-protected-record(token)==0{panic("vi view exact generation")}
    let first=128;let last=0;let closing=0
    if kind==1{first=129;last=1;}
    if kind==2{first=129|(128<<8);}
    if kind==3{first=1;closing=1;}
    if terminal-view-send(token,first,last,closing)!=0 || gui-protected-record(token)!=0{panic("vi malformed view payload")}
    if terminal-view-write(token,"x",1)!=0 || terminal-view-close(token)!=0{panic("vi stale view after refusal")}
    kind+=1
  }
  serial-write-cstr(port,"vi: four malformed protected view payloads retired; stale routes refused PASS");serial-nl(port)
}
'''
        text = text.replace('  let count = 0\n', '  let count = 0\n  let start = terminal-vi-trace-size\n',1)
        text = text.replace('  return count\n', '  if count>0 && terminal-view-write(terminal-vi-view,terminal-vi-trace+start,count)!=1{panic("vi live terminal pixels")}\n  return count\n',1)
        text = text.replace('  let authority =', '''  if gui-protected-launch-valid()!=1 && gui-protected-bootstrap()!=1{panic("vi terminal view authority")}
  if out-set-bga-mode(port,1024,768,100,100)<=0{panic("vi terminal view output")}
  let image=boot-image-find(270)
  terminal-vi-view-refusals(port,image)
  terminal-vi-view=terminal-view-open(port,image,runtime-instance-image-boot-size(image))
  if terminal-vi-view<=0{panic("vi terminal view open")}
  let authority =''',1)
        text = text.replace('  let buffer = alloc(64)', '  serial-write-cstr(port,"vi: trace address ");serial-write-dec-wide(port,terminal-vi-trace);serial-nl(port)\n  let buffer = alloc(64)',1)
        text = text.replace('      let key = ps2-kbd-getchar()', '''      if progress>0{
        serial-write-cstr(port,"vi: painted ");serial-write-dec-wide(port,run);serial-put(port,32)
        serial-write-dec-wide(port,keys);serial-put(port,32);serial-write-dec-wide(port,terminal-vi-trace-size);serial-nl(port)
      }
      let key = ps2-kbd-getchar()''',1)
        text = text.replace('  serial-write-cstr(port,"vi: trace ")','  if terminal-view-close(terminal-vi-view)!=1 || gui-protected-record(terminal-vi-view)!=0{panic("vi terminal view close")}\n  serial-write-cstr(port,"vi: trace ")',1)
        fixture.write_text(text)
        report['derived_fixture_sha256']=sha(fixture)
    report['derived_fixture_sha256']=sha(snapshot/'fixtures/terminal-session/vi-checks.in')
    fnv = 0xcbf29ce484222325
    for byte in app.read_bytes(): fnv = ((fnv ^ byte) * 1099511628211) & ((1 << 64) - 1)
    if fnv >= 1 << 63: fnv -= 1 << 64
    root = 'kernel-root.in' if a.root == 'standard' else 'kernel-root-minimal.in'
    source = (snapshot / 'kernel' / root).read_text()
    source = re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(snapshot / m[1])),source)
    source = ('const TERMINAL-VI-ELF-SIZE = '+str(app.stat().st_size)+'\nconst TERMINAL-VI-FNV = '+str(fnv)+'\n'
        'import '+json.dumps(str(snapshot / 'fixtures/terminal-session/vi-checks.in'))+'\n'+source)
    if a.root == 'minimal':
        source = 'import '+json.dumps(str(snapshot / 'components/ps2-keyboard.in'))+'\n'+source
    assert source.count('  shell(port)') == 1
    setup = '  counter-init(mb-info)\n' if a.root == 'minimal' else ''
    if a.view: setup += '  if fb-ready==0 && fb-init(mb-info)!=0{panic("vi framebuffer init")}\n'
    source = source.replace('  shell(port)',setup+'  terminal-vi-fixture(port)\n  shell(port)')
    (out / 'kernel.in').write_text(source)
    with (out / 'compile.log').open('w') as log:
        subprocess.run(['nasm','-f','bin',str(snapshot / 'boot/multiboot.asm'),'-o',str(out / 'trampoline.bin')],check=True,stdout=log,stderr=subprocess.STDOUT)
        subprocess.run([str(compiler),'compile','--path',str(out / 'kernel.in'),'--entry','kernel-entry','--emit','boot',
            '--trampoline',str(out / 'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none',
            '--linkage','static-lib','--out',str(out / 'kernel.bin')],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        if a.view:
            commands = [
                [str(compiler),'compile','--path',str(snapshot / 'components/app-terminal-view.in'),'--entry','client-entry','--emit','sci','--base','0x60000000','--target','native','--target-triple','x86_64-unknown-none','--out',str(out / 'view.raw.sci')],
                ['python3',str(snapshot / 'scripts/pack-gui-sci.py'),str(out / 'view.raw.sci'),str(out / 'view.raw.component-metadata.json'),str(out / 'view.sci'),'--protected'],
                ['python3',str(snapshot / 'scripts/pack-sci-image.py'),str(out / 'kernel.bin'),str(out / 'combined.bin'),'270:'+str(out / 'view.sci')]]
            for build in commands: subprocess.run(build,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    image = out / ('combined.bin' if a.view else 'kernel.bin')
    command = ['qemu-system-x86_64','-cpu','max','-kernel',str(image),'-m','512M','-display','none','-no-reboot',
        '-serial',f'unix:{out}/serial.sock,server=on,wait=on','-monitor',f'unix:{out}/monitor.sock,server=on,wait=off',
        '-device',f'loader,file={app},addr=0x10000000,force-raw=on']
    report.update(qemu_command=command,kernel_sha256=sha(image))
    with (out / 'qemu.log').open('w') as log:
        process = subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        serial = connect(out / 'serial.sock'); monitor = connect(out / 'monitor.sock')
        for run, text in enumerate(['native42','again42']):
            wait(f'vi: keyboard ready {run}\n'.encode())
            typed='native24' if a.navigation and run==0 else text
            edits=[('i',105)]+[(c,ord(c)) for c in typed]
            if a.navigation:
                if run==0: edits += [('left',129),('backspace',8),('delete',134),('4',52),('2',50)]
                edits += [('home',132),('right',130),('end',133)]
            keys = edits + [('esc',27),('shift-semicolon',58),('w',119),('q',113),('ret',10)]
            for index,(key,byte) in enumerate(keys):
                monitor.sendall(f'sendkey {key} 50\n'.encode())
                wait(f'vi: key {run} {index} {byte}\n'.encode())
                # Let the actual key-up finish, especially Shift on the colon.
                time.sleep(.08)
                if a.view and index == len(edits)-1:
                    marker=f'vi: painted {run} {index+1} '.encode();wait(marker)
                    expression=re.escape(marker)+rb'(\d+)\n'
                    deadline=time.monotonic()+10
                    while not re.search(expression,received) and time.monotonic()<deadline:
                        try: received.extend(serial.recv(65536))
                        except socket.timeout: pass
                    match=re.search(expression,received);assert match
                    size=int(match[1]);address=int(re.search(rb'vi: trace address (\d+)\n',received)[1])
                    screenshot = out / f'vi-edit-{run}.ppm'
                    prefix=out/f'vi-edit-{run}-stream.bin'
                    monitor.sendall(f'stop\npmemsave {address:#x} {size} "{prefix}"\nscreendump "{screenshot}"\ncont\n'.encode())
                    deadline = time.monotonic()+10
                    while (not screenshot.exists() or screenshot.stat().st_size<1024*768*3 or not prefix.exists() or prefix.stat().st_size!=size) and time.monotonic()<deadline: time.sleep(.02)
                    assert screenshot.exists() and prefix.exists(), 'actual QEMU capture unavailable'
                    oracle=out/f'vi-edit-{run}-pixels.json'
                    result=subprocess.run([str(a.oracle_python),str(snapshot/'scripts/check-terminal-view-pixels.py'),
                        '--capture',str(screenshot),'--stream',str(prefix),'--font',str(snapshot/'assets/fonts/desktop/DejaVuSansMono.ttf'),
                        '--out',str(oracle)],capture_output=True,text=True,timeout=60)
                    (out/f'vi-edit-{run}-pixels.log').write_text(result.stdout+result.stderr)
                    assert result.returncode==0,result.stdout+result.stderr
                    report.setdefault('screenshots',[]).append(dict(path=str(screenshot),sha256=sha(screenshot),pixel_oracle=json.loads(oracle.read_text())))
            wait(f'vi: saved exact {run}\n'.encode())
            report['keyboard'].append({'process':run,'real_ps2_text_events':len(keys),'keys':keys,'saved_bytes':(text + ('original\n' if run == 0 else 'native42original\n'))})
        wait(b'vi: two actual original keyboard edit/save/reopen processes PASS\n')
        wait(b'space> ')
        match = re.search(rb'vi: trace (\d+) (\d+)\n',received); assert match
        address,size = map(int,match.groups()); assert 0 < size <= 65536
        capture = out / 'original-vi-output.bin'
        monitor.sendall(f'pmemsave {address:#x} {size} "{capture}"\n'.encode())
        deadline = time.monotonic() + 5
        while (not capture.exists() or capture.stat().st_size != size) and time.monotonic() < deadline: time.sleep(.02)
        output = capture.read_bytes(); assert len(output) == size and b'\x1b[' in output and b'original' in output
    assert all((ROOT / name).read_bytes() == data for name,data in contents.items()), 'source changed during run'
    assert sha(compiler) == report['compiler_sha256'] and sha(app) == report['application_sha256']
    report.update(status='passed',original_application_entries=2,actual_ps2_text_events=sum(len(x['keys']) for x in report['keyboard']),
        interactive_keyboard=True,interactive_gui=a.view,original_output_sha256=sha(capture),original_output_bytes=size,
        exact_saved_files=['native42original\n','again42native42original\n'],stable_after_warmup=True)
    print(f"PASS original vi: two protected keyboard edit/save/reopen processes, {report['actual_ps2_text_events']} real PS2 text events, exact saved files and owned cleanup")
except Exception as error:
    report.update(status='failed',error=str(error)); raise
finally:
    (out / 'serial.log').write_bytes(received)
    if serial: serial.close()
    if monitor: monitor.close()
    if process:
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill(); process.wait()
    (out / 'report.json').write_text(json.dumps(report,indent=2) + '\n')
