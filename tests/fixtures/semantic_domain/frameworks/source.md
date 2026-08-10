---
"@context": https://chris-page-gov.github.io/okf-explorer/profile/bundle-wiki/v1/context.jsonld
"@id": https://example.test/id/source-service
"@type": okf:Concept
type: Concept
title: Source service
description: A service governed by the example authority.
modified: "2026-08-10T10:00:00Z"
status: stable
assertions:
  - "@id": https://example.test/assertions/service-governed-by-authority
    "@type": [rdf:Statement, okf:RelationshipAssertion]
    target: {"@id": https://example.test/id/authority}
    target_route: frameworks/target.md
    predicate: {"@id": https://example.test/terms/governedBy}
    kind: governed-by
    label: governed by
    inverse_label: governs
    assertion_status: official
    assertion_scope: real-world
    authority:
      class: official
      label: Example authority
      source: https://example.test/evidence/authority
    derivation: https://example.test/rules/direct-field-v1
    observed_at: "2026-08-10T10:00:00Z"
    evidence:
      - "@id": https://example.test/evidence/relationship-1
        type: source-field
        url: https://example.test/evidence/authority
        source_field: governed_by
        source_value_sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
        retrieved_at: "2026-08-10T10:00:00Z"
    rights:
      source: https://creativecommons.org/publicdomain/zero/1.0/
      assertion: Example repository-authored assertion.
---

# Source service

The relationship above is an explicit domain assertion, not an inference from
a Markdown link.
