---
"@context": "https://chris-page-gov.github.io/okf-explorer/profile/bundle-wiki/v1/context.jsonld"
"@id": "https://chris-page-gov.github.io/okf-ai-infrastructure/id/federated/secure-aggregation"
"@type": "okf:Concept"
type: "Concept"
title: "Secure aggregation"
description: "The server learns the aggregate of updates, not any individual update."
resource: "https://arxiv.org/abs/1611.04482"
tags: [fl, privacy, security, federated]
status: stable
sources:
  - resource: "https://arxiv.org/abs/1611.04482"
    last_modified: "2017-10-01"
---

A cryptographic protocol so the coordinating server can compute the *sum* of client updates without reading any individual contribution. Often necessary because model updates can leak information. A composable trust layer alongside [differential privacy](differential-privacy.md).

Relates to: [Federated learning](federated-learning.md), [Membership inference](membership-inference.md).
