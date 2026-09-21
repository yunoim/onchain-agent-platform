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
1. MCP Server (Python 3.12, FastMCP, web3.py 7) — 읽기 전용 도구 9개, stdio + streamable-http
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

기타: Ingress는 ingress-nginx + `*.localtest.me`. LLM은 Anthropic 기본, Ollama 대체 경로.
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

### 다음: Phase 1 — MCP 서버
- `services/mcp-server/` uv 프로젝트, `onchain_mcp/` 패키지, 도구 9개, RPC mock 단위 테스트
- Claude Desktop config에 stdio 등록해 실제 질의로 검증
