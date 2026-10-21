"""CI-only Linux age tools from the maintainer's hash-pinned release.

No system install/PATH/service changes. Only two regular files from the official
archive are copied into a NEW ignored verification directory. Sigsum proof is
not verified by this helper; archive digest comes from the reviewed release.
"""
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import platform
import tarfile
from urllib.request import urlopen
from uuid import uuid4

URL='https://github.com/FiloSottile/age/releases/download/v1.3.2/age-v1.3.2-linux-amd64.tar.gz'
DIGEST='cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10'


def main():
    if platform.system()!='Linux' or platform.machine() not in ('x86_64','AMD64'):
        raise SystemExit('This CI-only provisioning helper requires Linux amd64')
    from app.backup_crypto import validate_age
    root=Path(__file__).resolve().parent.parent/'.verification'/'phase9-tools'/('age-ci-'+uuid4().hex)
    with urlopen(URL,timeout=60) as response:
        data=response.read(25*1024*1024+1)
    if len(data)>25*1024*1024 or sha256(data).hexdigest()!=DIGEST:
        raise SystemExit('Official age archive digest/size verification failed')
    files={}
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
        for member in archive:
            if member.name not in ('age/age','age/age-keygen'):continue
            if not member.isreg() or member.pax_headers or not 0<member.size<=64*1024*1024 or member.name in files:
                raise SystemExit('Unexpected native tool archive member')
            with archive.extractfile(member) as source:files[member.name]=source.read(64*1024*1024+1)
    if set(files)!= {'age/age','age/age-keygen'}:raise SystemExit('Missing native encryption tools')
    root.mkdir(parents=True,mode=0o700)
    provenance=[]
    for name,data in files.items():
        target=root/name.split('/')[-1]
        with target.open('xb') as output:output.write(data)
        target.chmod(0o700)
        provenance.append(dict(name=target.name,sha256=sha256(data).hexdigest()))
    executable=root/'age';digest=next(f['sha256'] for f in provenance if f['name']=='age')
    validate_age(executable,digest)
    (root/'provenance.json').write_text(json.dumps(dict(version='1.3.2',asset=URL,asset_sha256=DIGEST,
        files=provenance,sigsum_verified=False),indent=2)+'\n',encoding='utf-8')
    environment=Path(os.environ['GITHUB_ENV'])
    with environment.open('a',encoding='utf-8') as output:
        output.write(f'TEST_AGE_BIN={executable}\nTEST_AGE_SHA256={digest}\nREQUIRE_BACKUP_ENCRYPTION=1\n')
    print('Pinned native age tools provisioned only for isolated CI verification')


if __name__=='__main__':main()
