#!/usr/bin/env python3
"""Run original QuickJS REPL with real PS/2 input and optional verified SCI pixels."""
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
p.add_argument('--oracle-python',type=Path,help='Pinned pyte/Pillow interpreter for --view pixel comparison')
a = p.parse_args(); out = a.out.resolve(); compiler = a.compiler.resolve(); app = a.app.resolve()
assert not a.view or a.root == 'standard'
assert not a.view or a.oracle_python, '--view needs an independent pixel oracle interpreter'
assert not out.exists() or not any(out.iterdir()), 'preserve prior evidence'
out.mkdir(parents=True, exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = ROOT / 'fixtures/applications/quickjs-2024-01-13.json'
pin = json.loads(manifest.read_text())['apps'][0]
assert sha(app) == pin['sha256'] and app.stat().st_size == pin['size_bytes']
paths = [x for d in ['components','kernel','protocol','services','fixtures/terminal-session']
         for x in (ROOT / d).rglob('*.in')]
paths += [ROOT / 'boot/multiboot.asm',ROOT/'fixtures/terminal-session/select.asm',manifest,Path(__file__).resolve()]
if a.view:
    paths += [ROOT / 'scripts/pack-gui-sci.py',ROOT / 'scripts/pack-sci-image.py',
              ROOT / 'scripts/check-terminal-view-pixels.py',ROOT / 'assets/fonts/desktop/DejaVuSansMono.ttf']
contents = {str(x.relative_to(ROOT)): x.read_bytes() for x in paths}
snapshot = out / 'source'
for name, data in contents.items():
    path = snapshot / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
report = {'status':'running','goal_status':'OPEN','original_application_entries':0,
    'scope':'Original unchanged-source QuickJS REPL, real PS2 input and exact file/reopen over owned terminal; finite ASCII, no resize/concurrency claim',
    'compiler_sha256':sha(compiler),'application_sha256':sha(app),'manifest_sha256':sha(manifest),
    'root':a.root,
    'source_sha256':{name:hashlib.sha256(data).hexdigest() for name,data in contents.items()},'keyboard':[]}
if a.view:
    report['scope']='Original QuickJS REPL, real PS2 evaluation/file/reopen and protected client-owned ANSI16 terminal pixels; finite ASCII80x24, no resize/concurrency claim'
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
            (out/'serial.log').write_bytes(received)
        except socket.timeout: pass
try:
    with (out/'control-build.log').open('w') as log:
        subprocess.run(['nasm','-f','elf64',str(snapshot/'fixtures/terminal-session/select.asm'),'-o',str(out/'select.o')],stdout=log,stderr=subprocess.STDOUT,check=True)
        subprocess.run(['ld','-static','-z','noexecstack','-o',str(out/'select.elf'),str(out/'select.o')],stdout=log,stderr=subprocess.STDOUT,check=True)
    report['own_control_elf_sha256']=sha(out/'select.elf')
    if a.view:
        fixture=snapshot/'fixtures/terminal-session/quickjs-checks.in'
        text='import "../../components/terminal-view.in"\nvar quickjs-repl-view:Int=0\n'+fixture.read_text()
        text=text.replace(' let count=0;while terminal-session-query',' let start=quickjs-repl-bytes;let count=0;while terminal-session-query',1)
        text=text.replace('count+=1;}return count;','count+=1;}if count>0 && terminal-view-write(quickjs-repl-view,quickjs-repl-trace+start,count)!=1{panic("QuickJS actual SCI terminal pixels");}return count;',1)
        text=text.replace(' if heap-next>=0x10000000',''' if gui-protected-launch-valid()!=1 && gui-protected-bootstrap()!=1{panic("QuickJS view authority");}
 if out-set-bga-mode(port,1024,768,100,100)<=0{panic("QuickJS view output mode");}
 let image=boot-image-find(270);quickjs-repl-view=terminal-view-open(port,image,runtime-instance-image-boot-size(image));if quickjs-repl-view<=0{panic("QuickJS SCI view open");}
 if heap-next>=0x10000000''',1)
        text=text.replace(' serial-write-cstr(port,"qjs: trace ")',' if terminal-view-close(quickjs-repl-view)!=1 || gui-protected-record(quickjs-repl-view)!=0{panic("QuickJS SCI terminal retirement");}\n serial-write-cstr(port,"qjs: trace ")',1)
        fixture.write_text(text)
        report['derived_fixture_sha256']=sha(fixture)
    fnv = 0xcbf29ce484222325
    for byte in app.read_bytes(): fnv = ((fnv ^ byte) * 1099511628211) & ((1 << 64) - 1)
    if fnv >= 1 << 63: fnv -= 1 << 64
    root = 'kernel-root.in' if a.root == 'standard' else 'kernel-root-minimal.in'
    source = (snapshot / 'kernel' / root).read_text()
    source = re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(snapshot / m[1])),source)
    source = ('const TERMINAL-SELECT-SIZE = '+str((out/'select.elf').stat().st_size)+'\nconst QUICKJS-REPL-SIZE = '+str(app.stat().st_size)+'\nconst QUICKJS-REPL-FNV = '+str(fnv)+'\n'
        'import '+json.dumps(str(snapshot / 'fixtures/terminal-session/quickjs-checks.in'))+'\n'+source)
    if a.root == 'minimal':
        source = 'import '+json.dumps(str(snapshot / 'components/ps2-keyboard.in'))+'\n'+source
    assert source.count('  shell(port)') == 1
    setup = '  counter-init(mb-info)\n' if a.root == 'minimal' else ''
    if a.view: setup += '  if fb-ready==0 && fb-init(mb-info)!=0{panic("QuickJS framebuffer init")}\n'
    source = source.replace('  shell(port)',setup+'  quickjs-repl-check(port)\n  shell(port)')
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
        '-device',f'loader,file={app},addr=0x10000000,force-raw=on',
        '-device',f'loader,file={out}/select.elf,addr=0x12000000,force-raw=on']
    report.update(qemu_command=command,kernel_sha256=sha(image))
    with (out / 'qemu.log').open('w') as log:
        process = subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        serial = connect(out / 'serial.sock'); monitor = connect(out / 'monitor.sock')
        scripts=["6*7\nvar f=std.open('/repl.txt','w')\nf.puts('saved');f.close()\n\\q\n", "std.loadFile('/repl.txt')\ntypeof f\nJSON.stringify({a:42})\n\\q\n"]
        keynames={'\n':'ret',' ':'spc',"'":'apostrophe','"':'shift-apostrophe','(':'shift-9',')':'shift-0','{':'shift-bracket_left','}':'shift-bracket_right','[':'bracket_left',']':'bracket_right','/':'slash','\\':'backslash',';':'semicolon',':':'shift-semicolon','.':'dot',',':'comma','=':'equal','+':'shift-equal','*':'shift-8','-':'minus','_':'shift-minus'}
        for run,text in enumerate(scripts):
            wait(f'qjs: keyboard ready {run}\n'.encode())
            keys=[]
            for char in text:
                name=keynames.get(char,('shift-'+char.lower()) if char.isupper() else char)
                keys.append((name,ord(char)))
            if run==0:
                keys=[('6',54),('shift-8',42),('8',56),('7',55),('left',129),
                      ('backspace',8),('delete',134),('7',55),('home',132),('right',130),('end',133),('ret',10)]+keys[4:]
            for index,(name,code) in enumerate(keys):
                monitor.sendall(f'sendkey {name} 50\n'.encode())
                wait(f'qjs: key {run} {index} {code}\n'.encode());time.sleep(.08)
                if a.view and index==len(keys)-4:
                    marker=f'qjs: idle {run} {index+1} '.encode();wait(marker)
                    pattern=re.escape(marker)+rb'(\d+)\n';deadline=time.monotonic()+10
                    match=re.search(pattern,received)
                    while not match and time.monotonic()<deadline:
                        try:received.extend(serial.recv(65536))
                        except socket.timeout:pass
                        match=re.search(pattern,received)
                    assert match,'complete native paint marker unavailable'
                    size=int(match[1]);address=int(re.search(rb'qjs: trace address (\d+)\n',received)[1])
                    shot=out/f'quickjs-repl-{run}.ppm';stream=out/f'quickjs-repl-{run}-stream.bin'
                    monitor.sendall(f'stop\npmemsave {address:#x} {size} "{stream}"\nscreendump "{shot}"\ncont\n'.encode())
                    deadline=time.monotonic()+10
                    while (not shot.exists() or shot.stat().st_size<1024*768*3 or not stream.exists() or stream.stat().st_size!=size) and time.monotonic()<deadline:time.sleep(.02)
                    assert shot.exists() and stream.exists(),'actual QEMU capture absent'
                    oracle=out/f'quickjs-repl-{run}-pixels.json'
                    result=subprocess.run([str(a.oracle_python),str(snapshot/'scripts/check-terminal-view-pixels.py'),
                        '--capture',str(shot),'--stream',str(stream),'--font',str(snapshot/'assets/fonts/desktop/DejaVuSansMono.ttf'),
                        '--ansi-colors','--out',str(oracle)],capture_output=True,text=True,timeout=60)
                    (out/f'quickjs-repl-{run}-pixels.log').write_text(result.stdout+result.stderr)
                    assert result.returncode==0,result.stdout+result.stderr
                    pixel=json.loads(oracle.read_text());rows=[row.strip() for row in pixel['rows']]
                    if run==0:assert '42' in rows and '0' in rows
                    else:assert '"saved"' in rows and '"undefined"' in rows and '"{\\"a\\":42}"' in rows
                    report.setdefault('screenshots',[]).append({'path':str(shot),'sha256':sha(shot),'pixel_oracle':pixel})
            wait(f'qjs: saved exact {run}\n'.encode())
            report['keyboard'].append({'process':run,'real_ps2_text_events':len(keys),'keys':keys,'evaluated_script':text})
        wait(b'qjs: two original keyboard REPL file/reopen processes PASS\n');wait(b'space> ')
        match=re.search(rb'qjs: trace (\d+) (\d+)\n',received);assert match
        address,size=map(int,match.groups());assert 0<size<=262144
        capture=out/'original-quickjs-output.bin';monitor.sendall(f'pmemsave {address:#x} {size} "{capture}"\n'.encode())
        deadline=time.monotonic()+5
        while (not capture.exists() or capture.stat().st_size!=size) and time.monotonic()<deadline:time.sleep(.02)
        output=capture.read_bytes();assert len(output)==size and b'QuickJS' in output
    assert all((ROOT / name).read_bytes() == data for name,data in contents.items()), 'source changed during run'
    assert sha(compiler) == report['compiler_sha256'] and sha(app) == report['application_sha256']
    assert b'terminal-select: 15 own CPU controls, 60 idle waits, actual fd/deadline/grant/cancel and CRLF partial-write ownership PASS' in received
    report.update(status='passed',original_application_entries=2,actual_ps2_text_events=sum(x['real_ps2_text_events'] for x in report['keyboard']),
        own_control_activations=15,own_control_idle_probes=60,
        interactive_keyboard=True,interactive_gui=a.view,original_output_sha256=sha(capture),original_output_bytes=size,
        exact_saved_files=['saved','saved'],stable_after_warmup=True)
    print(f"PASS original QuickJS: two real REPL processes, {report['actual_ps2_text_events']} PS2 events and exact saved/reopened bytes")
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
