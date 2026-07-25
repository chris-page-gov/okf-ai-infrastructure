# AI Infrastructure OKF Bundle Wiki

Independent human-first Markdown/YAML-LD knowledge bundle covering AI
infrastructure, standards, federated systems, research and UK public-sector
implications. The Explorer projection contains 155 concepts and 579 typed
relationships.

```sh
python3 scripts/migrate_okf_v02.py --check
python3 scripts/build_okf_bundle.py --check
python3 scripts/update_viewer.py --check
python3 scripts/build_publication.py
python3 scripts/check_publication.py
```

Markdown with structured YAML-LD frontmatter remains the source of truth;
JSON-LD and Explorer JSON are publication projections. The Markdown layer
conforms to OKF v0.2: only the root index declares `okf_version`, reserved
indexes/logs have no concept frontmatter, concepts require `type`, and
source-backed concepts use standard `sources`. The invalid actor-free legacy
`verified: "yes"` flag is deliberately not promoted into a trust claim.
