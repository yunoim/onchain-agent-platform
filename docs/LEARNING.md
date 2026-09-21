# Learning Log: Kubernetes, Helm, Terraform

Purpose: after finishing this project I should be able to explain, without
looking at the code, how the cluster, the charts and the Terraform roots fit
together and why each choice was made. Entries are appended per phase and
written as answers to the questions an interviewer would actually ask.

Format for each entry:

- **Concept**: one paragraph, plain words.
- **Where it shows up here**: file or command in this repo.
- **Why this choice / trade-off**: what the alternative was.
- **Gotcha**: the thing that bit me (if it did).

---

## Phase 0: Design

### Why write ADRs before code

- **Concept**: an Architecture Decision Record freezes *why* a choice was made
  at the moment the alternatives were still fresh. Six months later the code
  shows *what* was done; only the ADR shows what was rejected and why.
- **Where**: `docs/adr/`.
- **Trade-off**: costs an hour up front. Pays back the first time someone asks
  "why not just call the Anthropic SDK directly?" (ADR-0004).

### Cluster layer vs platform layer

- **Concept**: a Kubernetes cluster is a substrate. What you install on it
  (ingress controller, monitoring, your apps) is the platform. Keeping the two
  in separate Terraform units means the platform can be applied to kind today
  and EKS tomorrow without rewriting it.
- **Where**: `infra/terraform/modules/platform` (platform), `infra/terraform/local`
  and `infra/terraform/aws-eks` (cluster roots).
- **Trade-off**: more files than a single `main.tf`. Worth it because the
  module boundary is exactly the boundary an interviewer will ask about.

### MCP transports

- **Concept**: MCP defines the messages (tools/list, tools/call) separately
  from how bytes move. stdio is for a locally spawned child process;
  streamable-http is for a server on the network. Same tools, different pipe.
- **Where**: `onchain-mcp --transport stdio|streamable-http` (Phase 1).
- **Gotcha to watch**: streamable-http keeps per-client session state by
  default, which matters once there are 2+ replicas behind one Service.

---

## Phase 1: MCP server

_(pending)_

## Phase 2: Agent, gateway, docker compose

_(pending)_

## Phase 3: kind + Helm

_(pending: Pod, Deployment, Service, Ingress, ConfigMap, Secret, probes,
resource requests/limits; Helm chart anatomy, values precedence, `helm
template` as a debugging tool; kind extraPortMappings and why ingress-nginx
needs hostPort on kind.)_

## Phase 4: Terraform

_(pending: providers vs resources vs modules, state and why it holds secrets,
`depends_on` vs implicit graph, the "provider configured from a resource in
the same apply" problem, `plan` as a review artifact, EKS cost model and
`destroy` discipline.)_

## Phase 5: Observability and CI

_(pending: Prometheus pull model, ServiceMonitor CRDs, Grafana provisioning
via ConfigMap sidecar, four golden signals applied to an LLM service, GitHub
Actions matrix and GHCR permissions.)_

## Phase 6: Wrap-up

_(pending: what I would change with a second attempt.)_
