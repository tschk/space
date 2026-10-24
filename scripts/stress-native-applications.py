#!/usr/bin/env python3
"""Retain every fresh-boot native application run, including serial failures."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--image', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--runs', type=int, default=8)
a=p.parse_args()
if a.runs<1:p.error('--runs must be positive')
out=a.out.resolve();image=a.image.resolve()
if out.exists() and any(out.iterdir()):p.error('--out must be new or empty')
out.mkdir(parents=True,exist_ok=True)
report={'image':str(image),'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'runs':[]}
for index in range(a.runs):
    destination=out/f'run-{index+1:02d}'
    with (out/f'run-{index+1:02d}.log').open('w') as log:
        result=subprocess.run([sys.executable,str(Path(__file__).with_name('check-native-applications.py')),
                               '--image',str(image),'--out',str(destination)],stdout=log,stderr=subprocess.STDOUT)
    child=json.loads((destination/'report.json').read_text())
    entry={'number':index+1,'returncode':result.returncode,'report':str(destination/'report.json'),
           'scenarios':child['scenarios'],'last_input':child.get('inputs',[None])[-1],
           'last_wait':child.get('last_wait'),'last_render':child.get('last_render')}
    report['runs'].append(entry)
    report['passed_runs']=sum(item['returncode']==0 for item in report['runs'])
    report['failed_runs']=len(report['runs'])-report['passed_runs']
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f"Run {index+1}/{a.runs}: {'PASS' if result.returncode==0 else 'FAIL'}",flush=True)
print(f"{report['passed_runs']} passed, {report['failed_runs']} failed; {out/'report.json'}")
sys.exit(1 if report['failed_runs'] else 0)
