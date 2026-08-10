# Vendored Bundle Wiki profile

The [`v1/`](v1/) directory is an immutable, byte-for-byte mirror of the
canonical Bundle Wiki profile published by OKF Explorer. The adjacent
[`v1.vendor-lock.json`](v1.vendor-lock.json) records the exact Explorer release,
Git identities, file inventory, byte counts and SHA-256 digests used to verify
the mirror. Its `release.git_tree`
`d26ae9a818041ff74c469e653ec714632ddbfc2a` is the Git tree identity of the
`profiles/bundle-wiki/v1/` profile subtree at the locked release commit; it is
not the root tree of the complete Explorer repository at that commit.

Do not edit files inside `v1/` locally. Read the
[published Bundle Wiki profile](https://chris-page-gov.github.io/okf-explorer/profile/bundle-wiki/v1/)
for the browsable explanation and canonical links. Update this repository only
with a reviewed sibling Explorer checkout, from the repository root:

```sh
.venv/bin/python ../okf-explorer/scripts/reconcile_okf_repositories.py \
  --repo . --sync-profile
```

If that command reports a divergent existing mirror, review the reported
source, release and byte identities before deliberately rerunning it with
`--replace-profile`. Then run the repository's complete local checks and a
strict reconciliation audit against the installed mirror and vendor lock.
