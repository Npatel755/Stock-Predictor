"""Install user-supplied local skill directories, backing up differing files.

Archive prompts/READMEs are reference documents, never commands. No bundled
program is executed, and non-skill top-level files are not activated.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import zipfile


def digest(blob): return hashlib.sha256(blob).hexdigest()


def main():
    home=Path.home();root=home/'.codex/skills';root.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup=home/'.codex/skill-install-backups'/stamp
    archives=[home/'Downloads'/n for n in ('claude-skills.zip','devin-news-trading-intelligence-addon.zip','devin-quant-skills-complete-43.zip')]
    records=[];sources=[]
    for path in archives:
        sources.append(dict(path=str(path),sha256=digest(path.read_bytes())))
        with zipfile.ZipFile(path) as z:
            files={}
            assert sum(i.file_size for i in z.infolist())<64*1024*1024
            for info in z.infolist():
                n=PurePosixPath(info.filename.replace('\\','/'))
                if n.is_absolute() or '..' in n.parts or any(':' in p for p in n.parts):
                    raise ValueError('Unsafe archive path')
                if (info.external_attr>>16)&0o170000==0o120000: raise ValueError('Archive symlink')
                if not info.is_dir():
                    if str(n) in files: raise ValueError('Duplicate archive file')
                    files[str(n)]=z.read(info)
            for n in sorted(files):
                if PurePosixPath(n).name!='SKILL.md':continue
                folder=PurePosixPath(n).parent;name=folder.name
                if not re.fullmatch(r'[a-z0-9-]+',name): raise ValueError('Unsafe skill name')
                body=files[n].decode('utf-8-sig')
                declared=re.search(r'^name:\s*(.+)\s*$',body,re.M)
                if not body.startswith('---') or not declared or declared.group(1).strip()!=name:
                    raise ValueError('Invalid skill frontmatter: '+name)
                if not re.search(r'^description:\s*\S',body,re.M):raise ValueError('Missing description')
                dest=root/name
                if not dest.resolve().is_relative_to(root.resolve()):raise ValueError('Destination escapes skill root')
                prefix=str(folder)+'/'
                members={k[len(prefix):]:v for k,v in files.items() if k.startswith(prefix)}
                existing=dest.exists()
                changes=[r for r,b in members.items() if not (dest/r).exists() or (dest/r).read_bytes().replace(b'\r\n',b'\n')!=b.replace(b'\r\n',b'\n')]
                status='already_present' if not changes else 'updated_with_backup' if existing else 'installed'
                saved=None
                if changes:
                    if existing:
                        saved=backup/name;saved.parent.mkdir(parents=True,exist_ok=True)
                        shutil.copytree(dest,saved)
                    for rel,blob in members.items():
                        target=dest/rel
                        if not target.resolve().is_relative_to(root.resolve()):raise ValueError('File escapes skill root')
                        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(blob)
                for rel,blob in members.items():
                    assert (dest/rel).read_bytes().replace(b'\r\n',b'\n')==blob.replace(b'\r\n',b'\n')
                records.append(dict(name=name,status=status,archive=path.name,destination=str(dest),backup=str(saved) if saved else None,
                    files={r:digest((dest/r).read_bytes()) for r in members}))
    result=dict(installed_at=stamp,archives=sources,skills=records,
        counts={s:sum(x['status']==s for x in records) for s in ('installed','updated_with_backup','already_present')},
        total_skills=len(records),bundled_programs_executed=False,non_skill_prompts_activated=False)
    project=Path(__file__).resolve().parents[1]
    report=project/'quant_trading_bot/reports/SKILL_ARCHIVE_INSTALL_20261111.json'
    report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(counts=result['counts'],total_skills=result['total_skills'],manifest=str(report),backup_root=str(backup)),indent=2))


if __name__=='__main__':main()
