#!/usr/bin/env python3
"""Execute the actual hex-dump byte formatter for all 256 byte values."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--in', dest='compiler', required=True)
parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1]/'components/app-hd.in')
args = parser.parse_args()
text = args.source.read_text()
start = text.index('fn hd-byte(')
function = text[start:text.index('\n}',start)+2]
expected = [ord(char) for byte in range(256) for char in f'{byte:02x}']
source = 'var expected:[Int]=['+','.join(map(str,expected))+'];\n' + '''var output:[Int]=[0,0];var position:Int=0;
fn lib-put(port:Int,ch:Int)->Void{output[position]=ch;position+=1;}
'''+function+'''
fn main()->Int{
 let byte=0;while byte<256{
  position=0;hd-byte(0,byte);
  if position!=2 || output[0]!=expected[byte*2] || output[1]!=expected[byte*2+1]{return 1000+byte;}
  byte+=1;
 }
 return 42;
}
'''
with tempfile.TemporaryDirectory(prefix='space-hd-byte-') as directory:
    path = Path(directory)/'hd-byte.in'
    path.write_text(source)
    for profile in ('default','lean','harden'):
        result = subprocess.run([args.compiler,'compile','--path',str(path),'--target','jit',
                                 '--entry','main','--profile',profile,'--out',str(Path(directory)/profile),'--json'],capture_output=True,text=True)
        if not result.stdout.strip():
            raise SystemExit(f'FAIL {profile}: {result.stderr}')
        report = json.loads(result.stdout)
        if result.returncode or not report.get('success') or report.get('eval_result')!={'Int':42}:
            raise SystemExit(f'FAIL {profile}: {result.stdout}\n{result.stderr}')
        print(f'PASS {profile}: all 256 bytes format as two lowercase hexadecimal digits')
