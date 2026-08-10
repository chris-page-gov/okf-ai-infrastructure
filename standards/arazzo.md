---
"@context": "https://chris-page-gov.github.io/okf-explorer/profile/bundle-wiki/v1/context.jsonld"
"@id": "https://chris-page-gov.github.io/okf-ai-infrastructure/id/standards/arazzo"
"@type": "okf:Concept"
type: "Specification"
title: "Arazzo"
description: "Machine-readable workflow narratives over API descriptions."
resource: "https://spec.openapis.org/arazzo/latest.html"
tags: [arazzo, workflows, standard]
status: stable
sources:
  - resource: "https://spec.openapis.org/arazzo/latest.html"
    last_modified: "2026-04-15"
---

Defines sequences of calls, dependencies, async coordination and success/failure actions — the bridge from single-call tool use to governed multi-step execution. v1.1.0 (2026) added AsyncAPI support. New and still early in tooling maturity; depends on the underlying [OpenAPI](openapi.md)/[AsyncAPI](asyncapi.md) descriptions.

# Terms
Glossary terms used here: [Tool use](../glossary/tool-use.md).
