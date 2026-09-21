# ADR-0005: Terraform is split into a cluster layer and a reusable platform module

- Status: Accepted
- Date: 2026-09-21

## Context

The completion criterion is "a fresh machine runs `terraform apply` once and
the whole stack is up on a local cluster". At the same time an AWS EKS variant
must exist as code (plan-only, cost constraint). Two Terraform roots that each
inline every Helm release would duplicate the platform definition and drift.

## Decision

```
infra/terraform/
  modules/platform/   # helm_release: ingress-nginx, kube-prometheus-stack, onchain-agent-platform
                      # kubernetes_secret: platform-secrets (from variables)
  local/              # kind_cluster (tehcyx/kind provider) + module "platform"
  aws-eks/            # terraform-aws-modules/vpc + /eks + module "platform"
```

- `modules/platform` takes a kubeconfig-shaped set of provider inputs plus
  application variables (image tag, hostnames, secrets). It knows nothing about
  where the cluster came from.
- `local` is the default root. One `terraform apply` creates the kind cluster,
  waits for the API server, then applies the platform module. `terraform
  destroy` removes everything including the cluster.
- `aws-eks` is validated and planned in CI with dummy credentials. It is never
  applied by automation; applying is an explicit manual decision documented
  with cost estimates and a destroy procedure.
- Secrets enter via `TF_VAR_*` environment variables, never via committed
  `.tfvars`. It is recorded in LEARNING.md that these values still land in the
  local state file, and what the production alternative would be (External
  Secrets Operator, SOPS).

## Consequences

- Positive: "cluster vs platform" is a real production pattern and is easy to
  explain in an interview: the platform module is the deployable unit; the
  cluster is an interchangeable substrate.
- Positive: EKS parity is a small root, not a fork.
- Negative: Terraform managing Helm releases means Helm state lives in
  Terraform state; `helm upgrade` by hand causes drift. The rule is: Terraform
  owns releases; Helm CLI is for `lint` and `template` only.
- Negative: provider configuration that depends on a resource created in the
  same apply (kind cluster -> kubernetes/helm providers) is a known Terraform
  sharp edge. The `local` root handles it with explicit `depends_on` and
  provider inputs read from the kind resource outputs; the caveat is recorded in
  LEARNING.md.
