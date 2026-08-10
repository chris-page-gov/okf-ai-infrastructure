---
"@context": "https://chris-page-gov.github.io/okf-explorer/profile/bundle-wiki/v1/context.jsonld"
"@id": "https://chris-page-gov.github.io/okf-ai-infrastructure/id/research/gorilla"
"@type": "okf:Concept"
type: "Research"
title: "Gorilla & APIBench (2023)"
description: "Fine-tuned LLM + document retriever; adapts to doc change, cuts hallucination."
resource: "https://arxiv.org/abs/2305.15334"
tags: [benchmark, tool-use, research]
status: stable
sources:
  - resource: "https://arxiv.org/abs/2305.15334"
    last_modified: "2023-05-01"
---

A genuine advance: pairing a fine-tuned model with a **document retriever**, claiming adaptation to test-time documentation change, and introducing **APIBench**. The key qualification: it improved retrieval-grounded syntax and reduced hallucinated usage but did **not** solve authorisation, stateful recovery, policy adherence or legal accountability.

Relates to: [Discovery and retrieval](../stack/discovery-and-retrieval.md), [Failure taxonomy](../document/themes/failure-taxonomy.md).
