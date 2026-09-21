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

### Container hygiene picked up along the way

- Two-stage `uv` build: the resolver runs in a builder image; the runtime image gets
  only the virtualenv. Dependency layer is installed before source is copied so code
  edits do not re-resolve packages.
- Non-root user (`uid 10001`), `HEALTHCHECK` hitting `/healthz`, `PYTHONUNBUFFERED=1`
  so logs stream. Image is about 80 MB.
- `.dockerignore` excludes `.venv` and tests; otherwise the host virtualenv (Windows
  binaries) would be copied into the Linux build context.

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
