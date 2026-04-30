# Implementation Plan: Alfred Jr (v1)

## Overview

단일 코드베이스에서 `local`(맥북 개인 bot)과 `server`(전사 운영 bot) 두 profile을 동시에
운영하는 Teams Q&A 챗봇을 구축한다. v1은 도구 없이 Gemini 기반 Q&A만 제공하며,
profile별 tool 확장을 위한 구조(config, registry)를 v1에서 완성한다.

## 현재 상태

- `src/agent/graph.py`: LangGraph 템플릿 placeholder (교체 대상)
- `src/agent/client.py`: langgraph_sdk 테스트 클라이언트 (유지)
- `pyproject.toml`: 기본 의존성 있음, fastapi·uvicorn·botbuilder·pydantic-settings 누락
- `tests/`: placeholder 수준 (재작성 대상)
- `infra/`, `src/agent/tools/`: 미존재 (신규 생성)

## 의존성 그래프

```
[pyproject.toml 의존성 추가]
        │
        ▼
[ProfileSettings — config.py]
        │
        ├──────────────────────────────┐
        ▼                              ▼
[Tool Registry — tools/]     [Unit tests: config]
        │
        ▼
[LangGraph Q&A Agent — graph.py]
        │
        ├──────────────────────────────┐
        ▼                              ▼
[FastAPI Webhook Server — server.py]  [Unit tests: graph]
        │
        ▼
[Integration test: webhook → agent]
        │
        ▼
[Infra 파일 — infra/local/]
```

## 아키텍처 결정

- **pydantic-settings**: 환경변수를 타입 안전하게 로드. profile별 `.env` 파일 동적 선택.
- **botbuilder-core + botbuilder-integration-aiohttp**: Teams Bot Framework 공식 Python SDK.
  `aiohttp` 기반이나 FastAPI와 브리지 가능 (`Request` body를 직접 파싱).
- **Tool registry**: v1은 빈 list, 파일 구조만 완성. 새 tool 추가 시 `registry.py`만 수정.
- **graph.py 전면 교체**: 현재 파일은 placeholder. MessagesState + Gemini + profile 인식으로 재작성.
- **langgraph.json**: `env` 필드를 `.env.local`로 고정하지 않고 `PROFILE` 주입 방식으로 운용.

## 리스크

| 리스크 | 영향 | 대응 |
|---|---|---|
| `botbuilder` 패키지와 Python 3.11 호환성 | High | Task 1에서 설치 후 즉시 import 확인 |
| Bot Framework 서명 검증 복잡도 | Medium | Task 5에서 검증 우회 없이 구현, 실패 시 별도 이슈화 |
| cloudflared 계정·도메인 설정 필요 (외부 의존) | Low | infra 파일만 제공, 실제 설정은 README로 안내 |

## 미결 사항

- `server` profile의 `BOT_APP_ID`/`BOT_APP_PASSWORD`는 별도 Azure bot 등록 후 확보 필요
  → Task 7 infra 파일에서 placeholder로 표기

---

## Phase 1: Foundation

### Task 1: 의존성 추가 및 환경 파일 정비

**Description:** pyproject.toml에 누락된 의존성을 추가하고, `.env.example`과 `.gitignore`를
정비해 두 profile 환경변수 관리 기반을 마련한다.

**Acceptance criteria:**
- [ ] `fastapi`, `uvicorn`, `botbuilder-core`, `botbuilder-integration-aiohttp`, `pydantic-settings`가 pyproject.toml에 추가되고 `uv sync` 성공
- [ ] `botbuilder-core`가 Python 3.11에서 `import` 가능
- [ ] `.env.example`에 `PROFILE`, `GEMINI_API_KEY`, `BOT_APP_ID`, `BOT_APP_PASSWORD`, `TUNNEL_URL`, `INTERNAL_API_BASE_URL` 항목 존재
- [ ] `.gitignore`에 `.env.local`, `.env.server` 포함

**Verification:**
- [ ] `uv sync` 오류 없음
- [ ] `python -c "import botbuilder.core; import fastapi; import pydantic_settings"` 성공

**Dependencies:** 없음

**Files:**
- `pyproject.toml`
- `.env.example` (신규)
- `.gitignore`

**Scope:** S

---

### Task 2: ProfileSettings (config.py)

**Description:** `ProfileSettings`를 구현한다. `PROFILE` 환경변수로 `.env.local` 또는
`.env.server`를 선택적으로 로드하고, 공통·profile 전용 설정을 타입 안전하게 노출한다.

**Acceptance criteria:**
- [ ] `load_settings()`가 `PROFILE=local`일 때 `.env.local`을 읽음
- [ ] `load_settings()`가 `PROFILE=server`일 때 `.env.server`를 읽음
- [ ] `gemini_api_key`가 없으면 `ValidationError` 발생
- [ ] `os.getenv` 직접 호출 없음

**Verification:**
- [ ] `pytest tests/unit_tests/test_config.py` 통과

**Dependencies:** Task 1

**Files:**
- `src/agent/config.py` (신규)
- `tests/unit_tests/test_config.py` (재작성)

**Scope:** S

---

### Task 3: Tool Registry scaffold

**Description:** v1은 도구 없이 Q&A only이지만, 향후 tool 추가를 위한 파일 구조와 registry를
완성한다. 각 파일은 빈 tool 목록을 반환하며, `PROFILE_TOOLS` 딕셔너리가 단일 진실 공급원이 된다.

**Acceptance criteria:**
- [ ] `get_tools("local")`과 `get_tools("server")` 모두 빈 list 반환 (v1)
- [ ] `common.py`, `local.py`, `server.py` 파일이 각각 `COMMON_TOOLS`, `LOCAL_TOOLS`, `SERVER_TOOLS` 변수를 export
- [ ] `local.py`와 `server.py`의 tool이 registry 명시 없이 cross-profile로 섞이지 않음

**Verification:**
- [ ] `python -c "from agent.tools.registry import get_tools; assert get_tools('local') == []"` 성공

**Dependencies:** Task 2

**Files:**
- `src/agent/tools/__init__.py` (신규)
- `src/agent/tools/registry.py` (신규)
- `src/agent/tools/common.py` (신규)
- `src/agent/tools/local.py` (신규)
- `src/agent/tools/server.py` (신규)

**Scope:** S

---

## Checkpoint 1 — Foundation
- [ ] `uv sync` 성공, 모든 의존성 import 가능
- [ ] `pytest tests/unit_tests/test_config.py` 통과
- [ ] tool registry가 양쪽 profile에서 빈 list 반환
- [ ] 진행 전 검토

---

## Phase 2: Agent & Server

### Task 4: LangGraph Q&A Agent

**Description:** `graph.py`를 전면 교체한다. `ProfileSettings`와 tool registry를 받아
Gemini 모델 기반 Q&A 그래프를 빌드하는 `build_graph(settings)` 함수를 구현한다.
v1은 tool node 없이 llm_call → END 단순 구조.

**Acceptance criteria:**
- [ ] `build_graph(settings)`가 `CompiledStateGraph`를 반환
- [ ] `MessagesState`에 `messages` 필드 존재
- [ ] `HumanMessage` 입력 → `AIMessage` 응답 반환
- [ ] `graph.py` 내에서 `PROFILE` 환경변수 직접 참조 없음
- [ ] `langgraph.json`의 `agent` 엔트리포인트가 새 graph 객체를 가리킴

**Verification:**
- [ ] `pytest tests/unit_tests/test_graph.py` 통과 (mock Gemini 사용)

**Dependencies:** Task 2, Task 3

**Files:**
- `src/agent/graph.py` (전면 교체)
- `src/agent/__init__.py` (업데이트)
- `tests/unit_tests/test_graph.py` (재작성)

**Scope:** M

---

### Task 5: FastAPI Webhook Server

**Description:** Teams Bot Framework 메시지를 수신하는 FastAPI 서버를 구현한다.
`BotFrameworkAdapter`로 서명 검증 후 메시지를 추출해 LangGraph agent를 호출하고 응답을 반환한다.

**Acceptance criteria:**
- [ ] `POST /api/messages` 엔드포인트 존재
- [ ] Bot Framework 서명 검증 통과한 요청만 처리 (검증 실패 시 401)
- [ ] `GET /health` 엔드포인트가 200과 profile 이름 반환
- [ ] `server.py` 내 `PROFILE` 환경변수 직접 참조 없음

**Verification:**
- [ ] `uv run uvicorn src.agent.server:app --port 8000` 실행 성공
- [ ] `curl localhost:8000/health` → 200

**Dependencies:** Task 4

**Files:**
- `src/agent/server.py` (신규)

**Scope:** M

---

### Task 6: Webhook → Agent 통합 테스트

**Description:** FastAPI TestClient로 실제 Teams Activity payload를 전송해
webhook → agent → 응답 전체 흐름을 검증한다. Bot Framework 서명 검증은 테스트 환경에서
mock 처리한다.

**Acceptance criteria:**
- [ ] mock Activity payload 전송 시 200 응답
- [ ] 잘못된 서명 전송 시 401 응답
- [ ] `messages` 상태에 AIMessage가 포함됨

**Verification:**
- [ ] `pytest tests/integration_tests/test_webhook.py` 통과

**Dependencies:** Task 5

**Files:**
- `tests/integration_tests/test_webhook.py` (재작성)
- `tests/conftest.py` (보강)

**Scope:** S

---

## Checkpoint 2 — Agent & Server
- [ ] `pytest tests/` 전체 통과
- [ ] health endpoint 응답 확인
- [ ] `PROFILE=local`로 서버 기동 후 로그 정상 출력
- [ ] 진행 전 검토

---

## Phase 3: Infra

### Task 7: 인프라 파일 (local profile)

**Description:** cloudflared named tunnel 설정 파일과 launchd LaunchAgent plist를 생성한다.
실제 tunnel ID와 username은 placeholder로 표기하고, 설정 방법을 README로 안내한다.

**Acceptance criteria:**
- [ ] `infra/local/cloudflared.yml` 존재, `tunnel`·`credentials-file`·`ingress` 필드 포함
- [ ] `infra/local/com.alfred-jr.tunnel.plist` 존재, `RunAtLoad=true`·`KeepAlive=true` 포함
- [ ] `infra/server/` 디렉터리와 `alfred-jr.service` placeholder 존재
- [ ] `langgraph.json`의 `env` 필드가 `.env.local` 참조 (로컬 개발 기본값)

**Verification:**
- [ ] `plutil -lint infra/local/com.alfred-jr.tunnel.plist` 오류 없음
- [ ] `cat infra/local/cloudflared.yml` 에 placeholder 식별 가능

**Dependencies:** Task 1

**Files:**
- `infra/local/cloudflared.yml` (신규)
- `infra/local/com.alfred-jr.tunnel.plist` (신규)
- `infra/server/alfred-jr.service` (신규, placeholder)
- `langgraph.json` (업데이트)

**Scope:** S

---

## Checkpoint 3 — Complete
- [ ] `pytest tests/` 전체 통과
- [ ] `PROFILE=local uv run uvicorn src.agent.server:app --port 8000` 정상 기동
- [ ] `plutil -lint` plist 통과
- [ ] `.env.local`, `.env.server` git에서 제외 확인
- [ ] 전체 검토 후 완료
