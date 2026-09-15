"""[주석·설명용 사본] controllers/auth_controller.py — 회원가입 / 로그인 / 내 정보

이 파일은 원본 controllers/auth_controller.py 를 복사해 주석만 덧붙인 학습용 사본이다.
  · 실행 코드는 원본과 똑같다(주석과 이 설명 문자열만 추가).
  · 원본을 고쳐도 이 사본에는 반영되지 않는다.
  · 앱은 원본을 쓴다(controllers/__init__.py 가 from .auth_controller import auth_bp).
    이 사본은 파일 이름에 공백·하이픈이 있어 import 할 수 없다.

==============================================================================
0. 한 줄 요약
==============================================================================
  원본 설명: "회원가입 / 로그인 / 내 정보."

  → 회원가입(비밀번호는 해시로만 저장), 로그인(비밀번호 확인 → JWT 발급,
    실패는 Graylog 로 신고, 잠긴 계정은 423 거부), 내 정보(토큰으로 누구인지·등급 확인)
    — API 3개를 담은 파일.

==============================================================================
1. 쉬운 비유 — 호텔 프런트
==============================================================================
  POST /api/auth/register   = 투숙객 등록 카드 작성. 비밀번호는 원문 대신 '지문(해시)' 만 보관
  POST /api/auth/login      = 신분 확인 뒤 객실 카드키(JWT) 발급 — 유효기간 2시간
  GET  /api/auth/me         = 카드키를 리더기에 대면 "몇 번 손님, 무슨 등급" 이 뜨는 화면
  failed_logins             = 비밀번호를 틀린 횟수 메모 (표시용)
  is_locked                 = 보안팀이 걸어 둔 '출입 정지' 표시 → 423
  send_gelf (Graylog 신고)  = 수상한 시도를 보안관제실에 무전
  n8n                       = 무전 기록을 보고 실제로 출입 정지(계정 잠금)를 거는 보안팀

  프런트(이 파일)는 틀린 시도를 '세고, 무전으로 알리기' 만 한다.
  몇 번 틀리면 잠글지는 관제실(Graylog)·보안팀(n8n) 쪽이 판단해 POST /api/admin/lock 으로 잠근다.
  잠긴 손님은 비밀번호가 맞아도 카드키를 받지 못한다.

==============================================================================
2. 기본 개념
==============================================================================
  ■ 비밀번호 해시 — werkzeug.security (설치 버전 Werkzeug 3.0.1)
      generate_password_hash(평문)
        → "scrypt:32768:8:1$<소금 16자>$<해시값>" 모양의 문자열 (기본 방식 scrypt)
        · 소금(salt)을 매번 무작위로 만들어 섞는다 → 같은 비밀번호도 저장값이 다르다
        · 해시는 되돌릴 수 없다 → DB 가 털려도 원문 비밀번호가 바로 드러나지 않는다
      check_password_hash(저장값, 입력값)
        → 저장값에서 방식·소금을 꺼내 입력값을 똑같이 해시한 뒤 비교(hmac.compare_digest)
      models/user.py 의 password 칸 주석: "해시만 저장(평문 금지)"

  ■ JWT 발급 — flask_jwt_extended.create_access_token (설치 버전 4.6.0)
      create_access_token(identity=str(user.id))
        · identity 가 토큰의 sub(주체) 칸에 들어간다  예) "3"
        · 문자열로 바꾸는 이유: 설치된 PyJWT 2.13 은 토큰을 검증할 때 sub 가 문자열이 아니면
          InvalidSubjectError 로 거절한다 (jwt/api_jwt.py 의 _validate_sub)
        · 서명 키 JWT_SECRET_KEY, 만료 JWT_ACCESS_TOKEN_EXPIRES = 2시간 (config.py)
        · 토큰에는 등급(role)이 들어가지 않는다 → 등급은 요청 때마다 DB 에서 읽는다(rbac.py)

  ■ 토큰은 어디에 두나 — localStorage
      화면 JS(index.html·admin.html)가 로그인 응답의 access_token·username 을
      localStorage 'token'·'username' 에 저장한다. 쿠키가 아니라서 요청에 자동으로 실리지 않는다.
      → API 를 부를 때 JS 가 헤더를 직접 붙인다   Authorization: Bearer <JWT 토큰>
      → 페이지를 열 때 서버는 누구인지 모른다 → 그래서 GET /api/auth/me 가 필요하다 (me 의 docstring)

  ■ 이 파일이 쓰는 응답 코드
      201 Created    가입 성공 (새 자원이 생김)
      200 OK         로그인 성공 / 내 정보
      400            요청 값이 잘못됨 (필수값 누락, 이미 있는 아이디)
      401            누구인지 확인 실패 (비밀번호 틀림, 토큰 없음·만료)
      423 Locked     원래 WebDAV 규격의 "자원이 잠겨 있음" 코드 — 여기서는 '계정 잠김' 뜻으로 빌려 쓴다

  ■ 계정 잠금과 브루트포스(무차별 대입) 대응
      브루트포스 = 비밀번호를 수없이 바꿔 가며 계속 로그인해 보는 공격.
      역할 분담
        이 파일        실패마다 failed_logins +1, Graylog 로 GELF 신고
        Graylog·n8n    신고를 모아 임계치를 넘으면 POST /api/admin/lock 호출 (models/user.py 주석)
        이 파일        is_locked 인 계정은 비밀번호 검사 전에 423 으로 거부

  ■ GELF 신고 — controllers/gelf.py 의 send_gelf(short_message, rule, **fields)
      Graylog 로 JSON 한 줄을 UDP 로 던진다 (host 는 'board', level 은 4 고정).
      키워드 인자는 이름 앞에 '_' 가 붙어 필드가 된다   username='kim' → _username
      전송이 실패해도 예외를 올리지 않는다 → Graylog 가 꺼져 있어도 로그인은 동작한다.

  ■ request.get_json(silent=True) or {}
      Content-Type 이 JSON 이 아니거나 본문이 깨져 있어도 에러 대신 None → or {} 로 빈 dict.
      덕분에 바로 data.get(...) 을 부를 수 있다.

  ■ X-Forwarded-For 와 remote_addr
      remote_addr       서버에 실제로 연결을 맺은 상대 IP (프록시 뒤라면 프록시 IP)
      X-Forwarded-For   프록시가 "원래 손님 IP 는 이것" 이라고 적어 주는 헤더 — 누구나 위조해 보낼 수 있다

==============================================================================
3. 동작 원리
==============================================================================
  (A) 회원가입  POST /api/auth/register
     body JSON 읽기
       → username · password 중 하나라도 비었나?     예 → 400
       → 같은 username 이 이미 있나?                  예 → 400
       → User(username, password=해시) 저장   (role 은 모델 기본값 'user')
       → 201 {"msg": "회원가입 성공"}

  (B) 로그인  POST /api/auth/login
     body JSON 읽기 → username 앞뒤 공백 제거 → users 표 조회 → src_ip 정하기
       ① 계정이 있고 is_locked           → GELF 신고(_locked '1')             → 423
       ② 계정 없음 또는 비밀번호 틀림    → 계정이 있으면 failed_logins +1
                                           → GELF 신고(_count 1)                → 401
       ③ 성공                             → failed_logins 가 0 이 아니면 0 으로
                                           → create_access_token
                                           → 200 {access_token, username, role, role_label}
     화면: index.html · admin.html 이 access_token · username 을 localStorage 에 저장
     그 뒤: Graylog 가 실패 신고를 모아 판단 → n8n → POST /api/admin/lock → 다음 로그인부터 ①

  (C) 내 정보  GET /api/auth/me
     Authorization: Bearer <JWT 토큰>
       → rbac.current_user()   토큰 없음·만료·위조·없는 회원 → None → 401
       → 200 {id, username, role, role_label, is_gold, is_admin}
     화면: gold.html 의 checkGrade() 가 is_gold 로 골드 화면 / 예외 화면을 고른다

==============================================================================
4. 옵션 설명
==============================================================================
  ■ 엔드포인트 (url_prefix = /api/auth)
    메서드  URL                  인증                               body(JSON) 필드             응답 코드
    ──────  ───────────────────  ─────────────────────────────────  ──────────────────────────  ───────────────
    POST    /api/auth/register   없음                               username, password (필수)   201 / 400
    POST    /api/auth/login      없음                               username, password          200 / 401 / 423
    GET     /api/auth/me         Authorization: Bearer <JWT 토큰>   없음                        200 / 401
    · 공통: 차단된 IP 는 여기 오기 전에 app.py 가 403
    · 로그인은 400 을 내지 않는다 — body 가 비어도 "없는 아이디" 로 처리되어 401

  ■ 응답 필드
    register 201   msg
    register 400   msg  ("username, password 는 필수입니다." / "이미 존재하는 사용자입니다.")
    login 200      access_token, username, role, role_label
    login 401      msg  ("아이디 또는 비밀번호가 잘못되었습니다.")
    login 423      msg, locked (true)
    me 200         id, username, role, role_label, is_gold, is_admin
    me 401         msg  ("로그인이 필요합니다.")
      role_label   models/user.py ROLE_LABEL 로 바꾼 한글 이름 (user 일반 / gold 골드 / admin 관리자)
      is_gold      gold 이상이면 true — admin 도 true (계단식)
      is_admin     role 이 정확히 admin 일 때만 true

  ■ 로그인이 보내는 GELF 신고 (_rule = login-bruteforce, level 4, host board)
    상황             short_message                                  추가 필드
    ───────────────  ─────────────────────────────────────────────  ──────────────────────────────────────────
    잠긴 계정 시도   login attempt on LOCKED account '<아이디>'      _username, _src_ip, _locked = '1'
    로그인 실패      failed login for '<아이디>' from <IP>          _username (비었으면 '(unknown)'), _src_ip, _count = 1

  ■ 함수 옵션
    request.get_json(silent=True)
        silent=True  →  JSON 형식이 아니거나 깨져도 에러 대신 None
    generate_password_hash(password, method='scrypt', salt_length=16)
        이 파일은 기본값 그대로 쓴다
    create_access_token(identity, fresh=False, expires_delta=None, additional_claims=None, additional_headers=None)
        identity 만 넘긴다 → 만료는 config 의 2시간, 추가 클레임(role 같은 것) 없음
    request.headers.get('X-Forwarded-For', request.remote_addr)
        헤더가 있으면 그 값, 없을 때만 remote_addr

  ■ 사용하는 설정 (config.py, 실제 값은 .env)
    JWT_SECRET_KEY             토큰 서명 키. .env 에 없으면 'dev-only-change-me'
    JWT_ACCESS_TOKEN_EXPIRES   timedelta(hours=2)
    GELF_HOST / GELF_PORT      Graylog 주소. 기본 localhost / 12201 (gelf.py 가 읽는다)

==============================================================================
5. 요청·응답 예시 (Git Bash 기준, 값은 가짜)
==============================================================================
  회원가입
    curl -X POST http://localhost:5000/api/auth/register -H "Content-Type: application/json" -d '{"username": "kim", "password": "<비밀번호>"}'
    → 201 {"msg": "회원가입 성공"}

  로그인
    curl -X POST http://localhost:5000/api/auth/login -H "Content-Type: application/json" -d '{"username": "kim", "password": "<비밀번호>"}'
    → 200 {"access_token": "<JWT 토큰>", "role": "user", "role_label": "일반", "username": "kim"}
    → 401 {"msg": "아이디 또는 비밀번호가 잘못되었습니다."}
    → 423 {"locked": true, "msg": "계정이 잠겨 있습니다. 관리자에게 문의하세요."}

  내 정보
    curl -H "Authorization: Bearer <JWT 토큰>" http://localhost:5000/api/auth/me
    → 200 {"id": 3, "is_admin": false, "is_gold": false, "role": "user", "role_label": "일반", "username": "kim"}
    → 401 {"msg": "로그인이 필요합니다."}

  · Flask 는 JSON 키를 알파벳 순으로 정렬하고 한글을 유니코드 이스케이프 문자로 내보낸다
    (sort_keys · ensure_ascii = True). 위 예시는 읽기 쉽게 한글로 풀었다.
  · tests/test_rbac.py 가 확인하는 것: 로그인 응답의 role 기본값 'user',
    /api/auth/me 미로그인 401, 로그인하면 username · role 반환.

==============================================================================
6. 자주 걸리는 함정
==============================================================================
  ① src_ip 의 주석과 코드가 반대다. 주석은 "X-Forwarded-For 는 위조될 수 있어 remote_addr 를 쓴다" 인데,
     코드는 X-Forwarded-For 헤더가 '있으면 그 값을 먼저' 쓴다(없을 때만 remote_addr).
     공격자가 헤더에 가짜 IP 를 넣으면 Graylog 신고의 _src_ip 가 그 값이 된다 → 이 값을 믿고 IP 를
     차단하면 엉뚱한 IP 를 막고 공격자는 놓칠 수 있다. 쉼표로 여러 IP 가 오면 문자열 통째로 기록된다
     (app.py 의 _client_ip 는 첫 번째만 잘라 쓴다 — 두 곳의 기준도 다르다).
  ② 잠금은 '새 로그인'만 막는다. 잠기기 전에 받은 토큰은 만료(2시간)까지 /api/auth/me,
     게시글 쓰기(@jwt_required), 골드 API, admin JWT 경로에서 그대로 통한다
     (어디서도 is_locked 를 다시 보지 않는다).
  ③ 이 파일은 실패를 세기만 하고 잠그지 않는다. 앱 자체에는 횟수 제한·지연이 없어서
     Graylog·n8n 이 꺼져 있으면 비밀번호를 끝없이 대입해 볼 수 있다.
  ④ 아이디가 있는지 드러나는 곳이 있다. 로그인 실패 문구는 "아이디 또는 비밀번호" 로 합쳐 두었지만,
     잠긴 계정은 비밀번호와 무관하게 423 이 오고(없는 아이디는 401),
     가입할 때 "이미 존재하는 사용자입니다." 로도 알 수 있다.
  ⑤ 가입은 username 앞뒤 공백을 떼지 않고, 로그인은 뗀다(strip).
     " kim" 처럼 공백을 붙여 가입하면 그 계정으로는 로그인할 수 없다.
  ⑥ password 가 문자열이 아니면(숫자 1234, null) 500 이 난다. werkzeug 가 내부에서 password.encode() 를 부르기 때문.
     가입은 {"password": 1234} 에서, 로그인은 '있는 아이디' 에 숫자·null 비밀번호를 보낼 때 난다.
  ⑦ .env 에 JWT_SECRET_KEY 가 없으면 코드에 적힌 'dev-only-change-me' 로 서명한다 →
     이 글자를 아는 누구나 아무 회원 id 로 토큰을 만들어 로그인 없이 들어올 수 있다.
  ⑧ index.html 은 토큰이 유효한지 확인하지 않고, localStorage 에 값만 있으면 "안녕하세요" 로 그린다.
     2시간이 지나면 화면은 로그인 상태인데 글쓰기는 "처리에 실패했습니다." → 로그아웃 후 다시 로그인.
  ⑨ 같은 아이디로 거의 동시에 가입하면 둘 다 중복 검사를 통과할 수 있다.
     두 번째 저장은 DB 의 unique 제약에 걸리는데 예외 처리가 없어 500 이 난다.
"""
# ─────────────────────────────────────────────────────────────────────────────
# import
# ─────────────────────────────────────────────────────────────────────────────
# Blueprint : 주소 묶음 부품 / jsonify : dict → JSON 응답 / request : 지금 들어온 요청(본문·헤더·IP)
from flask import Blueprint, jsonify, request
# create_access_token : 로그인 성공 시 JWT(access 토큰) 문자열을 만든다
from flask_jwt_extended import create_access_token
# check_password_hash    : 저장된 해시와 입력 비밀번호가 맞는지 비교
# generate_password_hash : 평문 비밀번호 → 해시 문자열 (기본 scrypt, 소금 16자)
from werkzeug.security import check_password_hash, generate_password_hash

# db : SQLAlchemy 인스턴스 (session.add / session.commit 에 쓴다)
from extensions import db
# User : users 표 모델
from models import User
# ROLE_LABEL : {'user': '일반', 'gold': '골드', 'admin': '관리자'} — 응답에 한글 등급 이름을 담을 때
from models.user import ROLE_LABEL

# send_gelf : Graylog 로 보안 로그(GELF)를 UDP 로 보낸다. 실패해도 예외를 올리지 않는다
from .gelf import send_gelf
# current_user : 요청의 JWT → User 또는 None (등급 판정 규칙과 같은 곳, rbac.py)
from .rbac import current_user

# ═════════════════════════════════════════════════════════════════════════════
# auth_bp — 이 파일의 블루프린트
# ─────────────────────────────────────────────────────────────────────────────
# 이름 'auth', 주소 앞머리 /api/auth  →  /api/auth/register, /api/auth/login, /api/auth/me
# 누가 등록하나: controllers/__init__.py 의 all_blueprints → app.py 의 register_blueprint
# ═════════════════════════════════════════════════════════════════════════════
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


# ═════════════════════════════════════════════════════════════════════════════
# register() — POST /api/auth/register : 회원가입
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 호텔 투숙객 등록 카드. 비밀번호는 원문 대신 지문(해시)만 서랍(DB)에 넣는다.
#
# 입력 : body JSON {"username": "...", "password": "..."}  (둘 다 필수)
# 출력 : 201 {"msg": "회원가입 성공"}
#        400 필수값 누락 / 이미 있는 username
# 누가 호출하나: templates/index.html 의 submitAuth() (회원가입 모드),
#               tests/test_rbac.py 의 register() 도우미
# role 을 입력으로 받지 않는다 → 가입만으로 gold·admin 이 될 수 없다 (항상 모델 기본값 'user')
# ═════════════════════════════════════════════════════════════════════════════
@auth_bp.route('/register', methods=['POST'])
def register():
  # JSON 본문 → dict. JSON 이 아니거나 깨져 있으면 None → or {} 로 빈 dict (그러면 아래에서 400)
  data = request.get_json(silent=True) or {}
  # 없음 · 빈 문자열 · null 은 모두 거짓 → 400
  if not data.get('username') or not data.get('password'):
    return jsonify({'msg': 'username, password 는 필수입니다.'}), 400
  # 같은 username 이 있는지 먼저 확인 (.first() : 없으면 None)
  #   주의: 로그인과 달리 여기서는 앞뒤 공백을 떼지 않는다 (6절 ⑤)
  if User.query.filter_by(username=data['username']).first():
    return jsonify({'msg': '이미 존재하는 사용자입니다.'}), 400

  # 비밀번호는 해시로 바꿔서 저장한다. 결과 모양: "scrypt:32768:8:1$<소금>$<해시값>"
  #   role · is_locked · failed_logins 는 적지 않았으므로 모델 기본값(user / False / 0)이 들어간다
  user = User(username=data['username'],
              password=generate_password_hash(data['password']))
  # add = 저장 예약,  commit = 실제로 DB 에 반영 (INSERT INTO users ...)
  db.session.add(user)
  db.session.commit()
  # 201 Created. 토큰은 주지 않는다 → 화면(index.html)은 "회원가입 완료! 로그인해주세요." 후 로그인 창을 연다
  return jsonify({'msg': '회원가입 성공'}), 201


# ═════════════════════════════════════════════════════════════════════════════
# login() — POST /api/auth/login : 로그인 (잠금 확인 → 비밀번호 확인 → 토큰 발급)
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 호텔 프런트. 출입 정지 표시(is_locked)부터 보고, 신분(비밀번호)을 확인한 뒤
#       카드키(JWT)를 준다. 틀린 시도는 메모(failed_logins)하고 관제실(Graylog)에 무전한다.
#
# 입력 : body JSON {"username": "...", "password": "..."}
# 출력 : 200 {"access_token": "<JWT 토큰>", "username", "role", "role_label"}
#        401 아이디 없음 또는 비밀번호 틀림 (두 경우 문구가 같다 — 어느 쪽이 틀렸는지 숨긴다)
#        423 잠긴 계정 (비밀번호가 맞아도)
# 누가 호출하나: templates/index.html 의 submitAuth(), templates/admin.html 의 login(),
#               tests/test_rbac.py 의 login() 도우미
# 판정 순서가 중요하다: ① 잠김 → ② 실패 → ③ 성공
# ═════════════════════════════════════════════════════════════════════════════
@auth_bp.route('/login', methods=['POST'])
def login():
  data = request.get_json(silent=True) or {}
  # 값이 없거나 null 이면 '' 로 바꾼 뒤 앞뒤 공백 제거 → " kim " 도 "kim" 으로 찾는다
  username = (data.get('username') or '').strip()
  # 없으면 None. (username 이 '' 이어도 조회는 하고 None 이 나온다)
  user = User.query.filter_by(username=username).first()
  # (아래 원본 주석에 덧붙임) 신고에 남길 접속 IP.
  #   headers.get('X-Forwarded-For', 기본값) 은 헤더가 '있으면 그 값', 없을 때만 remote_addr 을 준다.
  #   → 원본 주석의 의도(remote_addr 사용)와 실제 동작이 반대다 (6절 ①).
  #   끝의 or '0.0.0.0' : 둘 다 비어 있을 때 쓰는 대체값
  # 공격자가 X-Forwarded-For 를 위조할 수 있으니 실습에선 remote_addr 를 쓴다.
  src_ip = request.headers.get('X-Forwarded-For', request.remote_addr) or '0.0.0.0'

  # ① 이미 잠긴 계정은 비번이 맞아도 거부(423 Locked)
  #   (덧붙임) 계정이 있을 때만 검사한다 — 없는 아이디는 ② 로 간다.
  #   비밀번호를 확인하기 '전에' 막으므로 잠긴 동안은 맞는 비밀번호로도 토큰을 못 받는다.
  #   이 경로에서는 failed_logins 를 늘리지 않는다.
  if user and user.is_locked:
    # 잠긴 계정에 대한 시도도 신고 → _rule=login-bruteforce, _username, _src_ip, _locked='1'
    send_gelf(f"login attempt on LOCKED account '{username}'",
              rule='login-bruteforce', username=username, src_ip=src_ip, locked='1')
    # locked: true 는 프로그램이 읽기 좋은 표시. 현재 화면들(index.html·admin.html)은 msg 만 띄운다
    return jsonify({'msg': '계정이 잠겨 있습니다. 관리자에게 문의하세요.',
                    'locked': True}), 423

  # ② 인증 실패 → Graylog 로 신고 + 실패 카운트(표시용) 증가
  #   (덧붙임) 조건 = 아이디가 없거나(not user) 비밀번호 해시가 안 맞음.
  #   or 는 앞이 참이면 뒤를 보지 않는다 → 없는 아이디면 check_password_hash 를 부르지 않는다.
  #   data.get('password', '') : 키가 없으면 '' (숫자·null 이 오면 werkzeug 안에서 500 — 6절 ⑥)
  if not user or not check_password_hash(user.password, data.get('password', '')):
    # 있는 아이디일 때만 실패 횟수 +1 후 바로 저장. (or 0) 은 값이 None 이어도 더할 수 있게 하는 안전장치.
    # 이 숫자로 잠그지는 않는다 — 잠금은 n8n 이 POST /api/admin/lock 으로 한다
    if user:
      user.failed_logins = (user.failed_logins or 0) + 1
      db.session.commit()
    # 실패 1건 = GELF 1줄. 모아서 세고 탐지·대응하는 일은 Graylog + n8n 이 맡는다 (gelf.py 설명)
    #   아이디가 비어 있으면 _username 은 '(unknown)'
    #   _count=1 : 숫자 필드 — Graylog 에서 합계 조건을 걸기 좋다
    send_gelf(f"failed login for '{username}' from {src_ip}",
              rule='login-bruteforce', username=username or '(unknown)',
              src_ip=src_ip, count=1)
    # 아이디 없음 / 비밀번호 틀림을 같은 문구로 → 어느 쪽이 틀렸는지 알려 주지 않는다
    return jsonify({'msg': '아이디 또는 비밀번호가 잘못되었습니다.'}), 401

  # ③ 성공 → 실패 카운트 초기화 + 토큰 발급
  #   (덧붙임) 0 이면 바꿀 게 없으니 commit 을 건너뛴다
  if user.failed_logins:
    user.failed_logins = 0
    db.session.commit()
  # identity → 토큰의 sub 칸. 숫자 id 를 str 로 바꿔 넣는다 (PyJWT 2.13 은 검증할 때 문자열 sub 만 받는다).
  #   꺼낼 때는 rbac.current_user() 가 int(uid) 로 되돌린다.
  #   만료는 config.py 의 JWT_ACCESS_TOKEN_EXPIRES(2시간). 토큰 안에 role 은 넣지 않는다.
  token = create_access_token(identity=str(user.id))
  # role 을 함께 내려주면 화면이 곧바로 등급에 맞는 메뉴를 그릴 수 있다.
  #   (덧붙임) jsonify(키=값, ...) 처럼 키워드로 넘겨도 dict 를 넘긴 것과 같은 JSON 이 된다.
  #   index.html · admin.html 은 access_token · username 만 localStorage 'token' · 'username' 에 저장한다
  #   (role · role_label 은 현재 화면들이 저장하지 않는다 — gold.html 은 매번 /api/auth/me 로 묻는다)
  return jsonify(access_token=token, username=user.username,
                 role=user.role, role_label=ROLE_LABEL.get(user.role, user.role))


# ═════════════════════════════════════════════════════════════════════════════
# me() — GET /api/auth/me : 지금 토큰의 주인이 누구이고 어떤 등급인지
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 카드키를 리더기에 대면 "3번 손님 kim, 일반 등급" 이 뜨는 화면.
#
# 입력 : 헤더 Authorization: Bearer <JWT 토큰>  (body 없음)
# 출력 : 200 {id, username, role, role_label, is_gold, is_admin}
#        401 {"msg": "로그인이 필요합니다."}  ← 토큰 없음·만료·위조·없는 회원 모두 같은 응답
# 누가 호출하나: templates/gold.html 의 checkGrade() — is_gold 로 골드 화면 / 예외 화면 결정
#               tests/test_rbac.py 의 test_me_requires_login, test_me_returns_username_and_role
# @role_required 를 쓰지 않고 current_user() 를 직접 부른다 — 등급 제한 없이 '로그인했는지' 만 보면 되고,
#   401 응답에도 required_role 같은 필드가 필요 없기 때문이다.
# ═════════════════════════════════════════════════════════════════════════════
@auth_bp.route('/me', methods=['GET'])
def me():
  """지금 로그인한 사람이 누구이고 어떤 등급인지 — 화면의 등급 확인용.

  토큰은 localStorage 에 있어서 페이지를 열 때 서버로 자동 전송되지 않는다.
  그래서 화면 JS 가 이 API 를 불러 등급을 확인하고 예외 화면 여부를 정한다."""
  # rbac.current_user() : 토큰 검증 + DB 에서 User 조회. 실패하면 예외 대신 None
  #   등급(role)은 토큰이 아니라 지금 DB 값 → 관리자가 방금 바꾼 등급이 바로 보인다
  #   주의: is_locked 는 보지 않는다 → 잠긴 계정도 잠기기 전에 받은 토큰이면 200 (6절 ②)
  user = current_user()
  if user is None:
    return jsonify({'msg': '로그인이 필요합니다.'}), 401
  return jsonify({
      # users.id (정수)
      'id': user.id,
      'username': user.username,
      # 'user' | 'gold' | 'admin'
      'role': user.role,
      # 한글 이름. 표에 없는 값이면 영문 그대로 (dict.get 의 두 번째 인자 = 기본값)
      'role_label': ROLE_LABEL.get(user.role, user.role),
      # gold 이상이면 True — admin 도 True (User.is_gold → has_role('gold'), 계단식)
      'is_gold': user.is_gold,
      # role 이 정확히 'admin' 일 때만 True
      'is_admin': user.is_admin,
  })
