# 001. security_events 테이블은 어디서 만들어지는가

작성일: 2026-09-08 · 대상: `_7_board_test` (Flask 앱 팩토리 구조)

---

## 1. 한 줄 답

**`app.py` 의 `create_app()` 안에 있는 `db.create_all()` 한 줄이 만든다.**
단, 그보다 먼저 `models/security_event.py` 의 `SecurityEvent` 클래스가 **import 되어 있어야** 한다.
표 이름 `security_events` 는 그 클래스의 `__tablename__` 에서 온다.

```python
# app.py  (create_app 안, 맨 끝)
with app.app_context():
    db.create_all()
```

---

## 2. 생성 순서 (import 체인)

`app.py` 를 실행하면 아래 순서로 흘러간다. ★ 표시 두 곳이 핵심이다.

```
app.py :  app = create_app()
  │
  ├─ from config import Config
  │     └─ load_dotenv() → .env 의 DATABASE_URL 을 SQLALCHEMY_DATABASE_URI 로
  │
  ├─ from controllers import all_blueprints
  │     └─ controllers/__init__.py
  │           └─ security_controller.py
  │                 └─ from models import Post, SecurityEvent, User
  │                       └─ models/__init__.py
  │                             └─ from .security_event import SecurityEvent
  │                                   → class SecurityEvent(db.Model) 정의가 실행됨
  │                                   → db.metadata 에 'security_events' 설계도 등록   ★①
  │
  ├─ db.init_app(app)            # SQLAlchemy 를 이 app 에 연결
  │
  └─ with app.app_context():
        db.create_all()          # metadata 의 표 중 DB 에 없는 것만 CREATE TABLE      ★②
```

**★① 등록(설계도 그리기) 이 먼저, ★② 실행(실제 CREATE) 이 나중.**
순서가 뒤바뀌거나 ①이 빠지면 표가 안 만들어진다. → §5 참고

---

## 3. 관련 파일 4개

| 파일 | 역할 | 해당 줄 |
|---|---|---|
| `models/security_event.py` | `SecurityEvent` 클래스 = 표의 **설계도** | `__tablename__ = 'security_events'` |
| `models/__init__.py` | 설계도를 **import 해서 등록**시키는 통로 | `from .security_event import SecurityEvent` |
| `extensions.py` | `db = SQLAlchemy()` — 설계도가 모이는 그릇 | `db = SQLAlchemy()` |
| `app.py` | `db.create_all()` — **실제 CREATE TABLE 실행** | `create_app()` 끝부분 |

`config.py` 는 표를 만들지는 않지만, **어느 DB 에** 만들지를 정한다 (`.env` 의 `DATABASE_URL`).

---

## 4. 설계도 — SecurityEvent 모델

`models/security_event.py`

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | Integer | PK, auto increment | |
| `student` | String(50) | NOT NULL, **index** | 본인 식별자(제출 증적용) |
| `src_ip` | String(45) | NOT NULL, **index** | IPv6 까지 담으려 45자 |
| `fail_count` | Integer | NOT NULL, default 0 | 로그인 실패 횟수 |
| `decision` | String(10) | NOT NULL | `allow` / `deny` |
| `severity` | String(10) | NOT NULL, default `'Low'` | |
| `reason` | String(200) | NULL 허용 | 판정 사유 |
| `users` | String(255) | NULL 허용 | 시도된 계정들 |
| `last_seen` | String(32) | NULL 허용 | 마지막 시도 시각 |
| `window_min` | Integer | NULL 허용 | 집계 구간(분) |
| `source` | String(50) | default `'login_guard'` | 이벤트 출처 |
| `generated_at` | String(32) | NULL 허용 | **보낸 쪽**이 만든 시각 |
| `created_at` | DateTime | default `datetime.now` | **DB 에 저장된** 시각 |

`index=True` 를 준 `student` · `src_ip` 두 개는 아래 DDL 에서 `KEY ix_...` 로 나타난다.

---

## 5. 실제로 만들어진 테이블 (MySQL 확인 결과)

DB: `my_new_board_db` (도커 MySQL 26.7.0)

```sql
CREATE TABLE `security_events` (
  `id` int NOT NULL AUTO_INCREMENT,
  `student` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `src_ip` varchar(45) COLLATE utf8mb4_unicode_ci NOT NULL,
  `fail_count` int NOT NULL,
  `decision` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `severity` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `reason` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `users` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `last_seen` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `window_min` int DEFAULT NULL,
  `source` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `generated_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_security_events_src_ip` (`src_ip`),
  KEY `ix_security_events_student` (`student`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

같은 DB 안의 표: `posts`, `security_events`, `users` (3개)

> **모델의 `default` 는 DB DDL 에 안 들어간다.**
> `fail_count` 의 `default=0`, `severity` 의 `default='Low'` 는 DDL 에 `DEFAULT` 로 나타나지 않는다.
> SQLAlchemy 가 **INSERT 할 때 파이썬 쪽에서 채워 넣는** 값이기 때문이다.
> 따라서 SQL 로 직접 `INSERT` 하면 이 기본값은 적용되지 않는다.

---

## 6. `db.create_all()` 의 규칙 2가지 (꼭 기억할 것)

### 규칙 1 — import 안 된 모델은 만들어주지 않는다

`db.create_all()` 은 **그 시점까지 `db.metadata` 에 등록된** 표만 만든다.
클래스는 `import` 되는 순간 등록되므로, import 되지 않은 모델은 조용히 무시된다(에러도 안 난다).

`models/__init__.py` 의 주석이 바로 이 이야기다:

> `db.create_all()` 이 테이블을 만들려면 모든 모델 클래스가 미리 import 되어 있어야 한다.

이 앱에서는 `app.py` → `controllers` → `security_controller.py` → `models` 순으로
**우연이 아니라 의도적으로** import 체인이 걸려 있어서 등록이 보장된다.
그래서 `app.py` 에 이런 주석이 붙어 있다:

> 테이블 생성 (models 를 import 한 뒤여야 한다 — controllers 가 이미 import 함)

**증상**: 새 모델을 만들었는데 표가 안 생긴다 → `models/__init__.py` 에 추가했는지 확인.

### 규칙 2 — 이미 있는 표는 절대 건드리지 않는다

`create_all()` 은 **없는 표만 CREATE** 한다. 이미 있으면 그냥 넘어간다.
즉 **컬럼을 추가·삭제·변경해도 DB 에 반영되지 않는다.** (마이그레이션 기능이 없다)

컬럼을 바꿨을 때의 선택지:

| 방법 | 명령 | 주의 |
|---|---|---|
| 표를 지우고 다시 생성 | `DROP TABLE security_events;` 후 앱 재시작 | **데이터 전부 사라짐** |
| SQL 로 직접 변경 | `ALTER TABLE security_events ADD COLUMN ...` | 모델과 수동으로 맞춰야 함 |
| 마이그레이션 도구 도입 | `Flask-Migrate` (Alembic) | 권장, 별도 설치 필요 |

---

## 7. 확인 방법

```powershell
cd E:\0-Aleph-Python-Test\Python-Lab-ALeph-T
.\.venv\Scripts\Activate.ps1
cd _7_board_test
```

**표가 만들어졌는지 / 스키마 보기**

```python
python -c "from app import app; from extensions import db; from sqlalchemy import inspect, text; app.app_context().push(); print(inspect(db.engine).get_table_names()); print(db.session.execute(text('SHOW CREATE TABLE security_events')).fetchone()[1])"
```

**MySQL 클라이언트로 직접**

```sql
USE my_new_board_db;
SHOW TABLES;
DESC security_events;
SELECT COUNT(*) FROM security_events;
```

**앱을 켜서 만들기** — `python app.py` 실행만 해도 `create_app()` 이 돌면서 없는 표가 생성된다.

---

## 8. 이 표에 데이터를 넣는 쪽

`controllers/security_controller.py` — n8n(SOAR) 이 판정 결과를 REST 로 보낸다.

| 메서드 | 경로 | 인증 | 설명 |
|---|---|---|---|
| `POST` | `/api/security/events` | `X-API-Key` 헤더 필수 | 이벤트 1건 저장 (**여기서 INSERT**) |
| `GET` | `/api/security/events` | 없음 | 목록 (`?student=`, `?decision=`, `?limit=`) |
| `GET` | `/api/security/events/summary` | 없음 | 허용/거부 건수 + 거부 상위 IP 5개 |
| `GET` | `/api/security/students` | 없음 | 기록이 있는 학생 목록 |

- 인증은 **fail-closed**: `.env` 의 `SECURITY_API_KEY` 가 비어 있으면 `POST` 는 항상 401.
- `decision == 'deny'` 이고 `.env` 의 `AUTO_POST_ON_DENY=1` 이면
  `_create_security_post()` 가 게시판에 '보안' 공지글을 함께 남긴다.
  이벤트 저장과 공지글 등록을 **한 트랜잭션**으로 묶어 `commit()` 한다.
- 화면은 `/dashboard` (`templates/dashboard.html`).

---

## 참고

- 정의: `models/security_event.py`
- 등록: `models/__init__.py`
- 그릇: `extensions.py`
- 실행: `app.py` → `create_app()` → `db.create_all()`
- 접속 대상 DB: `config.py` → `.env` 의 `DATABASE_URL`
