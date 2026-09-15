"""[주석·설명용 사본] controllers/__init__.py — 컨트롤러(블루프린트) 묶음

이 파일은 원본 controllers/__init__.py 를 복사해 주석만 덧붙인 학습용 사본이다.
  · 실행 코드는 원본과 똑같다(주석과 이 설명 문자열만 추가).
  · 원본을 고쳐도 이 사본에는 반영되지 않는다.
  · 앱(app.py)의 from controllers import all_blueprints 는 원본 __init__.py 를 실행한다.
    이 사본은 파일 이름에 공백·하이픈이 있어 import 할 수 없고, 상대 import(from .xxx)
    때문에 직접 실행해도 에러가 난다 — 읽기 전용 교재다.

==============================================================================
0. 한 줄 요약
==============================================================================
  원본 설명: "컨트롤러(블루프린트) 묶음. app.py 가 이 목록을 한 번에 등록한다."

  → controllers 폴더의 블루프린트 7개를 all_blueprints 튜플 하나로 모아 두면,
    app.py 는 for 문 한 번으로 전부 등록한다. 새 기능을 붙일 때 app.py 를 고치지 않는다.

==============================================================================
1. 쉬운 비유 — 쇼핑몰 1층 안내판
==============================================================================
  Flask 앱(app)               = 쇼핑몰 건물
  블루프린트(Blueprint)       = 입점 매장 하나 (매장마다 맡은 주소 구역이 있다)
  url_prefix                  = 매장이 차지한 층·구역  (/api/auth, /api/posts ...)
  controllers/__init__.py     = 1층 안내판 (어떤 매장이 입점했는지 한 장에 적어 둠)
  all_blueprints              = 안내판에 적힌 매장 목록
  app.register_blueprint(bp)  = 매장을 건물에 실제로 입점시키는 계약

  관리사무소(app.py)는 매장 파일을 하나하나 찾아다니지 않는다.
  안내판(all_blueprints)만 보고 앞에서부터 차례로 입점 계약(register_blueprint)을 맺는다.
  새 매장을 열 때는 매장 파일을 만들고 이 안내판에 이름만 올리면 된다.
  안내판에 안 올린 매장은 건물 안에 있어도 손님이 찾아갈 수 없다(주소가 404).

==============================================================================
2. 기본 개념
==============================================================================
  ■ 패키지와 __init__.py
      controllers 폴더 안의 __init__.py 는 "controllers 패키지를 import 할 때 맨 먼저
      실행되는 파일"이다. 여기서 만든 이름(all_blueprints, auth_bp ...)이
      곧 controllers 패키지의 이름이 된다.
        app.py :  from controllers import all_blueprints
                  → 이 파일이 한 번 실행되고 → all_blueprints 를 꺼내 간다.

  ■ 상대 import — from .auth_controller import auth_bp
      점(.) 하나 = "이 파일과 같은 패키지(controllers) 안에서 찾아라".
      controllers/auth_controller.py 안의 auth_bp 변수를 가져온다.

  ■ 블루프린트(Blueprint)
      주소(URL)와 함수를 기능별로 묶어 두는 Flask 의 조립 부품.
      각 컨트롤러 파일이 Blueprint 를 하나씩 만든다.
        auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')
          'auth'       블루프린트 이름
          __name__     이 모듈 이름
          url_prefix   주소 앞머리 (이 블루프린트의 모든 주소 앞에 붙는다)
      만들기만 해서는 주소가 열리지 않는다. 앱에 register_blueprint 해야 열린다.

  ■ import 의 부수효과 — 모델·도우미 모듈이 함께 올라온다
      컨트롤러들이 from models import ... 를 하므로 이 파일을 import 하면
      models 패키지(User·Post·SecurityEvent·BlockedIP·Incident)도 같이 import 된다.
      app.py 의 create_app() 이 db.create_all() 을 부를 때 모든 표가 만들어지는 이유다
      (app.py 주석: "models 를 import 한 뒤여야 한다 — controllers 가 이미 import 함").
      rbac.py(등급 판정)·gelf.py(Graylog 신고)는 블루프린트가 아니라 도우미 모듈이라
      목록에 없다. auth·admin·gold 컨트롤러가 필요할 때 import 한다.

  ■ 튜플 ( , )
      all_blueprints 는 리스트가 아니라 튜플 — 실행 중에 실수로 추가·삭제되지 않는 목록.

  ■ __all__
      from controllers import * 를 했을 때 딸려 갈 이름 목록.
      app.py 처럼 이름을 콕 집어 import 하는 경우에는 영향이 없다.

==============================================================================
3. 동작 원리 — 앱이 켜질 때
==============================================================================
   python app.py
     │  from controllers import all_blueprints
     ▼
   controllers/__init__.py 실행 (이 파일)
     │  ① 컨트롤러 모듈 7개 import → 모듈마다 Blueprint 객체가 만들어진다
     │     (그 과정에서 extensions · models · rbac · gelf 도 import 된다)
     │  ② all_blueprints 튜플에 7개를 담는다
     ▼
   app.py  create_app()
     │  db.init_app(app) / jwt.init_app(app)
     │  for bp in all_blueprints:  app.register_blueprint(bp)   ← 여기서 주소가 열린다
     │  db.create_all() → _ensure_schema()
     ▼
   http://localhost:5000 에서 요청을 받기 시작

==============================================================================
4. 옵션 설명 — 등록되는 블루프린트 7개 (all_blueprints 순서대로)
==============================================================================
  변수          Blueprint 이름  파일                     url_prefix      맡은 일
  ───────────   ──────────────  ───────────────────────  ──────────────  ──────────────────────────────────
  page_bp       'page'          page_controller.py       (없음)          화면(HTML) 주소 /, /gold, /admin ...
  auth_bp       'auth'          auth_controller.py       /api/auth       회원가입·로그인·내 정보
  post_bp       'post'          post_controller.py       /api/posts      게시글 목록·작성·수정·삭제
  security_bp   'security'      security_controller.py   /api/security   보안 이벤트 저장·조회(n8n)
  public_bp     'public'        public_controller.py     /api/public     공공데이터(부산 테마여행) 프록시
  admin_bp      'admin'         admin_controller.py      /api/admin      권한 부여·회수, 잠금, IP 차단, 인시던트
  gold_bp       'gold'          gold_controller.py       /api/gold       골드 등급 전용 게시글

  · import 줄은 파일 이름 알파벳순, all_blueprints 는 화면 → 기능 순으로 적혀 있다.
    주소 앞머리가 서로 겹치지 않으므로 등록 순서는 동작에 영향이 없다.
  · Blueprint 이름('auth' 등)은 엔드포인트 이름 앞에 붙는다  → 'auth.login', 'gold.gold_posts'
    한 앱 안에서 다른 블루프린트와 이름이 겹치면 등록할 때 ValueError 가 난다(Flask 3.0 소스 확인).

==============================================================================
5. 예시 — 새 블루프린트를 붙이는 순서 (가상의 silver 기능)
==============================================================================
  1) controllers/silver_controller.py 를 만든다
        silver_bp = Blueprint('silver', __name__, url_prefix='/api/silver')
  2) 이 파일에 import 한 줄 추가
        from .silver_controller import silver_bp
  3) all_blueprints 튜플에 silver_bp 추가  (__all__ 에도 적어 두면 목록이 맞는다)
  → app.py 는 고칠 필요가 없다. 앱을 다시 켜면 /api/silver/... 주소가 열린다.

==============================================================================
6. 자주 걸리는 함정
==============================================================================
  ① 컨트롤러 파일을 만들고 import 까지 했어도 all_blueprints 에 빠뜨리면 그 주소는 404.
     에러 메시지도 없다. 반대로 __all__ 에만 넣는 것은 등록과 아무 관계가 없다.
  ② 이 파일이 컨트롤러 7개를 한꺼번에 import 하므로 하나만 고장 나도 앱 전체가 안 켜진다.
     예) public_controller.py 는 requests 패키지를 쓴다 → 설치돼 있지 않으면
         게시판·로그인까지 모두 ModuleNotFoundError 로 멈춘다.
  ③ 컨트롤러 안에서 from app import ... 를 하면 app.py → controllers → app.py 로
     고리가 생긴다(순환 import). 그래서 db·jwt 는 app.py 가 아니라 extensions.py 에 둔다
     (extensions.py 설명 참고).
  ④ Blueprint 이름이 겹치면 앱이 켜질 때 ValueError. 기존 컨트롤러를 복사해 새 파일을 만들 때
     Blueprint('gold', ...) 의 첫 인자를 바꾸는 것을 잊기 쉽다.
  ⑤ 이런 "... copy-주석설명용.py" 사본 파일은 어디서도 import 되지 않는다.
     사본을 고쳐도 앱 동작은 그대로다 — 코드를 바꾸려면 원본을 고친다.
"""
# ═════════════════════════════════════════════════════════════════════════════
# 컨트롤러 모듈 import — 모듈마다 만들어 둔 Blueprint 변수 하나씩을 가져온다
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 매장(컨트롤러 파일)마다 찾아가 간판(Blueprint 객체)을 받아 오는 일.
# 점(.) = 같은 controllers 패키지 안.
# import 하는 순간 그 파일 전체가 한 번 실행되어 Blueprint 가 만들어지고,
# 파일 안의 @xxx_bp.route(...) 주소들이 그 블루프린트에 기록된다(앱에 열리는 건 등록 뒤).
# 누가 이 파일을 부르나: app.py 의 from controllers import all_blueprints
# ═════════════════════════════════════════════════════════════════════════════
# /api/admin    — 권한 부여·회수, 계정 잠금, IP 차단, 인시던트 (X-API-Key 또는 admin JWT)
from .admin_controller import admin_bp
# /api/auth     — 회원가입·로그인·내 정보
from .auth_controller import auth_bp
# /api/gold     — 골드 등급 이상 전용 게시글
from .gold_controller import gold_bp
# (앞머리 없음) — 화면 HTML 주소 /, /dashboard, /gold, /admin, /public-posts ...
from .page_controller import page_bp
# /api/posts    — 게시글 CRUD (쓰기·수정·삭제는 JWT 필요)
from .post_controller import post_bp
# /api/public   — 공공데이터(부산 테마여행) 프록시
from .public_controller import public_bp
# /api/security — n8n 이 보내는 보안 이벤트 저장, 대시보드 조회
from .security_controller import security_bp

# ═════════════════════════════════════════════════════════════════════════════
# all_blueprints — app.py 가 등록할 블루프린트 목록 (이 파일의 핵심)
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 1층 안내판에 적힌 입점 매장 목록.
# 값  : 튜플 (page_bp, auth_bp, post_bp, security_bp, public_bp, admin_bp, gold_bp)
# 누가 쓰나: app.py create_app() 의
#              for bp in all_blueprints:
#                app.register_blueprint(bp)
# 여기 없는 블루프린트는 위에서 import 했더라도 앱에 주소가 생기지 않는다(404).
# 괄호 안에서는 줄을 바꿔 적어도 한 문장으로 이어진다.
# ═════════════════════════════════════════════════════════════════════════════
all_blueprints = (page_bp, auth_bp, post_bp, security_bp, public_bp,
                  admin_bp, gold_bp)

# ═════════════════════════════════════════════════════════════════════════════
# __all__ — "from controllers import *" 를 했을 때 내보낼 이름 목록
# ─────────────────────────────────────────────────────────────────────────────
# app.py 는 이름을 콕 집어(from controllers import all_blueprints) 가져가므로 영향이 없다.
# 이 패키지가 밖에 보여 주는 이름을 목록으로 정리해 둔 역할이다.
# ═════════════════════════════════════════════════════════════════════════════
__all__ = ['all_blueprints', 'page_bp', 'auth_bp', 'post_bp',
           'security_bp', 'public_bp', 'admin_bp', 'gold_bp']
