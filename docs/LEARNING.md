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

### What an MCP server actually is

- **Concept**: a process that answers three questions over JSON-RPC: "what tools do you
  have?" (`tools/list`), "run this one with these arguments" (`tools/call`), and
  "what should the model know about you?" (`instructions`). The tool schema is
  generated from Python type hints, so the function signature *is* the API contract
  the LLM sees. Docstrings become the tool descriptions the model reads to decide
  when to call what.
- **Where**: `services/mcp-server/src/onchain_mcp/tools/*.py`; the in-memory
  protocol test in `tests/test_server_tools.py` asserts the schema has exactly the
  parameters we intend and that the injected `Context` never leaks into it.
- **Gotcha**: the `mcp` SDK 2.x renamed `FastMCP` to `MCPServer` and switched result
  attributes to snake_case (`input_schema`, `is_error`). Pinning the SDK major in
  `pyproject.toml` is not optional for a server that is meant to be rebuilt later.

### Lifespan context instead of globals

- **Concept**: the server has a lifespan (startup to shutdown). Whatever the lifespan
  yields is handed to every tool call through `ctx.request_context.lifespan_context`.
  This is where long-lived clients (the web3 provider, the Etherscan HTTP client)
  belong, so they are created once, closed once, and are trivially swappable in tests.
- **Where**: `state.py` (`AppState`), `server.py` (`build_server(..., state_factory=)`).
- **Trade-off**: slightly more plumbing than a module-level `w3 = Web3(...)`, but the
  whole test suite runs offline because the factory injects a fake Web3. Same pattern
  Kubernetes will want later: configuration in, dependencies constructed at start,
  readiness only after they exist.

### Sync tools, async server

- **Concept**: web3.py's HTTP provider is blocking. The SDK runs a plain `def` tool on a
  worker thread automatically, so blocking calls do not stall the event loop that is
  serving other MCP requests. Writing the tools as sync functions was the simpler and
  correct choice here.
- **Gotcha**: this means CPU-bound or very slow RPC calls compete for the default
  thread pool. Fine for a demo; a production server would cap concurrency or move to
  `AsyncWeb3`.

### Two transports, one binary (ADR-0003 in practice)

- **Concept**: stdio means the client (Claude Desktop) spawns the server as a child and
  talks over stdin/stdout. That is why logs must go to stderr: a stray `print()` on
  stdout corrupts the protocol stream. streamable-http means the server is a normal
  HTTP service (`POST /mcp`), which is what a Kubernetes Service can front.
- **Where**: `server.py::main`, `--transport` flag; `logging.basicConfig(stream=sys.stderr)`.
- **Stateless HTTP**: the SDK defaults to one session per client with server-side
  state. `MCP_STATELESS=true` turns that off so two replicas behind one Service can
  answer any request. The cost is no server-initiated notifications, which these
  tools do not need.
- **DNS-rebinding protection**: the SDK can reject requests whose `Host` header is not
  localhost. Inside a cluster the `Host` header is `mcp-server:8000`, so it must be
  off there; the cluster network boundary is the actual control.

### Bounded reads are a security property, not just a quota trick

- **Concept**: `eth_getLogs` over an unbounded range is how you get a public RPC to ban
  you. Capping at 2000 blocks (`MAX_LOG_BLOCK_RANGE`) and 100 results makes the worst
  case a model can cause cheap and predictable. The same cap protects the Etherscan
  free tier via `MAX_HISTORY_ITEMS`.
- **Measured**: 200 blocks of USDC transfers = about 19,800 log entries, 6 seconds on
  PublicNode. 2000 blocks stays under the provider's response-size limit but is the
  practical ceiling.

### Exact money math

- **Concept**: 1 ETH is 10^18 wei; USDC has 6 decimals. Floats lose precision above
  2^53, so every human-readable amount is produced with `Decimal` and returned as a
  string. The raw integer is returned alongside for anyone who wants to compute.
- **Where**: `formatting.py`; tests assert `wei_to_eth(1) == "0.000000000000000001"`.

### The read-only guarantee as code

- **Concept**: an architecture rule that lives only in a document decays. ADR-0001 is
  enforced twice: `tests/test_read_only_guarantee.py` greps the package for signing
  identifiers and checks the ERC-20 ABI is view-only; `scripts/check-no-signing.sh`
  does the same in CI across all services.
- **Trade-off**: grep-based, so a determined author could evade it. The point is to
  make accidental scope creep fail loudly, not to stop a malicious insider.

### Two gotchas from connecting Claude Desktop

- **MSIX filesystem virtualisation**: the Microsoft Store build of Claude Desktop sees
  `%APPDATA%\Claude` but a normal shell does not; the real file is under
  `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\`. Child processes of the
  app inherit the virtual view, so a tool running inside the app and the user's own
  terminal disagree about whether a path exists. Lesson: when two observers disagree
  about a file, ask which process context each one is in before assuming a typo.
- **Config ownership**: the app reads `claude_desktop_config.json` once at startup and
  rewrites the whole file from memory whenever it saves a preference. Any edit made
  while it runs is silently lost within minutes. `scripts/register-claude-desktop.ps1`
  refuses to run while the app is open for exactly this reason. Same failure mode as
  editing a ConfigMap that a controller also writes: decide who owns the file.
- **JSON numbers are not integers**: the server returns `balance_wei` as an exact
  Python int, but a JavaScript client parsed 6712603153701629485 as
  6712603153701630000 (IEEE-754 double, 2^53 limit). The exact decimal *string*
  fields are the authoritative values; raw integers above 2^53 should be strings too.

### Container hygiene picked up along the way

- Two-stage `uv` build: the resolver runs in a builder image; the runtime image gets
  only the virtualenv. Dependency layer is installed before source is copied so code
  edits do not re-resolve packages.
- Non-root user (`uid 10001`), `HEALTHCHECK` hitting `/healthz`, `PYTHONUNBUFFERED=1`
  so logs stream. Image is about 80 MB.
- `.dockerignore` excludes `.venv` and tests; otherwise the host virtualenv (Windows
  binaries) would be copied into the Linux build context.

## Phase 2: Agent, gateway, docker compose

### What a "tool-calling loop" is, mechanically

- **Concept**: the model never runs anything. It returns a structured request
  ("call `get_eth_balance` with `{address: vitalik.eth}`"), the *agent* executes it, appends
  the result as a `tool` message, and asks the model again. The loop ends when a reply has
  no tool calls. Everything the model "did" is therefore visible in the message list.
- **Where**: `services/agent/src/onchain_agent/agent.py::Agent.run`.
- **Why bounded**: an 8B model can loop forever re-calling the same tool. `MAX_TOOL_ITERATIONS`
  caps the round-trips; when it is hit the agent sends one more request *without tools*
  and the instruction "answer from what you have". The user always gets an answer and the
  RPC quota has a ceiling.
- **Gotcha**: tool results must go back *verbatim-ish* but bounded. A 20-row transfer list
  is a few thousand tokens; unbounded it overflows a local model's context. The agent
  truncates tool output (`MAX_TOOL_RESULT_CHARS`) and the gateway raises `num_ctx`.

### Why the agent talks to a gateway, not a provider (ADR-0004 in practice)

- **Concept**: the agent imports the `openai` SDK but points `base_url` at LiteLLM. It
  requests an *alias* (`local-default`); the gateway maps that to `ollama_chat/qwen3:8b`
  today and could map it to Anthropic tomorrow. Provider keys exist only in the gateway
  container's environment.
- **Where**: `services/gateway/litellm/config.yaml` (`model_list`, `router_settings.fallbacks`),
  `docker-compose.yml` (only `litellm` receives `ANTHROPIC_API_KEY`).
- **Trade-off**: one more hop and one more container. In exchange, model routing, retries,
  fallbacks and rate limits are configuration reviewed in a PR, not code paths in every
  service. This is the same argument as putting TLS termination in an ingress controller.

### Where cost becomes observable

- **Concept**: the gateway returns `usage` (prompt/completion tokens) on every response.
  The agent multiplies by a per-alias price table and exports Prometheus counters
  (`onchain_agent_llm_tokens_total`, `onchain_agent_llm_cost_usd_total`). Local inference is
  priced at zero so the metric stays honest.
- **Why here and not in the gateway**: LiteLLM's Prometheus callback is an enterprise
  feature, and persistent spend logs need a database. Counting in the consumer keeps the
  local stack at three containers. Phase 5 scrapes these counters.

### docker compose as the first "orchestrator"

- **Concept**: compose gives the same primitives Kubernetes will: a network where services
  resolve each other by name (`http://litellm:4000`), health checks, and start ordering via
  `depends_on: condition: service_healthy`. Reading the compose file is a preview of the
  Helm chart.
- **Gotcha**: containers cannot see the host's `localhost`. Ollama runs on the host GPU, so
  the gateway reaches it through `host.docker.internal` (Docker Desktop provides it; on
  Linux `extra_hosts: host-gateway` adds it). In Kubernetes the equivalent is an external
  Service or an endpoint pointing at the node.
- **Gotcha**: health checks must not depend on tools the image lacks. The slim images have
  no `curl`, so the checks use `python -c "urllib.request..."`.

### Measured on the first full run (RTX 3070 Laptop 8 GB, qwen3:8b)

| Demo question | LLM round-trips | Tools | Tokens | Wall time |
|---|---|---|---|---|
| ETH balance of vitalik.eth | 2 | `get_eth_balance` | 3,667 | 20 s |
| USDC transfers > 1M in 300 blocks | 2 | `get_recent_token_transfers` | 4,939 | 46 s |
| Gas price + latest block | 2 | `get_gas_price`, `get_block` | 3,986 | 27 s |

Most of the prompt tokens are the nine tool schemas repeated every round-trip; the
answer itself is a few hundred. This is the argument for keeping tool descriptions tight.

**Debugging note**: the first run failed with `Cannot connect to host host.docker.internal`.
The compose file had `extra_hosts: host.docker.internal:host-gateway`, which on Docker
Desktop *replaces* the built-in mapping (host loopback) with the Linux VM bridge IP.
Lesson: a "portable" line copied from Linux guides can break the platform that already
solved the problem. The agent's 502 carried the gateway's error text verbatim, which is
why it took one log read to find.

### Small-model realities (ADR-0007)

- `qwen3:8b` emits `<think>...</think>` reasoning in `content`; the agent strips it before
  returning an answer and before echoing assistant messages back into the conversation.
- Temperature is pinned low (0.1) for tool loops: creativity is the enemy of well-formed
  JSON arguments.
- Malformed tool arguments are not a crash. The agent replies to the model with the parse
  error as a tool result and lets it correct itself on the next turn.

## Phase 3: kind + Helm

### The five objects that carry the whole app

- **Deployment**: "keep N copies of this pod template running, roll them when the template
  changes." Ours have `replicas: 1`; the value of the Deployment is not scale but the
  controller loop: it recreates a crashed pod and rolls a new image without downtime.
- **Pod**: one or more containers sharing a network namespace. We never write Pods by
  hand; the Deployment stamps them from `spec.template`.
- **Service**: a stable DNS name and virtual IP in front of pods selected by labels.
  `http://oap-onchain-agent-platform-litellm:4000` works from any pod because the Service
  exists, even while the pod behind it is replaced.
- **ConfigMap / Secret**: configuration mounted as files (LiteLLM's `config.yaml`) or
  injected as env vars (`ETHERSCAN_API_KEY`). Same shape; Secret is base64 and can be
  RBAC-restricted and encrypted at rest. Neither is "secure" by itself.
- **Ingress**: an L7 routing rule ("host `agent.localtest.me` -> Service `agent`") that
  does nothing until an ingress *controller* (ingress-nginx) implements it.
- **Where**: `deploy/helm/onchain-agent-platform/templates/*.yaml`.

### Why Helm, and how a chart is put together

- **Concept**: Helm is a templating engine plus a release database. Templates under
  `templates/` are Go templates rendered with `values.yaml` (overridden by `-f` files
  and `--set`, later wins). The rendered YAML is applied and recorded as a release
  revision, which is what makes `helm rollback` and `helm diff` possible.
- **Where**: `Chart.yaml` (metadata), `values.yaml` (defaults for GHCR images),
  `values-local.yaml` (kind overrides), `templates/_helpers.tpl` (named templates for
  labels and names used by every object), `templates/NOTES.txt` (printed after install),
  `templates/tests/` (pods run by `helm test`).
- **Design choices in this chart**:
  - One chart, three components, selected by `app.kubernetes.io/component`. Selector
    labels are immutable on a Deployment, so the selector set is deliberately tiny.
  - `checksum/config` annotations on pod templates. Helm does not restart pods when a
    ConfigMap changes; hashing the content into the template makes a config change a
    template change, which triggers a rollout.
  - `secrets.existingSecret`: the chart can create the Secret (local) or reference one
    created elsewhere (Terraform in Phase 4). Charts should not own secrets in
    production.
  - LiteLLM config is injected with `--set-file`, so the canonical file in
    `services/gateway/litellm/` is the only copy. The chart default is a minimal config
    that still works, so `helm install` with no flags is not broken.
- **Debugging tools**: `helm template` renders without a cluster (used above to count
  eleven objects); `helm lint` catches schema mistakes; `helm get manifest <release>`
  shows exactly what was applied.

### Probes and resources: what the scheduler and the controller need from you

- **Liveness** ("restart me if this fails") vs **readiness** ("do not send traffic until
  this passes"). The agent's readiness probe is `/readyz`, which checks the MCP server
  and the gateway, so the Ingress only routes to an agent pod that can actually answer.
  Liveness is the cheap `/healthz`; a slow upstream must not get the agent killed.
- **Requests vs limits**: requests are what the scheduler reserves; limits are what the
  kernel enforces (memory: OOM-kill; CPU: throttle). We set memory limits but no CPU
  limits, a common recommendation, because CPU throttling hurts latency more than it
  protects neighbours on a small cluster.
- **Security context**: `runAsNonRoot`, `readOnlyRootFilesystem`, drop all capabilities
  for the images we build (uid 10001 baked in the Dockerfile). The upstream LiteLLM image
  is left alone: hardening a third-party image is its maintainers' contract to define.

### kind: a cluster made of Docker containers

- **Concept**: each kind "node" is a Docker container running containerd and kubelet.
  This is why `docker build` images are invisible to the cluster (different image store)
  and `kind load docker-image` exists (ADR-0006).
- **Ingress on kind**: no cloud load balancer, so `deploy/kind/cluster.yaml` maps node
  ports 80/443 to the host and ingress-nginx is installed with `hostPort` enabled and a
  `nodeSelector` on the labelled node. `*.localtest.me` resolves to 127.0.0.1, so
  `http://agent.localtest.me` reaches the controller with no hosts-file edits.
- **Same chart, different values**: the ingress-nginx chart is the one used on EKS; only
  `deploy/kind/ingress-nginx-values.yaml` differs (hostPort vs LoadBalancer). This is the
  pattern the platform Terraform module reuses in Phase 4.
- **Reaching the host from a pod**: on Docker Desktop, kind nodes inherit the embedded DNS,
  so pods resolve `host.docker.internal` and the gateway reaches Ollama on the host GPU
  with no extra objects. Verified with a throwaway busybox pod before writing any values.
- **Gotcha, `kind load` and multi-platform images**: loading the upstream LiteLLM image
  failed with `content digest ... not found`. The host store holds only the amd64 layers
  of a multi-arch manifest, and `ctr import --all-platforms` asks for the rest. Let kubelet
  pull third-party images; only load the ones you build.
- **Gotcha, tool output formats change**: `helm test` on Helm v4 prints a different report
  than v3, so a grep written for v3 returned nothing and looked like a hang. The test pod
  had already passed and been garbage-collected by `hook-succeeded`. Check the release
  status before assuming failure.

### Measured on kind (same laptop, same model)

Demo answers through Ingress took 60 s, 52 s and 39 s, roughly 1.5x to 3x slower than
docker compose. The extra time is not Kubernetes; it is GPU contention from the LiteLLM
image pull and cluster bring-up finishing in the background on an 8 GB Docker VM. Worth
knowing before blaming the platform layer for latency.

## Phase 4: Terraform

### Providers, resources, modules, state

- **Provider**: a plugin that knows how to talk to one API (kind, kubernetes, helm, aws).
  `required_providers` declares which; `terraform init` downloads them and writes
  `.terraform.lock.hcl` with exact versions and checksums. That lock file is committed,
  like `uv.lock`, so a teammate's `init` resolves identically.
- **Resource**: one object Terraform owns (`kind_cluster.this`, `helm_release.app`).
  Terraform diffs desired (HCL) against known (state) against real (refresh) and plans
  the minimum change.
- **Module**: a directory of resources with variables and outputs, called like a
  function. `modules/platform` is called from two roots; the roots differ only in how the
  cluster is made and which values they pass.
- **State**: the JSON record of what Terraform created and every attribute it read back.
  It is the only way Terraform maps HCL to real objects, which is why losing it is a
  disaster and why it is treated as sensitive: `kubernetes_secret_v1.platform` stores the
  API keys in state in plain text. Locally that is a file on disk; in a team it must be a
  remote backend with encryption and locking (S3 + DynamoDB, or Terraform Cloud), and the
  production answer is to not put secret *values* through Terraform at all (External
  Secrets Operator pulling from a vault).
- **Where**: `infra/terraform/{modules/platform,local,aws-eks}`.

### The dependency graph, implicit and explicit

- **Concept**: Terraform builds a DAG from attribute references. `module.platform` uses
  `kind_cluster.this.endpoint` through the provider block, so the cluster is created
  first without anyone saying so. `depends_on` is for dependencies the graph cannot see:
  the app chart needs the ingress-nginx *IngressClass* to exist, which no attribute
  expresses, so `helm_release.app` lists `helm_release.ingress_nginx` explicitly.
- **Trade-off**: `depends_on` on a module forces everything inside it to wait for
  everything it names, which can serialise an apply. Use references when an attribute
  exists; reserve `depends_on` for ordering that is real but invisible.

### The sharp edge: providers configured from a resource in the same apply

- **Concept**: the `kubernetes` and `helm` providers need an endpoint and credentials, and
  in the local root those come from `kind_cluster.this`, which does not exist until
  mid-apply. Terraform allows this but with limits: values must be known after the
  resource is created (kind's are), `plan` shows provider-dependent resources as
  "known after apply", and `destroy` can fail if the cluster disappears before the
  provider tries to delete the Helm releases inside it.
- **How this root copes**: `wait_for_ready = true` on the cluster; the platform module is
  `depends_on` the cluster and the image-load step; on destroy, Terraform reverses the
  graph so releases go before the cluster. If a destroy ever wedges, `kind delete cluster`
  plus `terraform state rm` of the in-cluster resources is the escape hatch.
- **Why not split into two applies?** Many teams do (cluster root, then platform root
  with a kubeconfig data source). The completion criterion here was one `apply`, and the
  EKS root demonstrates the same pattern with `aws_eks_cluster_auth`, so the sharp edge
  is worth showing rather than hiding. Recorded as a conscious trade-off in ADR-0005.

### Helm through Terraform vs Helm CLI

- **Concept**: `helm_release` renders and installs the chart exactly as `helm upgrade
  --install` would, but records the release in Terraform state as well as in Helm's own
  release Secret. Two owners of one object is drift waiting to happen, so the rule is:
  Terraform owns releases; the Helm CLI is for `lint`, `template`, `test` and reading.
- **Values plumbing**: the module composes `values = [file(...), yamlencode(...)]` in a
  fixed order (chart defaults < values files < inline < module-owned). The module forces
  `secrets.create=false` and `existingSecret` so the chart can never recreate the Secret
  Terraform manages. Same layering as Helm's own precedence, made explicit.
- **`terraform_data` + `local-exec`** copies locally built images into the kind node. It is
  the one imperative step in the root, isolated and re-runnable with `-replace`. On EKS it
  does not exist because images come from GHCR (ADR-0006).

### Measured: one `terraform apply` from nothing

| Step | Resource | Time |
|---|---|---|
| kind cluster (kubeadm init, CNI, ready) | `kind_cluster.this` | 1 m 18 s |
| load two local images into the node | `terraform_data.kind_load_images` | 19 s |
| namespace + Secret | `kubernetes_*` | < 1 s |
| ingress-nginx chart, `wait = true` | `helm_release.ingress_nginx` | 1 m 16 s |
| application chart, `wait = true` (includes the LiteLLM image pull) | `helm_release.app` | 2 m 53 s |
| **total** | 6 resources | **about 6 min** |

A second `terraform plan` reported "No changes": the configuration is idempotent, which
is the property that makes `apply` safe to run again after editing a value.

**Gotcha, node image vs provider library**: pinning `kindest/node:v1.37.0` (the image the
kind CLI 0.33 uses) made `kubeadm init` fail inside the provider. The provider bundles its
own kind library, whose default node is v1.35.0; a node image *newer* than the library's
kubeadm config API is not supported. Two lessons: a Terraform provider is a frozen copy of
a tool, not a wrapper around the one on your PATH; and "pin everything" needs the pin to
come from the thing that consumes it.

**Gotcha, interrupted apply**: the first run died with the session and left an empty
`terraform.tfstate` and a stale `.terraform.tfstate.lock.info`. Because no resource had
been created yet, deleting both files was the correct fix; had the cluster existed, the
answer would have been `terraform import` (or `kind delete cluster` and start over).
Long applies now run detached with output to a log file.

### `plan` as the review artifact; `destroy` as discipline

- A `terraform plan` output is the thing a reviewer reads in a PR: it lists every create,
  update-in-place, and destroy-and-recreate (`-/+`, the dangerous one) before anything
  happens. CI runs `validate` everywhere and `plan` where credentials exist.
- The EKS root carries its own price list (about $0.30 per hour: control plane, two
  t3.medium, one NAT gateway, one NLB) and a `destroy_reminder` output, because the two
  most expensive items bill while idle. Policy for this repo: EKS is planned, never
  auto-applied.

## Phase 5: Observability and CI

### Prometheus pulls; the Operator tells it where from

- **Concept**: Prometheus scrapes `/metrics` on a schedule (pull), it is not sent data
  (push). Something must tell it *which* endpoints. With the Prometheus Operator that
  something is a **ServiceMonitor**: a CRD that says "scrape the Services matching these
  labels, on this port, at this path". The Operator watches ServiceMonitors and rewrites
  Prometheus's config. Our chart ships one per service.
- **Where**: `templates/servicemonitor.yaml`, guarded by
  `.Capabilities.APIVersions.Has "monitoring.coreos.com/v1"` so the chart installs on a
  cluster without the Operator too. CI renders both ways.
- **Gotcha**: kube-prometheus-stack by default only honours monitors carrying its own
  release label. `serviceMonitorSelectorNilUsesHelmValues: false` (and the pod/rule
  equivalents) makes it pick up everything. Forgetting this is the classic "my
  ServiceMonitor exists but the target never appears".
- **Ordering**: because the templates are CRD-gated, the application release must be
  installed *after* the monitoring release. In Terraform that is a `depends_on`; the
  first apply with monitoring re-rendered the app chart and the monitors appeared.

- **Gotcha, chart version is the change signal**: after adding the monitoring templates,
  `terraform apply` installed kube-prometheus-stack and reported the application release
  as "0 changed". The helm provider (like Helm itself) decides whether a local chart needs
  an upgrade from its `version` and values, not from a hash of the template files. Bumping
  `Chart.yaml` to 0.2.0 produced the in-place upgrade and the monitors appeared. Rule:
  every template change bumps the chart version, which is also what makes `helm history`
  meaningful.

### Four golden signals, applied to an LLM service

| Signal | Metric | Alert |
|---|---|---|
| Traffic | `onchain_agent_requests_total` | (dashboard only) |
| Errors | `requests_total{status!="ok"} / total` | `OnchainAgentHighErrorRate` > 20 % for 10 m |
| Latency | `request_duration_seconds` histogram | `OnchainAgentSlowAnswers` p95 > 120 s |
| Saturation | tokens/min, LLM round-trips per question, MCP tool p95 | (dashboard) |

Plus the dependency view: `onchain_mcp_tool_calls_total{status="error"}` ratio tells
whether the RPC provider or a missing key is the problem, not the model.
Cost is a first-class series (`onchain_agent_llm_cost_usd_total`), which is what makes
"switch `LLM_MODEL` to a hosted alias" a decision you can watch on a graph.

- **Where**: `templates/prometheusrule.yaml` (PrometheusRule CRD, evaluated by
  Prometheus; without Alertmanager they show as firing in the Prometheus UI),
  `dashboards/onchain-agent-platform.json` shipped as a ConfigMap with
  `grafana_dashboard: "1"` for the Grafana sidecar (`searchNamespace: ALL`).

### Grafana provisioning by label

- **Concept**: kube-prometheus-stack's Grafana runs a sidecar that watches ConfigMaps
  with a label and drops their JSON into the dashboards folder. Dashboards therefore
  live in git next to the service they describe, deploy with the chart, and survive pod
  restarts without a persistent volume.
- **Gotcha**: the datasource UID in the JSON must match the provisioned datasource
  (`prometheus` in kube-prometheus-stack); an exported dashboard from another Grafana
  usually carries a random UID and shows "datasource not found".

### GitHub Actions: what each job proves

| Job | Proves |
|---|---|
| `python` (matrix per service) | `uv sync --frozen` reproduces the lock, ruff, pytest |
| `read-only-guard` | ADR-0001 grep across all services |
| `helm` | lint, render with and without Operator CRDs, dashboard JSON parses |
| `terraform` (matrix per root) | `fmt -check`, `init -backend=false`, `validate` with no credentials |
| `images` (main only) | build both Dockerfiles, push `sha-<short>` and `latest` to GHCR |

- **GHCR permissions**: `permissions: packages: write` plus `GITHUB_TOKEN` is enough to
  push to `ghcr.io/<owner>/<image>`. The first push creates a *private* package; making it
  public (so `values.yaml` defaults pull anonymously) is a one-time click in the package
  settings, not something a workflow can do.
- **`-backend=false`**: validates HCL and provider schemas without touching any state or
  cloud API, which is why the EKS root can be checked on every PR without AWS keys.
- **Matrix + `fail-fast: false`**: one service's failure does not hide the other's result.

## Phase 6: Wrap-up

### Reproduction test: destroy, then apply from GHCR images

The completion criterion was "a fresh machine, one `terraform apply`". Simulated by
`terraform destroy` (cluster included) followed by `terraform apply -var
use_local_images=false`, so nothing built on this laptop was used: the node pulled the
two service images from the public GHCR packages CI had published.

| Step | Time |
|---|---|
| `terraform destroy` (9 resources, cluster included) | 2 m 01 s |
| `terraform apply -var use_local_images=false` (8 resources) | 11 m 51 s |
| of which: cluster 1 m 22 s, ingress-nginx 1 m 05 s, kube-prometheus-stack 4 m 58 s, app chart 4 m 14 s | |
| three demo questions through the Ingress afterwards | 42 s, 37 s, 18 s |

The application chart took four minutes because the node pulled three images over the
network (two from GHCR, LiteLLM from its registry); with `kind load` it was under three. The destroy path exercised the sharp edge from
Phase 4 (providers configured from the cluster resource) and Terraform ordered it
correctly: Helm releases and Secrets first, the cluster last.

### Interview-shaped summary of the whole stack

- **Kubernetes** gives me a declarative target: Deployments keep pods alive and roll them,
  Services give stable names, Ingress maps hostnames to Services, ConfigMaps and Secrets
  separate configuration from images, probes tell the platform when a pod is alive and
  when it may receive traffic, and resource requests let the scheduler place work.
- **Helm** packages those objects as one versioned unit with defaults and overrides, so
  the same chart deploys with local images on kind and GHCR images anywhere else; the
  chart version is the change signal, and `helm test` proves the wiring after install.
- **Terraform** owns the order and the lifecycle: create the substrate (kind or EKS),
  create the Secrets it should own, install the operators (ingress, monitoring), then the
  application chart, with the dependency graph making the order explicit and `destroy`
  reversing it. Its state is the one artefact to protect.
- **The platform/cluster split** is what makes the EKS root a small file instead of a
  fork, and it is the same split a real team uses to let one group own clusters and
  another own what runs on them.

### What I would do differently on a second attempt

1. **Two Terraform roots for local too.** Configuring the kubernetes and helm providers
   from a resource in the same apply worked, but it is the part most likely to bite
   someone else. A `cluster` root that writes a kubeconfig and a `platform` root that
   reads it is duller and safer; "one apply" could be a wrapper script.
2. **Raw integers as strings from the MCP server.** A JavaScript client already mangled
   a wei balance above 2^53. The exact-decimal strings are authoritative today; the raw
   fields should be strings too so no client can get it wrong.
3. **Bump the chart version in the same change as any template edit, enforced by CI**
   (compare `Chart.yaml` against `main` when `templates/` changed). I lost twenty minutes
   to a "0 changed" apply that was doing exactly what Helm semantics say.
4. **Pin the kind node image from the provider's default, in the provider's terms.** The
   Kubernetes version should be an explicit variable that CI checks against the provider
   version, not something discovered by a failed `kubeadm init`.
5. **A smaller tool schema payload.** Nine tool schemas are resent on every round-trip and
   dominate prompt tokens with an 8B model. Shorter descriptions, or letting the agent
   send only the tools relevant to the question, would cut latency more than any
   infrastructure change.
6. **Alertmanager plus a notification channel**, even a local webhook sink, so the four
   alert rules end somewhere visible instead of only in the Prometheus UI.
7. **Trace-level visibility for the tool loop** (Langfuse or OpenTelemetry through the
   gateway). Metrics show that a question took 60 s; a trace would show which of the two
   LLM round-trips took 50 of them.

### What held up well

- Read-only by construction never needed revisiting; the grep guard is cheap and loud.
- The gateway alias indirection made "no API key" a configuration decision (ADR-0007)
  instead of a rewrite.
- Health-gated startup in compose, readiness probes in Kubernetes, and `wait = true` in
  Terraform are the same idea three times, and each layer caught real misorderings.
- Writing the ADRs first meant every later debugging session had a document to update
  rather than a decision to reconstruct.
