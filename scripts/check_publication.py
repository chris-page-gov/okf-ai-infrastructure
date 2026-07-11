#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'bundle'
def main():
    d=json.loads((OUT/'okf-bundle.json').read_text()); corpus=d['corpora']['ai-infrastructure-wiki']; edges=corpus.get('relationships',corpus.get('edges',[])); errors=[]
    if len(corpus['nodes'])!=155: errors.append('expected 155 nodes')
    if len(edges)!=579: errors.append('expected 579 relationships')
    for name in ('okf-bundle.yamlld','okf-bundle.jsonld','checksums.json','index.html'):
        if not (OUT/name).is_file(): errors.append(f'missing {name}')
    if errors: print(', '.join(errors)); return 1
    print('publication validation passed: 155 nodes, 579 relationships'); return 0
if __name__=='__main__': raise SystemExit(main())
