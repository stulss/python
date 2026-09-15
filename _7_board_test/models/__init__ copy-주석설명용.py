"""[주석·설명용 사본] models/__init__.py — 모델 묶음(패키지 입구)

이 파일은 원본 models/__init__.py 를 복사해 주석만 덧붙인 학습용 사본이다.
  · 실행 코드는 원본과 똑같다(주석과 이 설명 문자열만 추가).
  · 원본을 고쳐도 이 사본에는 반영되지 않는다.
  · 앱(app.py·controllers·tests)은 원본 models 패키지를 import 한다.
    이 사본은 이름에 공백·하이픈이 있어 import 문으로 불러올 수도 없다 — 읽기 전용 교재다.

원본 모듈 설명(내용 그대로)
  "모델 묶음.
   db.create_all() 이 테이블을 만들려면 모든 모델 클래스가 미리 import 되어 있어야 한다."

==============================================================================
0. 한 줄 요약
==============================================================================
  "models 폴더를 패키지로 묶고, 표 설계도(모델 클래스) 5개를 한꺼번에 import 해서
   db.create_all() 이 빠짐없이 표를 만들 수 있게 등록해 두는 입구 파일"

==============================================================================
1. 쉬운 비유 — 건축사무소의 '설계도 접수 창구'
==============================================================================
  models 폴더            = 설계도 보관실
  모델 클래스 1개         = 표(테이블) 1개의 설계도
  이 파일(__init__.py)   = 접수 창구 — 보관실의 설계도를 모두 접수대에 올린다
  db.metadata            = 접수 대장(등록된 표 목록)
  db.create_all()        = 시공팀 — 접수 대장에 적힌 표 중 아직 없는 것만 짓는다

  시공팀(create_all)은 보관실을 직접 뒤지지 않는다. 대장에 오른 설계도만 본다.
  설계도가 대장에 오르는 순간은 "그 클래스가 적힌 파일이 import(실행)될 때"다.
  그래서 창구가 설계도 5장을 모두 import 해 두어야 표가 빠짐없이 생긴다.
  창구에서 빠진 설계도는? 에러 없이 조용히 표가 안 생긴다.

==============================================================================
2. 기본 개념
==============================================================================
  ■ 패키지와 __init__.py
      __init__.py 가 있는 폴더는 import 할 수 있는 '패키지'가 된다.
      import models / from models import User 를 하면 이 파일이 먼저 한 번 실행된다.
      from models.user import ROLE_LABEL 처럼 하위 파일을 직접 불러도
      부모 패키지인 이 파일이 먼저 실행된다(controllers/rbac.py·auth_controller.py 가 이렇게 쓴다).

  ■ 상대 import — from .user import User
      점(.) 하나 = "이 파일과 같은 패키지(models) 안". 패키지로 import 될 때만 동작한다.

  ■ 모델 등록(metadata)
      models/*.py 의 class User(db.Model): 문장이 실행되는 순간
      SQLAlchemy 가 db.metadata 에 'users' 표 정보(컬럼·키·인덱스)를 적어 둔다.
      다섯 파일 모두 같은 db(extensions.py 의 SQLAlchemy() 한 개)를 쓰므로 대장도 하나다.

  ■ db.create_all()
      app.py create_app() 안에서 호출된다. 대장에 있는 표 중 DB 에 '없는 표'만 CREATE TABLE.
      이미 있는 표의 컬럼은 고치지 않는다
      → 그래서 app.py 에 users 표 전용 보강 함수 _ensure_schema()(ALTER TABLE)가 따로 있다.

  ■ 모듈은 한 번만 실행된다
      처음 import 된 모듈은 sys.modules 에 보관된다. 다른 파일이 또 import 해도
      다시 실행하지 않고 보관본을 준다 → 모델 클래스가 두 번 등록되지 않는다.

  ■ __all__
      from models import * 를 할 때 가져갈 이름 목록. 이름을 콕 집는 import 에는 영향이 없다.
      (이 프로젝트 .py 파일에는 import * 를 쓰는 곳이 없다 — 사실상 '공개 이름표' 역할)

==============================================================================
3. 동작 원리 — python app.py 를 켰을 때
==============================================================================

   app.py  from controllers import all_blueprints
     │
     ▼
   controllers/__init__.py  →  첫 줄 from .admin_controller import admin_bp
     │
     ▼
   admin_controller.py  from models import BlockedIP, Incident, SecurityEvent, User
     │   ← 여기서 이 파일(models/__init__.py)이 처음 실행된다
     │
     ├─ from .blocked_ip import BlockedIP          → blocked_ips 표 등록
     ├─ from .incident import Incident             → incidents 표 등록
     ├─ from .post import Post                     → posts 표 등록
     ├─ from .security_event import SecurityEvent  → security_events 표 등록
     └─ from .user import User                     → users 표 등록
     │
     ▼
   app.py  from models import BlockedIP   (이미 실행됨 → 보관본 재사용)
     │
     ▼
   create_app() → with app.app_context():
                    db.create_all()    → 5개 표 중 DB 에 없는 표만 CREATE TABLE
                    _ensure_schema()   → users 표에 빠진 role·잠금 컬럼만 ALTER TABLE

==============================================================================
4. 옵션 설명 — 이 파일의 import 줄과 __all__
==============================================================================
  import 줄(모듈 → 클래스)         테이블 이름        주로 쓰는 곳
  ------------------------------  -----------------  ------------------------------------------
  .blocked_ip → BlockedIP         blocked_ips        app.py 차단 미들웨어,
                                                     admin_controller /block·/unblock·/blocked
  .incident → Incident            incidents          admin_controller /incident·/incidents·/incident/close
  .post → Post                    posts              post_controller /api/posts,
                                                     gold_controller /api/gold/posts,
                                                     security_controller 보안 공지글 자동 등록
  .security_event → SecurityEvent security_events    security_controller /api/security/*,
                                                     admin_controller 회수·잠금·차단 감사기록, 인시던트 취합
  .user → User                    users              auth_controller 가입·로그인·/me, rbac.current_user,
                                                     admin_controller 권한·잠금, security_controller soarbot 계정

  · import 순서: 파일 이름 알파벳순. post 가 user 보다 먼저지만 문제없다
    (post.py 는 User 를 문자열 'User' 로 가리키고, 실제 클래스로 바꾸는 건 나중이다).
  · __all__ = ['User', 'Post', 'SecurityEvent', 'BlockedIP', 'Incident']
    목록 순서는 동작에 영향이 없다. tests/test_rbac.py 는 from models import Post, User 로 쓴다.

==============================================================================
5. 예시
==============================================================================
    from models import User, Post          # 이 파일을 거쳐 가져온다(프로젝트 표준 방식)
    from models.user import ROLE_LABEL     # 하위 파일 직접 — 이때도 이 파일이 먼저 실행된다
    from models import *                   # __all__ 의 5개 이름만 들어온다

  새 모델(표)을 추가하는 순서
    ① models/<이름>.py 에 class X(db.Model): 작성 (__tablename__ 지정)
    ② 이 파일에 from .<이름> import X 한 줄 + __all__ 에 'X' 추가
    ③ 앱을 다시 켠다 → create_all() 이 새 표를 만든다

==============================================================================
6. 자주 걸리는 함정
==============================================================================
  ① 새 모델을 여기 import 하지 않으면 표가 안 생기는데 에러도 안 난다.
     (컨트롤러가 그 파일을 직접 import 하면 그 경로로 우연히 등록되기도 해서 더 헷갈린다)
  ② 기존 표에 컬럼을 추가해도 create_all() 은 반영하지 않는다 → DB 에 컬럼이 없어 쿼리 에러.
     users 표만 app.py _ensure_schema() 가 보강한다. posts·security_events·blocked_ips·incidents 는
     그런 보강이 없으니 ALTER TABLE 을 직접 하거나 표를 다시 만들어야 한다(데이터 주의).
  ③ __all__ 에만 적고 import 줄을 빠뜨리면 from models import * 에서 AttributeError.
     반대로 __all__ 에서 빠뜨려도 from models import User 는 정상 동작한다.
  ④ app.py 맨 위 설명에는 "models/ User · Post · SecurityEvent" 3개만 적혀 있다.
     설명이 옛날 것이고, 실제 모델은 이 파일의 5개다.
  ⑤ 이 파일을 python models/__init__.py 로 직접 실행하면 상대 import(점) 때문에 ImportError.
     항상 프로젝트 폴더에서 python app.py 나 pytest 로 패키지째 쓴다.
"""
# ═════════════════════════════════════════════════════════════════════════════
# 모델 5개 import — 표 설계도를 db.metadata 에 '등록'시키는 줄들
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 접수 창구에 설계도 5장을 올려 두는 일. 올라온 것만 create_all() 이 짓는다.
# 입력·출력: 없음 — import 되는 순간 각 파일의 class 문장이 실행되며 등록이 끝난다.
# 누가 쓰나: controllers/*·app.py·tests 의 "from models import ..." 가 모두 이 파일을 거친다.
#
# 점(.) = 같은 패키지(models) 안의 파일. 순서는 파일 이름 알파벳순이다.
# ═════════════════════════════════════════════════════════════════════════════
# 차단 IP 목록 → blocked_ips 표 (app.py 차단 미들웨어, /api/admin/block)
from .blocked_ip import BlockedIP
# 보안 인시던트 티켓 → incidents 표 (/api/admin/incident)
from .incident import Incident
# 게시글 → posts 표 (/api/posts, /api/gold/posts)
# User 보다 먼저 import 되지만 괜찮다: Post 는 User 를 문자열 'User' 로 가리키고,
# 그 문자열을 실제 클래스로 찾는 건 매퍼 설정 때(보통 처음 쿼리하거나 객체를 만들 때)다.
from .post import Post
# n8n 판정·감사기록 → security_events 표 (/api/security/events, 보안 대시보드)
from .security_event import SecurityEvent
# 회원·등급(RBAC)·계정 잠금 → users 표 (/api/auth/*, /api/admin/*)
from .user import User

# ═════════════════════════════════════════════════════════════════════════════
# __all__ — 이 패키지의 '공개 이름표'
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 창구 앞 안내판 "여기서 받아 갈 수 있는 설계도: 5종".
# 효과: from models import * 를 하면 이 목록의 이름만 가져간다.
#       from models import User 처럼 이름을 콕 집는 import 에는 영향이 없다.
# 목록 순서는 동작에 영향이 없다.
# ═════════════════════════════════════════════════════════════════════════════
__all__ = ['User', 'Post', 'SecurityEvent', 'BlockedIP', 'Incident']
