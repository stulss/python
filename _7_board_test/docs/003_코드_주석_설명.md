# 003. security_events 관련 코드 — 주석·설명

작성일: 2026-09-08 · 대상: `_7_board_test`

> 이 문서는 **설명 전용**입니다. 주석을 뺀 복붙용 코드는 [002_코드_복붙용.md](002_코드_복붙용.md) 에 있습니다.
> 여기 실린 코드는 **주석이 그대로 살아 있는 원본**입니다.

## 목차

1. `extensions.py`
2. `config.py`
3. `models/security_event.py`
4. `models/__init__.py`
5. `controllers/security_controller.py`
6. `controllers/__init__.py`
7. `app.py`

---

## 1. `_7_board_test/extensions.py`

<details><summary>원본 코드 (주석 포함) — 펼치기</summary>

```python
"""확장(Extension) 객체를 한 곳에서 만든다.

app 과 분리해 두면 models·controllers 어디서든 import 해도
순환 참조(circular import)가 생기지 않는다.
"""
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
jwt = JWTManager()
```

</details>

### 왜 파일을 따로 뺐나

`db = SQLAlchemy()` 를 `app.py` 안에 두면 **순환 참조(circular import)** 가 생긴다.

```
app.py 가 models 를 import  →  models 가 db 를 쓰려고 app.py 를 import  →  무한 루프
```

`extensions.py` 로 빼두면 `app.py` 도 `models` 도 **각자 이 파일만** import 하면 되므로 고리가 끊긴다.

### 핵심

| 코드 | 뜻 |
|---|---|
| `db = SQLAlchemy()` | **앱 없이 빈 껍데기로** 먼저 만든다. 나중에 `db.init_app(app)` 으로 앱과 연결 |
| `jwt = JWTManager()` | 로그인 토큰 관리자. 역시 나중에 `jwt.init_app(app)` |

이 `db` 객체가 **모든 모델의 설계도가 모이는 그릇**(`db.metadata`)이다.

---

## 2. `_7_board_test/config.py`

<details><summary>원본 코드 (주석 포함) — 펼치기</summary>

```python
"""설정 한 곳에 모으기.

비밀값(DB 비밀번호·JWT 키·API 키)은 코드에 쓰지 않고 같은 폴더의 .env 에서 읽는다.
.env 는 절대 깃에 올리지 않는다(.gitignore). 제출·공유용으로는 .env.example 만 남긴다.
"""
import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()  # .env → 환경변수 (import 시점 1회)


class Config:
  # ── 데이터베이스 (도커 MySQL) ──
  SQLALCHEMY_DATABASE_URI = os.environ.get(
      'DATABASE_URL',
      # 기본값에는 비밀번호를 두지 않는다 — 반드시 .env 의 DATABASE_URL 을 쓴다
      'mysql+pymysql://<user>:<password>@localhost:3306/my_new_board_db',
  )
  SQLALCHEMY_TRACK_MODIFICATIONS = False

  # ── 로그인 토큰 ──
  JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'dev-only-change-me')
  JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)

  # ── 보안 이벤트 REST (n8n 이 호출) ──
  # 값이 비어 있으면 POST 는 항상 401 (fail-closed: 실수로 열어두지 않는다)
  SECURITY_API_KEY = os.environ.get('SECURITY_API_KEY', '')
  # 거부(deny) 시 게시판에 '보안' 공지글 자동 등록
  AUTO_POST_ON_DENY = os.environ.get('AUTO_POST_ON_DENY', '0') == '1'

  # ── 공공데이터(부산 테마여행) ──
  PUBLIC_API_KEY = os.environ.get('PUBLIC_API_KEY')
  PUBLIC_API_URL = (
      'http://apis.data.go.kr/6260000/RecommendedService/getRecommendedKr'
  )
```

</details>

### 핵심

| 코드 | 뜻 |
|---|---|
| `load_dotenv()` | 같은 폴더의 `.env` 를 읽어 환경변수로 올린다. **import 시점에 1회** |
| `os.environ.get('DATABASE_URL', 기본값)` | `.env` 에 있으면 그 값, 없으면 기본값 |
| `SQLALCHEMY_DATABASE_URI` | **표를 어느 DB 에 만들지**가 여기서 결정된다 |
| `SQLALCHEMY_TRACK_MODIFICATIONS = False` | 안 쓰는 추적 기능 끄기(경고 제거·메모리 절약) |
| `SECURITY_API_KEY = ..., '')` | 기본값이 **빈 문자열** → 키가 없으면 POST 는 항상 401 (**fail-closed**) |
| `AUTO_POST_ON_DENY = ... == '1'` | `.env` 값은 항상 문자열이라 `'1'` 과 비교해 **bool 로 변환** |

### 함정 ① — `load_dotenv()` 는 `.env` 를 하나만 읽는다

인자 없이 호출하면 이 파일 위치부터 **위로 올라가며 처음 만난 `.env` 하나만** 읽는다.
이 프로젝트에는 `.env` 가 두 개 있었고(`_7_board_test/.env`, 상위 폴더의 `.env`),
`PUBLIC_API_KEY` 가 상위 것에만 있어서 **값이 `None` 인 채로 API 호출이 실패**했다.

→ 해결: 이 앱이 쓰는 키는 **`_7_board_test/.env` 한 곳에** 모아둔다.

```python
from dotenv import find_dotenv
print(find_dotenv())   # 실제로 어떤 .env 를 읽는지 확인하는 방법
```

### 함정 ② — 기본값에 비밀번호를 쓰지 않는다

`SQLALCHEMY_DATABASE_URI` 기본값이 `<user>:<password>` 인 이유다.
기본값에 진짜 비밀번호를 적으면 **코드에 비밀이 박혀 깃에 올라간다.**

---

## 3. `_7_board_test/models/security_event.py`

<details><summary>원본 코드 (주석 포함) — 펼치기</summary>

```python
from datetime import datetime

from extensions import db


class SecurityEvent(db.Model):
  """n8n 이 판정한 허용/거부 결과를 저장하는 표.

  student 를 남겨 두면 제출 증적에 본인 식별자가 찍혀 채점·표절 확인이 쉽다.
  """
  __tablename__ = 'security_events'

  id = db.Column(db.Integer, primary_key=True)
  student = db.Column(db.String(50), nullable=False, index=True)   # 본인 식별자(필수)
  src_ip = db.Column(db.String(45), nullable=False, index=True)    # IPv6 까지 45자
  fail_count = db.Column(db.Integer, nullable=False, default=0)
  decision = db.Column(db.String(10), nullable=False)              # allow | deny
  severity = db.Column(db.String(10), nullable=False, default='Low')
  reason = db.Column(db.String(200))
  users = db.Column(db.String(255))
  last_seen = db.Column(db.String(32))
  window_min = db.Column(db.Integer)
  source = db.Column(db.String(50), default='login_guard')
  generated_at = db.Column(db.String(32))                          # 보낸 쪽이 만든 시각
  created_at = db.Column(db.DateTime, default=datetime.now)        # DB 저장 시각

  def to_dict(self):
    return {
        'id': self.id, 'student': self.student, 'src_ip': self.src_ip,
        'fail_count': self.fail_count, 'decision': self.decision,
        'severity': self.severity, 'reason': self.reason, 'users': self.users,
        'last_seen': self.last_seen, 'window_min': self.window_min,
        'source': self.source, 'generated_at': self.generated_at,
        'created_at': self.created_at.isoformat() if self.created_at else None,
    }
```

</details>

### 핵심

| 코드 | 뜻 |
|---|---|
| `class SecurityEvent(db.Model)` | 이 클래스 = 표 하나. **정의되는 순간** `db.metadata` 에 등록된다 |
| `__tablename__ = 'security_events'` | **실제 DB 표 이름.** 안 쓰면 클래스명 기반으로 자동 생성됨 |
| `primary_key=True` | 기본키 + MySQL 에서 `AUTO_INCREMENT` 로 만들어짐 |
| `nullable=False` | `NOT NULL` |
| `index=True` | 인덱스 생성 → DDL 에 `KEY ix_security_events_student` 로 나타남 |
| `default=0`, `default='Low'` | **DB 기본값이 아니다.** SQLAlchemy 가 INSERT 할 때 파이썬 쪽에서 채운다 |
| `db.String(45)` | IPv6 최대 길이가 45자라서 45 |
| `to_dict()` | `jsonify()` 에 넘기려고 dict 로 변환. `datetime` 은 문자열로 |

### 왜 `default` 가 DDL 에 안 보이나

```sql
`fail_count` int NOT NULL,          -- DEFAULT 0 이 없다
```

`default=0` 은 SQLAlchemy 레벨 기본값이라 `CREATE TABLE` 에 안 들어간다.
**SQL 로 직접 `INSERT` 하면 이 기본값이 적용되지 않는다**는 뜻이다.
DB 레벨 기본값을 원하면 `server_default=text('0')` 을 써야 한다.

### `generated_at` 과 `created_at` 의 차이

| 컬럼 | 누가 만든 시각인가 |
|---|---|
| `generated_at` | **보낸 쪽(n8n)** 이 이벤트를 만든 시각. 문자열로 그대로 저장 |
| `created_at` | **우리 DB** 에 저장된 시각. `default=datetime.now` 로 자동 |

둘을 나눠두면 "언제 탐지됐고 언제 도착했는지" 시차를 볼 수 있다.

---

## 4. `_7_board_test/models/__init__.py`

<details><summary>원본 코드 (주석 포함) — 펼치기</summary>

```python
"""모델 묶음.

db.create_all() 이 테이블을 만들려면 모든 모델 클래스가 미리 import 되어 있어야 한다.
"""
from .post import Post
from .security_event import SecurityEvent
from .user import User

__all__ = ['User', 'Post', 'SecurityEvent']
```

</details>

### 이 파일이 없으면 표가 안 만들어진다

`db.create_all()` 은 **그 시점까지 `db.metadata` 에 등록된 표만** 만든다.
클래스는 **import 되는 순간** 등록되므로, import 되지 않은 모델은 **조용히 무시**된다 — 에러도 안 난다.

```
from models import SecurityEvent
  → models/__init__.py 실행
      → from .security_event import SecurityEvent
          → class SecurityEvent(db.Model) 정의 실행
              → db.metadata 에 'security_events' 등록  ★
```

**새 모델을 만들었는데 표가 안 생긴다면** 이 파일에 추가했는지부터 확인할 것.

---

## 5. `_7_board_test/controllers/security_controller.py`

<details><summary>원본 코드 (주석 포함) — 펼치기</summary>

```python
"""보안 이벤트 REST — n8n 이 판정 결과를 보내 저장하는 곳.

인증: 헤더 X-API-Key (사람이 아니라 봇이 부르므로 로그인 대신 공유 비밀 1개)
"""
import os
from functools import wraps

from flask import Blueprint, current_app, jsonify, request
from werkzeug.security import generate_password_hash

from extensions import db
from models import Post, SecurityEvent, User

security_bp = Blueprint('security', __name__, url_prefix='/api/security')


def require_api_key(fn):
  """X-API-Key 가 설정값과 같을 때만 통과. 키가 비었거나 다르면 401(fail-closed)."""
  @wraps(fn)
  def wrapper(*args, **kwargs):
    expected = current_app.config.get('SECURITY_API_KEY', '')
    if not expected or request.headers.get('X-API-Key', '') != expected:
      return jsonify({'msg': 'API 키가 없거나 잘못되었습니다.'}), 401
    return fn(*args, **kwargs)
  return wrapper


def _create_security_post(ev):
  """심화: 거부 이벤트를 게시판 '보안' 공지글로 자동 등록(작성자 = 시스템 계정)."""
  bot = User.query.filter_by(username='soarbot').first()
  if not bot:
    bot = User(username='soarbot',
               password=generate_password_hash(os.urandom(16).hex()))
    db.session.add(bot)
    db.session.flush()

  post = Post(
      title=f'[보안][{ev.student}] {ev.src_ip} 접근 거부 ({ev.severity})',
      content=(f'{ev.reason}\n시도 계정: {ev.users}\n'
               f'마지막 시도: {ev.last_seen}\n수집: {ev.generated_at}'),
      category='보안', author_id=bot.id)
  db.session.add(post)
  db.session.flush()
  return post.id


@security_bp.route('/events', methods=['POST'])
@require_api_key
def create_security_event():
  data = request.get_json(silent=True) or {}      # JSON 아니어도 500 대신 400
  student = (data.get('student') or '').strip()
  src_ip = data.get('src_ip')
  decision = data.get('decision')
  if not student or not src_ip or decision not in ('allow', 'deny'):
    return jsonify({'msg': 'student, src_ip, decision(allow|deny) 은 필수입니다.'}), 400

  ev = SecurityEvent(
      student=student[:50], src_ip=src_ip,
      fail_count=int(data.get('fail_count') or 0), decision=decision,
      severity=data.get('severity', 'Low'), reason=data.get('reason'),
      users=data.get('users'), last_seen=data.get('last_seen'),
      window_min=data.get('window_min'),
      source=data.get('source', 'login_guard'),
      generated_at=data.get('generated_at'),
  )
  db.session.add(ev)
  db.session.flush()                              # ev.id 확보

  post_id = None
  if decision == 'deny' and current_app.config.get('AUTO_POST_ON_DENY'):
    post_id = _create_security_post(ev)

  db.session.commit()                             # 이벤트+공지글을 한 트랜잭션으로
  return jsonify({'id': ev.id, 'student': ev.student,
                  'decision': ev.decision, 'post_id': post_id}), 201


@security_bp.route('/events', methods=['GET'])
def list_security_events():
  """조회는 키 없이(수업 확인용). ?student= 로 본인 것만 고른다."""
  student = request.args.get('student')
  decision = request.args.get('decision')
  limit = request.args.get('limit', default=20, type=int)

  query = SecurityEvent.query
  if student:
    query = query.filter_by(student=student)
  if decision in ('allow', 'deny'):
    query = query.filter_by(decision=decision)

  rows = query.order_by(SecurityEvent.id.desc()).limit(min(limit, 100)).all()
  return jsonify({'count': len(rows), 'events': [r.to_dict() for r in rows]})


@security_bp.route('/events/summary', methods=['GET'])
def security_events_summary():
  """허용/거부 건수 + 거부 상위 IP 5개."""
  from sqlalchemy import func

  student = request.args.get('student')
  q1 = db.session.query(SecurityEvent.decision, func.count(SecurityEvent.id))
  q2 = (db.session.query(SecurityEvent.src_ip, func.sum(SecurityEvent.fail_count))
        .filter(SecurityEvent.decision == 'deny'))
  if student:
    q1 = q1.filter(SecurityEvent.student == student)
    q2 = q2.filter(SecurityEvent.student == student)

  by_decision = dict(q1.group_by(SecurityEvent.decision).all())
  top = (q2.group_by(SecurityEvent.src_ip)
         .order_by(func.sum(SecurityEvent.fail_count).desc()).limit(5).all())

  return jsonify({
      'student': student,
      'by_decision': by_decision,
      'top_deny_ips': [{'src_ip': ip, 'fails': int(n)} for ip, n in top],
  })


@security_bp.route('/students', methods=['GET'])
def list_students():
  """대시보드 드롭다운용 — 기록이 있는 학생 목록."""
  rows = (db.session.query(SecurityEvent.student)
          .distinct().order_by(SecurityEvent.student).all())
  return jsonify({'students': [r[0] for r in rows]})
```

</details>

### 라우트 4개

| 메서드 | 경로 | 인증 | 설명 |
|---|---|---|---|
| `POST` | `/api/security/events` | `X-API-Key` 필수 | 이벤트 1건 저장 (**INSERT 지점**) |
| `GET` | `/api/security/events` | 없음 | 목록 (`?student=`, `?decision=`, `?limit=`) |
| `GET` | `/api/security/events/summary` | 없음 | 허용/거부 건수 + 거부 상위 IP 5개 |
| `GET` | `/api/security/students` | 없음 | 기록이 있는 학생 목록 (드롭다운용) |

### `require_api_key` — 왜 데코레이터인가

사람이 아니라 **봇(n8n)** 이 부르므로 로그인(JWT) 대신 **공유 비밀 1개**로 인증한다.

```python
if not expected or request.headers.get('X-API-Key', '') != expected:
    return jsonify(...), 401
```

`not expected` 가 앞에 있는 게 핵심 — **키가 설정 안 됐으면 무조건 차단**한다(**fail-closed**).
이게 없으면 `.env` 를 깜빡했을 때 API 가 **누구에게나 열린다.**

`@wraps(fn)` 은 원래 함수의 이름을 보존한다. 없으면 Flask 가 라우트 등록 시
모든 함수를 `wrapper` 라는 같은 이름으로 인식해 **에러가 난다.**

### `flush()` 와 `commit()` 의 차이

```python
db.session.add(ev)
db.session.flush()      # SQL 은 보내되 확정은 안 함 → ev.id 를 받아올 수 있다
...
db.session.commit()     # 여기서 확정
```

| | 역할 |
|---|---|
| `flush()` | INSERT 를 DB 로 보내 **`id` 를 확보**. 아직 되돌릴 수 있음 |
| `commit()` | **확정.** 이 줄을 지나야 다른 연결에서도 보인다 |

`deny` 일 때 이벤트와 게시판 공지글을 **한 트랜잭션**으로 묶으려고 이렇게 쓴다.
중간에 실패하면 **둘 다 취소**된다 — 이벤트만 남고 공지글이 없는 상태가 생기지 않는다.

### 입력 검증

```python
data = request.get_json(silent=True) or {}
```

`silent=True` 가 없으면 JSON 이 아닌 요청에 **500**(서버 에러)이 난다.
`or {}` 까지 붙여 `None` 도 빈 dict 로 만들어, 아래 검증에서 **400**(잘못된 요청)으로 정상 처리한다.

```python
student = (data.get('student') or '').strip()
...
student=student[:50]
```

컬럼이 `String(50)` 이라 **미리 잘라서** DB 에러를 막는다.

### `limit` 상한

```python
rows = query.order_by(...).limit(min(limit, 100)).all()
```

`?limit=999999` 로 서버를 괴롭히지 못하도록 **최대 100건**으로 막아둔 것.

---

## 6. `_7_board_test/controllers/__init__.py`

<details><summary>원본 코드 (주석 포함) — 펼치기</summary>

```python
"""컨트롤러(블루프린트) 묶음. app.py 가 이 목록을 한 번에 등록한다."""
from .auth_controller import auth_bp
from .page_controller import page_bp
from .post_controller import post_bp
from .public_controller import public_bp
from .security_controller import security_bp

all_blueprints = (page_bp, auth_bp, post_bp, security_bp, public_bp)

__all__ = ['all_blueprints', 'page_bp', 'auth_bp', 'post_bp',
           'security_bp', 'public_bp']
```

</details>

### 핵심

| 코드 | 뜻 |
|---|---|
| `from .security_controller import security_bp` | 컨트롤러를 import → **그 안의 `from models import ...` 도 같이 실행**된다 |
| `all_blueprints = (...)` | `app.py` 가 `for bp in all_blueprints` 로 **한 번에 등록** |

### 숨은 역할 — 모델 등록의 통로

이 파일은 블루프린트를 모으는 게 목적이지만, **결과적으로 모델 import 도 보장**한다.

```
app.py → controllers/__init__.py → security_controller.py → models → 모델 등록 완료
```

그래서 `app.py` 에 이런 주석이 붙어 있다:

> 테이블 생성 (models 를 import 한 뒤여야 한다 — controllers 가 이미 import 함)

**주의**: 컨트롤러를 하나 빼면 그쪽에서만 import 하던 모델도 같이 등록에서 빠질 수 있다.
안전하게 하려면 `app.py` 에서 `import models` 를 **명시적으로** 한 줄 추가하는 방법도 있다.

---

## 7. `_7_board_test/app.py`

<details><summary>원본 코드 (주석 포함) — 펼치기</summary>

```python
"""엔트리포인트 — 앱 팩토리(create_app) 패턴.

구조
  config.py       설정(.env 로딩)
  extensions.py   db · jwt 인스턴스
  models/         User · Post · SecurityEvent
  controllers/    page · auth · post · security · public (블루프린트)
  templates/      화면 (partials/_nav.html = 공통 반응형 헤더)

실행:  python app.py   →  http://localhost:5000
"""
from flask import Flask

from config import Config
from controllers import all_blueprints
from extensions import db, jwt


def create_app(config_class=Config):
  app = Flask(__name__)
  app.config.from_object(config_class)

  # 확장 초기화
  db.init_app(app)
  jwt.init_app(app)

  # 컨트롤러(블루프린트) 등록
  for bp in all_blueprints:
    app.register_blueprint(bp)

  # 테이블 생성 (models 를 import 한 뒤여야 한다 — controllers 가 이미 import 함)
  with app.app_context():
    db.create_all()

  return app


app = create_app()


if __name__ == '__main__':
  # host='0.0.0.0' 이면 같은 공유기의 다른 기기에서도 접속 가능.
  # 도커 안 n8n 에서는 http://host.docker.internal:5000 으로 부른다.
  app.run(debug=True, host='0.0.0.0', port=5000)
```

</details>

### 앱 팩토리(create_app) 패턴

앱을 **모듈 최상단에서 바로 만들지 않고 함수 안에서 만든다.**

| 장점 | 설명 |
|---|---|
| 설정 교체 | `create_app(TestConfig)` 로 테스트용 DB 를 쓸 수 있다 |
| 순환 참조 회피 | 확장(`db`)을 나중에 `init_app` 으로 붙인다 |
| 여러 개 생성 | 테스트에서 앱을 매번 새로 만들 수 있다 |

### 실행 순서 — 이 순서가 전부다

```python
app.config.from_object(config_class)   # ① 어느 DB 인지 확정
db.init_app(app)                       # ② db 를 이 앱에 연결
for bp in all_blueprints: ...          # ③ 이때 models 가 import 되며 설계도 등록  ★
with app.app_context():
    db.create_all()                    # ④ 등록된 표 중 없는 것만 CREATE TABLE     ★
```

**③ 이 ④ 보다 먼저**여야 한다. 순서가 바뀌면 표가 안 생긴다.

### `with app.app_context()` 가 왜 필요한가

`db.create_all()` 은 "어느 앱의 어느 DB 인지" 알아야 한다.
Flask 는 그 정보를 **앱 컨텍스트**에서 찾으므로, 컨텍스트 밖에서 부르면
`Working outside of application context` 에러가 난다.

### `db.create_all()` 의 한계 2가지

| 규칙 | 뜻 |
|---|---|
| **없는 표만 만든다** | 이미 있으면 건너뛴다 |
| **기존 표는 안 고친다** | 컬럼을 추가·변경해도 **DB 에 반영되지 않는다** |

컬럼을 바꿨다면 `DROP TABLE` 후 재실행(데이터 사라짐)하거나,
`ALTER TABLE` 로 직접 맞추거나, `Flask-Migrate`(Alembic)를 도입해야 한다.

### `host='0.0.0.0'` 과 `debug=True`

| 설정 | 뜻 | 주의 |
|---|---|---|
| `host='0.0.0.0'` | 같은 공유기의 다른 기기에서도 접속 가능 | 외부 노출 주의 |
| `debug=True` | 코드 수정 시 자동 재시작 + 에러 화면 | **운영에서는 절대 금지** (임의 코드 실행 가능) |

도커 안의 n8n 에서 부를 때는 `http://host.docker.internal:5000` 을 쓴다.

---

## 자주 나는 에러와 원인

| 증상 | 원인 | 해결 |
|---|---|---|
| 표가 안 만들어짐 (에러도 없음) | 모델이 import 안 됨 | `models/__init__.py` 에 추가 |
| `Working outside of application context` | 컨텍스트 밖에서 `create_all()` | `with app.app_context():` 안으로 |
| 컬럼을 추가했는데 DB 에 없음 | `create_all()` 은 기존 표를 안 고침 | `DROP TABLE` 후 재실행 또는 `ALTER TABLE` |
| `POST /api/security/events` 가 항상 401 | `.env` 의 `SECURITY_API_KEY` 가 비어 있음 | `.env` 에 키 설정 (fail-closed 설계) |
| 설정값이 `None` | `load_dotenv()` 가 다른 `.env` 를 읽음 | `find_dotenv()` 로 확인 후 한 곳에 모으기 |
| `Can't connect to MySQL server` | 도커 MySQL 미기동 | 컨테이너 먼저 실행 |
| 라우트 등록 시 함수명 충돌 | 데코레이터에 `@wraps` 누락 | `functools.wraps` 추가 |
