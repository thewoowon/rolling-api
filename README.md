# rolling-api

> Rolling 백엔드 — 누구나 방장이 되고, Rolling 플래너가 운영을 맡는 오프라인 소개팅 플랫폼.

`FastAPI + PostgreSQL + SQLAlchemy 2.x (async)` 기반의 API 서버입니다. 웹 클라이언트는 [`rolling`](../../web/rolling/)에 있어요. 도메인 / IA 의도는 `rolling_blueprint.md`에 정리되어 있습니다.

---

## 한눈에 보는 도메인

```
[Host (누구나)]                                 [Rolling 직원]
   ▶ 방 생성 (DRAFT)
   ▶ 공개 (PUBLISHED)
   ▶ 신청자 큐레이션 (승인 → 결제 확정)
                                                 양쪽 성별 모두 50% 도달
                                                 ⤷ 자동 VIABLE 전환
                                                 ⤷ Rolling 큐 진입
                                  Admin ─────────▶ 플래너 배정 (ASSIGNED)
                                                 ⤷ 플래너 수락 (CONFIRMED)
                                                 ⤷ 체크인 / 로테이션 / 종료
                                                                  ▼
                                                          ▶ 상호 선택 / 매치
                                                          ▶ 애프터 / 피드백
```

이 흐름이 모든 엔드포인트의 출발점이에요. 누가 어디서 권한이 있는지를 기억해두면 API 설계가 자연스럽게 따라옵니다.

| 액터 | 권한 |
| --- | --- |
| **Host** (누구나, 인증됨) | 자기 방의 생성·공개·신청자 승인·결제 확정 |
| **Planner** (`role=planner`, `status=approved`) | 배정된 방의 체크인·로테이션·종료 |
| **Admin** (`role=admin`) | 유저/플래너 모더레이션, 큐 모니터링, 플래너 배정 |
| **Participant** (인증됨) | 방 둘러보기·신청·체크인·선택·피드백·신고 |

---

## 빠른 시작

```bash
cp .env.example .env
# JWT_SECRET_KEY 최소한 바꿔주세요

docker compose up -d --build
docker compose exec api poetry run alembic upgrade head
docker compose exec api poetry run python -m app.scripts.seed
```

→ <http://localhost:8000/api/v1/docs>

이걸로 어드민/플래너/참가자 시드 계정과 시드 방 한 개까지 준비됩니다.

| 이메일 | 비밀번호 | 역할 |
| --- | --- | --- |
| `admin@example.com` | `admin1234` | admin |
| `planner@example.com` | `planner1234` | planner (approved) |
| `participant1@example.com` | `participant1234` | participant |
| `participant2@example.com` | `participant1234` | participant |

> 호스트 권한은 별도 role이 아니라 **인증된 누구나** 가질 수 있어요. 즉 위 시드 유저 전부 방을 만들 수 있습니다.

---

## 기술 스택

| 영역 | 선택 |
| --- | --- |
| 언어 | Python 3.11 |
| 웹 프레임워크 | FastAPI 0.115+ |
| ORM | SQLAlchemy 2.x (async, `Mapped[...]` API) |
| 마이그레이션 | Alembic |
| DB | PostgreSQL 16 (UUID PK, JSONB) |
| 스키마 검증 | Pydantic v2 |
| 인증 | JWT access + 회전 refresh (HS256) |
| 비밀번호 | bcrypt (passlib) |
| 패키지 | Poetry 1.8 |
| 실행 | Uvicorn + Docker Compose |

### 의도된 선택 몇 가지

- **Async 우선, sync 잔재 최소화** — 서비스 레이어 전체 `AsyncSession`. 동기 엔진은 Alembic 자동생성용으로만 살아 있어요.
- **UUID PK + 표준 timestamps** — 모든 테이블에 `id UUID`, `created_at`, `updated_at`. 외부 노출하기 안전하고 분산 ID 생성에도 자연스럽습니다.
- **상태 머신 명시** — `app/models/_enums.py`의 `RoomStatus`, `ApplicationStatus`, `CheckInStatus`, `RotationSessionStatus`, `MatchStatus` 등으로 비즈니스 로직을 enum 기반으로 강제.
- **In-memory 레이트리미터** — slowapi 등 외부 의존 없이 `app/core/middleware.py`에 슬라이딩 윈도우 구현. 단일 워커 가정. 멀티 워커 가면 Redis 백엔드로 교체 예정.

---

## 디렉토리

```
app/
  main.py                     FastAPI 앱 부트스트랩, 미들웨어 + 예외 핸들러
  core/
    config.py                 Pydantic Settings (env 검증)
    database.py               async/sync 엔진 + 세션 팩토리
    security.py               bcrypt + JWT 헬퍼
    middleware.py             X-Request-Id + RateLimit
    exceptions.py             표준 APIError 계층
    logging.py                구조화된 로그 셋업
  api/
    deps.py                   get_current_user · require_roles · get_db
    v1/
      router.py               전체 v1 라우터 조립
      health.py
      auth.py                 register / login / refresh / logout / me
      profile.py              참가자 프로필 upsert
      rooms.py                public room 둘러보기
      host.py                 방장 CRUD + 신청자 큐레이션
      planner.py              플래너 — 배정된 방만 다룸 (운영)
      admin.py                어드민 — 모더레이션 + 큐 + 배정
      event.py                참가자 — 당일 체크인 / 현재 라운드
      matches.py              상호 선택 / 매치 / 애프터
      feedback.py             피드백
      reports.py              신고
      me.py                   참가자 — 내 신청 / 내 방
  models/                     SQLAlchemy 2.x 모델 (UUID PK + timestamps)
  schemas/                    Pydantic 요청/응답 모델
  services/                   비즈니스 로직 (Service 패턴)
    auth_service.py           JWT 발급/회전, 비밀번호 검증
    host_service.py           방장 액션 + 자동 VIABLE 전환
    planner_service.py        배정된 방의 ops + dashboard counts
    admin_service.py          모더레이션 + 큐 + 배정
    checkin_service.py        체크인 오픈 + 코드 발급 + 확정
    rotation_service.py       라운드 로빈 알고리즘 + 세션 진행
    choice_service.py         상호 선택 + 매치 계산
    feedback_service.py       피드백 (1인 1회)
    report_service.py         신고 (참가자 관계 검증)
    audit_service.py          감사 로그 헬퍼
  scripts/
    seed.py                   시드 유저/플래너/방 생성
  tests/
    integration/              live API 통합 테스트
alembic/
  versions/                   마이그레이션 (history)
```

서비스 패턴은 다음과 같이 일관됩니다:

```python
# 1. endpoint (api/v1/*.py)
async def confirm_my_room(room_id, request, db = Depends(...), user = PlannerUser):
    planner = await planner_service.get_planner_for_user(db, user)
    room = await planner_service.confirm_room(db, planner, room_id)
    await audit_service.log_action(db, actor=user, action="room.confirmed", ...)
    await db.commit()
    return APIResponse(data=...)

# 2. service (services/*.py)
async def confirm_room(db, planner, room_id):
    room = await _get_assigned_room(db, planner, room_id)
    if room.status not in CONFIRMABLE_FROM:
        raise InvalidStateTransition(...)
    # ... business rules
    room.status = RoomStatus.CONFIRMED.value
    await db.flush()
    return room
```

**endpoint는 얇게, service에 비즈니스 로직**. 트랜잭션 커밋은 endpoint 책임.

---

## 도메인 모델 (16 + 1)

```
User ─┬─ Profile (1:1)
      ├─ Planner (1:1, role=planner인 경우만)
      └─ RefreshToken (N)

Room ─┬─ host_user_id  → User (RESTRICT)
      ├─ planner_id    → Planner (nullable, SET NULL)
      ├─ RoomApplication (N) — 신청 + 결제 상태
      ├─ Payment (N) — 결제 트랜잭션
      ├─ CheckIn (N) — 코드 발급 + 체크인 상태
      ├─ RotationSession (1) ─ RotationRound (N) ─ SeatAssignment (N)
      ├─ ParticipantChoice (N) — 누가 누구에게 어떻게 응답
      ├─ MatchResult (N) — 상호 매치 (canonical pair ordering)
      │     └─ AfterDateProposal (N)
      ├─ Feedback (N) — 1 user 1 room
      └─ Report (N)

AuditLog — actor, action, entity, before/after, IP, UA
```

### Room 상태 머신

```
DRAFT ──host publish──▶ PUBLISHED ──auto─▶ VIABLE ──admin assign──▶ ASSIGNED
                                                                       │
                                                          planner confirm
                                                                       ▼
                                                                   CONFIRMED
                                                                       │
                                                          rotation start
                                                                       ▼
                                                                IN_PROGRESS
                                                                       │
                                                          rotation end
                                                                       ▼
                                                                 COMPLETED
```

`VIABLE` 전환 트리거: **양쪽 성별 모두** `ceil(capacity × 0.5)` 이상이 `CONFIRMED` 상태일 때 (`host_service.maybe_promote_to_viable`).

### Application 상태 머신

```
SUBMITTED ─host approve─▶ APPROVED ─host mark-paid─▶ CONFIRMED
   │                          │
   ├─ host waitlist ───▶ WAITLISTED
   └─ host reject ────▶ REJECTED
   user cancel ──▶ CANCELLED  (소프트, 재신청 시 SUBMITTED로 복원)
```

---

## 주요 엔드포인트

전체 OpenAPI: <http://localhost:8000/api/v1/docs>

### 공개

| Method | Path | 비고 |
| --- | --- | --- |
| GET | `/api/v1/health` | DB 연결 확인 |
| POST | `/api/v1/auth/register` | email + password 가입 |
| POST | `/api/v1/auth/login` | access + refresh 발급 |
| POST | `/api/v1/auth/refresh` | refresh 회전 (재사용 시 401) |
| GET | `/api/v1/rooms` | 모집 중인 방 목록 |
| GET | `/api/v1/rooms/{id}` | 방 상세 |

### 참가자 (인증)

| Method | Path | 비고 |
| --- | --- | --- |
| GET/PUT | `/api/v1/profile/me` | 프로필 upsert |
| POST | `/api/v1/rooms/{id}/apply` | 방 신청 (프로필 필수) |
| GET | `/api/v1/me/applications` | 내 신청 |
| POST | `/api/v1/me/applications/{id}/cancel` | 신청 취소 |
| GET | `/api/v1/me/rooms` | 참가 확정된 방 |
| GET | `/api/v1/event/{room_id}/checkin` | 내 체크인 코드 |
| GET | `/api/v1/event/{room_id}/rotation/current` | 현재 라운드 + 상대 |
| GET/POST | `/api/v1/rooms/{id}/choice-targets`, `/choices` | 상호 선택 |
| GET | `/api/v1/rooms/{id}/my-matches` | mutual만 반환 |
| POST | `/api/v1/matches/{id}/after-date-proposals` | 애프터 제안 |
| POST | `/api/v1/rooms/{id}/feedback` | 피드백 (1회) |
| POST | `/api/v1/reports` | 신고 |

### 방장 (Host)

| Method | Path | 비고 |
| --- | --- | --- |
| GET/POST | `/api/v1/host/rooms` | 내 방 목록 / 생성 |
| GET/PUT | `/api/v1/host/rooms/{id}` | 상세 / 수정 |
| POST | `/api/v1/host/rooms/{id}/publish` | DRAFT → PUBLISHED |
| GET | `/api/v1/host/rooms/{id}/applications` | 신청자 |
| POST | `/api/v1/host/applications/{id}/approve` | 승인 |
| POST | `/api/v1/host/applications/{id}/reject` | 거절 |
| POST | `/api/v1/host/applications/{id}/waitlist` | 대기열 |
| POST | `/api/v1/host/applications/{id}/mark-paid` | 결제 확정 → CONFIRMED |

### 플래너 (배정된 방만)

| Method | Path | 비고 |
| --- | --- | --- |
| GET | `/api/v1/planner/dashboard` | 카운트 (배정/진행/완료) |
| GET | `/api/v1/planner/assigned` | 내가 맡은 잡 |
| GET | `/api/v1/planner/rooms/{id}` | 잡 상세 |
| POST | `/api/v1/planner/rooms/{id}/confirm` | ASSIGNED → CONFIRMED |
| POST | `/api/v1/planner/rooms/{id}/checkins/open` | 체크인 오픈 + 코드 발급 |
| GET | `/api/v1/planner/rooms/{id}/checkins` | 명단 |
| POST | `/api/v1/planner/checkins/{id}/confirm` | OPEN → CHECKED_IN |
| POST | `/api/v1/planner/checkins/{id}/no-show` | → NO_SHOW |
| POST | `/api/v1/planner/rooms/{id}/rotation/start` | 라운드 로빈 자동 생성 |
| POST | `/api/v1/planner/rooms/{id}/rotation/next` | 다음 라운드 |
| POST | `/api/v1/planner/rooms/{id}/rotation/end` | 종료 → COMPLETED |
| GET | `/api/v1/planner/rooms/{id}/rotation` | 세션 전체 보기 |

### 어드민

| Method | Path | 비고 |
| --- | --- | --- |
| GET | `/api/v1/admin/dashboard` | 시스템 카운트 |
| GET | `/api/v1/admin/queue` | 성립된 + 미배정 방 |
| POST | `/api/v1/admin/queue/{room_id}/assign` | 플래너 배정 |
| GET | `/api/v1/admin/users` | 유저 목록 |
| POST | `/api/v1/admin/users/{id}/block`, `/unblock` | 차단/해제 |
| GET | `/api/v1/admin/planners` | 플래너 목록 |
| POST | `/api/v1/admin/planners/{id}/approve`, `/suspend` | 승인/정지 |
| GET | `/api/v1/admin/rooms` `/payments` `/reports` | 모니터링 |
| POST | `/api/v1/admin/reports/{id}/resolve`, `/dismiss` | 신고 처리 |

---

## 응답 포맷

성공:

```json
{
  "data": { ... },
  "meta": {}
}
```

에러:

```json
{
  "error": {
    "code": "INVALID_STATE_TRANSITION",
    "message": "Cannot confirm room in 'draft' state.",
    "details": {}
  }
}
```

`code`는 enum-like 문자열이고, FE에서 친근한 한국어 카피로 매핑합니다 (`PROFILE_INCOMPLETE` → "먼저 프로필을 완성해주세요").

자주 나오는 코드:

```
UNAUTHORIZED        FORBIDDEN           NOT_FOUND
VALIDATION_ERROR    CONFLICT            INVALID_STATE_TRANSITION
ROOM_NOT_FOUND      ROOM_NOT_ACCEPTING_APPLICATIONS
APPLICATION_ALREADY_EXISTS   APPLICATION_DEADLINE_PASSED
EMAIL_ALREADY_EXISTS PROFILE_INCOMPLETE
FEEDBACK_ALREADY_SUBMITTED
RATE_LIMITED        INTERNAL_ERROR
```

---

## 보안 / 운영 안전장치

### 인증

- access 토큰 30분, refresh 14일 (env로 조정).
- refresh는 `jti` UUID로 매번 고유, DB에 해시만 저장.
- refresh 사용 시 회전 — 직전 토큰은 즉시 revoke됨. 재사용하면 401.

### 레이트 리미트 (`app/core/middleware.py`)

per-IP 슬라이딩 윈도우. 기본값:

| 엔드포인트 | 한도 |
| --- | --- |
| `/auth/login` | 10 / min |
| `/auth/register` | 5 / min |
| `/auth/refresh` | 30 / min |

초과 시 `429` + `Retry-After` 헤더.

### 감사 로그

다음 액션은 `audit_logs` 테이블에 기록됩니다 (actor, before/after JSON, IP, UA):

- 유저 block / unblock
- 플래너 approve / suspend
- 신고 resolve / dismiss
- 방 publish / confirm
- 체크인 open
- 로테이션 start / end
- 어드민 플래너 배정

### Request ID

모든 응답에 `X-Request-Id` 헤더가 붙어요. 로그에 `rid=<id>`로 함께 기록되어 trace 가능.

---

## 환경 변수

`.env` (gitignored, `.env.example` 참고)

```env
APP_ENV=development
APP_NAME=rolling-api
APP_DEBUG=true

# Postgres — 컨테이너 내부 hostname 'postgres'
DATABASE_URL=postgresql+psycopg://rolling:rolling@postgres:5432/rolling
DATABASE_URL_ASYNC=postgresql+asyncpg://rolling:rolling@postgres:5432/rolling

JWT_SECRET_KEY=꼭_바꿔주세요_적어도_32자_랜덤
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=14

CORS_ORIGINS=http://localhost:3000

PAYMENT_PROVIDER=mock   # 실 결제 연동 전까지 mock
SMS_PROVIDER=mock
```

> 호스트에서 직접 띄울 땐 `DATABASE_URL`의 hostname을 `localhost:5433`(컴포즈 노출 포트)으로.

---

## 마이그레이션

```bash
# 새 마이그레이션 (모델 변경 후)
docker compose exec api poetry run alembic revision --autogenerate -m "내용 한 줄"

# 적용
docker compose exec api poetry run alembic upgrade head

# 한 단계 롤백
docker compose exec api poetry run alembic downgrade -1
```

> autogenerate가 모든 걸 잡지는 못해요. 특히 데이터 backfill, custom check constraint, 인덱스 이름 등은 손으로 검토해주세요. 예: `host_planner_split` 마이그레이션은 `host_user_id`를 nullable로 추가 → backfill → NOT NULL 잠금 순으로 직접 손봤습니다.

---

## 테스트

라이브 API를 띄운 상태에서 실행하는 통합 테스트 (`app/tests/integration/`):

```bash
docker compose exec api pip install pytest httpx  # 최초 1회
docker compose exec api pytest app/tests/integration -q
```

현재 5개 시나리오 통과:

- health (X-Request-Id 검증)
- register → login → me
- 중복 가입 409 (`EMAIL_ALREADY_EXISTS`)
- 비-admin이 admin endpoint 호출 시 403 (`FORBIDDEN`)
- admin 대시보드 200

> dev deps를 컨테이너에 영구 포함하지 않는 이유: 프로덕션 이미지를 가볍게 유지하려고요. CI에서는 별도 `docker compose -f compose.test.yml`를 검토 중.

---

## 프로덕션 준비 체크리스트

런칭 직전 점검하세요.

- [x] JWT access + 회전 refresh
- [x] bcrypt 비밀번호 해싱
- [x] Alembic 마이그레이션 + 시드
- [x] 역할 기반 인가 (서버 강제)
- [x] 호스트/플래너/어드민 ownership 체크
- [x] Room / Application 상태 머신 (invalid transition 에러)
- [x] 감사 로그 (민감 액션)
- [x] auth 레이트 리미트
- [x] 표준 에러 envelope
- [x] X-Request-Id
- [x] CORS env로 제어
- [x] 통합 테스트 스모크
- [ ] 결제 PG 연동 (현재 `mock` + 수동 확정)
- [ ] S3 호환 프로필 이미지 업로드
- [ ] 환불 플로우 (스키마 준비됨, 서비스 없음)
- [ ] 백업/복구 정책
- [ ] Sentry / 메트릭 익스포터 연결
- [ ] 멀티 워커 시 Redis 기반 레이트 리미터

---

## Railway 배포

### 0. 사전 준비

- Railway 계정 + 결제수단 (Postgres + API 서비스에 월 ~$10)
- GitHub 레포 푸시되어 있을 것
- FE 도메인 미리 결정 (CORS 설정에 필요). 모르면 일단 `*` 후 좁히기.

### 1. Postgres 서비스 띄우기

Railway 콘솔 → `+ New` → **Database → Postgres**. 30초 내 프로비저닝. 같은 프로젝트의 다른 서비스에 자동으로 환경변수가 노출돼요 (`DATABASE_URL`, `PGHOST`, 등).

### 2. API 서비스 띄우기

같은 프로젝트에서 `+ New` → **GitHub Repo** → `rolling-api` 레포 선택.

Railway는 레포 안의 `railway.json` + `Dockerfile`을 보고 자동 빌드합니다. start command도 `railway.json`에 정의되어 있어 alembic 마이그레이션이 매 배포마다 자동 실행돼요.

### 3. 환경변수 설정

API 서비스의 **Variables** 탭에서:

```env
APP_ENV=production
APP_DEBUG=false

# Postgres 참조 — Railway 변수 참조 문법
DATABASE_URL=${{ Postgres.DATABASE_URL }}
# DATABASE_URL_ASYNC는 자동 derive됨 (app/core/config.py)

JWT_SECRET_KEY=<openssl rand -hex 32 결과를 붙여넣으세요>
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=14

# 쉼표 구분, Railway가 발급한 FE 도메인을 포함
CORS_ORIGINS=https://rolling.vercel.app,https://your-fe-domain.com

PAYMENT_PROVIDER=mock
SMS_PROVIDER=mock
```

> `DATABASE_URL`이 `postgres://`로 시작해도 `app/core/config.py`가 자동으로
> `postgresql+psycopg://` (sync) / `postgresql+asyncpg://` (async)로 변환합니다.

### 4. 도메인 노출

API 서비스 → **Settings** → **Networking** → **Generate Domain**. `*.up.railway.app` 도메인 받음. FE의 `NEXT_PUBLIC_API_BASE_URL`을 이 도메인 + `/api/v1`로 세팅.

### 5. 첫 배포 후 시드

```bash
railway run --service rolling-api poetry run python -m app.scripts.seed
```

또는 Railway 콘솔의 Shell에서 같은 명령. 시드는 idempotent라 여러 번 실행해도 안전.

### 6. 헬스체크

```bash
curl https://<your-api>.up.railway.app/api/v1/health
```

`{"data": {"status": "ok", "db": true}}` 확인. `X-Request-Id` 헤더가 응답에 있어야 합니다.

### ⚠️ 운영 단계 주의

- **레이트 리미터는 in-memory**. Railway 기본 1 replica 가정. 2개 이상 띄우면 카운트 분산 → 효과 약화. Redis 백엔드로 교체 전엔 단일 replica 유지.
- **마이그레이션 실패 시 부팅 안 됨**. 배포 전에 로컬에서 `alembic upgrade head`가 깨끗히 도는지 확인.
- **Postgres 백업**. Hobby 플랜은 자동 백업 없음. Pro 이상 또는 cron으로 `pg_dump` 별도 설정 권장.

---

## 자주 만나는 상황

**`Could not find next/package.json`** — 이건 FE 에러. 여기 무관.

**`port 5432 already allocated`** — 로컬 다른 PG가 떠 있어요. `docker-compose.yml`에서 호스트 포트 5433으로 매핑 중. 그래도 충돌이면 다른 빈 포트로.

**`error parsing value for field "CORS_ORIGINS"`** — Pydantic-settings v2가 `list[str]`을 JSON으로 디코드 시도합니다. `CORS_ORIGINS=http://localhost:3000,http://localhost:8080`처럼 쉼표 구분 문자열로 넣어주세요 (`NoDecode` annotation으로 받습니다).

**Refresh 시 `duplicate key value violates unique constraint "refresh_tokens_token_hash_key"`** — 같은 초 안에 동일 페이로드 JWT가 두 번 만들어지면 발생. 현재는 `jti`를 모든 토큰에 부여해서 해결되어 있어요. 만약 이 에러 보이면 `app/core/security.py`의 `_create_token` 변경 의심.

---

## 라이선스

내부 사용 전용. Rolling 팀 외부 코드 공유 금지.
