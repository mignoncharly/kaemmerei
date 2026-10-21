"""Private staged storage; absence of a successful scanner never permits download."""
from dataclasses import dataclass
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from pathlib import Path,PurePosixPath
import json
import os
import re
import stat
import subprocess
from uuid import uuid4
from zipfile import ZipFile,BadZipFile
from xml.etree import ElementTree as ET
from fastapi import HTTPException
from fastapi.responses import Response
from sqlalchemy import select

MAX_BYTES=25*1024*1024
KEY=re.compile(r'[0-9a-f]{32}\.(?:pdf|docx|xlsx|pptx|odt|ods|odp|txt|csv|png|jpg|jpeg|gif)\Z')
MEDIA={'.pdf':'application/pdf','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
 '.xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
 '.pptx':'application/vnd.openxmlformats-officedocument.presentationml.presentation',
 '.odt':'application/vnd.oasis.opendocument.text','.ods':'application/vnd.oasis.opendocument.spreadsheet',
 '.odp':'application/vnd.oasis.opendocument.presentation','.txt':'text/plain','.csv':'text/csv',
 '.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.gif':'image/gif'}


def reject_links(path):
    for parent in (path,*path.parents):
        if parent.is_symlink() or parent.is_junction():
            raise ValueError('Linked storage paths are not permitted')


def validate_storage_setting(root):
    root=Path(root).absolute()
    reject_links(root)
    root=root.resolve()
    for served in (Path(__file__).parent/'static',Path(__file__).parent/'templates',Path(__file__).parent.parent/'public'):
        served=served.resolve()
        if root==served or root in served.parents or served in root.parents:
            raise ValueError('Document storage must be outside public/static/template roots')


def ensure_storage(settings):
    root=Path(settings.document_storage_dir).absolute()
    validate_storage_setting(root)
    # Python's special Windows mode 0700 creates a new DACL which excludes a
    # managed restricted token. Development inherits the workspace ACL; production
    # requires a separately provisioned and verified private Windows directory.
    if settings.production and os.name=='nt' and not root.exists():
        raise ValueError('Provision private Windows storage as the service identity before startup')
    mode=0o777 if os.name=='nt' and not settings.production else 0o700
    root.mkdir(mode=mode,parents=True,exist_ok=True)
    def verify_private(path):
        if os.name=='nt':
            # Read ACL only. Existing operator-owned directories are never re-ACL'd.
            script="$a=Get-Acl -LiteralPath $env:OHVR_STORAGE_ACL_PATH; @($a.Access | Where-Object {$_.AccessControlType -eq 'Allow'} | ForEach-Object {$_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value}) | ConvertTo-Json -Compress"
            try:
                sid=subprocess.run(['whoami','/user','/fo','csv','/nh'],capture_output=True,text=True,check=True,timeout=10).stdout.split(',')[-1].strip().strip('"')
                output=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],env={**os.environ,'OHVR_STORAGE_ACL_PATH':str(path)},capture_output=True,text=True,check=True,timeout=10)
                allowed=json.loads(output.stdout)
                if isinstance(allowed,str):allowed=[allowed]
                if not allowed or any(x not in (sid,'S-1-5-18','S-1-5-32-544') for x in allowed):
                    raise ValueError('Storage ACL permits other identities')
            except Exception:
                raise ValueError('Private Windows storage ACL must be provisioned and verified by the operator') from None
        elif path.stat().st_mode & 0o077:
            raise ValueError('Production storage requires owner-only permissions')
    if settings.production:verify_private(root)
    for area in ('staging','blobs'):
        path=root/area;reject_links(path);path.mkdir(mode=mode,exist_ok=True)
        if settings.production:verify_private(path)
    return root


def storage_path(root,area,key):
    if area not in ('staging','blobs','legacy') or not KEY.fullmatch(key or ''):
        raise ValueError('Invalid private storage identity')
    root=Path(root).absolute();reject_links(root)
    path=root/key if area=='legacy' else root/area/key
    reject_links(path)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Storage escape rejected')
    return path


def read_private(path):
    reject_links(path)
    fd=os.open(path,os.O_RDONLY | getattr(os,'O_NOFOLLOW',0) | getattr(os,'O_BINARY',0))
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>MAX_BYTES:
            raise ValueError('Invalid private blob')
        data=stream.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES:raise ValueError('Oversize private blob')
    return data


def validate_content(data,suffix):
    if not data or len(data)>MAX_BYTES or suffix not in MEDIA:
        raise ValueError('Unsupported, empty or oversized document; legacy binary Office and RTF are disabled')
    if suffix in ('.docx','.xlsx','.pptx','.odt','.ods','.odp'):
        from io import BytesIO
        try:
            with ZipFile(BytesIO(data)) as archive:
                entries=archive.infolist();names=[x.filename for x in entries]
                if len(entries)>1000 or len(names)!=len(set(names)) or sum(x.file_size for x in entries)>100*1024*1024:
                    raise ValueError('Unsafe archive bounds')
                for item in entries:
                    name=PurePosixPath(item.filename)
                    if (name.is_absolute() or '..' in name.parts or '\\' in item.filename or ':' in item.filename
                        or item.flag_bits & 1 or stat.S_ISLNK(item.external_attr >> 16)
                        or item.file_size>20*1024*1024 or item.file_size>max(1,item.compress_size)*200):
                        raise ValueError('Unsafe archive member')
                    if any(x in item.filename.casefold() for x in ('vba','activex','embeddings/','scripts/','basic/','macros/','externallinks/')):
                        raise ValueError('Active content is prohibited')
                    if name.suffix.casefold() in ('.bin','.exe','.dll','.ocx','.js','.vbs','.svg','.html','.htm'):
                        raise ValueError('Executable and active embedded parts prohibited')
                def xml(name):
                    if archive.getinfo(name).file_size>2*1024*1024:raise ValueError('XML part exceeds limit')
                    raw=archive.read(name)
                    if b'\x00' in raw or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('XML entities and NUL-encoded XML prohibited')
                    return ET.fromstring(raw)
                if suffix in ('.docx','.xlsx','.pptx'):
                    part={'.docx':'word/document.xml','.xlsx':'xl/workbook.xml','.pptx':'ppt/presentation.xml'}[suffix]
                    types=xml('[Content_Types].xml');xml(part)
                    expected={'.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml',
                        '.xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml',
                        '.pptx':'application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml'}[suffix]
                    if not any(x.attrib.get('PartName')=='/'+part and x.attrib.get('ContentType')==expected for x in types):
                        raise ValueError('Container type does not match extension')
                    for node in types:
                        if any(x in node.attrib.get('ContentType','').casefold() for x in ('macro','oleobject','activex')):
                            raise ValueError('Active Office content prohibited')
                else:
                    if archive.read('mimetype').decode('ascii')!=MEDIA[suffix]:raise ValueError('Wrong OpenDocument type')
                    xml('content.xml');xml('META-INF/manifest.xml')
                # Inspect all XML and relationship parts; no extraction or network fetch.
                for name in names:
                    if name.endswith(('.xml','.rels')):
                        tree=xml(name)
                        for node in tree.iter():
                            local=node.tag.rsplit('}',1)[-1].casefold()
                            if local in ('script','event-listener','object','object-ole','oleobj','oleobject') or node.attrib.get('TargetMode')=='External':
                                raise ValueError('Scripts, embedded objects and external relationships prohibited')
                            if local in ('instrtext','fldsimple') and re.search(r'\b(?:DDE|DDEAUTO|INCLUDETEXT|INCLUDEPICTURE)\b',
                                    ' '.join([node.text or '',*node.attrib.values()]),re.I):
                                raise ValueError('Dynamic external Office fields prohibited')
        except (BadZipFile,KeyError,ET.ParseError,UnicodeError,RuntimeError) as exc:
            raise ValueError('Invalid Office/OpenDocument container') from None
    elif suffix in ('.txt','.csv'):
        data.decode('utf-8-sig')
        if b'\x00' in data:raise ValueError('Binary text document')
    else:
        signatures={'.pdf':(b'%PDF-',),'.png':(b'\x89PNG\r\n\x1a\n',),'.jpg':(b'\xff\xd8\xff',),
            '.jpeg':(b'\xff\xd8\xff',),'.gif':(b'GIF87a',b'GIF89a')}
        if not data.startswith(signatures[suffix]):raise ValueError('Content/header mismatch')
    return MEDIA[suffix]


async def stage_upload(upload,root):
    filename=(upload.filename or '').replace('\\','/').rsplit('/',1)[-1].strip()
    suffix=Path(filename).suffix.casefold()
    if len(filename)>200 or suffix not in MEDIA:
        await upload.close()
        raise HTTPException(400,'Unsupported document type')
    key=uuid4().hex+suffix
    path=storage_path(root,'staging',key)
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_BINARY',0),0o600)
        size=0
        with os.fdopen(fd,'wb') as stream:
            while chunk:=await upload.read(65536):
                size+=len(chunk)
                if size>MAX_BYTES:raise HTTPException(413,'Document exceeds 25 MB')
                stream.write(chunk)
            stream.flush();os.fsync(stream.fileno())
        data=read_private(path)
        media=validate_content(data,suffix)
        return {'filename':filename,'storage_key':key,'size_bytes':len(data),'sha256':sha256(data).hexdigest(),
                'content_type':media,'path':path}
    except ValueError:
        path.unlink(missing_ok=True)
        raise HTTPException(400,'Document content rejected by static policy') from None
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


@dataclass(frozen=True)
class ScanResult:
    outcome:str
    version:str|None=None


class ClamAVScanner:
    def __init__(self,settings):self.settings=settings

    def scan(self,data):
        binary=self.settings.clamav_executable
        if binary is None:return ScanResult('unavailable')
        command=[str(binary)]
        if self.settings.clamav_database_dir is not None:
            command+=['--database='+str(self.settings.clamav_database_dir)]
        environment={**os.environ,'LC_ALL':'C','TZ':'UTC'}
        try:
            version=subprocess.run(command+['--version'],env=environment,capture_output=True,timeout=10,check=True).stdout.decode('ascii').strip()
            parts=version.split('/')
            if len(parts)!=3 or not re.fullmatch(r'ClamAV [0-9][0-9A-Za-z.+-]{0,60}',parts[0]) or not parts[1].isdigit():
                return ScanResult('invalid_database')
            stamp=datetime.strptime(parts[2],'%a %b %d %H:%M:%S %Y').replace(tzinfo=timezone.utc)
            age=datetime.now(timezone.utc)-stamp
            if age<timedelta(hours=-2) or age>timedelta(hours=self.settings.scanner_max_age_hours):
                return ScanResult('stale_database',version[:200])
            result=subprocess.run(command+['--no-summary','--alert-encrypted=yes','--alert-exceeds-max=yes','--alert-macros=yes',
                '--max-filesize=30M','--max-scansize=100M','-'],input=data,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                env=environment,timeout=self.settings.scanner_timeout,check=False)
            return ScanResult({0:'clean',1:'infected'}.get(result.returncode,'error'),version[:200])
        except (OSError,subprocess.SubprocessError,ValueError,UnicodeError):
            return ScanResult('error')


def new_document(db,contract,user,stored,*,replaces=None):
    from app.models import ContractDocument,DocumentJob
    document=ContractDocument(contract_id=contract.id,uploaded_by_id=user.id,original_filename=stored['filename'],
        storage_key=stored['storage_key'],content_type=stored['content_type'],size_bytes=stored['size_bytes'],
        sha256=stored['sha256'],state='quarantined',scan_result='pending',provenance='upload',
        replaces_id=replaces.id if replaces else None,replaces_version=replaces.version if replaces else None)
    db.add(document);db.flush()
    db.add(DocumentJob(document_id=document.id,contract_id=contract.id))
    return document


def process_document(db,settings,scanner,document_id,*,user=None,fault=lambda point:None):
    from app.models import Contract,ContractDocument,DocumentJob,now_utc
    from app.workflow import begin_mutation
    from app.identity_service import lock_identities,audit
    reference=db.get(ContractDocument,document_id)
    if reference is None:
        db.rollback();return 'missing'
    contract_id,key,state=reference.contract_id,reference.storage_key,reference.state
    if state in ('available','rejected','superseded','disposed','link'):
        db.rollback();return state
    parent=db.get(Contract,contract_id)
    if parent.archived_at is not None:
        db.rollback();return 'archived'
    expected_digest=reference.sha256
    root=ensure_storage(settings)
    data=media=digest=None
    try:
        stage=storage_path(root,'staging',key);final=storage_path(root,'blobs',key)
        source=stage if stage.exists() else final if final.exists() else storage_path(root,'legacy',key)
        data=read_private(source)
        digest=sha256(data).hexdigest()
        if expected_digest and digest!=expected_digest:raise ValueError('digest_mismatch')
        media=validate_content(data,Path(key).suffix)
    except (ValueError,OSError):
        data=None
    # No database/identity/parent lock is held during a slow external scan.
    # Publication below revalidates the live principal, parent and exact bytes.
    db.rollback()
    fault('before_scan')
    result=scanner.scan(data) if data is not None else ScanResult('integrity_or_storage')
    fault('after_scan')
    if user is not None:contract=begin_mutation(db,user,contract_id)
    else:
        lock_identities(db)
        contract=db.scalar(select(Contract).where(Contract.id==contract_id).with_for_update())
        if contract is None or contract.archived_at is not None:
            db.rollback();return 'archived'
    document=db.get(ContractDocument,document_id)
    if document.state in ('available','rejected','superseded','disposed','link'):
        state=document.state;db.rollback();return state
    job=db.get(DocumentJob,document_id)
    if job is None:
        job=DocumentJob(document_id=document.id,contract_id=contract_id);db.add(job)
    job.attempts+=1;job.updated_at=now_utc()
    document.scan_result=result.outcome;document.scanner_version=result.version;document.scanned_at=now_utc()
    try:
        if data is None or document.storage_key!=key or (document.sha256 and document.sha256!=digest):
            raise ValueError('integrity_failure')
        document.sha256=digest;document.verified_media_type=media
        if result.outcome=='clean':
            predecessor=db.get(ContractDocument,document.replaces_id) if document.replaces_id else None
            if predecessor and (predecessor.contract_id!=contract_id or predecessor.state in ('superseded','disposed')):
                raise ValueError('replacement_conflict')
            if read_private(source)!=data:raise ValueError('digest_mismatch')
            if source!=final:
                if final.exists():
                    if sha256(read_private(final)).hexdigest()!=digest:raise ValueError('destination_conflict')
                elif source==storage_path(root,'legacy',key):
                    fd=os.open(final,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_BINARY',0),0o600)
                    with os.fdopen(fd,'wb') as stream:
                        stream.write(data);stream.flush();os.fsync(stream.fileno())
                else:os.replace(source,final)
            fault('after_finalize')
            document.state='available';document.provenance='verified_upload';job.state='done';job.last_error=None
            if predecessor:
                predecessor.state='superseded';predecessor.version+=1
        elif result.outcome=='infected':
            document.state='rejected';job.state='rejected';job.last_error='infected'
        else:
            document.state='quarantined';job.state='retry';job.last_error=result.outcome[:40]
    except (ValueError,OSError):
        document.state='quarantined';job.state='retry';job.last_error='integrity_or_storage'
    document.version+=1
    audit(db,user.id if user else None,'document_processed',f'document:{document.id}',state=document.state,result=document.scan_result)
    fault('before_commit')
    db.commit()
    return document.state


def download_response(db,settings,document,request,*,actor=None,token=None):
    from app.models import SecurityEvent,now_utc
    from urllib.parse import quote
    # Capture identifiers before committing the dedicated append-only access event.
    allowed=document.state=='available' and document.scan_result=='clean' and bool(document.sha256)
    data=None
    if allowed:
        try:
            data=read_private(storage_path(settings.document_storage_dir,'blobs',document.storage_key))
            allowed=sha256(data).hexdigest()==document.sha256 and len(data)==document.size_bytes
        except (OSError,ValueError):allowed=False
    # A narrow SECURITY DEFINER insert path is installed for actual runtime roles.
    details={'document_id':document.id,'operation':'download'}
    correlation=db.info.get('request_context',{}).get('correlation_id') or str(uuid4())
    if db.info.get('enforce_rls'):
        from sqlalchemy import text
        db.execute(text('SELECT ohvr_security.document_access(:doc,:allowed)'),{'doc':document.id,'allowed':allowed})
    else:
        db.add(SecurityEvent(actor_id=actor.id if actor else None,token_id=token.id if token else None,
            principal='user' if actor else 'token',action='DOCUMENT_ACCESS',target=f'document:{document.id}',
            contract_id=document.contract_id,created_at=now_utc(),outcome='success' if allowed else 'denied',
            correlation_id=correlation,details=details))
    name=document.original_filename;media=document.verified_media_type
    db.commit()
    if not allowed:raise HTTPException(409,'Document is unavailable or failed integrity verification')
    headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(name,safe=''),
        'Accept-Ranges':'bytes','X-Content-Type-Options':'nosniff','Content-Security-Policy':"sandbox; default-src 'none'",'Cache-Control':'private, no-store'}
    range_header=request.headers.get('range')
    if range_header:
        if len(range_header)>64:return Response(status_code=416,headers={**headers,'Content-Range':f'bytes */{len(data)}'})
        match=re.fullmatch(r'bytes=(\d*)-(\d*)',range_header)
        if not match or not any(match.groups()):return Response(status_code=416,headers={**headers,'Content-Range':f'bytes */{len(data)}'})
        a,b=match.groups()
        start=int(a) if a else max(0,len(data)-int(b))
        end=min(len(data)-1,int(b)) if a and b else len(data)-1
        if start>end or start>=len(data):return Response(status_code=416,headers={**headers,'Content-Range':f'bytes */{len(data)}'})
        return Response(data[start:end+1],status_code=206,media_type=media,headers={**headers,'Content-Range':f'bytes {start}-{end}/{len(data)}'})
    return Response(data,media_type=media,headers=headers)


def reconcile(db,root):
    from app.models import ContractDocument
    report={'missing':[],'mismatched':[],'pending':[],'orphans':[],'unsafe':[]}
    known=set()
    for doc in db.scalars(select(ContractDocument)):
        if not doc.storage_key:continue
        known.add(doc.storage_key)
        if doc.state not in ('available','superseded','disposed','rejected'):report['pending'].append(doc.id)
        try:
            candidates=[storage_path(root,area,doc.storage_key) for area in ('blobs','staging','legacy')]
            present=[p for p in candidates if p.exists()]
            if not present:report['missing'].append(doc.id)
            elif doc.sha256 and any(sha256(read_private(p)).hexdigest()!=doc.sha256 for p in present):report['mismatched'].append(doc.id)
        except (ValueError,OSError):report['unsafe'].append(doc.id)
    for area in ('staging','blobs','legacy'):
        directory=Path(root) if area=='legacy' else Path(root)/area
        reject_links(directory)
        if directory.exists():
            for path in directory.iterdir():
                if area=='legacy' and path.name in ('staging','blobs'):continue
                if path.name not in known:report['orphans'].append({'area':area,'key':path.name if KEY.fullmatch(path.name) else 'unclassified'})
    return report


def audit_denied(db,document_id,*,actor=None,token=None):
    from app.models import SecurityEvent,now_utc
    from sqlalchemy import text
    safe_id=document_id if 0<document_id<2147483648 else 0
    if db.info.get('enforce_rls'):
        db.execute(text('SELECT ohvr_security.document_access(:doc,false)'),{'doc':safe_id})
    else:
        db.add(SecurityEvent(actor_id=actor.id if actor else None,token_id=token.id if token else None,
            principal='user' if actor else 'token',action='DOCUMENT_ACCESS',target=f'document:{safe_id}',
            created_at=now_utc(),outcome='denied',correlation_id=db.info.get('request_context',{}).get('correlation_id') or str(uuid4()),
            details={'requested_document_id':safe_id,'operation':'download'}))
    db.commit()


def disposal_eligibility(document):
    return {'eligible':False,'reason':'legal_hold' if document.legal_hold else 'retention_policy_not_approved'}
