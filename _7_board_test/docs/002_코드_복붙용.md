# 002. security_events 관련 코드 (복사·붙여넣기용)

작성일: 2026-09-08 · 대상: `_7_board_test`

> **주석을 모두 뺀 순수 코드**입니다. 그대로 복사해 붙여넣으면 동작합니다.
> 각 줄이 왜 그렇게 되어 있는지는 [003_코드_주석_설명.md](003_코드_주석_설명.md) 를 보세요.
> 전체 흐름 설명은 [001_security_events_테이블_생성.md](001_security_events_테이블_생성.md) 에 있습니다.

## 파일 만드는 순서

위에서 아래로 순서대로 만들면 import 에러가 나지 않습니다.

```
_7_board_test/
├── extensions.py
├── config.py
├── .env                      ← 비밀값 (깃에 올리지 않음)
├── models/
│   ├── security_event.py
│   └── __init__.py
├── controllers/
│   ├── security_controller.py
│   └── __init__.py
└── app.py                    ← 여기서 db.create_all() 실행
```

---

## 1. `_7_board_test/extensions.py`

db·jwt 객체를 만든다. 가장 먼저 있어야 나머지가 import 한다.

```python
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
jwt = JWTManager()
```

---

## 2. `_7_board_test/config.py`

.env 를 읽어 접속 정보를 담는다. 어느 DB 에 만들지가 여기서 정해진다.

```python
import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class Config:
  SQLALCHEMY_DATABASE_URI = os.environ.get(
      'DATABASE_URL',
      'mysql+pymysql://<user>:<password>@localhost:3306/my_new_board_db',
  )
  SQLALCHEMY_TRACK_MODIFICATIONS = False

  JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'dev-only-change-me')
  JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)

  SECURITY_API_KEY = os.environ.get('SECURITY_API_KEY', '')
  AUTO_POST_ON_DENY = os.environ.get('AUTO_POST_ON_DENY', '0') == '1'

  PUBLIC_API_KEY = os.environ.get('PUBLIC_API_KEY')
  PUBLIC_API_URL = (
      'http://apis.data.go.kr/6260000/RecommendedService/getRecommendedKr'
  )
```

---

## 3. `_7_board_test/models/security_event.py`

security_events 표의 설계도. __tablename__ 이 실제 표 이름.

```python
from datetime import datetime

from extensions import db


class SecurityEvent(db.Model):
  __tablename__ = 'security_events'

  id = db.Column(db.Integer, primary_key=True)
  student = db.Column(db.String(50), nullable=False, index=True)
  src_ip = db.Column(db.String(45), nullable=False, index=True)
  fail_count = db.Column(db.Integer, nullable=False, default=0)
  decision = db.Column(db.String(10), nullable=False)
  severity = db.Column(db.String(10), nullable=False, default='Low')
  reason = db.Column(db.String(200))
  users = db.Column(db.String(255))
  last_seen = db.Column(db.String(32))
  window_min = db.Column(db.Integer)
  source = db.Column(db.String(50), default='login_guard')
  generated_at = db.Column(db.String(32))
  created_at = db.Column(db.DateTime, default=datetime.now)

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

---

## 4. `_7_board_test/models/__init__.py`

설계도를 import 해 db.metadata 에 등록시킨다. 빠지면 표가 안 생긴다.

```python
from .post import Post
from .security_event import SecurityEvent
from .user import User

__all__ = ['User', 'Post', 'SecurityEvent']
```

---

## 5. `_7_board_test/controllers/security_controller.py`

표에 데이터를 넣고 꺼내는 REST API.

```python
import os
from functools import wraps

from flask import Blueprint, current_app, jsonify, request
from werkzeug.security import generate_password_hash

from extensions import db
from models import Post, SecurityEvent, User

security_bp = Blueprint('security', __name__, url_prefix='/api/security')


def require_api_key(fn):
  @wraps(fn)
  def wrapper(*args, **kwargs):
    expected = current_app.config.get('SECURITY_API_KEY', '')
    if not expected or request.headers.get('X-API-Key', '') != expected:
      return jsonify({'msg': 'API 키가 없거나 잘못되었습니다.'}), 401
    return fn(*args, **kwargs)
  return wrapper


def _create_security_post(ev):
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
  data = request.get_json(silent=True) or {}
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
  db.session.flush()

  post_id = None
  if decision == 'deny' and current_app.config.get('AUTO_POST_ON_DENY'):
    post_id = _create_security_post(ev)

  db.session.commit()
  return jsonify({'id': ev.id, 'student': ev.student,
                  'decision': ev.decision, 'post_id': post_id}), 201


@security_bp.route('/events', methods=['GET'])
def list_security_events():
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
  rows = (db.session.query(SecurityEvent.student)
          .distinct().order_by(SecurityEvent.student).all())
  return jsonify({'students': [r[0] for r in rows]})
```

---

## 6. `_7_board_test/controllers/__init__.py`

블루프린트 묶음. app.py 가 이 목록을 한 번에 등록한다.

```python
from .auth_controller import auth_bp
from .page_controller import page_bp
from .post_controller import post_bp
from .public_controller import public_bp
from .security_controller import security_bp

all_blueprints = (page_bp, auth_bp, post_bp, security_bp, public_bp)

__all__ = ['all_blueprints', 'page_bp', 'auth_bp', 'post_bp',
           'security_bp', 'public_bp']
```

---

## 7. `_7_board_test/app.py`

create_app() 안의 db.create_all() 이 실제로 CREATE TABLE 을 실행한다.

```python
from flask import Flask

from config import Config
from controllers import all_blueprints
from extensions import db, jwt


def create_app(config_class=Config):
  app = Flask(__name__)
  app.config.from_object(config_class)

  db.init_app(app)
  jwt.init_app(app)

  for bp in all_blueprints:
    app.register_blueprint(bp)

  with app.app_context():
    db.create_all()

  return app


app = create_app()


if __name__ == '__main__':
  app.run(debug=True, host='0.0.0.0', port=5000)
```

---

## 8. `_7_board_test/.env`  (실제 값은 각자 채울 것)

**깃에 절대 올리지 마세요.** `.gitignore` 에 이미 등록돼 있습니다.

```dotenv
DATABASE_URL=mysql+pymysql://<user>:<password>@localhost:3306/my_new_board_db
JWT_SECRET_KEY=<임의의_긴_문자열>
SECURITY_API_KEY=<n8n 과 공유할 키>
AUTO_POST_ON_DENY=0
PUBLIC_API_KEY=<공공데이터포털 서비스키>
```

---

## 9. 실행 (PowerShell)

```powershell
cd E:\0-Aleph-Python-Test\Python-Lab-ALeph-T
.\.venv\Scripts\Activate.ps1
cd _7_board_test
python app.py
```

`app.py` 가 뜨는 순간 `db.create_all()` 이 돌면서 없는 표가 만들어집니다.

## 10. 표가 생겼는지 확인

```sql
USE my_new_board_db;
SHOW TABLES;
DESC security_events;
SELECT COUNT(*) FROM security_events;
```

## 11. 표만 다시 만들기 (데이터 삭제됨)

```sql
DROP TABLE security_events;
```

지운 뒤 `python app.py` 를 다시 실행하면 `db.create_all()` 이 새로 만듭니다.
