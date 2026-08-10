---
"@context": "https://chris-page-gov.github.io/okf-explorer/profile/bundle-wiki/v1/context.jsonld"
"@id": "https://chris-page-gov.github.io/okf-ai-infrastructure/id/federated/differential-privacy"
"@type": "okf:Concept"
type: "Concept"
title: "Differential privacy"
description: "A formal bound on what any individual contributes to a released result."
tags: [fl, privacy, federated]
status: stable
---

Adds calibrated noise so that the presence or absence of any single record has a bounded effect on outputs — a standard countermeasure against inference about individual contributors. Composable with [secure aggregation](secure-aggregation.md) and [TEEs](trusted-execution-environments.md).

Relates to: [Membership inference](membership-inference.md).
