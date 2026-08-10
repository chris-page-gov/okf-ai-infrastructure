---
"@context": "https://chris-page-gov.github.io/okf-explorer/profile/bundle-wiki/v1/context.jsonld"
"@id": "https://chris-page-gov.github.io/okf-ai-infrastructure/id/standards/zero-trust"
"@type": "okf:Concept"
type: "Specification"
title: "Zero trust architecture (NIST SP 800-207)"
description: "No implicit trust based on network location."
resource: "https://csrc.nist.gov/pubs/sp/800/207/final"
tags: [zero-trust, security, standard]
status: stable
sources:
  - resource: "https://csrc.nist.gov/pubs/sp/800/207/final"
    last_modified: "2020-08-01"
---

Eliminates implicit trust derived from network position; every request is authenticated, authorised and continuously evaluated. A foundation for agent runtimes, paired with [workload identity](spiffe-spire.md) and [sender-constrained](../glossary/sender-constrained-token.md) credentials.

# Terms
Glossary terms used here: [Workload identity](../glossary/workload-identity.md).
