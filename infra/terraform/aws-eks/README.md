# infra/terraform/aws-eks (plan-only)

The same platform module as the local root, on AWS EKS. This directory exists to show the
cluster/platform split (ADR-0005) working across two substrates; it is **not applied** by
default.

| Step | Needs AWS credentials? | Run by |
|---|---|---|
| `terraform init` / `terraform validate` | no | CI, anyone |
| `terraform plan` | yes | you, deliberately |
| `terraform apply` | yes | you, after reading the cost note below |

## Cost if applied

About $0.30 per hour (EKS control plane $0.10, two t3.medium $0.10, one NAT gateway
$0.06, one NLB $0.03), so roughly $7 per day. Nothing here is free-tier eligible. The NAT
gateway and load balancer bill while idle. When done:

```powershell
terraform destroy
```

Confirm in the console afterwards that no `onchain-agent` ELB or NAT gateway remains.

## What differs from the kind root

- The cluster comes from `terraform-aws-modules/vpc` and `/eks` instead of the kind provider.
- ingress-nginx is installed with a `LoadBalancer` Service (NLB) instead of hostPort.
- Images are pulled from GHCR; there is no `kind load` step.
- There is no host GPU. `ollama_base_url` must point at an in-cluster Ollama deployment or
  an external endpoint, or set `LLM_MODEL` to a hosted alias and supply `anthropic_api_key`.

## Variables

Provide secrets through the environment, never through a committed tfvars file:

```powershell
$env:TF_VAR_litellm_master_key = "..."
```
