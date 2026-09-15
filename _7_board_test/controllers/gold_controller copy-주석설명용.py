"""[주석·설명용 사본] controllers/gold_controller.py — 골드 등급 전용 API

이 파일은 원본 controllers/gold_controller.py 를 복사해 주석만 덧붙인 학습용 사본이다.
  · 실행 코드는 원본과 똑같다(주석과 이 설명 문자열만 추가).
  · 원본을 고쳐도 이 사본에는 반영되지 않는다.
  · 앱은 원본을 쓴다(controllers/__init__.py 가 from .gold_controller import gold_bp).
    이 사본은 파일 이름에 공백·하이픈이 있어 import 할 수 없다.

==============================================================================
0. 한 줄 요약
==============================================================================
  원본 설명: "골드 등급 전용 API."

  → 카테고리가 '골드' 인 게시글 최신 20개를 골드 등급 이상(gold·admin)에게만
    JSON 으로 내준다. 등급 검사는 rbac.py 의 @role_required('gold') 가 맡는다.

==============================================================================
1. 쉬운 비유 — 백화점 VIP 라운지
==============================================================================
  /gold 화면(gold.html)       = 라운지 입구 안내판 (누구나 볼 수 있다)
  화면 JS 의 등급 확인         = 안내 직원의 "회원 카드 보여 주세요" (친절한 안내용)
  GET /api/gold/posts          = 라운지 안쪽 물품 창고의 문
  @role_required('gold')       = 창고 문에 달린 전자 자물쇠 (진짜 차단)
  카테고리 '골드' 게시글       = 창고 안의 VIP 전용 물품
  admin                        = 골드보다 높은 등급 → 같은 자물쇠로 들어갈 수 있다

  안내 직원(화면 JS)은 속일 수 있다 — F12 로 화면을 조작하거나, 안내판을 건너뛰고
  창고 주소(/api/gold/posts)를 주소창에 직접 칠 수도 있다.
  그래도 자물쇠(서버 검사)는 회원 카드(JWT)를 직접 확인하므로 열리지 않는다.
  ※ 단, 같은 물품이 일반 매대(GET /api/posts)에도 진열돼 있다 → 6절 함정 ①

==============================================================================
2. 기본 개념
==============================================================================
  ■ 화면에서 막기 vs 서버에서 막기 — 원본 설명
      화면에서 메뉴를 숨기는 것만으로는 막은 게 아니다 —
      주소창에 API 를 직접 쳐 보면 그대로 열린다.
      그래서 서버에서 한 번 더 등급을 검사한다(@role_required('gold')).
        화면  templates/gold.html 의 JS   /api/auth/me 로 등급 확인 → 예외 화면   = 사용자 경험
        서버  이 파일                     @role_required('gold') → 401 / 403      = 실제 차단

  ■ 블루프린트와 url_prefix
      gold_bp = Blueprint('gold', __name__, url_prefix='/api/gold')
      + @gold_bp.route('/posts')   →  최종 주소  /api/gold/posts
      만들기만 해서는 열리지 않고, controllers/__init__.py 의 all_blueprints 에 들어가
      app.py 가 register_blueprint 해야 주소가 생긴다.

  ■ 데코레이터 쌓기 — 아래에서 위로 감싼다
      @gold_bp.route(...)       ② 검사가 붙은 함수를 주소에 등록
      @role_required('gold')    ① 먼저 gold_posts 를 검사 함수(wrapper)로 감싼다
      def gold_posts(): ...

  ■ 계단식 등급 (models/user.py)
      user(1) < gold(2) < admin(3).  필요 등급 'gold' 이상 → gold · admin 통과

  ■ 인증(401) vs 인가(403)
      토큰 없음·만료 → 401,  로그인했지만 user 등급 → 403

  ■ SQLAlchemy 조회 체인
      Post.query                       posts 표에서
      .filter_by(category='골드')      WHERE category = '골드'
      .order_by(Post.id.desc())        ORDER BY id DESC  (id 가 클수록 최신 글)
      .limit(20)                       LIMIT 20
      .all()                           이때 실제로 DB 에 보내고 Post 객체 리스트를 받는다

  ■ to_dict() (models/post.py)
      Post 객체 → dict {id, title, content, category, author(작성자 username), author_id}
      jsonify 는 Post 같은 모델 객체를 그대로 JSON 으로 못 바꾸므로 dict 로 바꿔 넘긴다.

==============================================================================
3. 동작 원리
==============================================================================
   [gold.html 화면 JS]   (page_controller 의 GET /gold 가 내려준 화면)
        │ ① localStorage 'token' 확인 — 없으면 예외 화면 (여기서 끝)
        │ ② GET /api/auth/me   Authorization: Bearer <JWT 토큰>
        │    is_gold 가 false 면 예외 화면 (여기서 끝)
        │ ③ GET /api/gold/posts   (같은 헤더)
        ▼
   [app.py before_request]   차단된 IP 면 403 (등급과 무관)
        ▼
   [rbac.py  role_required('gold') 의 wrapper]
        │ 토큰 없음·만료·위조, 없는 회원   → 401
        │ role 이 user                      → 403  (required_role 'gold', current_role 'user')
        │ role 이 gold 또는 admin           → 통과
        ▼
   [gold_posts()  ← 이 파일]
        │ posts 표에서 category = '골드' 최신 20개
        ▼
   200 {"count": N, "posts": [...]}
        ▼
   [gold.html loadGoldPosts()]
        │ 응답이 ok 가 아니면 required_role · current_role 로 예외 화면
        │ 비었으면 "아직 골드 전용 게시글이 없습니다."
        ▼
   목록 표시 (제목·내용·작성자는 esc() 로 HTML 이스케이프해 넣는다)

==============================================================================
4. 옵션 설명
==============================================================================
  ■ 엔드포인트
    메서드  URL               인증(헤더)                         필요 등급   쿼리·body   응답 코드
    ──────  ────────────────  ─────────────────────────────────  ──────────  ──────────  ────────────────
    GET     /api/gold/posts   Authorization: Bearer <JWT 토큰>   gold 이상   없음        200 / 401 / 403
    · 쿼리 파라미터(?limit=, ?cursor= 같은 것)는 받지 않는다 — 항상 최신 20개 고정
    · GET 외 메서드는 405 (methods=['GET'])
    · 차단된 IP 는 등급과 상관없이 403 {"blocked": true, "ip": ..., "msg": "차단된 IP 입니다(관리자에게 문의)."}

  ■ 데코레이터 인자 — role_required(required)
    인자      통과하는 등급         user 로그인   비로그인
    ────────  ────────────────────  ───────────   ────────
    'user'    user, gold, admin     200           401
    'gold'    gold, admin           403           401       ← 이 파일
    'admin'   admin                 403           401
    등급 이름은 models/user.py 의 ROLE_LEVEL 키와 글자까지 같아야 한다 (rbac 사본 6절 ① 참고)

  ■ 이 파일의 고정값
    GOLD_CATEGORY = '골드'   posts.category 와 비교할 글자. index.html 글쓰기 선택지 value="골드" 와 같다
    .limit(20)               최대 20개
    Post.id.desc()           최신 글 먼저

  ■ 200 응답 필드
    count               이번에 돌려준 글 수 (전체 골드 글 수가 아니다 — 최대 20)
    posts[].id          글 번호
    posts[].title       제목
    posts[].content     내용
    posts[].category    항상 '골드'
    posts[].author      작성자 username
    posts[].author_id   작성자 users.id

  ■ 401 / 403 응답 필드 (rbac.py 가 만든다)
    msg · required_role · current_role (비로그인은 null)

==============================================================================
5. 요청·응답 예시 (토큰은 자리표시자)
==============================================================================
    curl -H "Authorization: Bearer <JWT 토큰>" http://localhost:5000/api/gold/posts

  골드·관리자 → 200
    {"count": 1,
     "posts": [{"author": "goldie", "author_id": 3, "category": "골드",
                "content": "골드 회원만 보는 글", "id": 12, "title": "골드글"}]}
  일반 회원 → 403
    {"current_role": "user", "msg": "골드 등급 이상만 이용할 수 있습니다.", "required_role": "gold"}
  토큰 없음·만료 → 401
    {"current_role": null, "msg": "로그인이 필요합니다.", "required_role": "gold"}

  · Flask 는 JSON 키를 알파벳 순으로 정렬하고 한글을 유니코드 이스케이프 문자로 내보낸다.
    위 예시는 읽기 쉽게 한글로 풀었다.
  · tests/test_rbac.py 가 확인하는 것
      test_gold_api_rejects_anonymous            비로그인 401
      test_gold_api_rejects_plain_user           user 403 + required_role / current_role
      test_gold_api_allows_gold                  gold 200
      test_gold_api_allows_admin_by_hierarchy    admin 200 (계단식)
      test_gold_api_returns_only_gold_category   '골드' 카테고리 글만, count 1

==============================================================================
6. 자주 걸리는 함정
==============================================================================
  ① 골드 글은 일반 게시글 API 로도 그대로 보인다 — 로그인도 필요 없다.
       GET /api/posts?category=골드
     post_controller.get_posts 는 등급 검사도, 골드 카테고리 제외도 하지 않는다.
     카테고리를 '전체' 로 두면 일반 글 사이에 섞여 나오고, index.html 필터에도 '골드' 선택지가 있다.
     → 이 파일의 자물쇠는 '골드 전용 출입구 하나' 만 잠근다. 같은 데이터로 가는 다른 길이 열려 있으면
       접근제어가 되지 않는다. (막으려면 /api/posts 쪽에서도 골드 글을 걸러야 한다)
  ② 일반 회원도 카테고리 '골드' 로 글을 쓸 수 있다. post_controller.create_post 는 category 값을
     검사하지 않고, index.html 글쓰기 선택지 '골드 (골드 등급 전용)' 도 로그인한 누구에게나 보인다.
  ③ 데코레이터 순서를 뒤집으면(@role_required 를 @gold_bp.route 위에) 검사 없이 열린다.
  ④ category 글자가 정확히 '골드' 여야 목록에 나온다. 'gold' 나 뒤에 공백이 붙은 '골드 ' 는 다른 값이다.
  ⑤ 최신 20개 고정 — 21번째부터는 이 API 로 볼 방법이 없다(쿼리 파라미터를 받지 않는다).
  ⑥ 등급을 회수하면 옛 토큰으로 온 다음 요청부터 403 이다(rbac 가 매 요청 DB 에서 등급을 읽는다).
     단 계정 잠금(is_locked)은 보지 않아서, 잠긴 골드 회원도 토큰이 살아 있는 동안(최대 2시간)은 200.
"""
# ─────────────────────────────────────────────────────────────────────────────
# import
# ─────────────────────────────────────────────────────────────────────────────
# Blueprint : 주소 묶음 부품 / jsonify : dict → JSON 응답
from flask import Blueprint, jsonify

# Post : posts 표 모델 (models/post.py)
from models import Post
# role_required : 등급 검사 데코레이터. 점(.) = 같은 controllers 패키지의 rbac.py
from .rbac import role_required

# ═════════════════════════════════════════════════════════════════════════════
# gold_bp — 이 파일의 블루프린트
# ─────────────────────────────────────────────────────────────────────────────
# 'gold'      : 블루프린트 이름 → 엔드포인트 이름이 'gold.gold_posts' 가 된다
# __name__    : 이 모듈 이름 (Flask 가 이 블루프린트의 위치를 알아내는 데 쓴다)
# url_prefix  : 아래 @gold_bp.route('/posts') 앞에 붙는 주소 → /api/gold/posts
# 누가 등록하나: controllers/__init__.py 의 all_blueprints → app.py 의 register_blueprint
# ═════════════════════════════════════════════════════════════════════════════
gold_bp = Blueprint('gold', __name__, url_prefix='/api/gold')

# 골드 전용 글을 구분하는 카테고리 글자. posts.category 값과 글자까지 똑같아야 한다.
#   글쓰기 화면(index.html)의 선택지 value="골드" 가 이 값을 저장한다.
#   상수로 빼 두면 나중에 바꿀 때 이 한 줄만 고치면 된다.
GOLD_CATEGORY = '골드'


# ═════════════════════════════════════════════════════════════════════════════
# gold_posts() — GET /api/gold/posts : 골드 전용 게시글 최신 20개
# ─────────────────────────────────────────────────────────────────────────────
# 비유: VIP 창고 문(주소) + 전자 자물쇠(@role_required('gold')) + 물품 꺼내 주기(함수 본문).
#
# 입력 : 없음 (쿼리 파라미터를 받지 않는다). 헤더 Authorization: Bearer <JWT 토큰> 필요
# 출력 : 200 {"count": N, "posts": [ {id, title, content, category, author, author_id}, ... ]}
#        비로그인·만료 401 / user 등급 403   ← 이 두 응답은 rbac.py 의 wrapper 가 만든다
# 누가 호출하나: templates/gold.html 의 loadGoldPosts() (먼저 /api/auth/me 로 is_gold 를 확인한 뒤)
#
# 데코레이터는 아래에서 위로 적용된다.
#   ① @role_required('gold') 가 gold_posts 를 '검사가 붙은 함수(wrapper)' 로 감싸고
#   ② @gold_bp.route(...) 가 그 감싼 함수를 /posts 주소에 등록한다.
#   순서를 바꾸면 ② 가 검사 없는 원래 함수를 등록해 버린다 → 누구나 통과.
# ═════════════════════════════════════════════════════════════════════════════
@gold_bp.route('/posts', methods=['GET'])
@role_required('gold')
def gold_posts():
  """골드 전용 게시글 목록. 일반 게시판(/api/posts)과 달리 등급이 없으면 403."""
  # (docstring 보충) 정확히는 비로그인은 401, 로그인했지만 user 등급이면 403 이다.
  #   이 본문까지 왔다면 이미 gold 또는 admin 으로 확인된 요청이다.
  #
  # SQL 로 치면   SELECT * FROM posts WHERE category = '골드' ORDER BY id DESC LIMIT 20
  #   filter_by(category=...)   : WHERE 조건 (같다 비교)
  #   order_by(Post.id.desc())  : id 큰 것(최신 글)부터
  #   limit(20)                 : 최대 20개 — 다음 페이지(커서)는 없다
  #   all()                     : 여기서 실제로 DB 에 보내고 Post 객체 리스트를 받는다
  # 바깥 괄호 덕분에 메서드 체인을 두 줄로 나눠 적어도 한 문장으로 읽힌다
  rows = (Post.query.filter_by(category=GOLD_CATEGORY)
          .order_by(Post.id.desc()).limit(20).all())
  # Post 객체는 그대로 JSON 이 안 되므로 to_dict() 로 dict 로 바꾼다
  #   to_dict → {id, title, content, category, author(작성자 username), author_id}
  # count 는 '이번에 돌려준 개수' — 골드 글이 30개여도 최대 20
  return jsonify({'count': len(rows), 'posts': [p.to_dict() for p in rows]})
