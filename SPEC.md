# SPEC.md — Alfred Jr

## 1. Objective

Microsoft Teams에서 동작하는 AI 어시스턴트 챗봇. 임직원이 Teams 채팅에서 질문을 보내면
Gemini 모델이 답변한다.

**핵심 원칙:** `local`과 `server` 두 profile이 단일 코드베이스에 공존한다.
profile에 따라 활성화되는 도구(tool)와 권한이 달라지며, 인프라 설정만 분리된다.

**대상 사용자:** 사내 임직원  
**배포 환경:** 로컬 맥북 (`local`) ↔ 사내 온프레미스 클라우드 (`server`)

---

## 2. Profile 개요

두 profile은 동시에 운영된다. `local`은 맥북에서 항시 실행, `server`는 온프레미스 클라우드에서 항시 실행. 서로 대체하지 않고, 각자 고유한 역할을 가진다.

| 항목 | `local` | `server` |
|---|---|---|
| 목적 | **개인 맥북 제어** — 파일·앱·시스템 명령 실행 | **사내 시스템 조회** — 데이터 접근, 구동 서버 제어 불가 |
| 채널 | **Telegram** (개인 계정, bot token) | **Microsoft Teams** (Bot Framework) |
| 도구 | 없음 (Q&A only, v1) → 맥북 제어 tool 확장 예정 | 없음 (Q&A only, v1) → 사내 API 조회 tool 확장 예정 |
| 시스템 제어 | ✅ 맥북 (파일, 앱, 쉘 명령 등) | ❌ 서버 자체 제어 불가 |
| 사내 시스템 접근 | ❌ | ✅ |
| 네트워크 | ngrok 고정 tunnel | 직접 공인 엔드포인트 (터널 불필요) |
| 프로세스 관리 | launchd (LaunchAgent) | systemd / 컨테이너 |
| 인증 | Telegram bot token | Azure Bot Framework 서명 검증 |
| 설정 파일 | `.env.local` | `.env.server` |

profile은 `PROFILE` 환경변수 하나로 선택한다. 코드 내 `if profile == "server"` 분기는
`config.py`와 `tools/registry.py`에만 허용하고, 나머지 코드는 profile을 직접 참조하지 않는다.

---

## 3. 아키텍처

```
[Telegram 사용자]          [Teams 사용자]
       │ webhook                  │ HTTPS POST (Activity)
       ▼                          ▼
[ngrok tunnel]         [Bot Framework / 직접 엔드포인트]
       │                          │
       └──────────┬───────────────┘
                  ▼
     [FastAPI webhook server]     src/agent/server.py
              │
              ▼
     [Channel registry]          src/agent/channels/registry.py
      profile → 활성 채널 결정
      ├── local  → TelegramChannel   src/agent/channels/telegram.py
      └── server → TeamsChannel      src/agent/channels/teams.py
              │
              ▼
     [LangGraph agent]           src/agent/graph.py
       build_graph(settings)
              │
              ├── ProfileSettings    src/agent/config.py
              ├── Tool registry      src/agent/tools/registry.py
              └── Gemini model       google_genai
```

---

## 4. 프로젝트 구조

```
alfred-jr/
├── src/
│   └── agent/
│       ├── __init__.py
│       ├── config.py              # ProfileSettings — 단일 진실 공급원
│       ├── graph.py               # build_graph(settings) — profile-aware
│       ├── server.py              # FastAPI + 채널 registry mount
│       ├── client.py              # 로컬 테스트용 클라이언트
│       ├── channels/
│       │   ├── __init__.py
│       │   ├── base.py            # 추상 Channel 인터페이스
│       │   ├── registry.py        # PROFILE_CHANNELS — 단일 진실 공급원
│       │   ├── teams.py           # Teams/Bot Framework 구현
│       │   └── telegram.py        # Telegram Bot API 구현
│       └── tools/
│           ├── __init__.py
│           ├── registry.py        # profile별 tool 목록 반환
│           ├── common.py          # 모든 profile 공통 tool
│           ├── local.py           # local 전용 tool (맥북 제어)
│           └── server.py          # server 전용 tool (사내 시스템)
├── infra/
│   ├── local/
│   │   ├── com.alfred-jr.tunnel.plist       # launchd — ngrok tunnel
│   │   └── com.alfred-jr.server.plist       # launchd — FastAPI server
│   └── server/
│       ├── alfred-jr.service                # systemd unit
│       └── Dockerfile
├── tests/
│   ├── conftest.py
│   ├── unit_tests/
│   │   ├── __init__.py
│   │   ├── test_config.py
│   │   ├── test_graph.py
│   │   └── test_channels.py       # channel registry 검증
│   └── integration_tests/
│       ├── __init__.py
│       ├── test_telegram.py       # Telegram webhook → agent
│       └── test_teams.py          # Teams webhook → agent
├── .env.local
├── .env.server
├── .env.example
├── pyproject.toml
├── langgraph.json
└── SPEC.md
```

---

## 5. Channel Registry (`src/agent/channels/registry.py`)

tool registry와 동일한 원칙으로 설계한다. profile별 활성 채널을 단일 위치에서 관리하며,
`server.py`는 이 registry만 참조하고 채널 구현을 직접 알지 못한다.

```python
PROFILE_CHANNELS = {
    "local":  ["telegram"],
    "server": ["teams"],
}

def get_channels(profile: str) -> list[BaseChannel]:
    ...
```

각 채널은 `BaseChannel.mount(app, graph, settings)` 구현으로 FastAPI에 라우트를 등록한다:
- `TelegramChannel` → `POST /telegram/webhook`
- `TeamsChannel`    → `POST /api/messages`

**channel registry 원칙:**

| 원칙 | tools | channels |
|---|---|---|
| 단일 진실 공급원 | `tools/registry.py` | `channels/registry.py` |
| Cross-profile 혼용 금지 | ✅ | ✅ |
| 새 항목 추가 위치 | registry + 전용 파일 | registry + 전용 파일 |
| profile 분기 허용 위치 | registry만 | registry만 |

---

## 6. Config 설계 (`src/agent/config.py`)

Pydantic `BaseSettings`로 환경변수를 읽고, profile에 따라 허용 tool 목록과 권한을 결정한다.

```python
from pydantic_settings import BaseSettings
from typing import Literal

class ProfileSettings(BaseSettings):
    profile: Literal["local", "server"] = "local"

    # 공통
    gemini_api_key: str

    # local 전용
    tunnel_url: str = ""
    telegram_bot_token: str = ""      # Telegram BotFather에서 발급

    # server 전용
    bot_app_id: str = ""
    bot_app_password: str = ""
    bot_tenant_id: str = ""
    internal_api_base_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env.local",    # PROFILE에 따라 동적으로 교체
        env_file_encoding="utf-8",
    )

def load_settings() -> ProfileSettings:
    profile = os.getenv("PROFILE", "local")
    return ProfileSettings(_env_file=f".env.{profile}")
```

`server.py`와 `graph.py`는 `load_settings()`로 받은 객체만 참조하고
`PROFILE` 환경변수를 직접 읽지 않는다.

---

## 7. Tool Registry (`src/agent/tools/registry.py`)

profile별 tool 목록을 단일 위치에서 관리한다. 새 tool 추가 시 이 파일만 수정한다.

```python
from .common import COMMON_TOOLS
from .local import LOCAL_TOOLS
from .server import SERVER_TOOLS
from langchain_core.tools import BaseTool

PROFILE_TOOLS: dict[str, list[BaseTool]] = {
    "local":  COMMON_TOOLS,                        # v1: Q&A only
    "server": COMMON_TOOLS + SERVER_TOOLS,         # v2+: 확장
}

def get_tools(profile: str) -> list[BaseTool]:
    return PROFILE_TOOLS.get(profile, COMMON_TOOLS)
```

**v1 tool 목록:**

| Tool | common | local | server |
|---|---|---|---|
| (없음, Q&A only) | — | — | — |

**v2+ 예정:**

| Tool | common | local | server |
|---|---|---|---|
| 맥북 파일 R/W | | ✅ | |
| 맥북 쉘 명령 실행 | | ✅ | |
| 맥북 앱 제어 | | ✅ | |
| 사내 API 조회 | | | ✅ |
| 사내 데이터 검색 | | | ✅ |

---

## 8. 권한 매트릭스

| 권한 | local | server | 비고 |
|---|---|---|---|
| Gemini Q&A | ✅ | ✅ | 항상 허용 |
| Tool 호출 | ❌ (v1) | ❌ (v1) | v2+에서 profile별 확장 |
| 맥북 파일 시스템 R/W | ❌ (v1) → ✅ (v2+) | ❌ 영구 금지 | local 전용 |
| 맥북 쉘 명령 실행 | ❌ (v1) → ✅ (v2+) | ❌ 영구 금지 | local 전용, 추가 시 확인 필요 |
| 맥북 앱 제어 | ❌ (v1) → ✅ (v2+) | ❌ 영구 금지 | local 전용, 추가 시 확인 필요 |
| 사내 API 조회 | ❌ 영구 금지 | ❌ (v1) → ✅ (v2+) | server 전용 |
| 서버 자체 시스템 제어 | ❌ 영구 금지 | ❌ 영구 금지 | 어느 profile도 불가 |
| 외부 인터넷 호출 | ❌ | ❌ | 추가 전 반드시 확인 |

---

## 9. 인프라 설정

### 8-1. Teams Bot 등록 (최초 1회)

1. Azure Portal → Azure Bot 리소스 생성
2. Messaging endpoint 등록:
   - `local`: `https://<tunnel-subdomain>.cfargotunnel.com/api/messages`
   - `server`: `https://<온프레미스-도메인>/api/messages`
3. `BOT_APP_ID`, `BOT_APP_PASSWORD` 발급 → 각 `.env.*` 파일에 저장

### 8-2. cloudflared Named Tunnel (local profile)

```bash
# 최초 1회 설정
cloudflared login
cloudflared tunnel create alfred-jr
cloudflared tunnel route dns alfred-jr <subdomain>
```

`infra/local/cloudflared.yml`:
```yaml
tunnel: alfred-jr
credentials-file: ~/.cloudflared/<tunnel-id>.json
ingress:
  - hostname: <subdomain>.cfargotunnel.com
    service: http://localhost:8000
  - service: http_status:404
```

Named tunnel 사용 → URL 영구 고정 → Teams endpoint 재등록 불필요.

### 8-3. launchd 자동 시작 (local profile, 맥북 로그인 시)

`infra/local/com.alfred-jr.tunnel.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
  <key>Label</key><string>com.alfred-jr.tunnel</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/local/bin/cloudflared</string>
    <string>tunnel</string>
    <string>--config</string>
    <string>/Users/<username>/repos/alfred-jr/infra/local/cloudflared.yml</string>
    <string>run</string>
    <string>alfred-jr</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/tmp/alfred-jr-tunnel.log</string>
  <key>StandardErrorPath</key><string>/tmp/alfred-jr-tunnel.err</string>
</dict>
</plist>
```

등록:
```bash
cp infra/local/com.alfred-jr.tunnel.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.alfred-jr.tunnel.plist
```

### 8-4. 실행

```bash
# local
PROFILE=local uv run uvicorn src.agent.server:app --host 0.0.0.0 --port 8000

# server
PROFILE=server uv run uvicorn src.agent.server:app --host 0.0.0.0 --port 8000
```

---

## 9. 환경변수 파일

`.env.example` (git 포함, 실제 값 없음):
```dotenv
PROFILE=local

# 공통
GEMINI_API_KEY=

# local 전용
TUNNEL_URL=
TELEGRAM_BOT_TOKEN=

# server 전용
BOT_APP_ID=
BOT_APP_PASSWORD=
BOT_TENANT_ID=
INTERNAL_API_BASE_URL=
```

`.env.local`, `.env.server` → **git 제외** (`.gitignore`에 추가)

---

## 10. 의존성

```toml
dependencies = [
    "langchain>=1.0.0",
    "langchain-google-genai>=2.0.0",
    "langgraph>=1.0.0",
    "fastapi>=0.110.0",
    "uvicorn>=0.29.0",
    "botbuilder-core>=4.16.0",
    "botbuilder-integration-aiohttp>=4.16.0",
    "python-telegram-bot>=21.0.0",
    "pydantic-settings>=2.0.0",
    "python-dotenv>=1.0.0",
    "ipython>=8.0.0",
]
```

---

## 11. 코드 스타일

- Python 3.11+, 타입 힌트 필수
- 비동기(async/await) 우선
- `profile` 분기는 `config.py`와 `tools/registry.py`에만 허용
- 환경변수는 `ProfileSettings`를 통해서만 접근 — `os.getenv` 직접 호출 금지
- 주석은 WHY가 명확할 때만

---

## 12. 테스트 전략

| 레벨 | 대상 | profile | 방법 |
|---|---|---|---|
| Unit | config 로딩, tool registry | local·server 양쪽 | pytest, mock 환경변수 |
| Unit | LangGraph graph 로직 | local | pytest, mock Gemini |
| Integration | webhook → agent 전체 흐름 | local | pytest + FastAPI TestClient |
| 수동 | Teams 실제 메시지 | local | cloudflared tunnel |

새 tool 추가 시 해당 profile의 unit test도 함께 추가한다.

---

## 13. Boundaries

**항상 한다:**
- `ProfileSettings`를 통해서만 설정 접근
- Bot Framework 서명 검증 (`BotFrameworkAdapter` 사용)
- `.env.local`, `.env.server`는 git에서 제외
- 새 tool은 `tools/registry.py`의 `PROFILE_TOOLS`에 명시적으로 등록

**먼저 확인한다:**
- 새 tool 추가 — 어느 profile에 넣을지, 권한 범위는 무엇인지
- `server` profile에 외부 API 접근 추가
- Teams 외 채널 추가

**절대 하지 않는다:**
- API 키·비밀번호 코드에 직접 작성
- Bot Framework 서명 검증 우회
- `local` tool을 `server`에 자동 포함 (registry 명시 필수)
- `server` profile에서 서버 시스템 제어 (쉘 명령, 파일 쓰기 등)
- `server` profile에서 맥북 제어 tool 실행
- 사용자 메시지를 무단으로 외부 전송

---

## 14. 배포 구성

두 profile은 독립적으로 상시 실행된다.

```
[Teams 테스트 bot]                [Teams 운영 bot]
       │                                 │
       ▼                                 ▼
[cloudflared tunnel]          [온프레미스 공인 엔드포인트]
       │                                 │
       ▼                                 ▼
[로컬 맥북 :8000]              [온프레미스 서버 :8000]
  PROFILE=local                  PROFILE=server
```

**Teams bot 등록은 2개로 분리한다.**  
같은 코드베이스를 실행하지만 서로 다른 bot 자격증명(`BOT_APP_ID`, `BOT_APP_PASSWORD`)과
엔드포인트를 사용하므로 `.env.local`과 `.env.server`의 값이 달라진다.

### server profile 추가 배포 체크리스트

| 항목 | 내용 |
|---|---|
| `.env.server` 작성 | 서버 전용 환경변수 (bot 자격증명, 사내 API URL 등) |
| Teams 운영 bot 등록 | Azure Portal에서 별도 bot 생성, 서버 도메인 endpoint 등록 |
| `infra/server/` 설정 | systemd unit 또는 Dockerfile 작성 |
| `server` profile tool 활성화 | `tools/registry.py`에 추가 후 테스트 |
| 권한 매트릭스 재검토 | 사내 API 접근 범위 확인 후 진행 |
