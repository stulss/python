"""[주석·설명용 사본] controllers/rbac.py — 등급별 접근제어(RBAC) 공용 규칙

이 파일은 원본 controllers/rbac.py 를 복사해 주석만 덧붙인 학습용 사본이다.
  · 실행 코드는 원본과 똑같다(주석과 이 설명 문자열만 추가).
  · 원본을 고쳐도 이 사본에는 반영되지 않는다.
  · 앱은 원본을 import 한다 — gold_controller · auth_controller · admin_controller 가
    from .rbac import ... 로 가져간다. 이 사본은 파일 이름에 공백·하이픈이 있어 import 할 수 없다.

==============================================================================
0. 한 줄 요약
==============================================================================
  원본 설명: "등급별 접근제어(RBAC) 공용 규칙 — 한 곳에서만 판정한다."

  → 요청에 붙은 로그인 토큰(JWT)으로 '누구인지' 알아내는 current_user() 와,
    그 사람의 등급이 필요 등급 이상인지 검사해 401/403 으로 막는 @role_required(...) 를
    한 파일에 모았다. 판정 규칙이 여러 컨트롤러에 흩어지지 않게 하려는 것이다.

==============================================================================
1. 쉬운 비유 — 놀이공원 손목 팔찌
==============================================================================
  JWT 토큰                 = 손목 팔찌 (매표소 = 로그인 에서 채워 준다, 2시간짜리)
  팔찌의 바코드(sub)       = 회원 번호만 적혀 있다 (등급은 적혀 있지 않다)
  current_user()           = 바코드를 찍어 회원 명부(users 표)에서 그 사람을 찾는 스캐너
  role(등급)               = 이용권 종류   일반(user) < 골드(gold) < 관리자(admin)
  @role_required('gold')   = "골드 이상 탑승" 표지판을 든 놀이기구 입구 직원
  401                      = "팔찌가 없거나 가짜·만료네요. 매표소부터 다녀오세요."
  403                      = "팔찌는 진짜인데, 이 기구는 골드 이상만 탈 수 있어요."

  입구 직원은 팔찌 바코드로 회원 번호만 읽고, 등급은 매번 명부를 다시 펼쳐 확인한다.
  그래서 관리자가 명부에서 등급을 내리면 옛 팔찌를 찬 사람도 다음 기구부터 바로 막힌다.
  이용권은 계단식이라 관리자 이용권으로도 골드 기구를 탈 수 있다.

==============================================================================
2. 기본 개념
==============================================================================
  ■ 인증(authentication) vs 인가(authorization) — 원본 설명
      인증(authentication) 과 인가(authorization) 는 다른 문제라 응답 코드도 다르다.
        401 = 네가 누구인지 모른다(로그인 안 함)
        403 = 누구인지는 알지만 등급이 모자라다
      이 파일에서는 토큰이 만료·위조됐거나, 토큰 속 회원이 DB 에 없어도 401 이다.

  ■ RBAC(역할 기반 접근제어)와 계단식 등급 — 원본 설명
      등급은 계단식이다.  user(1) < gold(2) < admin(3)
        · 필요 등급보다 내 등급이 같거나 높으면 통과
        · 그래서 admin 은 골드 화면도 볼 수 있다(등급마다 계정을 새로 만들 필요가 없다)
      숫자표는 models/user.py 의 ROLE_LEVEL, 한글 이름표는 ROLE_LABEL 이 갖는다.
      role_level(이름) 은 표에 없는 이름을 0 으로 돌려준다.

  ■ JWT(JSON Web Token) 와 flask_jwt_extended (설치 버전 4.6.0)
      로그인에 성공하면 auth_controller 가 create_access_token(identity=str(user.id)) 로 발급한다.
        · 토큰 안의 sub(주체) 칸에 회원 id 가 문자열로 들어간다  예) "3"
        · JWT_SECRET_KEY 로 서명 → 내용을 바꾸면 서명이 안 맞아 거절된다
        · JWT_ACCESS_TOKEN_EXPIRES = 2시간 (config.py) 뒤에 만료
      화면 JS 는 요청마다 헤더를 직접 붙인다  →  Authorization: Bearer <JWT 토큰>
      (헤더 이름과 앞말 Bearer 는 라이브러리 기본값. config.py 는 바꾸지 않는다)

  ■ verify_jwt_in_request(optional=True)
      "토큰이 있으면 검사하고, 없으면 그냥 넘어간다."
        · Authorization 헤더가 없거나 Bearer 형식이 아님   → 예외 없이 통과 (비로그인 취급)
        · 토큰이 있는데 만료·서명 불일치·모양이 깨짐       → 예외를 던진다
      (라이브러리 소스 flask_jwt_extended/view_decorators.py 로 확인)
      이 파일은 그 예외도 잡아서 None(비로그인)으로 바꾼다.

  ■ get_jwt_identity()
      검증을 통과한 토큰의 sub 값을 돌려준다. 토큰이 없었으면 None.

  ■ 데코레이터와 데코레이터 팩토리
      데코레이터 = 함수를 받아 '기능이 덧붙은 새 함수' 를 돌려주는 함수.
        @role_required('gold')
        def gold_posts(): ...
      는 아래 한 줄과 같은 뜻이다.
        gold_posts = role_required('gold')(gold_posts)
      괄호 안에 인자('gold')를 받으려고 한 겹이 더 있다 — 그래서 함수가 3겹이다.
        role_required(required)            인자를 받아 기억한다 (클로저)
          └ decorator(fn)                  감쌀 뷰 함수를 받는다
              └ wrapper(*args, **kwargs)   요청이 올 때마다 실제로 검사한다

  ■ functools.wraps
      wrapper 로 바꿔치기하면 함수 이름(__name__)이 'wrapper' 가 된다.
      Flask 는 함수 이름을 엔드포인트 이름으로 쓰기 때문에, 같은 블루프린트에서 이 데코레이터를
      두 라우트에 붙이면 둘 다 'wrapper' 가 되어 앱이 켜질 때 AssertionError
      ("View function mapping is overwriting an existing endpoint function") 가 난다.
      @wraps(fn) 은 원래 이름·docstring 을 wrapper 에 복사해 이를 막는다.

  ■ 다시 내보내기(re-export) 와 # noqa: F401
      이 파일은 ROLE_LEVEL·VALID_ROLES 를 직접 쓰지 않지만 import 해 둔다.
      admin_controller 가 from .rbac import VALID_ROLES 로 가져간다.
      # noqa: F401 은 린터(flake8)의 "import 해 놓고 안 쓴다(F401)" 경고를 그 줄에서만 끈다.

==============================================================================
3. 동작 원리 — @role_required('gold') 가 붙은 GET /api/gold/posts 한 번
==============================================================================
   브라우저 (templates/gold.html 의 JS)
     │  GET /api/gold/posts
     │  Authorization: Bearer <JWT 토큰>      ← localStorage 'token' 값을 JS 가 붙인다
     ▼
   app.py  before_request (_block_ip_guard)  — 차단된 IP 면 여기서 403
     ▼
   wrapper()  ← role_required('gold') 가 만든 검사 함수
     │  ① current_user()
     │       verify_jwt_in_request(optional=True)
     │         헤더 없음 / Bearer 형식 아님       → 통과(토큰 없음) → uid None → None
     │         만료 · 서명 불일치 · 깨진 토큰     → 예외 → except     → None
     │         정상                               → uid "3" → db.session.get(User, 3)
     │                                               (그 행이 없으면 None)
     │  ② user 가 None                                   → 401
     │  ③ role_level(user.role) < role_level('gold')    → 403
     │  ④ 통과 → request.current_user = user
     ▼
   gold_posts()  ← 원래 뷰 함수 실행 → 200

==============================================================================
4. 옵션 설명
==============================================================================
  ■ 이 파일의 함수
    이름                      인자                        돌려주는 것
    ────────────────────────  ──────────────────────────  ─────────────────────────────────────────
    current_user()            없음                        User 또는 None
    role_required(required)   'user' | 'gold' | 'admin'   데코레이터 (통과하면 원래 응답, 아니면 401/403)

  ■ role_required 인자별 결과
    required       비로그인   user   gold   admin
    ─────────────  ────────   ────   ────   ─────
    'user'         401        통과   통과   통과
    'gold'         401        403    통과   통과     ← gold_controller.py 가 쓰는 값
    'admin'        401        403    403    통과
    'glod' (오타)  401        통과   통과   통과     ← 표에 없는 이름은 0 → 모두 통과 (6절 ①)

  ■ 401 / 403 응답 JSON 필드
    msg             사람이 읽는 안내 문구
    required_role   필요 등급 이름(인자 그대로)       → 화면 _denied.html 의 "필요 등급" 칸
    current_role    내 등급 이름, 비로그인은 null     → "현재 등급" 칸

  ■ verify_jwt_in_request 옵션 (flask_jwt_extended 4.6.0) — 이 파일은 optional=True 만 쓴다
    옵션                    기본값   뜻
    ──────────────────────  ───────  ──────────────────────────────────────────────────────
    optional                False    True 면 토큰이 없어도 에러 없이 통과          ← 사용
    fresh                   False    True 면 fresh 로 표시된 토큰만 인정 (이 앱의 로그인 토큰은 fresh 아님)
    refresh                 False    True 면 refresh 토큰을 요구 (이 앱은 refresh 토큰을 발급하지 않는다)
    locations               None     토큰을 찾을 곳. None 이면 설정 JWT_TOKEN_LOCATION (기본 headers)
    verify_type             True     access / refresh 종류를 확인할지
    skip_revocation_check   False    True 면 토큰 폐기(블록리스트) 확인을 건너뜀

  ■ 관련 설정 (config.py + 라이브러리 기본값)
    JWT_SECRET_KEY             .env 값, 없으면 'dev-only-change-me'    서명 키
    JWT_ACCESS_TOKEN_EXPIRES   2시간 (config.py)                       만료
    JWT_TOKEN_LOCATION         headers (기본값)                        토큰 찾는 곳
    JWT_HEADER_NAME / TYPE     Authorization / Bearer (기본값)         헤더 모양
    JWT_IDENTITY_CLAIM         sub (기본값)                            get_jwt_identity 가 읽는 칸

  ■ 누가 이 파일을 쓰나
    controllers/gold_controller.py    @role_required('gold')   → GET /api/gold/posts
    controllers/auth_controller.py    current_user()           → GET /api/auth/me
    controllers/admin_controller.py   current_user()           → admin JWT 로 /api/admin/* 를 부를 때
                                      VALID_ROLES              → 부여할 수 있는 등급인지 검사

==============================================================================
5. 요청·응답 예시 (토큰은 자리표시자)
==============================================================================
    curl -H "Authorization: Bearer <JWT 토큰>" http://localhost:5000/api/gold/posts

  토큰 없음·만료·위조 → 401
    {"current_role": null, "msg": "로그인이 필요합니다.", "required_role": "gold"}
  일반 회원(user) → 403
    {"current_role": "user", "msg": "골드 등급 이상만 이용할 수 있습니다.", "required_role": "gold"}
  골드·관리자 → 200  (gold_posts 의 응답)

  · Flask 는 JSON 키를 알파벳 순으로 정렬하고, 한글은 유니코드 이스케이프 문자로 내보낸다
    (flask/json/provider.py 의 sort_keys · ensure_ascii = True). 위 예시는 읽기 쉽게 한글로 풀었다.
  · tests/test_rbac.py 가 이 규칙을 검사한다 — 비로그인 401 · user 403 · gold 200 · admin 200.

==============================================================================
6. 자주 걸리는 함정
==============================================================================
  ① role_required 의 인자 오타는 '막기'가 아니라 '모두 통과'가 된다.
     role_level() 은 모르는 이름을 0 으로 바꾼다. 내 등급이 이상한 값이면 0 이라 막히지만(안전),
     필요 등급이 오타면 role_level('glod') = 0 → 로그인한 누구나(user 1 ≥ 0) 통과한다.
     인자는 models/user.py ROLE_LEVEL 의 키('user'·'gold'·'admin')와 글자까지 같아야 한다.
  ② 데코레이터 순서: @xxx_bp.route(...) 가 위, @role_required(...) 가 아래.
     순서를 뒤집으면 route 가 '검사 없는 원래 함수' 를 주소에 등록해 버려 누구나 들어온다.
  ③ 잠긴 계정(is_locked)을 검사하지 않는다. 잠기기 전에 받은 토큰은 만료(최대 2시간)까지
     current_user() 를 통과한다 → /api/auth/me, /api/gold/posts, admin JWT 경로가 모두 열린다.
     잠금은 auth_controller 의 로그인(423)에서만, 즉 '새 토큰 발급' 만 막는다.
  ④ 만료·위조·형식 오류가 전부 같은 401 "로그인이 필요합니다." 로 보인다(except 가 원인을 삼킨다).
     "방금까지 되던 게 갑자기 401" 이면 토큰 만료(2시간)부터 의심한다.
  ⑤ 등급은 매 요청 DB 에서 다시 읽는다 — 회수·부여가 서버 판정에 바로 반영되는 대신
     요청마다 users 표 조회가 1번 일어난다. 두 번째 try 는 TypeError·ValueError 만 잡으므로
     DB 가 꺼져 있으면 401 이 아니라 500 이 난다.
"""
# ─────────────────────────────────────────────────────────────────────────────
# import
# ─────────────────────────────────────────────────────────────────────────────
# wraps : 데코레이터가 감싼 함수의 이름·docstring 을 새 함수에 복사해 준다 (아래 role_required)
from functools import wraps

# jsonify : dict → JSON 응답
# request : 지금 처리 중인 HTTP 요청 (헤더·본문. 요청 동안만 쓰는 속성을 붙여 둘 수도 있다)
from flask import jsonify, request
# get_jwt_identity      : 검증된 토큰의 sub(회원 id 문자열)를 꺼낸다
# verify_jwt_in_request : 요청 헤더에서 토큰을 찾아 서명·만료를 검사한다
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

# db : SQLAlchemy 인스턴스. app.py 가 아니라 extensions.py 에 있어 순환 import 가 생기지 않는다
from extensions import db
# User : users 표 모델
from models import User
# (아래 원본 주석에 덧붙임) 이 파일이 직접 쓰는 것은 ROLE_LABEL · role_level 둘뿐이다.
#   ROLE_LEVEL · VALID_ROLES 는 다시 내보내기용 — admin_controller 가 from .rbac import VALID_ROLES 로 가져간다.
#   줄 끝의 # noqa: F401 = "import 해 놓고 안 쓴다" 는 flake8 경고(F401)를 이 줄에서만 끈다.
# 등급 정의는 모델(models/user.py)이 갖는다 — 새 등급은 거기 한 곳에만 추가한다.
from models.user import ROLE_LABEL, ROLE_LEVEL, VALID_ROLES, role_level  # noqa: F401


# ═════════════════════════════════════════════════════════════════════════════
# current_user() — "지금 요청을 보낸 사람이 누구인가" 를 User 객체로 알아낸다
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 손목 팔찌(JWT)의 바코드를 찍어 회원 명부(users 표)에서 그 사람을 찾는 스캐너.
#       팔찌가 없거나, 가짜거나, 명부에 없는 사람이면 조용히 "모름(None)" 이라고만 답한다.
#
# 입력 : 없음 (지금 요청의 Authorization 헤더를 스스로 읽는다)
# 출력 : User 객체 또는 None
# 누가 호출하나:
#   · 이 파일 role_required() 안의 wrapper      → GET /api/gold/posts
#   · auth_controller.me()                       → GET /api/auth/me
#   · admin_controller._current_admin_user()     → /api/admin/* 의 'admin 로그인' 경로
# ═════════════════════════════════════════════════════════════════════════════
def current_user():
  """JWT 가 유효하면 그 User, 아니면 None. 토큰이 없거나 깨져도 예외를 내지 않는다."""
  try:
    # optional=True : 토큰이 '없으면' 에러 없이 넘어간다.
    #   토큰이 '있는데' 만료·서명 불일치 등으로 깨졌으면 예외를 던진다.
    verify_jwt_in_request(optional=True)
  except Exception:
    # 깨진 토큰 → 비로그인과 똑같이 취급 (어떤 이유로 깨졌는지는 구분하지 않는다)
    return None
  # 토큰 안의 sub 값. 로그인 때 identity=str(user.id) 로 넣었으므로 "3" 같은 문자열.
  # 토큰이 없었으면 None.
  uid = get_jwt_identity()
  if not uid:
    return None
  try:
    # 문자열 id → 정수로 바꿔 기본키로 한 줄 조회. 그 행이 없으면(탈퇴·DB 초기화 등) None.
    # 핵심: 등급(role)은 토큰이 아니라 '지금 DB' 에서 읽는다
    #   → 관리자가 등급을 바꾸면 옛 토큰으로 온 다음 요청부터 바로 반영된다.
    return db.session.get(User, int(uid))
  except (TypeError, ValueError):
    # int("abc") 처럼 숫자로 못 바꾸는 sub → None
    return None


# ═════════════════════════════════════════════════════════════════════════════
# role_required(required) — "required 등급 이상만 들어오세요" 문지기를 만들어 준다
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 놀이기구 입구에 "골드 이상 탑승" 표지판(required)을 세우고 직원(wrapper)을 둔다.
#       직원은 팔찌 스캐너(current_user)로 사람을 확인하고 등급 숫자를 비교한다.
#
# 입력 : required — 필요 등급 이름 문자열 'user' | 'gold' | 'admin'
# 출력 : 데코레이터 (뷰 함수를 받아 '검사가 붙은 함수' 로 바꿔 준다)
# 응답 : 미로그인 401 / 등급 부족 403 / 통과하면 원래 뷰 함수의 응답 그대로
# 누가 쓰나: controllers/gold_controller.py 의 @role_required('gold') (현재 유일한 사용처)
#
# 3겹 구조 (데코레이터 팩토리)
#   role_required('gold')                ← 1겹: 인자를 받아 기억한다 (클로저)
#     └ decorator(fn)                    ← 2겹: 감쌀 뷰 함수(gold_posts)를 받는다
#         └ wrapper(*args, **kwargs)     ← 3겹: 요청이 올 때마다 실행되는 검사 코드
# ═════════════════════════════════════════════════════════════════════════════
def role_required(required):
  """required 등급 이상만 통과. 미로그인 401, 등급 부족 403.

  403 응답에 required_role·current_role 을 함께 넘긴다 —
  화면이 "골드 등급이 필요합니다(현재: 일반)" 예외 화면을 그릴 때 쓴다.
  """
  # ── 2겹: decorator(fn) ── fn = 감쌀 뷰 함수 (예: gold_posts)
  def decorator(fn):
    # ── 3겹: wrapper ── 실제 요청마다 실행된다.
    # @wraps(fn) : wrapper 에 fn 의 이름(__name__)·docstring 을 복사한다.
    #   Flask 는 함수 이름을 엔드포인트 이름으로 쓰므로, 이게 없으면 이 데코레이터를 붙인 라우트가
    #   한 블루프린트에 둘 이상일 때 이름이 모두 'wrapper' 로 겹쳐 AssertionError 가 난다.
    # *args, **kwargs : URL 변수(예: <int:id>)가 있으면 그대로 받아 fn 에 넘기기 위함
    @wraps(fn)
    def wrapper(*args, **kwargs):
      # ① 누구인가? (토큰 → DB 의 User, 실패하면 None)
      user = current_user()
      # ② 모른다 → 인증 실패 401
      if user is None:
        return jsonify({
            'msg': '로그인이 필요합니다.',
            # 화면(_denied.html 의 showDenied)이 "필요 등급" 칸에 쓴다
            'required_role': required,
            # 비로그인이라 현재 등급이 없다 → JSON 에서는 null
            'current_role': None,
        }), 401
      # ③ 아는 사람인데 등급 숫자가 모자라다 → 인가 실패 403
      #   role_level : user 1, gold 2, admin 3, 표에 없는 값 0 (models/user.py)
      #   '<' 이므로 같은 등급이면 통과 → 계단식(같거나 높으면 통과)
      if role_level(user.role) < role_level(required):
        return jsonify({
            # ROLE_LABEL.get('gold', 'gold') → '골드'. 표에 없으면 영문 이름 그대로
            'msg': f'{ROLE_LABEL.get(required, required)} 등급 이상만 이용할 수 있습니다.',
            'required_role': required,
            # 화면이 "현재 등급" 칸에 쓴다
            'current_role': user.role,
        }), 403
      # ④ 통과. 찾아 둔 User 를 이번 요청(request)에 붙여 두면 뷰 함수가 DB 를 다시 뒤지지 않고 쓸 수 있다
      #   (현재 gold_posts 는 이 값을 쓰지 않는다)
      request.current_user = user
      # 원래 뷰 함수를 실행하고 그 응답을 그대로 돌려준다
      return fn(*args, **kwargs)
    # decorator 는 '검사가 붙은 함수(wrapper)' 를 돌려준다 → 이것이 gold_posts 자리를 차지한다
    return wrapper
  # role_required('gold') 는 decorator 를 돌려준다 → 파이썬이 곧바로 decorator(gold_posts) 를 부른다
  return decorator
