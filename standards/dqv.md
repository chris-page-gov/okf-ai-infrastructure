---
"@context": "https://chris-page-gov.github.io/okf-explorer/profile/bundle-wiki/v1/context.jsonld"
"@id": "https://chris-page-gov.github.io/okf-ai-infrastructure/id/standards/dqv"
"@type": "okf:Concept"
type: "Specification"
title: "Data Quality Vocabulary (DQV)"
description: "W3C companion vocabulary for expressing data quality metadata and quality annotations alongside DCAT."
resource: "https://www.w3.org/TR/vocab-dqv/"
tags: [dqv, data-quality, standard, dcat]
status: stable
sources:
  - resource: "https://www.w3.org/TR/vocab-dqv/"
    last_modified: "2026-07-09"
---

DQV provides a vocabulary for describing data quality metadata and quality annotations. OKF Explorer metadata-quality percentages are deterministic catalogue-completeness signals, not assurance scores. DQV is therefore the closest standards-family anchor for future exports of those quality annotations, while the UI should keep the OKF labels and explanations explicit.

Use DQV where an OKF bundle needs to export quality dimensions alongside DCAT, especially completeness, provenance of a score and source-observed metadata gaps.
