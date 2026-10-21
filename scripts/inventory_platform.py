"""Non-secret local tool inventory; no package install, patch or remote lookup."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


def inventory(postgres_bin=None, age_bin=None):
    tools = {'python': (Path(sys.executable), ['--version']),
             'powershell': (shutil.which('powershell.exe'), ['-NoProfile','-NonInteractive','-Command','$PSVersionTable.PSVersion.ToString()']),
             'caddy': (shutil.which('caddy'), ['version']),
             'clamscan': (shutil.which('clamscan'), ['--version'])}
    for name in ('psql','pg_dump','pg_restore'):
        tools[name]=(Path(postgres_bin)/(name+('.exe' if os.name=='nt' else '')) if postgres_bin else shutil.which(name),['--version'])
    for name in ('age','age-keygen'):
        tools[name]=(Path(age_bin)/(name+('.exe' if os.name=='nt' else '')) if age_bin else shutil.which(name),['--version'])
    result={}
    for name,(path,arguments) in tools.items():
        if not path or not Path(path).is_file():
            result[name]={'state':'not_observed'};continue
        path=Path(path)
        try:
            if path.is_symlink():raise ValueError()
            completed=subprocess.run([str(path),*arguments],capture_output=True,timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            raw=(completed.stdout or completed.stderr).decode('utf-8',errors='replace').strip()
            if completed.returncode or len(raw)>4096:raise ValueError()
            result[name]={'state':'observed','version':raw,'sha256':sha256(path.read_bytes()).hexdigest()}
        except Exception:
            result[name]={'state':'unverified'}
    return dict(format='ohvr-platform-inventory-v1',observed_at=datetime.now(timezone.utc).isoformat(),
                system=platform.system(),release=platform.release(),version=platform.version(),
                tools=result,scope='Local development tooling only; not STRATO or production inventory',
                advisory_review='Separate maintained-advisory review and host patch acceptance required')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--postgres-bin',type=Path)
    parser.add_argument('--age-bin',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=inventory(args.postgres_bin,args.age_bin)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2);stream.write('\n')
    print('Non-secret local platform inventory written; no installed software changed.')


if __name__=='__main__':main()
