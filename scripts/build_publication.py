#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'bundle'
DIRS=('document','federated','frameworks','glossary','organisations','research','stack','standards','uk-government')
FILES=('index.md','sources-index.md','log.md','okf.config.json','okf-bundle.json')
def main():
    OUT.mkdir(exist_ok=True)
    for name in DIRS:
        target=OUT/name
        if target.exists(): shutil.rmtree(target)
        shutil.copytree(ROOT/name,target)
    for name in FILES: shutil.copy2(ROOT/name,OUT/name)
    semantic={'@context':'https://chris-page-gov.github.io/okf-explorer/profile/bundle-wiki/v1/context.jsonld','@id':'https://chris-page-gov.github.io/okf-ai-infrastructure/','@type':'okf:Bundle','title':'AI Infrastructure OKF Wiki','description':'Agent-ready infrastructure, federated AI, standards, frameworks, research and UK public-sector implications.','version':'0.5.0','status':'preview','okf_version':'0.2','generated':{'by':'process:okf-ai-infrastructure-publication','at':'2026-07-25T11:16:40Z'},'profile':{'@id':'https://chris-page-gov.github.io/okf-explorer/profile/bundle-wiki/v1/'},'descriptor':{'@id':'https://chris-page-gov.github.io/okf-ai-infrastructure/okf-bundle.json'},'semanticDescriptor':{'@id':'https://chris-page-gov.github.io/okf-ai-infrastructure/okf-bundle.yamlld'},'home':{'@id':'https://chris-page-gov.github.io/okf-ai-infrastructure/'},'publisher':{'@id':'https://github.com/chris-page-gov'},'license':{'@id':'https://creativecommons.org/publicdomain/zero/1.0/'}}
    text=json.dumps(semantic,indent=2,sort_keys=True)+'\n'; (OUT/'okf-bundle.yamlld').write_text(text); (OUT/'okf-bundle.jsonld').write_text(json.dumps(semantic,sort_keys=True,separators=(',',':'))+'\n')
    html='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>AI Infrastructure OKF</title><style>body{font:18px/1.55 system-ui;max-width:850px;margin:4rem auto;padding:0 1.5rem}a{color:#1d70b8}</style></head><body><h1>AI Infrastructure OKF Bundle Wiki</h1><p>OKF v0.2 with 155 human-readable concepts and 579 typed relationships.</p><p><a href="https://chris-page-gov.github.io/okf-explorer/?bundle=https%3A%2F%2Fchris-page-gov.github.io%2Fokf-ai-infrastructure%2Fokf-bundle.json">Open in OKF Explorer</a></p><ul><li><a href="okf-bundle.yamlld">YAML-LD</a></li><li><a href="okf-bundle.jsonld">JSON-LD</a></li><li><a href="okf-bundle.json">Explorer JSON</a></li><li><a href="index.md">Markdown wiki index</a></li><li><a href="checksums.json">Checksums</a></li></ul></body></html>\n'; (OUT/'index.html').write_text(html)
    rows={p.relative_to(OUT).as_posix():{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in sorted(OUT.rglob('*')) if p.is_file() and p.name not in {'checksums.json','.DS_Store'}}
    (OUT/'checksums.json').write_text(json.dumps({'schema':'okf-checksums.v1','files':rows},indent=2,sort_keys=True)+'\n')
    print(f'published {len(rows):,} files')
if __name__=='__main__': main()
