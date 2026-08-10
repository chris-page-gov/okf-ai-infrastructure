---
"@context": "https://chris-page-gov.github.io/okf-explorer/profile/bundle-wiki/v1/context.jsonld"
"@id": "https://chris-page-gov.github.io/okf-ai-infrastructure/id/federated/hub-and-spoke-vs-hierarchical"
"@type": "okf:Concept"
type: "Concept"
title: "Hub-and-spoke vs hierarchical coordination"
description: "Centralised aggregation vs hierarchical/asynchronous/enclave-backed designs."
tags: [fl, architecture, federated]
status: stable
---

Federations can be centrally orchestrated (hub-and-spoke) or use hierarchical, partially asynchronous or enclave-backed aggregators for resilience and scale. Whether public-sector federations should remain hub-and-spoke is an open architectural question; systems research (e.g. Flotilla) shows newer designs can exceed Flower on very large, unstable federations.

Relates to: [Flower](../frameworks/flower.md), [Flotilla](../frameworks/flotilla.md).
