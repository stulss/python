"""[주석·설명용 사본] models/user.py — 회원 계정·등급(RBAC)·계정 잠금 모델

이 파일은 원본 models/user.py 를 복사해 주석만 덧붙인 학습용 사본이다.
  · 실행 코드는 원본과 똑같다(주석과 이 설명 문자열만 추가).
  · 원본을 고쳐도 이 사본에는 반영되지 않는다.
  · 앱은 원본 models/user.py 를 import 한다(models/__init__.py 경유, rbac.py·auth_controller.py 는
    from models.user import ... 로 등급 상수를 가져간다).
    이 사본은 이름에 공백·하이픈이 있어 import 문으로 불러올 수 없다 — 읽기 전용 교재다.
  · 원본에는 모듈 설명이 없어 이 설명 문자열을 새로 붙였다.

==============================================================================
0. 한 줄 요약
==============================================================================
  "회원 한 명 = users 표의 한 행. 로그인 정보(아이디·비밀번호 해시), 등급(user < gold < admin)과
   그 등급을 누가·언제·왜 줬는지(감사기록), 브루트포스 대응용 잠금 상태를 함께 담는다.
   등급 규칙(ROLE_LEVEL·role_level)도 이 파일 한 곳에서 정의한다"

==============================================================================
1. 쉬운 비유 — 회사의 '사원증'
==============================================================================
  users 행 1개(User)              = 사원증 한 장
  username / password             = 이름 / 비밀번호 — 금고에는 비밀번호 원문이 아니라 '지문(해시)'만 보관
  role                            = 사원증 색깔: 일반 < 골드 < 관리자
  ROLE_LEVEL                      = 색깔별 등급 숫자표(1·2·3). 높은 색은 낮은 색 문을 모두 연다
  role_granted_by/at/reason       = 사원증 뒷면의 발급 기록(누가·언제·왜 이 색을 줬나)
  is_locked / locked_at / lock_reason = 정지된 사원증 — 비밀번호가 맞아도 출입 거부(423)
  failed_logins                   = 비밀번호를 연속으로 틀린 횟수(표시용, 성공하면 0)
  n8n(SOAR)                       = 보안팀 — 사원증 정지(/api/admin/lock)·색깔 회수(/api/admin/revoke)

  출입문(API)마다 "골드 이상" 같은 표지가 붙어 있고, 경비원(rbac.role_required)은
  사원증 색깔의 숫자와 표지의 숫자를 비교해 같거나 높으면 들여보낸다.

==============================================================================
2. 기본 개념
==============================================================================
  ■ ORM · 모델 클래스 · 기본키 id
      class User(db.Model) ⇄ 표 users. 객체 1개 = 행 1개.
      id(정수 기본키, AUTO_INCREMENT)는 로그인 토큰(JWT)에 담기는 값이다:
      create_access_token(identity=str(user.id)) → rbac.current_user() 가 db.session.get(User, int(uid)) 로 되찾는다.

  ■ unique=True — 아이디 중복 금지
      DDL 에 UNIQUE (username) 가 생긴다. 같은 아이디 두 번째 INSERT 는 DB 가 거절한다.

  ■ 비밀번호는 해시만 저장
      해시 = 되돌릴 수 없는 '지문'. 가입 때 werkzeug 의 generate_password_hash() 로 만들고,
      로그인 때 check_password_hash() 로 입력값과 비교한다. DB 가 털려도 원문이 바로 드러나지 않는다.
      현재 설치된 Werkzeug 3.0 은 scrypt 방식 'scrypt:32768:8:1$<소금>$<해시값>' 형태, 약 162자 → String(255) 에 들어간다.

  ■ 인증(Authentication) vs 인가(Authorization)
      인증 = "너 누구야?" (로그인·토큰)            실패 → 401
      인가 = "너 이거 해도 돼?" (role 등급 확인)   실패 → 403
      잠긴 계정의 로그인 시도                       → 423 Locked

  ■ RBAC(역할 기반 접근제어) — 계단식 등급
      사람마다 권한을 따로 주지 않고 역할(role)에 권한을 묶는다.
      이 프로젝트는 숫자 사다리: user(1) < gold(2) < admin(3). "필요 등급 이상이면 통과".
      그래서 admin 계정은 골드 화면도 볼 수 있다(등급마다 계정을 따로 만들 필요가 없다).

  ■ 안전한 쪽으로 실패(fail-safe)
      role_level() 은 모르는 등급 이름을 0(권한 없음)으로 바꾼다.
      DB 에 이상한 role 값이 들어 있어도 그 회원은 어떤 등급 검사도 통과하지 못한다.

  ■ 감사기록(Audit trail)
      role_granted_by / role_granted_at / role_reason = 권한을 마지막으로 바꾼 주체·시각·사유.
      관리자 페이지 회원 목록과 회수봇이 이 값을 보여 준다.

  ■ 계정 잠금(Account lockout) — 브루트포스 대응
      로그인 실패 경보가 쌓이면 n8n 이 POST /api/admin/lock 으로 is_locked=True 로 만든다.
      잠긴 계정은 비밀번호가 맞아도 로그인이 거부된다(423). 해제는 /api/admin/unlock.

  ■ default vs server_default
      default        = 파이썬 쪽 기본값. ORM 이 INSERT 할 때 채운다. DDL 에는 안 나타난다.
      server_default = DB 쪽 기본값. CREATE TABLE 에 DEFAULT '...' 로 들어간다
                       → SQL 로 직접 INSERT 해도, 이미 있는 행에 컬럼을 추가해도 그 값이 채워진다.
      role·is_locked·failed_logins 는 둘 다 줬다(아래 4절).

  ■ @property
      메서드를 속성처럼 괄호 없이 읽게 한다.  user.is_admin  (O)    user.is_admin()  (X, bool 을 호출하려다 TypeError)

  ■ __repr__
      print(user)·디버거·로그에서 객체가 어떻게 보일지 정한다.  예) <User kim (gold)>

==============================================================================
3. 동작 원리
==============================================================================
  [가입]  POST /api/auth/register {username, password}              auth_controller.register
       │ 같은 아이디가 이미 있으면 400
       │ User(username, password=generate_password_hash(비번))
       │   → role='user', is_locked=False, failed_logins=0 은 기본값으로 채워짐
       ▼ 201 {"msg": "회원가입 성공"}

  [로그인]  POST /api/auth/login {username, password}                auth_controller.login
       │ ① user.is_locked 이면        → Graylog 신고 + 423 {"locked": true}   (비번 확인 전에 거부)
       │ ② 없는 아이디·틀린 비번이면  → (아이디가 있으면 failed_logins + 1) + Graylog 신고 + 401
       │ ③ 성공                        → failed_logins 를 0 으로 + JWT 발급
       ▼ 200 {"access_token": ..., "username": ..., "role": ..., "role_label": ROLE_LABEL[role]}

  [등급 검사]  controllers/rbac.py
       │ current_user() : 토큰 → id → User
       │ role_required('gold') : 로그인 안 함 401 / role_level(user.role) < role_level('gold') 이면 403
       │ admin_controller.admin_required : X-API-Key 이거나 user.is_admin 이면 통과
       ▼ GET /api/auth/me → {id, username, role, role_label, is_gold, is_admin}  (화면 JS 가 메뉴·예외 화면 결정)

  [권한 관리]  /api/admin/* (X-API-Key 또는 admin 로그인)
       │ grant  : role = 요청값(VALID_ROLES 안에서만), role_granted_by = 호출자, role_granted_at = 지금, role_reason
       │ revoke : role → 'user' (이미 user 면 변경 없음), 감사 3칸 갱신 + security_events 기록
       │ lock   : is_locked=True, locked_at=지금, lock_reason        + security_events 기록
       │ unlock : is_locked=False, failed_logins=0, lock_reason=None
       ▼ GET /api/admin/users(?role=) · /violations → [to_dict()] → admin.html 회원 목록, 회수봇

==============================================================================
4. 옵션 설명
==============================================================================
  [모듈 상수·함수]
  이름          값                                        뜻 · 누가 쓰나
  ------------  ----------------------------------------  ---------------------------------------------------
  ROLE_LEVEL    {'user': 1, 'gold': 2, 'admin': 3}        등급 → 숫자. 숫자가 클수록 높다. role_level()·rbac 가 비교에 쓴다.
  ROLE_LABEL    {'user': '일반', 'gold': '골드',          화면용 한글 이름. 로그인·/me 응답의 role_label,
                 'admin': '관리자'}                       403 메시지("골드 등급 이상만…")에 쓰인다.
  VALID_ROLES   tuple(ROLE_LEVEL)                         dict 의 키를 넣은 순서대로 → ('user', 'gold', 'admin').
                                                          튜플이라 실수로 바꿀 수 없다. admin_controller 가
                                                          grant 입력 검사·?role= 필터·오류 문구에 쓴다.
  role_level()  ROLE_LEVEL.get(role, 0)                   등급 이름 → 숫자. 모르는 이름·None 은 0.

  [컬럼]
  컬럼             파이썬 선언 → MySQL DDL(create_all 기준)       옵션                           뜻 · 이 값을 준 이유
  ---------------  ---------------------------------------------  -----------------------------  ---------------------------------------
  id               db.Integer → INTEGER AUTO_INCREMENT, PK        primary_key=True               회원 번호. JWT identity·posts.author_id 가 가리킨다.
  username         db.String(80) → VARCHAR(80) NOT NULL,          unique=True, nullable=False    로그인 아이디. 같은 아이디가 둘이면 누가 누군지
                   UNIQUE (username)                                                             모르므로 DB 가 중복을 막는다.
  password         db.String(255) → VARCHAR(255) NOT NULL         nullable=False                 비밀번호 해시(평문 금지). scrypt 해시 약 162자라 255 로 여유.
  role             db.String(20) → VARCHAR(20) NOT NULL           nullable=False, default='user',  등급 이름. 새 회원은 가장 낮은 'user'.
                   DEFAULT 'user'                                 server_default='user'          server_default 로 SQL 직접 INSERT 에도 'user'.
                                                                                                 app.py _ensure_schema 도 같은 DEFAULT 로 ALTER 한다.
  role_granted_by  db.String(80) → VARCHAR(80)                    (없음) → NULL 허용             마지막으로 권한을 바꾼 주체: 'apikey' 또는 admin 아이디.
                                                                                                 username 과 같은 길이 80.
  role_granted_at  db.DateTime → DATETIME                         (없음)                         그 시각(컨트롤러가 datetime.now() 로 넣음). 가입만 한 회원은 NULL.
  role_reason      db.String(200) → VARCHAR(200)                  (없음)                         사유. 컨트롤러가 [:200] 로 자른다.
  is_locked        db.Boolean → BOOL NOT NULL DEFAULT '0'         nullable=False, default=False,  잠금 여부. MySQL BOOL = TINYINT(1)(0/1),
                                                                  server_default='0'             JSON 에서는 true/false. 기존 행도 0(잠기지 않음)으로 시작.
  locked_at        db.DateTime → DATETIME                         (없음)                         잠근 시각(/lock 이 채움).
  lock_reason      db.String(200) → VARCHAR(200)                  (없음)                         잠근 사유(/lock 이 [:200] 로 채우고 /unlock 이 None 으로).
  failed_logins    db.Integer → INTEGER NOT NULL DEFAULT '0'      nullable=False, default=0,      로그인 실패 횟수(표시용). 틀리면 +1, 성공·unlock 때 0.
                                                                  server_default='0'             잠금 판정에는 쓰이지 않는다(판정은 n8n 몫).

  옵션 용어 풀이
    unique=True          : 같은 값이 두 행에 들어갈 수 없다(UNIQUE 제약 + 인덱스)
    nullable=False       : NOT NULL
    default=값           : ORM INSERT 때 파이썬이 채움(DDL 에 없음)
    server_default='값'  : DDL 에 DEFAULT '값' 으로 들어감. 문자열로 줘야 해서 Boolean·Integer 도 '0' 이라고 적었다
    db.Boolean           : 파이썬 True/False ⇄ MySQL BOOL(TINYINT(1)) 0/1
    (index · ForeignKey 는 이 모델에 없다. relationship 도 여기엔 없지만,
     models/post.py 의 backref 가 이 클래스에 user.posts 속성을 붙인다)

==============================================================================
5. 예시
==============================================================================
  users 표의 행
    id  username  password               role   role_granted_by  role_granted_at      role_reason   is_locked  failed_logins
    1   lsy       scrypt:32768:8:1$...   admin  apikey           2026-09-01 09:00:00  강사 지정     0          0
    2   kim       scrypt:32768:8:1$...   gold   lsy              2026-09-14 10:00:00  이벤트 당첨   0          0
    3   park      scrypt:32768:8:1$...   user   NULL             NULL                 NULL          1          6

  to_dict() 결과 = GET /api/admin/users 의 "users", /api/admin/violations 의 "violations" 배열 원소
    {"id": 2, "username": "kim", "role": "gold",
     "role_granted_by": "lsy", "role_granted_at": "2026-09-14T10:00:00", "role_reason": "이벤트 당첨",
     "is_locked": false, "locked_at": null, "lock_reason": null, "failed_logins": 0}
    · password 는 넣지 않는다 — 해시라도 API 로 내보내지 않는다.

  로그인 응답(auth_controller)       {"access_token": "<JWT 토큰>", "username": "kim", "role": "gold", "role_label": "골드"}
  GET /api/auth/me 응답              {"id": 2, "username": "kim", "role": "gold", "role_label": "골드",
                                      "is_gold": true, "is_admin": false}
  등급 부족 403(rbac.role_required)  {"msg": "골드 등급 이상만 이용할 수 있습니다.", "required_role": "gold", "current_role": "user"}

  사용 코드
    kim.has_role('gold')    # True   (2 >= 2)
    kim.has_role('admin')   # False  (2 >= 3 아님)
    kim.is_gold, kim.is_admin   # True, False   (괄호 없이 — @property)
    role_level('superuser')     # 0
    print(kim)                  # <User kim (gold)>

==============================================================================
6. 자주 걸리는 함정
==============================================================================
  ① '모르는 값은 0' 은 회원 쪽에만 안전하다. 요구 등급(required) 이름을 잘못 쓰면 반대로 뚫린다.
     has_role('golld') → role_level('golld') = 0 → 모든 회원이 0 이상이라 True.
     rbac.role_required('golld') 도 같은 계산이라 로그인한 누구나 통과한다 → 등급 이름은 VALID_ROLES 값만 쓴다.
  ② "새 등급은 이 두 표에만 추가" 는 서버 쪽 이야기다.
     templates/admin.html 의 부여 선택지(gold·admin·user)와 등급 배지는 따로 적혀 있어 새 등급이 화면에 안 나온다.
     is_admin 은 숫자 비교가 아니라 role == 'admin' 글자 비교라, admin 위에 새 등급을 만들면 그 등급은 관리자 API 를 못 쓴다.
     role 컬럼 길이도 20자다.
  ③ role 컬럼은 아무 문자열이나 받는다(DB 제약 없음). 입력 검사는 /api/admin/grant 의 VALID_ROLES 뿐이다.
  ④ unlock 은 is_locked·failed_logins·lock_reason 만 되돌리고 locked_at 은 그대로 둔다.
     해제된 계정도 to_dict() 에 옛 locked_at 이 남는다.
  ⑤ revoke 도 role_granted_by·role_granted_at·role_reason 을 덮어쓴다. 회수 뒤에는 이 칸이 '부여자'가 아니라 '회수자'다.
  ⑥ 가입은 "먼저 조회 → 없으면 INSERT" 라서 같은 아이디로 거의 동시에 가입하면 두 번째는 unique 제약에 걸려
     IntegrityError(500)가 난다. 최종 방어선은 unique=True 다.
  ⑦ failed_logins 는 표시용이다. 없는 아이디로 틀리면 세지 않고, 이 숫자로 자동 잠금되지도 않는다(잠금은 n8n 이 /lock 호출).
  ⑧ 아이디 대소문자: docs/004 의 DB 생성문은 utf8mb4_unicode_ci(대소문자 구분 안 함)라 MySQL 에서는
     'KIM' 과 'kim' 이 같은 아이디로 취급된다. 테스트용 SQLite 는 구분하고, ADMIN_ALLOWLIST 비교(파이썬)도 구분한다.
  ⑨ default 만 있고 server_default 가 없는 컬럼은 SQL 직접 INSERT 때 기본값이 안 들어간다.
     이 모델은 NOT NULL 기본값 컬럼(role·is_locked·failed_logins)에 둘 다 줘서 그 문제가 없다.
  ⑩ 시각 컬럼은 서버 PC 현지 시각(시간대 정보 없음)이고, MySQL DATETIME 은 초 단위까지만 저장한다.
"""
from datetime import datetime

# db : extensions.py 의 SQLAlchemy() 객체(모든 모델이 공유)
from extensions import db

# ═════════════════════════════════════════════════════════════════════════════
# 등급 정의 (ROLE_LEVEL · ROLE_LABEL · VALID_ROLES) — RBAC 규칙의 원본
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 사원증 색깔별 등급 숫자표 + 한글 이름표.
# 입력·출력: 없음(상수). 모듈을 import 할 때 한 번 만들어진다.
# 누가 쓰나: controllers/rbac.py(가져와 다시 내보냄), auth_controller.py(ROLE_LABEL),
#            admin_controller.py(VALID_ROLES — rbac 경유)
# ═════════════════════════════════════════════════════════════════════════════
# ── 등급 정의 ── 새 등급을 만들려면 이 두 표에만 추가하면 된다.
# 숫자가 클수록 높은 등급이고, 판정은 '같거나 높으면 통과'다.
# (주의: 화면 admin.html 의 선택지·배지는 따로 적혀 있다 — 모듈 설명 6절 ②)
ROLE_LEVEL = {'user': 1, 'gold': 2, 'admin': 3}
# 화면·메시지에 보여 줄 한글 이름. 로그인 응답의 role_label, 403 메시지에 쓰인다
ROLE_LABEL = {'user': '일반', 'gold': '골드', 'admin': '관리자'}
# 허용되는 등급 이름 목록. tuple(dict) = 키만 순서대로 → ('user', 'gold', 'admin')
#   튜플은 바꿀 수 없어 실수로 목록이 변하지 않는다. admin_controller 의 입력 검사에 쓰인다
VALID_ROLES = tuple(ROLE_LEVEL)


# ═════════════════════════════════════════════════════════════════════════════
# role_level() — 등급 이름을 비교할 수 있는 숫자로
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 사원증 색깔을 보고 숫자표에서 등급 숫자를 찾아 주기. 표에 없는 색이면 0.
# 입력: role (문자열 또는 None)   출력: 0~3 정수
# 누가 쓰나: 아래 User.has_role, controllers/rbac.py role_required
# ═════════════════════════════════════════════════════════════════════════════
def role_level(role):
  """모르는 값은 0(권한 없음)으로 떨어뜨린다 — 안전한 쪽으로 실패한다."""
  # dict.get(키, 기본값) : 키가 없으면 KeyError 대신 기본값 0
  #   'admin' → 3, 'superuser' → 0, None → 0
  #   회원의 role 이 이상하면 0 이라 안전하지만, 요구 등급 이름을 틀리게 쓰면 0 이 되어 오히려 모두 통과한다
  return ROLE_LEVEL.get(role, 0)


# ═════════════════════════════════════════════════════════════════════════════
# User — 회원 한 명 = users 표의 행 한 개
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 사원증 한 장(이름·비번 지문·색깔·발급 기록·정지 여부).
# 입력: 가입(username·해시), 관리 API(role·감사기록·잠금), 로그인(failed_logins)
# 출력: 표의 행 / to_dict() → /api/admin/users·/violations / 속성 is_admin·is_gold → /api/auth/me
# 누가 쓰나: auth_controller, rbac.current_user, admin_controller, security_controller(soarbot 계정),
#            models/post.py(ForeignKey('users.id')·relationship('User')), tests/test_rbac.py
# ═════════════════════════════════════════════════════════════════════════════
class User(db.Model):
  # DB 안의 표 이름. posts.author_id 의 ForeignKey('users.id') 가 이 이름을 가리킨다
  __tablename__ = 'users'

  # 회원 번호(대리키). JWT 의 identity 로 문자열 str(id) 가 들어간다
  id = db.Column(db.Integer, primary_key=True)
  # 로그인 아이디. unique=True → DDL 에 UNIQUE (username), 중복 INSERT 는 DB 가 거절
  username = db.Column(db.String(80), unique=True, nullable=False)
  # generate_password_hash() 결과(scrypt 약 162자)를 저장. to_dict() 에는 넣지 않는다
  password = db.Column(db.String(255), nullable=False)   # 해시만 저장(평문 금지)

  # ── 인가(authorization) ── 역할 기반 접근제어(RBAC)
  # 'user'(기본) | 'gold' | 'admin'. 등급은 계단식이다(user < gold < admin).
  #   gold  : 골드 전용 화면(/gold) 이용
  #   admin : 관리자 페이지·회원 권한 관리 (골드 화면도 볼 수 있다)
  # default='user'        : ORM 으로 가입시킬 때 파이썬이 채움
  # server_default='user' : CREATE TABLE 에 DEFAULT 'user' → SQL 직접 INSERT 에도 적용
  role = db.Column(db.String(20), nullable=False, default='user', server_default='user')
  # 감사(audit): 누가·언제·왜 이 권한을 부여/변경했는가
  # 주체: 'apikey'(기계 호출) 또는 admin 아이디. grant 뿐 아니라 revoke 도 이 칸을 덮어쓴다
  role_granted_by = db.Column(db.String(80))
  # 변경 시각. 컨트롤러가 datetime.now() 로 직접 넣는다(컬럼 default 는 없다)
  role_granted_at = db.Column(db.DateTime)
  # 사유. 컨트롤러가 200자로 자른다
  role_reason = db.Column(db.String(200))

  # ── 계정 잠금(account lockout) ── 브루트포스 대응
  # 로그인 실패가 임계 초과하면 n8n(SOAR)이 잠근다. 잠긴 계정은 로그인 거부(423).
  # Boolean → MySQL BOOL(TINYINT(1)). server_default 는 문자열이라 '0'(= False)
  is_locked = db.Column(db.Boolean, nullable=False, default=False, server_default='0')
  # 잠근 시각(/lock). /unlock 은 이 값을 지우지 않는다
  locked_at = db.Column(db.DateTime)
  # 잠근 사유(/lock). /unlock 이 None 으로 비운다
  lock_reason = db.Column(db.String(200))
  # 틀릴 때 +1(아이디가 있을 때만), 로그인 성공·/unlock 때 0. 자동 잠금 판정에는 쓰이지 않는다
  failed_logins = db.Column(db.Integer, nullable=False, default=0, server_default='0')  # 표시용(성공 시 0)

  # ═══════════════════════════════════════════════════════════════════════════
  # is_admin — 관리자인가 (@property: 괄호 없이 user.is_admin)
  # ───────────────────────────────────────────────────────────────────────────
  # 비유: "사원증이 빨간색인가?" — 숫자표를 보지 않고 색 이름을 그대로 비교한다.
  # 출력: bool   누가 쓰나: admin_controller._current_admin_user(사람 관리자 인가), /api/auth/me
  # ═══════════════════════════════════════════════════════════════════════════
  @property
  def is_admin(self):
    # 등급 숫자가 아니라 글자 비교 → 'admin' 정확히 일치할 때만 True
    return self.role == 'admin'

  # ═══════════════════════════════════════════════════════════════════════════
  # is_gold — 골드 화면을 볼 수 있는가 (@property)
  # ───────────────────────────────────────────────────────────────────────────
  # 비유: "골드 이상 색인가?" — 숫자표로 비교하므로 관리자(빨강)도 통과.
  # 출력: bool   누가 쓰나: /api/auth/me 의 is_gold (gold.html 화면 JS 가 예외 화면 여부를 정할 때)
  # ═══════════════════════════════════════════════════════════════════════════
  @property
  def is_gold(self):
    """골드 화면을 볼 수 있는가 — admin 도 True(등급이 더 높으므로)."""
    # 'gold' 이름을 직접 비교하지 않고 has_role 로 계단식 판정
    return self.has_role('gold')

  # ═══════════════════════════════════════════════════════════════════════════
  # has_role(required) — 내 등급이 required 이상인가
  # ───────────────────────────────────────────────────────────────────────────
  # 비유: 출입문 표지 숫자 vs 내 사원증 숫자 — 같거나 크면 통과.
  # 입력: required (등급 이름)   출력: bool
  # 누가 쓰나: 이 파일의 is_gold. (rbac.role_required 는 같은 비교를 role_level 로 직접 한다)
  # ═══════════════════════════════════════════════════════════════════════════
  def has_role(self, required):
    """내 등급이 required 이상인가. user < gold < admin."""
    # 예) gold(2) >= gold(2) → True,  gold(2) >= admin(3) → False
    #     required 이름을 틀리게 쓰면 오른쪽이 0 → 누구나 True (모듈 설명 6절 ①)
    return role_level(self.role) >= role_level(required)

  # ═══════════════════════════════════════════════════════════════════════════
  # to_dict() — 회원 1명을 JSON 으로 보낼 수 있는 dict 로 (password 제외)
  # ───────────────────────────────────────────────────────────────────────────
  # 비유: 사원증을 복사해 명단에 붙이되, 비밀번호 지문 칸은 가리고 붙인다.
  # 입력: 없음(self)   출력: 컬럼 10개 dict (시각은 ISO 8601 문자열 또는 None)
  # 누가 쓰나: admin_controller.list_users(GET /api/admin/users → admin.html 회원 목록·회수봇),
  #            admin_controller.list_violations(GET /api/admin/violations)
  # ═══════════════════════════════════════════════════════════════════════════
  def to_dict(self):
    return {
        # 식별 — password 는 일부러 넣지 않는다(해시라도 밖으로 내보내지 않기)
        'id': self.id,
        'username': self.username,
        # 인가 + 감사기록 (admin.html 이 부여자·부여시각·사유 칸에 표시)
        'role': self.role,
        'role_granted_by': self.role_granted_by,
        # 괄호로 감싸 두 줄로 나눈 조건식: 값이 있으면 ISO 문자열, 없으면(가입만 한 회원) None
        'role_granted_at': (self.role_granted_at.isoformat()
                            if self.role_granted_at else None),
        'role_reason': self.role_reason,
        # 잠금 상태 (JSON 에서 is_locked 는 true/false)
        'is_locked': self.is_locked,
        # 잠근 적이 없으면 None. unlock 뒤에도 옛 시각이 남아 있을 수 있다
        'locked_at': self.locked_at.isoformat() if self.locked_at else None,
        'lock_reason': self.lock_reason,
        'failed_logins': self.failed_logins,
    }

  # ═══════════════════════════════════════════════════════════════════════════
  # __repr__() — 개발자가 볼 때의 표시 모양
  # ───────────────────────────────────────────────────────────────────────────
  # 출력 예: <User kim (gold)>   누가 쓰나: print(user)·디버거·로그 (API 응답에는 쓰이지 않는다)
  # ═══════════════════════════════════════════════════════════════════════════
  def __repr__(self):
    return f'<User {self.username} ({self.role})>'
