---
"@context": "https://chris-page-gov.github.io/okf-explorer/profile/bundle-wiki/v1/context.jsonld"
"@id": "https://chris-page-gov.github.io/okf-ai-infrastructure/id/standards/dpop"
"@type": "okf:Concept"
type: "Specification"
title: "DPoP — RFC 9449"
description: "Application-layer sender-constraining without mutual TLS."
resource: "https://www.rfc-editor.org/rfc/rfc9449"
tags: [oauth, dpop, security]
status: stable
sources:
  - resource: "https://www.rfc-editor.org/rfc/rfc9449"
    last_modified: "2023-09-01"
---

Demonstrating Proof-of-Possession sender-constrains tokens at the application layer, mitigating replay of stolen tokens. Strong for browser/mobile or heterogeneous clients; still maturing in many stacks.

# Terms
Glossary terms used here: [Sender-constrained token](../glossary/sender-constrained-token.md).
