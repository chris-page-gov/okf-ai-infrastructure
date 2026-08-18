# AI Infrastructure OKF Bundle Wiki

Independent human-first Markdown/YAML-LD knowledge bundle covering AI
infrastructure, standards, federated systems, research and UK public-sector
implications. The Explorer projection contains 142 production concepts, 13
reserved navigation records and 579 typed relationships. Every production
concept has an absolute semantic identity, and every
authored local Markdown link is emitted as an evidence-bearing directed
`dcterms:references` assertion in synchronised YAML-LD, JSON-LD and Explorer
runtime projections.

## Reproducible environment

The semantic compiler requires Python 3.12 or newer because the pinned
YAML-LD implementation does. From a clean checkout, create an isolated
repository-local environment and install the reviewed exact Python package set:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --requirement requirements-okf.lock
```

`requirements-okf.txt` records the permitted direct dependency ranges;
`requirements-okf.lock` records the exact transitive Python package versions
used by the repository; the interpreter patch and operating system remain
separate execution controls. Updating dependencies is a deliberate operation:

```sh
uv pip compile requirements-okf.txt --python-version 3.12 --no-annotate --no-header --output-file requirements-okf.lock
```

## Build and check

Generate the synchronised Explorer, YAML-LD, JSON-LD, relationship and static
publication projections with:

```sh
.venv/bin/python scripts/build_okf_bundle.py
.venv/bin/python scripts/build_publication.py
```

The build validates all 579 runtime relationships and all 579 reified
counterparts against the exact shared Draft 2020-12 schema before it
writes `bundle/semantic-validation.json`; the receipt records the pinned schema
bytes and SHA-256 plus assertion-identity, payload and direct-triple digests.

`okf.config.json` records the reviewed release baseline in
`releaseExpectedCounts`. A legitimate corpus or relationship change updates
that data and the release documentation deliberately; it does not require an
edit to validation code. The build fails if the generated counts and declared
baseline differ.

The `semantic_layer.outputs` entries in `okf.semantic.json` enumerate only
artefacts with governed Bundle Wiki v1 semantic or Reader roles. The static
publication also generates `bundle/index.html` and `bundle/checksums.json`,
copies the four root Markdown/configuration surfaces, and copies all Markdown
under the nine corpus directories into `bundle/`. Repository-contract v1 has
no truthful generic role for those HTML, Markdown and configuration outputs,
so the descriptor scopes them explicitly in its limitations instead of
mislabelling them. `bundle/checksums.json` binds every other published file by
exact path, byte count and SHA-256; `scripts/check_publication.py` validates the
exact file set, checksum manifest and byte-exact source/configuration copies.
Source and publication inventories reject symlinks, non-regular files and
undeclared files rather than allowing a checksum entry to bless them.

Run the complete non-mutating contract from the repository root with:

```sh
.venv/bin/python scripts/migrate_okf_v02.py --check
.venv/bin/python scripts/build_okf_bundle.py --check
.venv/bin/python scripts/update_viewer.py --check
.venv/bin/python scripts/check_british_english.py
.venv/bin/python scripts/check_publication.py
.venv/bin/python scripts/check_publication_contract.py
.venv/bin/python -m unittest discover -s tests -v
```

These commands are the self-contained local CI contract. When a reviewed
sibling Explorer checkout is available, additionally run
`.venv/bin/python ../okf-explorer/scripts/reconcile_okf_repositories.py --repo . --strict`
as a cross-repository family audit.

## Publication contract and CI

[`okf.publication.json`](okf.publication.json) records the repository's source
families, authored and generated boundaries, dependency planes, exact commands,
documentation lockstep, CI policy, publication authority and verification
route. It is lifecycle governance, separate from the semantic authority in
[`okf.semantic.json`](okf.semantic.json).

`scripts/check_publication_contract.py` checks local identifiers and command
references, safe reviewed command declarations and the no-rebuild publication
policy. In pull requests and pushes it also requires controlled changes to
include `CHANGELOG.md` and updated human guidance in either `README.md` or
`AGENTS.md`. Dependency updates receive the same assessment; there is no
blanket automated-update exemption.

CI runs once for a pull request and again for the integrated `main` commit or a
version tag. Superseded runs are cancelled per pull request or ref. Pages is
triggered only by a successful complete `main` validation, checks out that
exact commit and uploads its existing `bundle/` directory without rebuilding
it. A manual deployment runs the same complete validation first.

After deployment, `scripts/verify_deployment.py` fetches the public
`checksums.json`, landing page, Explorer descriptor and semantic validation
receipt and compares them byte for byte with the validated checkout. This is a
bounded HTTP identity gate, not a real-browser interaction or console test.

The British-English check covers producer-authored Markdown plus human-facing
Python comments and strings. It reports path, line, column and the preferred
spelling, while excluding generated output, tests and the immutable vendored
Bundle Wiki profile.

Markdown with structured YAML-LD front matter remains the source of truth;
JSON-LD and Explorer JSON are publication projections. The Markdown layer
conforms to OKF v0.2: only the root index declares `okf_version`, reserved
indexes/logs have no concept front matter, concepts require `type`, and
production concepts also declare the additive profile's `@context`, absolute
`@id` and IRI-valued `@type`. Source-backed concepts use standard `sources`.
The invalid actor-free legacy
`verified: "yes"` flag is deliberately not promoted into a trust claim.

Markdown links express direction and endpoints but do not justify invented
domain predicates. The semantic compiler therefore gives them the exact
`normalized` status and uses the
conservative absolute predicate `http://purl.org/dc/terms/references`, retains
legacy presentation categories separately, and generates both the direct
triple and a rich `okf:RelationshipAssertion` with route mappings, evidence
hashes, provenance, authority, freshness and rights.

Domain relationships can be authored explicitly in a source concept's
front matter under `assertions`. Such an assertion supplies its absolute `@id`,
absolute `predicate`, semantic `target`, local `target_route`, labels, status,
scope, authority, derivation, observation time, evidence and rights. The
compiler rejects missing routes, mismatched IRIs and duplicate triples.
Authority, evidence and rights sources must also be canonical credential-free
HTTP(S) URLs; browser URL repair is not accepted as validation.

`main` requires a pull request, current CI, resolved conversations, linear
history and explicit maintainer self-review. A separate approving reviewer is
not required because this is a solo-maintained repository.
