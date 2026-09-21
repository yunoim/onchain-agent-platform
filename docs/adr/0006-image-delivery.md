# ADR-0006: Images are delivered through GHCR; local builds use `kind load`

- Status: Accepted
- Date: 2026-09-21

## Context

kind nodes run their own containerd and cannot see images in the host Docker
daemon. Before CI exists (Phase 3) images must reach the cluster somehow; after
CI exists (Phase 5) the cluster should pull published images so that a fresh
machine needs no local build step. The Helm chart must work in both modes
without edits.

## Decision

- Canonical images: `ghcr.io/yunoim/onchain-mcp-server` and
  `ghcr.io/yunoim/onchain-agent`, public packages, built and pushed by GitHub
  Actions on every push to `main`, tagged with the short SHA and `latest`.
- Helm values parameterise `image.repository`, `image.tag`, and
  `image.pullPolicy` per service. `values.yaml` defaults to GHCR + `latest` +
  `IfNotPresent`. `values-local.yaml` overrides to the local names
  (`onchain-mcp-server:dev`) with `pullPolicy: Never`.
- `scripts/kind-load.ps1` (and `.sh`) builds both images and runs
  `kind load docker-image` into the named cluster. This is the pre-CI and
  offline path.
- Terraform `local` root exposes `image_tag` and `use_local_images`
  variables that select between the two value files.

## Consequences

- Positive: the completion criterion (fresh machine, one apply) is met by the
  GHCR path with no Docker build required.
- Positive: the local path keeps the inner loop fast: build, load, `helm
  upgrade` via Terraform, no registry round trip.
- Negative: `latest` tags are mutable and make rollbacks vague. Production
  guidance in LEARNING.md: pin to SHA tags; `latest` is a convenience for the
  demo only.
- Negative: two value files can drift. `helm lint` runs against both in CI.
