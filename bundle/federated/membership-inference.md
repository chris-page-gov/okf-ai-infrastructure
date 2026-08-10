---
"@context": "https://chris-page-gov.github.io/okf-explorer/profile/bundle-wiki/v1/context.jsonld"
"@id": "https://chris-page-gov.github.io/okf-ai-infrastructure/id/federated/membership-inference"
"@type": "okf:Concept"
type: "Concept"
title: "Membership inference & gradient leakage"
description: "Privacy attacks that recover information from model updates."
tags: [fl, privacy, threat, federated]
status: stable
---

Attacks that determine whether a record was in the training set, or reconstruct data from gradients — evidence that FL is **not inherently private enough** for regulated public services. Motivates [secure aggregation](secure-aggregation.md) and [differential privacy](differential-privacy.md).
