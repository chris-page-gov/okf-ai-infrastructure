#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'bundle'
def main():
    d=json.loads((OUT/'okf-bundle.json').read_text()); corpus=d['corpora']['ai-infrastructure-wiki']; edges=corpus.get('relationships',corpus.get('edges',[])); errors=[]
    if d.get('okf_version')!='0.2': errors.append('expected OKF 0.2')
    if d.get('generated')!={'by':'process:okf-ai-infrastructure-publication','at':'2026-07-25T11:16:40Z'}: errors.append('missing structured publication provenance')
    if len(corpus['nodes'])!=155: errors.append('expected 155 nodes')
    if len(edges)!=579: errors.append('expected 579 relationships')
    for node_id,node in corpus['nodes'].items():
        if node_id.endswith('/index.md') or node_id in {'index.md','log.md'}: continue
        if not str(node.get('type','')).strip(): errors.append(f'{node_id} missing type')
        if 'timestamp' in node: errors.append(f'{node_id} retains legacy timestamp')
        if node.get('status') not in {'draft','stable','deprecated'}: errors.append(f'{node_id} has invalid status')
        sources=node.get('sources')
        if sources is not None and (not isinstance(sources,list) or any(not isinstance(source,dict) or not source.get('resource') for source in sources)): errors.append(f'{node_id} has invalid sources')
    for name in ('okf-bundle.yamlld','okf-bundle.jsonld','checksums.json','index.html'):
        if not (OUT/name).is_file(): errors.append(f'missing {name}')
    if errors: print(', '.join(errors)); return 1
    print('publication validation passed: 155 nodes, 579 relationships'); return 0
if __name__=='__main__': raise SystemExit(main())
