#!/usr/bin/env python3
"""Validate packaged instruction-only Agent Skills. Safe: never executes skills."""
from pathlib import Path
import re,sys
root=Path(__file__).resolve().parents[1]/'.agents'/'skills'
seen=set(); errors=[]
for f in sorted(root.glob('*/SKILL.md')):
 s=f.read_text(encoding='utf-8')
 match=re.match(r'\A---\n(?P<front>.*?)\n---\n',s,re.S)
 if not match: errors.append(f'{f}: YAML frontmatter missing');continue
 meta=dict(re.findall(r'^([a-z_]+):\s*(.*)$',match.group('front'),re.M))
 n=meta.get('name','');d=meta.get('description','')
 if n!=f.parent.name: errors.append(f'{f}: name mismatch')
 if not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*',n or ''): errors.append(f'{f}: invalid slug')
 if n in seen: errors.append(f'{f}: duplicate name')
 if not d or len(d)>1024: errors.append(f'{f}: invalid description')
 if len(s.splitlines())<10: errors.append(f'{f}: suspiciously short')
 seen.add(n)
print(f'Checked {len(seen)} skills; errors={len(errors)}')
for e in errors:print(e)
sys.exit(bool(errors))
