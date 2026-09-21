# 프로젝트: onchain-agent-platform

## 목적
AI 에이전트가 MCP를 통해 온체인 데이터를 읽고 분석하는 플랫폼을 만들고,
이를 Kubernetes 위에 Terraform으로 배포한다.
이 프로젝트는 DevOps/AI 플랫폼 엔지니어 포지션 지원용 GitHub 포트폴리오다.
완성도보다 "설계 의도를 설명할 수 있는 구조"가 더 중요하다.

- GitHub: https://github.com/yunoim/onchain-agent-platform (public)
- 이미지 레지스트리: `ghcr.io/yunoim/onchain-mcp-server`, `ghcr.io/yunoim/onchain-agent`

## 나에 대해
- 통신사 BSS/OSS 13년차 플랫폼 매니저. RAG, MCP, n8n 기반 에이전트 구축 경험 있음
- Kubernetes, Terraform, Helm은 실무 경험 없음 → 이 프로젝트로 학습하는 게 목적
- 환경: Windows 11 + Docker Desktop. 인프라 CLI는 **Windows 네이티브 PowerShell**에서 실행
  (WSL2는 `/mnt/c` I/O가 느리고 경로 문제가 있어 쓰지 않음)

## 작업 방식 (반드시 지킬 것)
1. 시작 전에 전체 설계와 Phase별 계획을 먼저 보여주고 내 승인을 받을 것
2. Phase가 끝날 때마다 멈추고, 내가 직접 실행할 명령어와 확인 방법을 알려줄 것
3. 인프라 작업(K8s, Terraform, Helm)은 각 결정의 이유를 설명하고,
   핵심 개념을 docs/LEARNING.md에 누적 정리할 것 (면접 대비용)
4. 코드·주석·README·docs는 영어로 작성 (글로벌 포트폴리오). 이 파일(CLAUDE.md)만 한국어
5. 설명과 대화는 한국어로
6. 이 파일에 프로젝트 규칙과 진행 상황을 기록해서 세션이 바뀌어도 이어갈 수 있게 할 것
7. 사용자에게 보여주는 명령어는 PowerShell 5.1 문법 (`&&` 금지, 한 블록에 한 명령)

## 제약 조건
- 온체인 접근은 읽기 전용. 개인키 보관, 서명, 거래 실행 기능은 절대 만들지 말 것
  (ADR-0001. `eth_account` 등 서명 모듈 import 금지, CI에서 grep으로 검사)
- 시크릿(API 키 등)은 절대 커밋하지 않음. .env.example과 K8s Secret으로 관리
- 비용 최소화: 기본은 로컬(kind) 클러스터. AWS EKS는 Terraform 코드만 작성하고
  apply는 내가 명시적으로 요청할 때만. EKS 사용 시 예상 비용과 destroy 방법을 먼저 안내할 것
- 이더리움 메인넷은 공개 RPC 또는 무료 티어 API 사용
- 공개물(README·커밋·문서)에 실명·현 직장명·직책을 넣지 않음. GitHub 핸들 `yunoim`만 사용

## 아키텍처 (상세: docs/ARCHITECTURE.md, 결정 근거: docs/adr/)
1. MCP Server (Python 3.12, mcp SDK 2.x `MCPServer`, web3.py 8) — 읽기 전용 도구 9개, stdio + streamable-http
2. AI Agent (FastAPI) — MCP 클라이언트 + 바운드된 tool-calling 루프, openai SDK로 게이트웨이만 호출
3. AI Gateway (LiteLLM Proxy 공식 이미지) — 모델 alias 라우팅, rate limit, spend log
4. Observability — kube-prometheus-stack + 서비스 /metrics, 토큰·비용 지표는 Agent가 노출
5. Infra — Dockerfile, 단일 Helm 차트, Terraform `local`(kind+helm) / `modules/platform` / `aws-eks`(plan만)
6. CI/CD — GitHub Actions: ruff, pytest, 이미지 빌드→GHCR, helm lint, terraform validate

툴체인: uv, ruff, pytest / Helm 3 / Terraform ≥1.9 / kind / kubectl / gh CLI

## 확정된 설계 결정 (ADR)
| ADR | 결정 |
|---|---|
| 0001 | 읽기 전용을 구조적으로 보장 (서명 모듈 부재 + CI grep) |
| 0002 | 데이터 2계층: RPC(상태, 필수) + Etherscan V2(이력, 선택·키 없으면 명확한 에러) |
| 0003 | MCP 서버 하나, `--transport stdio\|streamable-http` |
| 0004 | 모든 LLM 호출은 LiteLLM 경유. provider 키는 게이트웨이 pod에만 |
| 0005 | Terraform 클러스터 계층 / 플랫폼 모듈 분리. 시크릿은 TF_VAR로 주입 |
| 0006 | 이미지는 GHCR, 로컬은 `kind load`. Helm values로 전환 |

| 0007 | 로컬 우선 라우팅: Ollama qwen3:8b 기본, Anthropic alias는 키 있을 때만 (0004 보정) |

기타: Ingress는 ingress-nginx + `*.localtest.me`. Ollama는 호스트에서 실행(컨테이너 GPU 패스스루 회피).
Langfuse 자체 호스팅은 kind에 무거워 보류, Phase 5에서 Cloud 무료 티어로 재검토.

## Phase 계획
- Phase 0: 레포 구조, CLAUDE.md, 설계 문서(docs/ARCHITECTURE.md, mermaid 다이어그램), ADR
- Phase 1: MCP 서버 + 테스트, 로컬 실행 및 Claude Desktop 연결 확인
- Phase 2: AI 에이전트 + LiteLLM 게이트웨이, docker compose로 전체 로컬 구동
- Phase 3: kind 클러스터 + Helm chart로 K8s 배포
- Phase 4: Terraform으로 Phase 3 재현 (kind + helm provider), 이후 EKS 모듈 작성(plan까지만)
- Phase 5: Observability + GitHub Actions CI/CD
- Phase 6: README 정리 — 문제 정의, 아키텍처, 설계 결정(ADR), 데모 시나리오, 실행 방법

## 완료 기준
- 새 환경에서 README만 보고 terraform apply 한 번으로 로컬 클러스터에 전체 스택이 뜰 것
- 데모 질문 3개 이상이 게이트웨이를 거쳐 정상 응답할 것
- docs/LEARNING.md만 읽고 내가 K8s·Terraform·Helm 구조를 설명할 수 있을 것

## 데모 질문
1. vitalik.eth 잔고 + 최근 5개 트랜잭션 요약
2. 최근 2000블록 내 100만 USDC 이상 전송 찾기
3. 현재 가스비 + 최신 블록 번호

---

## 진행 로그

### 2026-09-21 — Phase 0 완료
- GitHub public 레포 생성 (`yunoim/onchain-agent-platform`), `main` 브랜치, 로컬 git init
- 디렉토리 스캐폴딩, LICENSE(MIT, yunoim), .gitignore, .env.example
- docs/ARCHITECTURE.md (mermaid 3종: 시스템 컨텍스트 · 요청 시퀀스 · kind 배포 토폴로지)
- docs/adr/0001~0006 + 인덱스, docs/LEARNING.md 골격(Phase 0 항목 3개 기록)
- 로컬 툴 확인: git·python·uv·docker·kubectl·helm 있음 / **kind·terraform 미설치** → Phase 3·4 전에 winget 설치
- 미확정: Anthropic API 키 준비 여부(Phase 2에 필요), EKS 실제 apply 여부(Phase 4 끝에 재확인)

### 2026-09-21 — Phase 1 완료 (MCP 서버)
- `services/mcp-server/`: uv 프로젝트, `onchain_mcp` 패키지, 도구 9개, `onchain-mcp` CLI(`--transport stdio|streamable-http`)
- **설치된 SDK는 mcp 2.2.0** — `FastMCP`가 `MCPServer`로 개명됨(`mcp.server.mcpserver`). 결과 속성은 snake_case(`input_schema`, `is_error`). web3 8.0.0
- 도구는 동기 함수로 작성(SDK가 워커 스레드에서 실행). 클라이언트는 lifespan에서 만들어 `ctx.request_context.lifespan_context`로 주입. 테스트는 `state_factory`로 가짜 Web3 주입
- 테스트 44개 통과(가짜 Web3, httpx MockTransport, 인메모리 `Client(server)`, ADR-0001 grep 테스트)
- 검증 완료: 실제 메인넷 스모크(ENS·잔고·finalized 블록·USDC 메타·200블록 전송 스캔 6초·Etherscan 키 부재 에러), stdio 전송(CLI spawn), HTTP 전송(`/healthz`·`/metrics`·`POST /mcp`), Docker 이미지 빌드·실행(79MB, uid 10001)
- `scripts/check-no-signing.sh|.ps1`: ADR-0001 CI 가드
- LEARNING.md Phase 1 항목 8개 기록
- **Claude Desktop 연결 확인 완료**(23:10): `scripts/register-claude-desktop.ps1`로 등록 → 앱 재시작 → Code 세션에 `mcp__onchain__*` 도구 9개 로드 → `get_eth_balance("vitalik.eth")`·`get_gas_price()` 실호출 성공
- ⚠️ Claude Desktop 등록 시 함정 2개 (재현 방지): ① Store(MSIX) 빌드는 `%APPDATA%\Claude`가 가상화돼 일반 셸에는 없음. 실제 파일은 `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\claude_desktop_config.json`. Claude Code 세션 내부 도구는 앱의 자식 프로세스라 가상화 경로가 보이므로 사용자 셸과 결과가 다름. ② 앱은 시작 시 파일을 한 번 읽고 이후 설정 저장마다 메모리 상태로 파일을 통째로 덮어씀 → **앱을 완전히 종료한 뒤** 편집해야 함. 스크립트가 두 경우 모두 처리
- 후속 과제: JS 클라이언트가 `balance_wei` 같은 큰 정수를 float으로 파싱해 정밀도가 깨짐(2^53 초과). 문자열 필드(`balance_eth`)가 정본이며, raw 정수 필드도 문자열로 바꾸는 것을 Phase 2에서 검토

### 2026-09-21 — Phase 2 완료 (Agent + LiteLLM + docker compose)
- **사용자 결정: Anthropic 키 없이 Ollama 로컬 모델로 진행** → ADR-0007(로컬 우선 라우팅, ADR-0004 보정). 호스트 RTX 3070 Laptop 8GB, `qwen3:8b`(tool calling 지원 확인), Ollama 0.34.0. `ollama serve`는 호스트에서 수동 실행 상태여야 함
- `services/gateway/litellm/config.yaml`: alias `local-default`(ollama_chat/qwen3:8b, num_ctx 12288, temp 0.1, 비용 0) · `claude-default`(claude-sonnet-5) · `claude-fast`(claude-haiku-4-5) → 키 없으면 `local-default`로 fallback. DB 없음(spend log 미사용, 토큰·비용은 Agent가 계측)
- `services/agent/`: FastAPI `POST /ask` · `/tools` · `/healthz` · `/readyz`(MCP+게이트웨이 모두 확인) · `/metrics`. `Agent.run` 루프: 최대 8회, 초과 시 도구 없이 최종 답 강제. `<think>` 제거, 도구 결과 6000자 캡, 잘못된 JSON 인자는 모델에 에러로 되돌림. openai SDK 3.16(호환), mcp 2.2 `Client(url)`. 테스트 12개(가짜 ChatClient·ToolExecutor, TestClient)
- `docker-compose.yml`: mcp-server · litellm(공식 이미지 main-stable) · agent, healthcheck + `depends_on: service_healthy`
- **데모 3문 전부 성공** (게이트웨이 경유, 로컬 모델, 비용 $0): ① vitalik.eth 잔고 20초/2회전/3,667토큰 ② USDC 300블록 100만+ 전송 상위 3건 46초/4,939토큰 ③ 가스+최신블록 27초/도구 2개. → **완료 기준 2번 충족**
- ⚠️ 삽질 기록: compose에 `extra_hosts: host.docker.internal:host-gateway`를 넣으면 Docker Desktop의 기본 매핑(호스트 루프백)을 172.17.0.1로 덮어써 Ollama 연결 실패. 제거로 해결. Linux 호스트는 `OLLAMA_BASE_URL`로 지정
- `scripts/demo.ps1|.sh`: 데모 3문 실행기
- 한계: 8B 모델은 요약 문구가 부정확할 수 있음(②에서 "3건 발견"이라 했지만 실제는 매칭 다수 중 상위 3건). 답변 정확성 자체는 도구 결과에 근거

### 다음: Phase 3 — kind + Helm
- 선행: `winget install Kubernetes.kind` (terraform은 Phase 4)
- `deploy/kind/cluster.yaml`(extraPortMappings 80/443), ingress-nginx, `deploy/helm/onchain-agent-platform/` 단일 차트(3 Deployment + Service + Ingress + ConfigMap(litellm) + Secret 참조), `values.yaml`(GHCR) / `values-local.yaml`(로컬 이미지, pullPolicy Never), `scripts/kind-load.ps1|.sh`
- Ollama는 호스트: 클러스터에서 `host.docker.internal:11434`(kind 노드 = Docker Desktop 컨테이너라 동일하게 해석되는지 확인 필요)
- 검증: `agent.localtest.me/ask`로 데모 3문
