"""Run extracted command-bar logic with deterministic record-memory adapters.

Kernel freestanding string literals are raw pointers. The hosted test frontend
uses Typ::String instead, so fixture generation interns literal bytes into the
modeled heap and replaces literals with numeric offsets. This adapts memory
representation, not filtering/geometry/dispatch algorithms. These checks do not
establish QEMU rendering or input behavior.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, timeout):
    command = [str(argument) for argument in command]
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    return {"command": command, "exit": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--in", dest="compiler", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
parser.add_argument("--group", choices=("all", "baseline", "lifecycle"), default="all")
a = parser.parse_args()
a.compiler = a.compiler.resolve()
a.out = a.out.resolve()
a.out.mkdir(parents=True, exist_ok=False)
root = Path(__file__).resolve().parents[1]
inputs = [root / "components" / name for name in
          ("display.in", "display-commandbar.in", "display-layout.in", "display-seat.in")]
input_hashes = {str(path.relative_to(root)): sha256(path) for path in inputs}
text = "\n".join(path.read_text() for path in inputs)


def function(name):
    start = text.index("fn " + name + "(")
    return text[start:text.index("\n}", start) + 2]


constants = "\n".join(line for line in text.splitlines()
                      if line.startswith("const COMP-")
                      and not line.startswith("const COMP-TERM-"))
base = "var heap:[Int]=[" + ",".join(["0"] * 4096) + """ ];
var comp-windows:Int=8;
var comp-count:Int=3;
var comp-focused:Int=0;
var comp-dragging:Int=1;
var comp-drag-mode:Int=2;
var fb-width:Int=1921;
var fb-height:Int=1080;
var damage:Int=0;
var comp-bar-titles:Int=0;
var comp-launcher-query:Int=0;
var comp-launcher-len:Int=0;
fn comp-win-base(i:Int)->Int{return comp-windows+i*COMP-WIN-SIZE;}
fn load8(p:Int)->Int{return heap[p];}
fn load32(p:Int)->Int{return heap[p];}
fn load64(p:Int)->Int{return heap[p];}
fn store32(p:Int,v:Int)->Void{heap[p]=v;}
fn store64(p:Int,v:Int)->Void{heap[p]=v;}
fn alloc(size:Int)->Int{return 1500;}
fn comp-win-damage(i:Int)->Void{damage=damage+1;return;}
""" + constants + "\n" + "\n".join(function(name) for name in (
    "comp-bar-set-title", "comp-bar-init", "comp-tile-count", "comp-tile-ready", "comp-tile-windows",
    "comp-bar-terminal", "comp-bar-title", "comp-bar-enabled",
    "comp-launcher-matches", "comp-launcher-at")) + "\n"

cases = []
for count, width, height, minimized, success in [(0, 1921, 1080, -1, False), (1, 1921, 1080, -1, True), (2, 1921, 1080, -1, True), (3, 1921, 1080, -1, True), (3, 1921, 1080, 1, True), (3, 800, 1080, -1, False), (1, 1921, 250, -1, False), (16, 1921, 1080, -1, False)]:
    visible = count - (1 if minimized >= 0 else 0)
    init = f'comp-count={count};fb-width={width};fb-height={height};let i=0;while i<comp-count{{let b=comp-win-base(i);store32(b+4,101+i);store32(b+8,201+i);store32(b+12,301+i);store32(b+16,401+i);store32(b+20,1);i=i+1;}}'
    if minimized >= 0:
        init += f'store32(comp-win-base({minimized})+20,8);'
    body = init + f'if comp-tile-windows()!={int(success)}{{return 1;}}'
    if success:
        body += f'if damage!={visible * 2} || comp-dragging!=-1 || comp-drag-mode!=-1{{return 2;}}let last=0;let col=0;let i=0;while i<comp-count{{let b=comp-win-base(i);if i!={minimized}{{let x=load32(b+4);let y=load32(b+8);let w=load32(b+12);let h=load32(b+16);if x<16 || y!=44 || w<280 || h<180{{return 3;}}if y+h+28!={height}-44{{return 4;}}if col>0 && x!=last+16{{return 5;}}last=x+w;col=col+1;}}else{{if load32(b+4)!=101+i{{return 6;}}}}i=i+1;}}if last!={width}-16{{return 7;}}'
    else:
        body += 'if damage!=0 || comp-dragging!=1 || comp-drag-mode!=2{return 8;}let i=0;while i<comp-count{let b=comp-win-base(i);if load32(b+4)!=101+i || load32(b+16)!=401+i{return 9;}i=i+1;}'
    cases.append((f'geometry-{count}-{width}-{height}-{minimized}', base + 'fn main()->Int{' + body + 'return 42;}'))
rowbody = 'store32(comp-win-base(0)+24,"TERMINAL 1");store32(comp-win-base(0)+40,3);store32(comp-win-base(0)+32,0);store32(comp-win-base(0)+20,1);\nstore32(comp-win-base(1)+24,"UTILITIES");store32(comp-win-base(1)+20,1);\nstore32(comp-win-base(2)+24,"TERMINAL 2");store32(comp-win-base(2)+40,3);store32(comp-win-base(2)+32,1);store32(comp-win-base(2)+20,8);\ncomp-launcher-query="";comp-launcher-len=0;\nif comp-launcher-at(0)!=0 || comp-launcher-at(1)!=1 || comp-launcher-at(2)!=2 || comp-launcher-at(3)!=16 || comp-launcher-at(4)!=-1{return 1;}\ncomp-launcher-query="close";comp-launcher-len=5;if comp-launcher-at(0)!=17 || comp-launcher-at(1)!=-1{return 2;}\ncomp-launcher-query="FOCUS TERMINAL 2";comp-launcher-len=16;if comp-launcher-at(0)!=20{return 3;}\nif comp-bar-terminal(1)!=2{return 4;}\n// Simulate the real close-record shift; terminal identity must follow its record.\nstore32(comp-win-base(1)+24,"TERMINAL 2");store32(comp-win-base(1)+40,3);store32(comp-win-base(1)+32,1);comp-count=2;\nif comp-bar-terminal(1)!=1{return 5;}\ncomp-count=1;if comp-bar-terminal(1)!=-1 || comp-bar-enabled(20)!=0{return 6;}\ncomp-launcher-query="zzzz";comp-launcher-len=4;if comp-launcher-at(0)!=-1{return 7;}\nreturn 42;'
cases.append(('filtered-rows-and-terminal-identity', base + 'fn main()->Int{' + rowbody + '}'))

# Extract central lifecycle implementations, with only device/render/terminal
# effects adapted to counters. Actual focus selection, record compaction, drag
# guards and key routing remain the component functions under test.
lifecycle = base + """
var comp-launcher-open:Int=0;
var comp-drag-off-x:Int=0;
var comp-drag-off-y:Int=0;
var comp-surf-sizes:Int=3200;
var terminal-events:Int=0;
var last-terminal-slot:Int=-1;
fn store8(p:Int,v:Int)->Void{heap[p]=v;}
fn comp-dmg-add(x0:Int,y0:Int,x1:Int,y1:Int)->Void{damage=damage+1;}
fn comp-launcher-key(port:Int,key:Int)->Void{return;}
fn comp-launcher-show(port:Int)->Void{comp-launcher-open=1;}
fn comp-term-focused-slot()->Int{return load64(comp-win-base(comp-focused)+32);}
fn comp-term-scroll-by(slot:Int,lines:Int)->Void{terminal-events=terminal-events+1;}
fn comp-term-backspace(slot:Int)->Void{terminal-events=terminal-events+1;}
fn comp-term-push-line(slot:Int,line:Int)->Void{terminal-events=terminal-events+1;}
fn comp-term-input-of(slot:Int)->Int{return 0;}
fn comp-term-line-eq(slot:Int,text:Int)->Int{return 0;}
fn comp-term-seed(slot:Int,text:Int)->Void{return;}
fn comp-term-set-len(slot:Int,len:Int)->Void{return;}
fn comp-term-set-mode(slot:Int,mode:Int)->Void{return;}
fn comp-term-get-mode(slot:Int)->Int{return 0;}
fn comp-term-append(slot:Int,key:Int)->Void{
 terminal-events=terminal-events+1;last-terminal-slot=slot;
}
""" + "\n".join(function(name) for name in (
    "comp-win-clear", "comp-win-close", "comp-win-focus",
    "comp-win-minimize", "comp-handle-drag", "comp-handle-key")) + "\n"

setup = """
let i=0;while i<3{
 let b=comp-win-base(i);store32(b+4,100+i);store32(b+8,200+i);
 store32(b+12,400);store32(b+16,300);store32(b+20,1);
 store32(b+32,i);store32(b+40,COMP-ROLE-TERMINAL);i=i+1;
}
"""
lifecycle_cases = [
    ("lifecycle-close-held-drag", setup + """
comp-focused=2;comp-dragging=2;comp-drag-mode=1;
comp-win-close(2);
if comp-count!=2 || comp-focused!=1 || comp-dragging!=-1 || comp-drag-mode!=-1{return 1;}
let before=damage;comp-handle-drag(900,900);
if damage!=before || load32(comp-win-base(1)+4)!=101{return 2;}
// Closing an earlier record preserves the moved window's content identity.
comp-dragging=1;comp-drag-mode=2;comp-win-close(0);
if comp-count!=1 || comp-focused!=0 || load64(comp-win-base(0)+32)!=1{return 3;}
if comp-dragging!=-1 || comp-drag-mode!=-1{return 4;}
comp-handle-key(0,65);if terminal-events!=1 || last-terminal-slot!=1{return 5;}
comp-win-close(0);if comp-count!=0 || comp-focused!=-1{return 6;}
comp-handle-key(0,65);if terminal-events!=1{return 7;}
return 42;
"""),
    ("lifecycle-minimize-input", setup + """
comp-win-focus(0);comp-win-minimize(0);
if comp-focused!=1 || comp-dragging!=-1 || comp-drag-mode!=-1{return 1;}
let flags=load32(comp-win-base(0)+20);
if (flags&COMP-WIN-VISIBLE)!=0 || (flags&COMP-WIN-FOCUSED)!=0 || (flags&COMP-WIN-MINIMIZED)==0{return 2;}
comp-handle-key(0,65);if terminal-events!=1 || last-terminal-slot!=1{return 3;}
// Even stale focus injected by another adapter cannot dispatch hidden input.
comp-focused=0;comp-handle-key(0,65);if terminal-events!=1{return 4;}
comp-focused=comp-count;comp-handle-key(0,65);if terminal-events!=1{return 5;}
comp-focused=1;comp-win-minimize(1);if comp-focused!=2{return 6;}
comp-win-minimize(2);if comp-focused!=-1{return 7;}
comp-handle-key(0,65);if terminal-events!=1{return 8;}
return 42;
"""),
    ("lifecycle-invalid-drag", setup + """
comp-drag-mode=1;comp-dragging=-1;comp-handle-drag(900,900);
comp-dragging=comp-count;comp-handle-drag(900,900);
comp-dragging=comp-count+3;comp-handle-drag(900,900);
if damage!=0 || load32(comp-win-base(0)+4)!=100{return 1;}
// Positive control: the same actual handler moves a valid record once.
comp-dragging=1;comp-drag-mode=1;comp-drag-off-x=10;comp-drag-off-y=20;
comp-handle-drag(510,420);
if load32(comp-win-base(1)+4)!=500 || load32(comp-win-base(1)+8)!=400 || damage!=2{return 2;}
return 42;
"""),
]
if a.group == "lifecycle":
    cases = []
if a.group != "baseline":
    cases.extend((name, lifecycle + "fn main()->Int{" + body + "}")
                 for name, body in lifecycle_cases)
expected_checks = len(cases) * 6

LITERAL = re.compile(r'"(?:[^"\\]|\\.)*"')


def pointer_fixture(source):
    """Intern ASCII literal bytes above the window-table region, with NULs."""
    strings = {}
    next_offset = 2048
    initialization = []

    def replace(match):
        nonlocal next_offset
        value = json.loads(match.group())
        if value not in strings:
            encoded = value.encode("ascii")
            assert next_offset + len(encoded) + 1 <= 4096
            strings[value] = next_offset
            for offset, byte in enumerate(encoded + b"\0"):
                initialization.append(f"heap[{next_offset + offset}]={byte};")
            next_offset += len(encoded) + 1
        return str(strings[value])

    source = LITERAL.sub(replace, source)
    entry = "fn main()->Int{"
    assert source.count(entry) == 1
    source = source.replace(entry, entry + "".join(initialization) + "comp-bar-init();", 1)
    return source, strings


receipt = {
    "complete": False,
    "compiler": str(a.compiler),
    "compiler_sha256": sha256(a.compiler),
    "version": run([a.compiler, "--version"], 15),
    "runner_sha256": sha256(Path(__file__)),
    "component_sha256": input_hashes,
    "representation_adapter": "interned ASCII pointers in 4096-cell modeled heap; strings begin at 2048",
    "fixtures": [],
    "checks": [],
}


def save():
    (a.out / "results.json").write_text(json.dumps(receipt, indent=2) + "\n")


save()
try:
    for name, source in cases:
        source, strings = pointer_fixture(source)
        path = a.out / (name + ".in")
        path.write_text(source)
        receipt["fixtures"].append({"name": name, "path": str(path),
                                    "sha256": sha256(path), "interned_strings": strings})
        for target in ("jit", "native"):
            for profile in ("default", "lean", "harden"):
                out = a.out / f"{name}-{target}-{profile}"
                row = {"name": name, "target": target, "profile": profile,
                       "source_sha256": sha256(path)}
                receipt["checks"].append(row)
                row["compile"] = run([
                    a.compiler, "compile", "--path", path, "--entry", "main",
                    "--target", target, "--profile", profile, "--out", out, "--json"], 60)
                save()
                report = row["report"] = json.loads(row["compile"]["stdout"])
                artifacts = [candidate for candidate in a.out.glob(out.name + "*")
                             if candidate.is_file()]
                row["artifact_sha256"] = {str(candidate): sha256(candidate)
                                          for candidate in artifacts}
                save()
                assert row["compile"]["exit"] == 0, row
                assert report.get("success") and not report.get("external_invocations"), row
                assert not report.get("degradations"), row
                if target == "jit":
                    assert report.get("execution_started"), row
                    assert report.get("eval_result") == {"Int": 42}, row
                else:
                    row["execution"] = run([out], 15)
                    save()
                    assert row["execution"]["exit"] == 42, row
                    assert not row["execution"]["stdout"] and not row["execution"]["stderr"], row
                row["passed"] = True
                save()
    assert len(receipt["checks"]) == expected_checks
    assert sha256(a.compiler) == receipt["compiler_sha256"]
    assert sha256(Path(__file__)) == receipt["runner_sha256"]
    assert {str(path.relative_to(root)): sha256(path) for path in inputs} == input_hashes
    receipt["complete"] = True
except BaseException as error:
    receipt["failure"] = repr(error)
    raise
finally:
    save()
print(f"{len(receipt['checks'])} checks passed")
