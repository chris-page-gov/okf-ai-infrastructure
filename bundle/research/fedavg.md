---
"@context": "https://chris-page-gov.github.io/okf-explorer/profile/bundle-wiki/v1/context.jsonld"
"@id": "https://chris-page-gov.github.io/okf-ai-infrastructure/id/research/fedavg"
"@type": "okf:Concept"
type: "Research"
title: "FedAvg — McMahan et al. (2017)"
description: "Communication-efficient decentralised training by model averaging."
resource: "https://arxiv.org/abs/1602.05629"
tags: [fl, foundational, research]
status: stable
sources:
  - resource: "https://arxiv.org/abs/1602.05629"
    last_modified: "2017-02-01"
---

Established the core FL training loop: iterative client-side training with **model averaging** dramatically reduces communication relative to synchronised SGD, while handling non-IID and unbalanced data.

Relates to: [Federated learning](../federated/federated-learning.md).
