---
okf_version: "0.2"
---

# ai-infrastructure-wiki

An **Open Knowledge Format (OKF v0.2)** bundle covering **AI
infrastructure** in two complementary threads: the **agent-ready vertical
stack** (contracts → discovery → identity → execution → policy →
observability/provenance) and the **federated collaborative-learning layer**.
Canonical concepts are Markdown with YAML front matter, cross-linked into a
graph; load the [Explorer JSON bundle](okf-bundle.json) in OKF Explorer for
search, record and directed-relationship views.

## Contents
- **[The reviewed sources](document/index.md)** — overview, [themes](document/themes/index.md), [source documents](document/sources/index.md), [evaluation](document/peer-review.md).
- **[Stack layers](stack/index.md)** (9) · **[Standards](standards/index.md)** (21) · **[Federated AI](federated/index.md)** (15)
- **[Frameworks](frameworks/index.md)** (12) · **[Research & benchmarks](research/index.md)** (17)
- **[UK government](uk-government/index.md)** (10) · **[Organisations](organisations/index.md)** (16) · **[Glossary](glossary/index.md)** (25)
- **[Sources index](sources-index.md)** · **[Change log](log.md)**

## Linking conventions

OKF v0.2 links are plain Markdown—unidirectional and untyped. This bundle
adopts two compatible authoring conventions:

1. **Glossary/vocabulary** terms are linked **from the concept that uses them** (a `Terms` section), mirroring wiki practice; each glossary entry also lists where it is used, so the term↔concept relationship is bidirectional in the files.
2. **Direction is meaningful**: a link means *source references target*;
   consumers build the reverse index (the viewer's "Referenced by"). The
   semantic compiler represents this conservatively as the absolute predicate
   `http://purl.org/dc/terms/references`. It does not infer domain predicates
   from link placement, prose or section. Legacy display categories remain
   non-semantic presentation metadata.

Each generated reference has a stable assertion IRI, absolute entity IRIs,
validated local routes, preferred and inverse labels, status and scope,
derived authority, deterministic derivation, observation time, source-file
evidence hashes and CC0 rights. The YAML-LD and JSON-LD graph contains both
the direct triple and its evidence-bearing `okf:RelationshipAssertion`; the
Explorer bundle contains the same rich row.

Domain-specific relationships are authored explicitly in a concept's YAML-LD
front matter. The source is the current concept; `target_route` must resolve to
another local concept and `target` must equal that concept's semantic `@id`:

```yaml
assertions:
  - "@id": "https://example.org/assertions/service-governed-by-authority"
    "@type": ["rdf:Statement", "okf:RelationshipAssertion"]
    target: {"@id": "https://example.org/id/authority"}
    target_route: "organisations/authority.md"
    predicate: {"@id": "https://example.org/terms/governedBy"}
    label: "governed by"
    inverse_label: "governs"
    assertion_status: "official"
    assertion_scope: "real-world"
    authority:
      class: "official"
      label: "Published by the responsible authority"
      source: "https://example.org/evidence"
    derivation: "https://example.org/rules/direct-field-v1"
    observed_at: "2026-08-09T00:00:00Z"
    evidence:
      - "@id": "https://example.org/evidence/relationship-1"
        type: "source-field"
        url: "https://example.org/evidence"
        source_field: "governed_by"
        source_value_sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        retrieved_at: "2026-08-09T00:00:00Z"
    rights:
      source: "https://creativecommons.org/publicdomain/zero/1.0/"
      assertion: "source-derived metadata"
```

## Provenance and trust

Source-backed concepts use `sources[].resource` and `sources[].last_modified`.
The former v0.1 `verified: "yes"` flag had neither an actor nor a verification
event time, so it is not promoted into v0.2 `verified`; those concepts remain
consumable but explicitly unverified until evidence-backed events are recorded.
All producer-specific tags, aliases, links and Explorer routes are retained.

## Companion
This is a standalone sibling of `api-mcp-wiki`. Where they share standards (OpenAPI, MCP, A2A, Arazzo, OAuth), each bundle describes them in its own realm's context.
