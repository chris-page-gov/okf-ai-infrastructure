# Changelog

## Unreleased — 2026-08-18

- Added the OKF publication-method v1 repository contract, local structural
  validation and documentation/`CHANGELOG.md` lockstep enforcement.
- Removed duplicate feature-branch push validation while retaining pull
  request, integrated `main`, version-tag and manual assurance; added per-ref
  cancellation, bounded job time and immutable action pins.
- Made Pages wait for the complete `main` validation and deploy that exact
  checked-in bundle without rebuilding it. Manual deployment runs the complete
  gate first.
- Added bounded post-deploy verification of the exact checksum manifest,
  landing page, Explorer descriptor and semantic validation receipt.

## 0.6.0 — 2026-08-10

- Added explicit YAML-LD context, absolute semantic identity and semantic type
  to all 142 production concept documents while preserving the 13 reserved
  OKF 0.2 navigation documents.
- Replaced descriptor-only YAML-LD with a relationship-authoritative graph of
  155 route-bearing entities, 579 direct `dcterms:references` triples and 579
  evidence-bearing `okf:RelationshipAssertion` nodes.
- Added the synchronised rich Explorer and flat relationship projections,
  pinned semantic context, assertion schema, deterministic evidence hashes and
  direct/reified reconciliation checks.
- Added explicit front matter `assertions` compilation for evidence-backed
  domain predicates with strict semantic-IRI and local-route reconciliation.
- Added a Python 3.12+ repository-local `.venv` setup contract, an exact
  transitive dependency lock, and clean-runner dependency installation for
  validation and Pages publication checks.
- Pinned the final shared Draft 2020-12 assertion schema byte-for-byte and now
  validate all 579 runtime rows plus all 579 reified assertions against it.
  The generated semantic receipt binds the schema digest, assertion identities,
  payloads and direct-triple set to the declared release-candidate build instant.
- Made semantic attestation fail closed: authored routes cannot override
  computed endpoints, invalid projections cannot produce passing receipts,
  publication starts from a clean generated directory, and checksum validation
  requires the exact safe published-file set rather than trusting omissions.
- Closed the remaining adversarial boundaries around JSON-LD control-key
  injection, Markdown and parent-directory symlinks, concurrent file swaps,
  oversized or excessively deep YAML-LD, aliases, duplicate JSON keys and
  self-declared publication files. Release counts are reviewed configuration
  data rather than validator constants.
- Vendored the complete 16-file Explorer v0.6.0 Bundle Wiki profile as an
  immutable byte-for-byte mirror with an adjacent release lock, replacing a
  locally modified copy that had incorrectly retained the canonical profile
  URI.
- Standardised producer-authored human-readable material on British English
  and generated pages on `en-GB`, while preserving exact schema identifiers,
  governed values and official titles.

## 0.5.0 — 2026-07-25

- Migrated the canonical Markdown layer and generated publication to OKF v0.2.
- Replaced source-oriented legacy timestamps with standard `sources` metadata,
  kept actor-free legacy verification from becoming an unsupported trust claim,
  and preserved producer extensions in Explorer JSON.
- Added v0.2 reserved-file, lifecycle, provenance, trust-shape and projection
  checks while retaining all 155 nodes and 579 relationships.

## 0.4.0 — 2026-07-11

- Extracted the Markdown wiki as an independent YAML-LD OKF Bundle Wiki.
- Added semantic descriptors, deterministic publication checks, CI and Pages.
