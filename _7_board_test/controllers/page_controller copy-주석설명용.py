"""[주석·설명용 사본] controllers/page_controller.py — 화면(HTML) 라우트 모음

이 파일은 원본 controllers/page_controller.py 를 복사해 주석만 덧붙인 학습용 사본이다.
  · 실행 코드는 원본과 똑같다(주석과 이 설명 문자열만 추가).
  · 원본을 고쳐도 이 사본에는 반영되지 않는다.
  · 앱은 원본을 쓴다(controllers/__init__.py 가 from .page_controller import page_bp).
    이 사본은 파일 이름에 공백·하이픈이 있어 import 할 수 없다.

==============================================================================
0. 한 줄 요약
==============================================================================
  원본 설명: "화면(HTML) 라우트만 모음. 데이터는 각 페이지의 JS 가 API 로 가져온다."

  → 주소창에 치는 화면 주소 6개를 templates/ 의 HTML 파일에 이어 주기만 한다.
    로그인·등급 검사도, DB 조회도 하지 않는다. 그 일은 화면 속 JS 와 API 가 맡는다.

==============================================================================
1. 쉬운 비유 — 식당의 빈 접시와 주방
==============================================================================
  page_controller (이 파일)          = 홀 직원이 테이블에 빈 접시·수저를 먼저 깔아 주는 일
  templates/*.html                   = 접시와 테이블 세팅 (틀만 있고 음식은 없다)
  화면 JS 의 fetch('/api/...')       = 손님 테이블에서 주방에 음식을 따로 주문하는 일
  API 블루프린트 (auth · post · gold …) = 주방 — 주문서(토큰·API 키)를 보고 음식을 줄지 정한다

  빈 접시는 누구에게나 깔아 준다. 골드 라운지 테이블(/gold)이든 관리자실 테이블(/admin)이든.
  하지만 음식(데이터)은 주방(API)이 주문서를 확인한 뒤에만 나온다.
  그래서 "화면이 열린다 = 데이터가 열린다" 가 아니다.

==============================================================================
2. 기본 개념
==============================================================================
  ■ 화면 라우트 vs API 라우트
      화면 라우트 (이 파일)   HTML 을 돌려준다.  주소창·링크로 이동할 때 불린다.
      API 라우트 (/api/...)   JSON 을 돌려준다.  화면 JS 가 fetch 로 부른다.

  ■ render_template('파일.html', 이름=값)
      templates/ 폴더에서 파일을 찾아 Jinja2 문법({% include %}, {{ 변수 }})을 채운 HTML 을 만든다.
      예) 대부분의 화면이 {% include 'partials/_nav.html' %} 로 공통 헤더를 붙인다.

  ■ url_prefix 없는 블루프린트
      page_bp = Blueprint('page', __name__)  → 적은 주소가 그대로 최종 주소가 된다  ('/gold' → /gold)

  ■ URL 변수와 변환기 — '/public-posts/<int:uc_seq>'
      주소의 그 자리 글자를 정수로 바꿔 함수 인자 uc_seq 로 넘긴다.
      정수가 아니면(/public-posts/abc) 함수까지 오지 않고 404.

  ■ methods 를 안 적으면 GET 전용
      @page_bp.route('/gold') 는 methods=('GET',) 과 같다 (flask/sansio/app.py 의 기본값).
      POST /gold 같은 요청은 405 Method Not Allowed.

  ■ 왜 화면 주소에서 로그인 검사를 안 하나
      로그인 토큰은 브라우저 localStorage('token')에 있다. 쿠키가 아니어서
      주소창 이동(페이지 요청)에는 자동으로 실리지 않는다 → 서버는 이 시점에 누구인지 모른다.
      그래서 HTML 은 누구에게나 주고, 화면 JS 가 Authorization: Bearer <JWT 토큰> 을
      직접 붙여 API 에 물어본다 (auth_controller.me 의 docstring 과 같은 이유).

  ■ 두 겹 방어
      화면 JS 의 검사(예외 화면)   사용자 경험.  F12 로 얼마든지 우회된다.
      API 의 검사(401/403)         실제 차단.    데이터는 여기서 막는다.

==============================================================================
3. 동작 원리 — /gold 를 열 때
==============================================================================
   브라우저 주소창  GET /gold
     ▼
   app.py before_request (_block_ip_guard)
     │  차단된 IP 면 HTML 대신 403 JSON (화면 주소도 예외가 아니다)
     ▼
   page_bp → gold_page() → render_template('gold.html')
     │  _nav.html(공통 헤더) + _denied.html(예외 화면 조각)이 합쳐진 HTML
     ▼
   200 HTML   ← 로그인 여부와 상관없이 누구에게나
     ▼
   브라우저가 HTML 을 그리고 <script> 실행
     │  localStorage 'token' 없음      → showDenied (로그인이 필요합니다)
     │  GET /api/auth/me 가 401        → 토큰 삭제 + showDenied
     │  me.is_gold 가 false            → showDenied (접근 권한이 없습니다)
     │  GET /api/gold/posts            → 서버가 한 번 더 검사 (@role_required('gold'))
     ▼
   골드 라운지 화면 완성

==============================================================================
4. 옵션 설명 — 화면 라우트 6개
==============================================================================
  모두 GET 전용이고, 서버 쪽 인증은 없다 (누구에게나 200 HTML).

  URL                          함수                      템플릿
  ───────────────────────────  ────────────────────────  ─────────────────────────────────────────
  /                            index                     index.html
  /dashboard                   dashboard                 dashboard.html
  /gold                        gold_page                 gold.html
  /admin                       admin_page                admin.html
  /public-posts                public_posts_page         public_posts.html
  /public-posts/<int:uc_seq>   public_post_detail_page   public_detail.html  (uc_seq=uc_seq 전달)

  ■ 화면별로 JS 가 부르는 API (templates/*.html 에서 확인)
    /               GET /api/posts (목록·검색·더보기, 토큰 없이)
                    POST /api/auth/login · /api/auth/register
                    POST /api/posts, PUT · DELETE /api/posts/<id>  (Authorization: Bearer <JWT 토큰>)
    /dashboard      GET /api/security/students, /api/security/events/summary, /api/security/events  (키·토큰 없이)
    /gold           GET /api/auth/me → GET /api/gold/posts
    /admin          POST /api/auth/login, GET /api/admin/users, POST /api/admin/grant,
                    POST /api/admin/revoke, GET /api/admin/violations   (admin JWT)
    /public-posts   GET /api/public/posts
    /public-posts/N GET /api/public/posts (전체를 받아 UC_SEQ 가 N 인 항목을 찾는다)

  ■ 응답 코드
    200   HTML (정상)
    404   /public-posts/ 뒤가 정수가 아님, 또는 없는 주소
    405   GET 이 아닌 메서드
    403   차단된 IP (app.py before_request — JSON 으로 msg · ip · blocked)
    500   템플릿 파일 이름이 틀림 등 (그 주소를 연 순간에 드러난다)

  ■ 템플릿이 함께 불러오는 조각
    partials/_nav.html      index · dashboard · gold · admin · public_posts 가 include (public_detail 은 안 함)
    partials/_denied.html   gold 만 include — showDenied() / showProtected() 를 제공

  ■ 토큰 저장 위치 (화면끼리 공유)
    localStorage 'token' / 'username'  — index.html · admin.html 이 로그인 때 저장, gold.html 이 읽는다

==============================================================================
5. 요청·응답 예시
==============================================================================
    curl -i http://localhost:5000/gold
      → 200, Content-Type: text/html  (토큰 없이도 HTML 이 온다 — 막는 건 화면 JS 와 API)
    curl -i http://localhost:5000/public-posts/58
      → 200 HTML (58 이 템플릿 변수 uc_seq 로 넘어간다)
    curl -i http://localhost:5000/public-posts/abc
      → 404
    curl -i -X POST http://localhost:5000/gold
      → 405

  tests/test_rbac.py 의 test_gold_page_route_exists 가 "GET /gold 는 로그인 없이 200" 을 확인한다.

==============================================================================
6. 자주 걸리는 함정
==============================================================================
  ① "/admin 화면이 열린다 = 관리자 기능이 열렸다" 가 아니다. HTML 은 누구나 받는다.
     실제 권한 부여·회수는 /api/admin/* 가 X-API-Key 또는 admin JWT 로 막는다.
     반대로, 화면 JS 의 등급 검사만 믿고 API 검사를 빼면 주소창·curl 로 데이터가 샌다.
  ② 차단된 IP 는 화면 주소도 403 JSON 을 받는다. app.py 의 예외는 '/api/admin' 으로 시작하는
     경로뿐이라 '/admin' 화면은 예외가 아니다 → 차단된 PC 에서는 관리자 화면은 안 열리고
     관리자 API 만 호출된다.
  ③ /dashboard 의 데이터 API(GET /api/security/events 등)는 키·로그인 없이 열려 있다
     (security_controller 주석: "조회는 키 없이(수업 확인용)"). 화면 주소를 아는 누구나
     student · src_ip · users(시도 계정) 가 담긴 보안 기록을 볼 수 있다.
  ④ public_detail.html 은 넘겨준 uc_seq 템플릿 변수를 쓰지 않는다. JS 가 주소(location.pathname)에서
     번호를 다시 잘라 쓰고, 목록 API 전체(최대 100건)를 받아 그중에서 찾는다.
     못 찾으면 getElementById('container') 를 부르는데 그런 id 가 없어서(class="container" 뿐)
     JS 오류가 나고, 오류 문구를 쓰는 loading 칸은 이미 숨겨져 있어 결국 빈 화면이 된다.
     (이 화면에는 공통 헤더 _nav.html 도 없다)
  ⑤ 템플릿 이름 오타는 앱을 켤 때가 아니라 그 주소를 처음 열 때 TemplateNotFound(500)로 드러난다.
"""
# ─────────────────────────────────────────────────────────────────────────────
# import
# ─────────────────────────────────────────────────────────────────────────────
# Blueprint       : 주소 묶음 부품
# render_template : templates/ 폴더의 HTML 파일을 Jinja2 로 채워 응답 문자열로 만든다
from flask import Blueprint, render_template

# ═════════════════════════════════════════════════════════════════════════════
# page_bp — 화면 주소용 블루프린트
# ─────────────────────────────────────────────────────────────────────────────
# url_prefix 가 없다 → @page_bp.route('/gold') 가 그대로 /gold 가 된다
#   (API 블루프린트들은 /api/... 앞머리를 가져서 화면 주소와 겹치지 않는다)
# 'page' : 블루프린트 이름 → 엔드포인트 이름 'page.index', 'page.gold_page' ...
# 누가 등록하나: controllers/__init__.py 의 all_blueprints (맨 앞) → app.py 의 register_blueprint
# ═════════════════════════════════════════════════════════════════════════════
page_bp = Blueprint('page', __name__)


# ═════════════════════════════════════════════════════════════════════════════
# index() — GET / : 게시판 메인 화면
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 식당 홀 — 빈 테이블(HTML)을 먼저 깔고, 음식(글 목록)은 JS 가 주방(API)에 주문한다.
# 입력 : 없음            출력 : 200 index.html (로그인 여부와 무관)
# 화면 JS 가 부르는 API:
#   GET  /api/posts?limit=5&search=&category=&cursor=   목록·검색·더보기 (토큰 없이)
#   POST /api/auth/login · /api/auth/register            로그인 모달 → 토큰을 localStorage 'token' 에 저장
#   POST /api/posts, PUT · DELETE /api/posts/<id>        Authorization: Bearer <JWT 토큰>
# 누가 여나: 주소창 /, 공통 헤더(_nav.html)의 로고·"게시판" 링크, _denied.html 의 버튼들
# ═════════════════════════════════════════════════════════════════════════════
@page_bp.route('/')
def index():
  # templates/index.html 을 렌더 → 안에서 {% include 'partials/_nav.html' %} 로 공통 헤더를 붙인다
  return render_template('index.html')


# ═════════════════════════════════════════════════════════════════════════════
# dashboard() — GET /dashboard : 보안 이벤트 대시보드 화면
# ─────────────────────────────────────────────────────────────────────────────
# 입력 : 없음            출력 : 200 dashboard.html (로그인 여부와 무관)
# 화면 JS 가 부르는 API (모두 키·토큰 없이):
#   GET /api/security/students          학생 드롭다운
#   GET /api/security/events/summary    허용/거부 건수, 거부 상위 IP
#   GET /api/security/events            최근 이벤트 표 (limit=50)
# 데이터를 넣는 쪽: n8n 이 POST /api/security/events (X-API-Key) 로 저장하고,
#                  관리자 API 의 회수·잠금·IP 차단도 security_events 에 감사기록을 남긴다
# ═════════════════════════════════════════════════════════════════════════════
@page_bp.route('/dashboard')
def dashboard():
  """보안 이벤트 대시보드 (n8n 이 저장한 허용/거부 기록)."""
  return render_template('dashboard.html')


# ═════════════════════════════════════════════════════════════════════════════
# gold_page() — GET /gold : 골드 등급 전용 화면 (틀)
# ─────────────────────────────────────────────────────────────────────────────
# 비유: VIP 라운지 입구 안내판. 누구나 볼 수 있고, 안내 직원(JS)이 회원 카드를 확인한다.
#       진짜 자물쇠는 창고 문(/api/gold/posts 의 @role_required('gold'))에 있다.
# 입력 : 없음            출력 : 200 gold.html (로그인·등급과 무관)
# 화면 JS 순서: localStorage 'token' → GET /api/auth/me (is_gold) → GET /api/gold/posts
#               모자라면 partials/_denied.html 의 showDenied() 로 예외 화면
# 테스트: tests/test_rbac.py 의 test_gold_page_route_exists (로그인 없이 200)
# ═════════════════════════════════════════════════════════════════════════════
@page_bp.route('/gold')
def gold_page():
  """골드 등급 전용 화면. 페이지 자체는 항상 렌더되고,
  등급 확인은 화면 JS 가 /api/auth/me 로 한다(모자라면 예외 화면).
  실제 데이터 차단은 서버(/api/gold/posts)가 담당한다."""
  # 여기서 등급을 검사할 수 없는 이유: 토큰이 localStorage 에 있어 페이지 요청에는 실려 오지 않는다
  return render_template('gold.html')


# ═════════════════════════════════════════════════════════════════════════════
# admin_page() — GET /admin : 관리자 화면 (틀)
# ─────────────────────────────────────────────────────────────────────────────
# 입력 : 없음            출력 : 200 admin.html (누구나 받는다 — 관리자 확인은 API 몫)
# 화면 JS 가 부르는 API (Authorization: Bearer <JWT 토큰>):
#   POST /api/auth/login         관리자 로그인 → localStorage 'token' · 'username' 저장
#   GET  /api/admin/users        목록 + admin 확인 겸용 (401 이면 "이 계정은 admin 이 아닙니다")
#   POST /api/admin/grant        권한 부여 (gold / admin / user)
#   POST /api/admin/revoke       권한 회수 (user 로)
#   GET  /api/admin/violations   허용목록 밖 admin 조회
# 실제 차단: admin_controller 의 admin_required (X-API-Key 또는 role 이 admin 인 JWT)
# ═════════════════════════════════════════════════════════════════════════════
@page_bp.route('/admin')
def admin_page():
  """관리자 페이지 — 회원 역할(인가) 부여/회수. admin 계정 로그인 필요."""
  # (docstring 보충) "로그인 필요" 는 화면 JS 와 /api/admin/* 가 확인한다. 이 함수는 검사 없이 HTML 만 준다.
  return render_template('admin.html')


# ═════════════════════════════════════════════════════════════════════════════
# public_posts_page() — GET /public-posts : 부산 테마여행 목록 화면
# ─────────────────────────────────────────────────────────────────────────────
# 입력 : 없음            출력 : 200 public_posts.html
# 화면 JS 가 부르는 API: GET /api/public/posts (공공데이터 프록시, 최대 100건)
#   카드를 누르면 /public-posts/<UC_SEQ> 상세 화면으로 이동한다
# ═════════════════════════════════════════════════════════════════════════════
@page_bp.route('/public-posts')
def public_posts_page():
  return render_template('public_posts.html')


# ═════════════════════════════════════════════════════════════════════════════
# public_post_detail_page(uc_seq) — GET /public-posts/<int:uc_seq> : 여행지 상세 화면
# ─────────────────────────────────────────────────────────────────────────────
# <int:uc_seq> : 주소의 그 자리가 정수일 때만 이 함수로 온다 → uc_seq 에 int 로 들어온다
#                /public-posts/abc 는 함수까지 오지 않고 404
# 입력 : uc_seq (예: /public-posts/58 → 58)
# 출력 : 200 public_detail.html (템플릿 변수 uc_seq 를 함께 넘긴다)
# 화면 JS: GET /api/public/posts 로 전체 목록을 다시 받아 UC_SEQ 가 같은 항목을 찾는다
#          (번호는 템플릿 변수가 아니라 location.pathname 에서 다시 잘라 쓴다 — 6절 ④)
# ═════════════════════════════════════════════════════════════════════════════
@page_bp.route('/public-posts/<int:uc_seq>')
def public_post_detail_page(uc_seq):
  # uc_seq=uc_seq : 템플릿 안에서 {{ uc_seq }} 로 쓸 수 있게 넘긴다 (현재 public_detail.html 은 쓰지 않는다)
  return render_template('public_detail.html', uc_seq=uc_seq)
